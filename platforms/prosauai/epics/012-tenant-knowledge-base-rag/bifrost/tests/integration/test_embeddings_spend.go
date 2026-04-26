// Package integration — embeddings spend tracking tests (epic 012, T078).
//
// Cross-repo artifact: drop into ``bifrost/tests/integration/`` of the
// Bifrost repo and run with ``go test -tags=integration ./tests/integration/...``.
//
// The tests stand up the OpenAIEmbeddingsAdapter against an httptest.Server
// that mimics the OpenAI ``/v1/embeddings`` payload deterministically (the
// real upstream is not contacted — this is an integration test, not a
// contract test). They cover three SC-010 / FR-032 / FR-033 invariants:
//
//  1. Spend accuracy — for 10 calls with known token counts the
//     ``bifrost_spend.cost_usd`` value matches the analytic formula
//     ``total_tokens * cost_per_1k_tokens_usd / 1000`` to 6 decimal
//     places (the precision of the underlying float64 / pgnumeric).
//
//  2. Rate limiting — request 3501 within a 1-minute window returns 429
//     with header ``Retry-After`` (the limiter is tested via a fake clock
//     so the test runs in milliseconds rather than minutes).
//
//  3. Circuit breaker — 5 upstream 5xx in 60 s opens the breaker for
//     30 s and a single half-open success closes it again.
//
// References:
//   - spec.md FR-030, FR-032, FR-033, SC-010
//   - plan.md §"Bifrost extension"
//   - ADR-042 (proposed)
//
//go:build integration

package integration

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"net/http/httptest"
	"strconv"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"github.com/paceautomations/bifrost/adapters"
	"github.com/paceautomations/bifrost/internal/breaker"
	"github.com/paceautomations/bifrost/internal/config"
	"github.com/paceautomations/bifrost/internal/ratelimit"
	"github.com/paceautomations/bifrost/internal/spend"
)

// ---------------------------------------------------------------------------
// Test fixtures
// ---------------------------------------------------------------------------

const (
	costPer1kTokensUSD = 0.00002 // matches openai-embeddings.toml [cost]
	tenantSlug         = "pace-internal-test"
	testModel          = "text-embedding-3-small"
)

// fakeUpstream returns a 200 OK response that echoes the OpenAI embeddings
// schema with a deterministic ``usage`` block driven by failureMode.
type fakeUpstream struct {
	calls       atomic.Int64
	failuresN   atomic.Int64 // when >0, the next N calls return 503
	totalTokens int          // returned in usage.total_tokens
}

func (u *fakeUpstream) Handler() http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		u.calls.Add(1)
		if u.failuresN.Load() > 0 {
			u.failuresN.Add(-1)
			http.Error(w, `{"error":"upstream_overloaded"}`, http.StatusServiceUnavailable)
			return
		}
		resp := map[string]any{
			"object": "list",
			"data": []map[string]any{
				{"index": 0, "embedding": make([]float64, 1536)},
			},
			"model": testModel,
			"usage": map[string]any{
				"prompt_tokens": u.totalTokens,
				"total_tokens":  u.totalTokens,
			},
		}
		body, _ := json.Marshal(resp)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusOK)
		_, _ = w.Write(body)
	}
}

// recordingSpend captures every Record() call in memory so tests can assert
// against the exact rows the adapter would have written to ``bifrost_spend``.
type recordingSpend struct {
	mu      sync.Mutex
	records []spend.Record
}

func (s *recordingSpend) Record(_ ctxLike, r spend.Record) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.records = append(s.records, r)
}

func (s *recordingSpend) Snapshot() []spend.Record {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]spend.Record, len(s.records))
	copy(out, s.records)
	return out
}

// ctxLike is the smallest surface needed by Record(); the production
// signature accepts context.Context — declared here so this test file
// compiles without dragging the full Bifrost imports.
type ctxLike = any

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

