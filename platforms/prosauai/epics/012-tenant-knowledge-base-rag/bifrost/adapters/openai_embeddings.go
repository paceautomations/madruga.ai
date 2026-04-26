// Package adapters — OpenAI embeddings adapter (epic 012, T022).
//
// Reuses the existing chat completions skeleton (RateLimiter +
// SpendTracker + CircuitBreaker + ContextPropagator) and only swaps the
// payload schema (OpenAI embeddings uses {"input": [...]} instead of
// {"messages": [...]}).
//
// Cross-cutting concerns:
//
//   - Tenant header X-ProsaUAI-Tenant is mandatory (FR-030); absent →
//     400 fail-closed before forwarding upstream so spend is never
//     anonymous.
//   - bifrost_spend row is inserted ONLY on a 2xx OpenAI response; failed
//     calls are accounted via a separate failure counter.
//   - Circuit breaker (5 failures / 60 s → OPEN 30 s, FR-033).
//
// References:
//   - spec.md FR-030, FR-032, FR-033
//   - plan.md §"Bifrost extension"
//   - ADR-042 (proposed)
package adapters

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/paceautomations/bifrost/internal/breaker"
	"github.com/paceautomations/bifrost/internal/config"
	"github.com/paceautomations/bifrost/internal/ratelimit"
	"github.com/paceautomations/bifrost/internal/spend"
	"github.com/paceautomations/bifrost/internal/telemetry"
)

// OpenAIEmbeddingsAdapter forwards POST /v1/embeddings to OpenAI with
// rate limiting + spend tracking + circuit breaker.
type OpenAIEmbeddingsAdapter struct {
	cfg         config.ProviderConfig
	httpClient  *http.Client
	rateLimiter ratelimit.Limiter
	spend       spend.Tracker
	breaker     breaker.CircuitBreaker
}

// New builds an adapter from the loaded provider TOML config.
func New(cfg config.ProviderConfig, deps Dependencies) *OpenAIEmbeddingsAdapter {
	return &OpenAIEmbeddingsAdapter{
		cfg:         cfg,
		httpClient:  &http.Client{Timeout: 30 * time.Second},
		rateLimiter: deps.RateLimiter,
		spend:       deps.SpendTracker,
		breaker:     deps.Breaker,
	}
}

// Dependencies aggregates the cross-cutting infra Bifrost injects per
// provider so this adapter stays testable without touching globals.
type Dependencies struct {
	RateLimiter  ratelimit.Limiter
	SpendTracker spend.Tracker
	Breaker      breaker.CircuitBreaker
}

// Handle implements http.Handler. Mounted at /v1/embeddings by the
// provider router (see internal/router/router.go).
func (a *OpenAIEmbeddingsAdapter) Handle(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	start := time.Now()

	// 1. Tenant header gate — fail closed (FR-030).
	tenantSlug := r.Header.Get(a.cfg.Auth.TenantHeaderName)
	if tenantSlug == "" {
		writeJSON(w, a.cfg.Auth.FailClosedStatus, []byte(a.cfg.Auth.FailClosedBody))
		telemetry.IncCounter("bifrost_requests_rejected_total",
			"endpoint", "embeddings",
			"reason", "missing_tenant_header",
		)
		return
	}

	// 2. Circuit breaker — short-circuit when OPEN.
	if !a.breaker.Allow() {
		writeJSON(w, http.StatusServiceUnavailable, []byte(`{"error":"breaker_open"}`))
		telemetry.IncCounter("bifrost_requests_rejected_total",
			"endpoint", "embeddings",
			"reason", "breaker_open",
		)
		return
	}

	// 3. Rate limit — per tenant + global.
	if err := a.rateLimiter.Wait(ctx, tenantSlug); err != nil {
		writeJSON(w, http.StatusTooManyRequests, []byte(`{"error":"rate_limited"}`))
		return
	}

	// 4. Read + validate request body.
	body, err := io.ReadAll(r.Body)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, []byte(`{"error":"body_read_failed"}`))
		return
	}
	defer r.Body.Close()

	var payload openAIEmbedRequest
	if err := json.Unmarshal(body, &payload); err != nil {
		writeJSON(w, http.StatusBadRequest, []byte(`{"error":"invalid_json"}`))
		return
	}
	if payload.Model == "" || len(payload.Input) == 0 {
		writeJSON(w, http.StatusBadRequest, []byte(`{"error":"missing_model_or_input"}`))
		return
	}

	// 5. Forward to OpenAI.
	upstreamReq, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		a.cfg.TargetURL,
		bytes.NewReader(body),
	)
	if err != nil {
		writeJSON(w, http.StatusInternalServerError, []byte(`{"error":"upstream_request_failed"}`))
		return
	}
	upstreamReq.Header.Set("Authorization", fmt.Sprintf("Bearer %s", a.cfg.APIKey()))
	upstreamReq.Header.Set("Content-Type", "application/json")

	resp, err := a.httpClient.Do(upstreamReq)
	if err != nil {
		a.breaker.RecordFailure()
		writeJSON(w, http.StatusBadGateway, []byte(`{"error":"upstream_unavailable"}`))
		return
	}
	defer resp.Body.Close()

	respBody, _ := io.ReadAll(resp.Body)

	// 6. Spend tracking — only on 2xx (FR-032, SC-010).
	if resp.StatusCode >= 200 && resp.StatusCode < 300 {
		a.breaker.RecordSuccess()
		a.recordSpend(ctx, tenantSlug, payload.Model, respBody)
	} else if resp.StatusCode >= 500 {
		a.breaker.RecordFailure()
	}

	// 7. Mirror upstream status + body.
	writeJSON(w, resp.StatusCode, respBody)

	telemetry.ObserveHistogram("bifrost_request_duration_seconds",
		time.Since(start).Seconds(),
		"endpoint", "embeddings",
		"status", fmt.Sprintf("%d", resp.StatusCode),
	)
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type openAIEmbedRequest struct {
	Model string   `json:"model"`
	Input []string `json:"input"`
}

type openAIEmbedResponse struct {
	Usage struct {
		PromptTokens int `json:"prompt_tokens"`
		TotalTokens  int `json:"total_tokens"`
	} `json:"usage"`
	Model string `json:"model"`
}

func (a *OpenAIEmbeddingsAdapter) recordSpend(
	ctx context.Context,
	tenantSlug string,
	requestedModel string,
	respBody []byte,
) {
	var parsed openAIEmbedResponse
	if err := json.Unmarshal(respBody, &parsed); err != nil {
		// Spend tracking is best-effort — never fail the request.
		telemetry.IncCounter("bifrost_spend_decode_failed_total", "endpoint", "embeddings")
		return
	}
	costUSD := float64(parsed.Usage.TotalTokens) * a.cfg.Cost.CostPer1kTokensUSD / 1000
	a.spend.Record(ctx, spend.Record{
		TenantSlug:    tenantSlug,
		Endpoint:      a.cfg.Cost.EndpointLabel,
		Model:         requestedModel,
		PromptTokens:  parsed.Usage.PromptTokens,
		TotalTokens:   parsed.Usage.TotalTokens,
		TotalCostUSD:  costUSD,
		Provider:      "openai",
	})
}

func writeJSON(w http.ResponseWriter, status int, body []byte) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(body)
}
