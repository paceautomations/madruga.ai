# Jornadas de Teste — madruga-ai

> Jornadas de usuário para validação end-to-end do portal madruga.ai.
> Atualizado por `speckit.tasks` e `reconcile`.

## J-001 — Portal carrega e exibe plataformas

Valida que o portal Astro inicializa corretamente e exibe as plataformas registradas
na listagem principal. Jornada obrigatória — falha bloqueia o QA.

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