func newAdapter(t *testing.T, upstream *httptest.Server, deps adapters.Dependencies) *adapters.OpenAIEmbeddingsAdapter {
	t.Helper()
	cfg := config.ProviderConfig{
		Name:      "openai_embeddings",
		Endpoint:  "/v1/embeddings",
		TargetURL: upstream.URL,
		Method:    http.MethodPost,
		Auth: config.AuthConfig{
			RequireTenantHeader: true,
			TenantHeaderName:    "X-ProsaUAI-Tenant",
			FailClosedStatus:    http.StatusBadRequest,
			FailClosedBody:      `{"error":"missing_tenant_header"}`,
		},
		Cost: config.CostConfig{
			CostPer1kTokensUSD:    costPer1kTokensUSD,
			SpendTrackingEnabled:  true,
			EndpointLabel:         "embeddings",
		},
		APIKeyValue: "sk-test",
	}
	return adapters.New(cfg, deps)
}

func doEmbedRequest(t *testing.T, h http.Handler, tokensRequested int) *http.Response {
	t.Helper()
	body := fmt.Sprintf(`{"model":%q,"input":[%q]}`, testModel,
		// One repeated word per 1 token in cl100k_base — close enough for
		// the upstream stub which honours ``totalTokens`` regardless.
		stringTimes("token ", tokensRequested))
	req := httptest.NewRequest(http.MethodPost, "/v1/embeddings", bytes.NewBufferString(body))
	req.Header.Set("X-ProsaUAI-Tenant", tenantSlug)
	req.Header.Set("Content-Type", "application/json")
	rr := httptest.NewRecorder()
	h.ServeHTTP(rr, req)
	return rr.Result()
}

func stringTimes(s string, n int) string {
	out := make([]byte, 0, len(s)*n)
	for i := 0; i < n; i++ {
		out = append(out, s...)
	}
	return string(out)
}

func almostEqual(a, b float64) bool {
	return math.Abs(a-b) < 1e-6
}

// ---------------------------------------------------------------------------
// Test 1: spend accuracy across 10 calls with varying token counts
// ---------------------------------------------------------------------------

func TestEmbeddingsSpend_AccuracyTo6Decimals(t *testing.T) {
	tokenScenarios := []int{50, 100, 250, 500, 1000, 1500, 2500, 5000, 7500, 10000}

	rec := &recordingSpend{}
	upstream := &fakeUpstream{}
	server := httptest.NewServer(upstream.Handler())
	defer server.Close()

	deps := adapters.Dependencies{
		RateLimiter:  ratelimit.NewNoop(),
		SpendTracker: rec,
		Breaker:      breaker.NewAlwaysOpen(), // i.e. always Allow()
	}
	adapter := newAdapter(t, server, deps)

	for i, tokens := range tokenScenarios {
		upstream.totalTokens = tokens
		resp := doEmbedRequest(t, http.HandlerFunc(adapter.Handle), tokens)
		if resp.StatusCode != http.StatusOK {
			body, _ := io.ReadAll(resp.Body)
			t.Fatalf("call %d: expected 200, got %d body=%s", i, resp.StatusCode, body)
		}
	}

	records := rec.Snapshot()
	if len(records) != len(tokenScenarios) {
		t.Fatalf("expected %d spend rows, got %d", len(tokenScenarios), len(records))
	}

	for i, r := range records {
		expectedCost := float64(tokenScenarios[i]) * costPer1kTokensUSD / 1000
		if !almostEqual(r.TotalCostUSD, expectedCost) {
			t.Errorf("call %d (tokens=%d): cost mismatch — got %.10f, want %.10f (delta=%.10f)",
				i, tokenScenarios[i], r.TotalCostUSD, expectedCost,
				math.Abs(r.TotalCostUSD-expectedCost))
		}
		if r.TenantSlug != tenantSlug {
			t.Errorf("call %d: tenant_slug mismatch — got %q, want %q", i, r.TenantSlug, tenantSlug)
		}
		if r.Endpoint != "embeddings" {
			t.Errorf("call %d: endpoint mismatch — got %q, want %q", i, r.Endpoint, "embeddings")
		}
		if r.TotalTokens != tokenScenarios[i] {
			t.Errorf("call %d: total_tokens mismatch — got %d, want %d", i, r.TotalTokens, tokenScenarios[i])
		}
	}
}

// ---------------------------------------------------------------------------
// Test 2: rate limiter rejects request 3501 within 1-minute window
// ---------------------------------------------------------------------------

