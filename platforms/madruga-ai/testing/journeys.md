# Jornadas de Teste — madruga-ai

> Jornadas de usuário para validação end-to-end do portal madruga.ai.
> Atualizado por `speckit.tasks` e `reconcile`.

## J-001 — Portal carrega e exibe plataformas (happy path / Deployment Smoke)

Happy path obrigatório consumido pelo Deployment Smoke (epic 027 phase 12):
portal home retorna 200 → documento vision da plataforma madruga-ai retorna 200.

Valida que o portal Astro inicializa corretamente, exibe as plataformas registradas
na listagem principal, e que o roteamento dinâmico `/[platform]/business/vision/`
serve a página esperada com status 200. Jornada obrigatória — falha bloqueia o QA.

A assertion final reutiliza `expect_status: 200` declarado em
`platform.yaml.testing.urls` (label "Plataforma madruga-ai (vision doc)") como
única fonte de verdade do critério de smoke.

```yaml
id: J-001
title: "Portal carrega e exibe plataformas"
required: true
steps:
  - type: browser
    action: "navigate http://localhost:4321"
    screenshot: true
  - type: browser
    action: "assert_contains madruga-ai"
  - type: browser
    action: "assert_contains prosauai"
  - type: api
    action: "GET http://localhost:4321/madruga-ai/business/vision/"
    assert_status: 200  # mirrors platform.yaml.testing.urls[vision doc].expect_status
```

## J-002 — Status do pipeline acessível via URL

Valida que a URL raiz do portal responde com HTTP 200, confirmando que o servidor
de desenvolvimento está ativo e servindo conteúdo corretamente.

```yaml
id: J-002
title: "Status do pipeline acessível via URL"
required: false
steps:
  - type: api
    action: "GET http://localhost:4321"
    assert_status: 200
```
