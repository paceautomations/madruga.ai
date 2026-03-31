# QA Template

Template de referência para o skill QA. Define as camadas de validação e estrutura do relatório.

## Camadas de QA (Auto-Adaptativas)

| Camada | Sempre | Condicional |
|--------|--------|-------------|
| Static Analysis | ruff, eslint, type-check | Ativado se código Python/TS existe |
| Unit Tests | pytest, jest/vitest | Ativado se diretório tests/ existe |
| Code Review | Diff review vs spec/tasks | Sempre |
| Build | npm run build, python -m build | Ativado se build script existe |
| API/Integration | Endpoint smoke tests | Ativado se API server configurado |
| Browser QA | Playwright visual/functional | Ativado se frontend existe e server roda |

## Estrutura do Relatório

```markdown
# QA Report — Epic {epic_id}

## Resumo
- **Status**: PASS | FAIL | PASS_WITH_WARNINGS
- **Camadas executadas**: [lista]
- **Issues encontrados**: {count}

## Resultados por Camada

### Static Analysis
- Tool: ruff / eslint
- Resultado: PASS/FAIL
- Issues: [lista]

### Tests
- Framework: pytest / vitest
- Cobertura: X%
- Resultado: X passed, Y failed

### Code Review
- Aderência ao spec: X%
- Aderência ao tasks.md: X%
- Issues: [lista]

### Build
- Resultado: SUCCESS/FAIL
- Warnings: [lista]

### Browser QA (se aplicável)
- Screenshots: [paths]
- Console errors: [lista]
- Visual regressions: [lista]

## Heal Loop
Issues que foram corrigidos automaticamente durante o QA:
- [lista de auto-fixes]

## Recomendação
- [ ] Aprovar para reconcile
- [ ] Bloquear — requer fixes manuais
```

## Critérios de Aprovação

- **PASS**: Zero BLOCKER, zero FAIL em tests, build OK
- **PASS_WITH_WARNINGS**: Zero BLOCKER, warnings aceitáveis
- **FAIL**: Qualquer BLOCKER ou test failure não resolvido pelo heal loop
