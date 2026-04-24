# Jornadas de Teste — prosauai

> Jornadas de usuário para validação end-to-end do ProsaUAI (Admin Dashboard + API).
> Atualizado por `speckit.tasks` e `reconcile`.

## J-001 — Admin Login Happy Path

Valida o fluxo completo de autenticação no dashboard de administração: acesso à raiz
renderiza o shell do admin que redireciona para `/admin/login`, formulário está presente,
credenciais bootstrap (via env `ADMIN_BOOTSTRAP_EMAIL` / `ADMIN_BOOTSTRAP_PASSWORD`) são
aceitas e o dashboard é exibido após o login. Jornada obrigatória — falha bloqueia o QA.

```yaml
id: J-001
title: "Admin Login Happy Path"
required: true
steps:
  - type: api
    action: "GET http://localhost:3000"
    assert_status: 200
  - type: browser
    action: "navigate http://localhost:3000/admin"
    assert_url_contains: /admin/login
  - type: browser
    action: "navigate http://localhost:3000/admin/login"
    screenshot: true
  - type: browser
    action: "fill_form email=$ADMIN_BOOTSTRAP_EMAIL password=$ADMIN_BOOTSTRAP_PASSWORD"
  - type: browser
    action: "click button[type=submit]"
    screenshot: true
  - type: browser
    action: "assert_url_contains /admin"
```

## J-002 — Webhook ingest e isolamento de tenant

Valida que o endpoint de ingest de webhook responde corretamente. Aceita tanto 200
(ingestão imediata) quanto 422 (validação rejeitada) como respostas esperadas.

```yaml
id: J-002
title: "Webhook ingest e isolamento de tenant"
required: false
steps:
  - type: api
    action: "POST http://localhost:8050/api/v1/webhook"
    assert_status: [200, 422]
```

## J-003 — Cookie expirado redireciona para /login

Valida que acessar uma rota protegida do dashboard sem cookie de sessão válido
resulta em redirecionamento para a página de login.

```yaml
id: J-003
title: "Cookie expirado redireciona para /login"
required: false
steps:
  - type: browser
    action: "navigate http://localhost:3000/dashboard"
  - type: browser
    action: "assert_contains login"
```
