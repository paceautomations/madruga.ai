---
paths:
  - "**/*.likec4"
  - "platforms/*/model/**"
---
# LikeC4 Model Conventions

## AUTO markers
Conteúdo entre `<!-- AUTO:name -->` e `<!-- /AUTO:name -->` é gerado por `vision-build.py`.
Editar os sources `.likec4`, depois rodar: `python3 .specify/scripts/vision-build.py <name>`

## Estrutura do model
- Cada plataforma tem `model/likec4.config.json` com `{"name": "<platform>"}` (obrigatório)
- `model/spec.likec4` é o único arquivo que synca via Copier — demais são platform-specific
- `.likec4` files definem elements, relationships e views
- `likec4 export json` → `model/output/likec4.json` → vision-build.py popula markdown tables

## Servir localmente
```bash
cd platforms/<name>/model && likec4 serve   # http://localhost:5173
```
