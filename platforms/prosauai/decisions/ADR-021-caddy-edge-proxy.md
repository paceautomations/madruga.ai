---
title: 'ADR-021: Caddy 2 como edge proxy publico (Fase 2 multi-tenant)'
status: Proposed
decision: Caddy 2 com TLS automatico via Let's Encrypt + rate limit por IP
alternatives: Traefik 3, Nginx + Certbot, Cloudflare Tunnel + Workers, AWS API Gateway / GCP Load Balancer
rationale: Simplicidade operacional maxima — single binary, config declarativa, TLS automatico zero-config, rate limit nativo. Time pequeno (5 pessoas) sem SRE dedicado prioriza menor superficie operacional.
---
# ADR-021: Caddy 2 como edge proxy publico (Fase 2 multi-tenant)

**Status:** Proposed | **Data:** 2026-04-10

> **Status note:** Esta ADR e **acionavel apenas a partir da Fase 2** (epic 012). Documentada agora (2026-04-10) durante o draft do epic 003 para registrar decisao end-state e evitar surpresa futura. Trigger de implementacao: primeiro cliente externo pagante.

## Contexto

Na Fase 1 (epic 003 — Multi-Tenant Foundation), o ProsauAI opera com 2 tenants internos (Pace Ariel + Pace ResenhAI) e **nenhuma porta publica**: dev usa Tailscale, prod usa Docker network privada compartilhada com a Evolution API na mesma VPS. Trafego nunca sai do host. Superficie de ataque externa = zero.

Na Fase 2 (epic 012 — Public API), surgira o primeiro cliente externo. Cliente externo significa:

1. Cliente tem **sua propria** instancia Evolution (rodando na infra dele, nao na VPS Pace)
2. Cliente precisa apontar webhook da Evolution dele para uma URL **publica** do ProsauAI
3. Essa URL publica precisa ter TLS valido (browsers e cURL rejeitam self-signed)
4. ProsauAI precisa proteger contra DDoS, abuso, e isolar tenants entre si

A ProsauAI API (FastAPI :8050) **nao deve** ser exposta diretamente na internet por 3 razoes:

- **Sem TLS:** uvicorn nao fala HTTPS nativamente; usar Let's Encrypt direto na app exige bibliotecas extra e logica de renewal customizada
- **Sem rate limit por IP global:** FastAPI middleware de rate limit opera por requisicao, nao por IP de origem antes da app processar. Atacante consegue fazer DDoS de logging + parsing antes do rate limit acionar.
- **Single point of failure:** se a app cair, nao ha proxy para mostrar pagina de erro ou rotear para health check. Cliente recebe `connection refused` opaco.

A pergunta e: **qual edge proxy colocar na frente do `prosauai-api` para Fase 2?**

## Decisao

We will usar **Caddy 2 alpine container** como edge proxy publico, configurado via `Caddyfile` declarativo, com TLS automatico via Let's Encrypt e rate limit por IP nativo.

### Topologia Fase 2

```text
Internet → :443 → Caddy 2 → reverse_proxy → prosauai-api:8050 (Docker network privada)
                       │
                       └─ rate_limit (zone tenants 100r/m)
                       └─ TLS automatico (Let's Encrypt + ACME)
                       └─ HTTP → HTTPS redirect (301)
```

### Caddyfile inicial (Fase 2)

```caddy
api.prosauai.com {
    encode zstd gzip

    rate_limit {
        zone webhook_per_ip {
            key {client_ip}
            window 1m
            events 200
        }
        zone admin_per_ip {
            key {client_ip}
            window 1m
            events 30
        }
    }

    @webhook path /webhook/*
    @admin path /admin/*

    handle @webhook {
        rate_limit zone webhook_per_ip
        reverse_proxy api:8050 {
            health_uri /health
            health_interval 30s
        }
    }

    handle @admin {
        rate_limit zone admin_per_ip
        reverse_proxy api:8050
    }

    handle / {
        respond "ProsaUAI Multi-Tenant API. See docs.prosauai.com" 200
    }

    log {
        output file /var/log/caddy/access.log
        format json
    }
}
```

### Mudancas em `docker-compose.prod.yml`

```yaml
services:
  caddy:
    image: caddy:2-alpine
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    networks: [pace-net]
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
      - caddy-config:/config
      - caddy-logs:/var/log/caddy

  api:
    # ... existing
    networks: [pace-net]
    # ports: REMAINS empty — only Caddy talks to it

volumes:
  caddy-data:
  caddy-config:
  caddy-logs:

networks:
  pace-net:
    external: true
```

### Operacoes cobertas pelo Caddy

