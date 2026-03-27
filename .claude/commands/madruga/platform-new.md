---
description: Cria nova plataforma a partir do template Copier e gera artefatos de arquitetura
arguments:
  - name: platform
    description: "Nome da plataforma em kebab-case (ex: meu-saas, energy-platform)"
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Platform New — Scaffolding + Arquitetura Completa

Cria uma nova plataforma no repositorio madruga.ai usando o script `platform.py new`, que automaticamente:
1. Scaffolda via Copier (estrutura completa)
2. Injeta o import no LikeC4Diagram.tsx (diagramas funcionam automaticamente)
3. Atualiza symlinks do portal (conteudo aparece no Starlight)

Opcionalmente gera artefatos de arquitetura via `/architecture-portal`.

## Uso

- `/platform-new meu-saas` — Cria plataforma "meu-saas"
- `/platform-new` — Pergunta o nome e coleta contexto

## Pre-requisitos

- `copier>=9.4.0` instalado (`pip install copier`)
- `likec4` CLI (`npm i -g likec4`)

## Instrucoes

### 1. Coletar Nome e Contexto

**Se `$ARGUMENTS.platform` existe:** usar como nome.
**Se vazio:** perguntar o nome da plataforma (kebab-case).

Validar: `^[a-z][a-z0-9-]*$`. Se invalido, pedir novamente.

Coletar tambem (para passar ao copier via `-d`):
- **Titulo** (ex: "Meu SaaS — Gestao de Pedidos")
- **Descricao** (1 linha)
- **Lifecycle**: design, development ou production
- **Business flow**: incluir view de fluxo de negocio? (default: sim)

### 2. Criar Plataforma

Rodar o script que faz TUDO automaticamente:

```bash
python3 .specify/scripts/platform.py new <nome>
```

**Em contexto nao-interativo** (quando o copier nao consegue fazer perguntas), usar:

```bash
copier copy .specify/templates/platform/ platforms/<nome>/ --trust --defaults \
  -d platform_name=<nome> \
  -d "platform_title=<titulo>" \
  -d "platform_description=<descricao>" \
  -d lifecycle=<lifecycle> \
  -d include_business_flow=true \
  -d register_portal=false
```

E depois registrar no portal (inject LikeC4 + symlinks):
```bash
python3 .specify/scripts/platform.py register <nome>
```

### 3. Verificar

```bash
python3 .specify/scripts/platform.py lint <nome>
python3 .specify/scripts/platform.py list
```

### 4. Gerar Conteudo (opcional)

Perguntar ao usuario:

```
Plataforma '<nome>' criada com sucesso!

Quer gerar os artefatos de arquitetura agora?
Isso inclui: vision, solution overview, domain model, containers, ADRs, epics, modelo LikeC4.

[S] Sim — roda /architecture-portal <nome>
[N] Nao — scaffold basico pronto, preencher depois
```

Se sim: rodar `/architecture-portal <nome>`.

### 5. Apresentar Resultado

```
## Plataforma Criada

**Nome:** <nome>
**Diretorio:** platforms/<nome>/

### O que foi feito automaticamente
- [x] Estrutura scaffoldada via Copier
- [x] Import LikeC4 injetado em LikeC4Diagram.tsx
- [x] Symlink criado no portal
- [x] .copier-answers.yml gerado (habilita `copier update` futuro)

### Estrutura
platforms/<nome>/
├── platform.yaml
├── .copier-answers.yml
├── business/vision.md, solution-overview.md
├── engineering/domain-model.md, containers.md, context-map.md, integrations.md
├── decisions/, epics/, research/
└── model/ (spec.likec4, likec4.config.json, views.likec4, ...)

### Proximo passo
- `cd portal && npm run dev` para ver no portal
- `/architecture-portal <nome>` para gerar conteudo completo
- `/vision-one-pager <nome>` para gerar apenas o vision
- `/solution-overview <nome>` para gerar apenas o feature map
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| copier nao instalado | `pip install copier` |
| Plataforma ja existe | Perguntar: sobrescrever ou escolher outro nome |
| Scaffold OK mas inject/symlinks falham | Rodar `python3 .specify/scripts/platform.py register <nome>` (faz inject + symlinks + validacao) |
| Portal nao mostra a plataforma | Rodar `python3 .specify/scripts/platform.py register <nome>` e reiniciar `npm run dev` |
| likec4 build falha no modelo vazio | Normal — o scaffold gera um `dynamic view businessFlow` vazio que da warning. Preencher o conteudo resolve. |
