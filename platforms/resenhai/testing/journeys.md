---
title: "Test Journeys"
updated: 2026-05-03
---
# Jornadas de Teste — resenhai

> Jornadas de usuário para validação end-to-end. Atualizado por `speckit.tasks` e `madruga:reconcile`.
> Marcar `required: true` para jornadas que bloqueiam o QA quando falham.

---

## J-001 — [Nome da jornada]

<!-- 1-2 frases descrevendo o que valida e por que importa. -->

```yaml
id: J-001
title: "[Titulo da jornada]"
required: true
steps:
  - type: browser              # ou: api
    action: "navigate http://localhost:PORT"
    screenshot: true
  - type: browser
    action: "assert_contains [texto esperado]"
```

<!-- Adicione mais jornadas (J-002, J-003 ...) seguindo o mesmo padrao YAML. -->