func TestEmbeddingsSpend_RateLimit3500RPM(t *testing.T) {
	rec := &recordingSpend{}
	upstream := &fakeUpstream{totalTokens: 10}
	server := httptest.NewServer(upstream.Handler())
	defer server.Close()

	// Fake clock-driven limiter — caps at 3500 in current 60s bucket.
	limiter := ratelimit.NewFixedWindow(3500, 60*time.Second)
	deps := adapters.Dependencies{
		RateLimiter:  limiter,
		SpendTracker: rec,
		Breaker:      breaker.NewAlwaysOpen(),
	}
	adapter := newAdapter(t, server, deps)
	handler := http.HandlerFunc(adapter.Handle)

	// 3500 successful calls.
	for i := 0; i < 3500; i++ {
		resp := doEmbedRequest(t, handler, 10)
		if resp.StatusCode != http.StatusOK {
			t.Fatalf("call %d: expected 200, got %d", i, resp.StatusCode)
		}
	}

	// The 3501st call MUST be rejected with 429 and a Retry-After header.
	resp := doEmbedRequest(t, handler, 10)
	if resp.StatusCode != http.StatusTooManyRequests {
		t.Fatalf("call 3501: expected 429, got %d", resp.StatusCode)
	}
	if resp.Header.Get("Retry-After") == "" {
		t.Errorf("call 3501: expected Retry-After header, got empty")
	}
	// Sanity: header must be a positive integer (seconds).
	if v, err := strconv.Atoi(resp.Header.Get("Retry-After")); err != nil || v <= 0 {
		t.Errorf("call 3501: Retry-After = %q (want positive integer seconds)",
			resp.Header.Get("Retry-After"))
	}

	// Spend should NOT have been recorded for the rejected call.
	if got := len(rec.Snapshot()); got != 3500 {
		t.Errorf("spend rows: got %d, want exactly 3500 (rejected call must NOT record spend)", got)
	}
}

// ---------------------------------------------------------------------------
// Test 3: circuit breaker opens after 5 failures in 60 s and recovers
// ---------------------------------------------------------------------------

func TestEmbeddingsSpend_CircuitBreakerOpensAfter5Failures(t *testing.T) {
	rec := &recordingSpend{}
	upstream := &fakeUpstream{totalTokens: 10}
	server := httptest.NewServer(upstream.Handler())
	defer server.Close()

	cb := breaker.New(breaker.Config{
		FailureThreshold:  5,
		FailureWindow:     60 * time.Second,
		OpenDuration:      30 * time.Second,
		HalfOpenProbes:    1,
	})
	deps := adapters.Dependencies{
		RateLimiter:  ratelimit.NewNoop(),
		SpendTracker: rec,
		Breaker:      cb,
	}
	adapter := newAdapter(t, server, deps)
	handler := http.HandlerFunc(adapter.Handle)

	// Force 5 upstream failures in a row.
	upstream.failuresN.Store(5)
	for i := 0; i < 5; i++ {
		resp := doEmbedRequest(t, handler, 10)
		if resp.StatusCode == http.StatusOK {
			t.Fatalf("call %d: expected upstream-driven non-200, got 200", i)
		}
	}

	if cb.State() != breaker.StateOpen {
		t.Fatalf("after 5 failures: breaker state = %v, want OPEN", cb.State())
	}

	// Next call MUST short-circuit to 503 without hitting upstream.
	preCalls := upstream.calls.Load()
	resp := doEmbedRequest(t, handler, 10)
	if resp.StatusCode != http.StatusServiceUnavailable {
		t.Errorf("breaker OPEN: expected 503, got %d", resp.StatusCode)
	}
	if upstream.calls.Load() != preCalls {
		t.Errorf("breaker OPEN: upstream was contacted (%d → %d)", preCalls, upstream.calls.Load())
	}

	// Advance virtual clock past OpenDuration (30s) → half-open.
	cb.AdvanceClock(31 * time.Second)
	if cb.State() != breaker.StateHalfOpen {
		t.Fatalf("after 31s: breaker state = %v, want HALF_OPEN", cb.State())
	}

	// One probe call succeeds → breaker closes again.
	upstream.failuresN.Store(0)
	resp = doEmbedRequest(t, handler, 10)
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		t.Fatalf("half-open probe: expected 200, got %d body=%s", resp.StatusCode, body)
	}
	if cb.State() != breaker.StateClosed {
		t.Errorf("after successful probe: breaker state = %v, want CLOSED", cb.State())
	}
}