- **TLS automatico:** Let's Encrypt issuance + renewal sem intervencao
- **HTTP → HTTPS redirect:** 301 automatico
- **Rate limit por IP:** zonas distintas para webhook (200/min) e admin (30/min)
- **Health check upstream:** Caddy verifica `/health` a cada 30s; remove instancia ruim do pool
- **Compression:** zstd + gzip
- **Logs estruturados JSON:** integraveis com Phoenix (epic 002) ou Loki futuro
- **Graceful reload:** `caddy reload` sem downtime
- **Hot reload do Caddyfile:** mount como volume read-only, edita o file, reload

## Alternativas consideradas

### Traefik 3
- **Pros:** integracao nativa com Docker labels (auto-discovery), dashboard built-in, popular em K8s
- **Cons:** YAML/labels mais verboso que Caddyfile; rate limit per-IP exige plugin externo; documentacao TLS/Let's Encrypt mais complexa que Caddy; observabilidade exige Prometheus + Grafana ja na Fase 2 (Fase 3 do nosso roadmap). **Overkill para 1-5 tenants iniciais.**

### Nginx + Certbot
- **Pros:** padrao da industria, performance battle-tested, tudo bem documentado
- **Cons:** TLS automatico nao e nativo (precisa Certbot scheduled job + reload); configuracao nginx.conf e proceduralmente complexa (blocks dentro de blocks); rate limit nativo opera por endereco, mas integracao com Docker DNS interno requer cuidado. Custo operacional alto para o tamanho do time.

### Cloudflare Tunnel + Workers
- **Pros:** zero infra de proxy local (Cloudflare gerencia), DDoS protection global, edge caching, WAF
- **Cons:** **dependencia critica externa** (CF down = ProsauAI inacessivel); custo mensal escalavel com trafego; vendor lock-in; webhook flow tem latencia extra (cliente → CF edge → tunnel → VPS); admin API nao pode ser exposta sem complexidade Workers extra; observabilidade vai para o painel CF (nao integra com Phoenix). **Acoplamento forte demais para Fase 2.**

### AWS API Gateway / GCP Load Balancer
- **Pros:** managed totalmente, escala infinita, integracao IAM
- **Cons:** **a ProsauAI nao roda em AWS/GCP** — VPS Hostinger. Migrar pra cloud so para usar API Gateway = custo mensal exorbitante + vendor lock-in + perda de simplicidade operacional. Rejeitado por incompatibilidade de stack.

## Consequencias

- [+] **Single binary container** (~50MB Caddy alpine) — operavel por 1 pessoa sem SRE
- [+] **TLS zero-config** — Let's Encrypt issuance + renewal automatico, sem cron jobs
- [+] **Rate limit nativo** com zonas configuraveis por path
- [+] **Hot reload** — editar Caddyfile + `docker exec caddy caddy reload`
- [+] **Health check upstream** automatico — degradacao graciosa quando api esta down
- [+] **Logs estruturados JSON** integraveis com Phoenix/Loki
- [+] **Caddyfile commitavel** no repo prosauai (versionado, code-review)
- [+] **Compatibility** com Docker network privada existente — `reverse_proxy api:8050` resolve via DNS interno
- [-] **Caddy aprende a ser o ponto unico de exposicao** — se Caddy cair, ProsauAI fica inacessivel publicamente. Mitigacao: `restart: unless-stopped` + health monitoring + rollback plan
- [-] **Rate limit por IP nao e per-tenant** — defesa contra DDoS, mas tenant abusivo legitimo passa pela rate limit do IP do servidor dele (resolvido pelo rate limit per-tenant em Redis no nivel da app — [ADR-015](ADR-015-noisy-neighbor-mitigation.md))
- [-] **TLS handshake adiciona ~10-50ms latencia** vs HTTP plain — irrelevante para webhooks (tipicamente >100ms ja)
- [-] **Logs do Caddy rotacionam manualmente** se nao usar logrotate ou lib externa — mitigacao: `--rotate` flag ou Loki/Vector pull

## Refinamentos Fase 3

Quando a Fase 3 (epic 013) entrar:

- **Caddy + Prometheus exporter** — metricas via `/metrics` endpoint; integracao com Grafana
- **WAF rules** customizaveis no Caddyfile (regex matching para inputs maliciosos antes de chegar na app)
- **JWT validation no proxy** — Caddy pode validar JWT antes de proxiar para `/admin/*` (libera a app de auth check duplicado)
- **TLS client certificates** opcional para tenants enterprise (mTLS)

---

> **Proximo passo:** Trigger de implementacao = primeiro cliente externo pagante. Quando isso acontecer, implementar como parte do epic 012 (Public API Fase 2) junto com [ADR-022](ADR-022-admin-api.md).
