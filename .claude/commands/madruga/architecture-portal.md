---
description: Gera portal de arquitetura completo — 6 artefatos visuais + ADRs + LikeC4 + Astro Starlight
argument-hint: "[nome-do-projeto] [descricao breve do negocio]"
arguments:
  - name: project
    description: "Nome do projeto (kebab-case). Ex: fulano, meu-saas, energy-platform"
    required: false
  - name: context
    description: "Descricao breve do negocio (1-2 frases)"
    required: false
---

# Architecture Portal — Gerador de Documentacao Arquitetural

Gera a documentacao completa de arquitetura de qualquer plataforma/sistema seguindo o framework de 6 artefatos visuais.

## Uso

- `/architecture-portal` — Modo interativo: coleta contexto via perguntas
- `/architecture-portal meu-projeto "plataforma SaaS de gestao de pedidos"` — Modo direto
- `/architecture-portal fulano` — Atualiza portal existente

## Pre-requisitos

- Node.js 20+, `likec4` CLI (`npm i -g likec4`)
- Knowledge: `.claude/knowledge/architecture-portal-knowledge.md`

## Instrucoes

### 1. Coletar Contexto

**Se o argumento `context` foi fornecido**, extrair o maximo possivel e pular para deep dive (passo 2).

**Se nao**, fazer as perguntas de discovery — apresentar TODAS de uma vez para o usuario responder em bloco (NAO uma por uma):

```
Para criar o portal de arquitetura, preciso entender o negocio. Responda o que souber:

1. **Tese**: Qual problema essa plataforma resolve? Por que precisa existir?
2. **Cliente**: Quem e o usuario principal? Mercado/tamanho?
3. **Sucesso**: 3-5 metricas com targets (ex: usuarios ativos, receita, churn)
4. **Principios**: 3-5 regras inegociaveis (ex: "multi-tenant desde dia 1")
5. **Anti-escopo**: O que NAO e? (ex: "nao e CRM, nao e marketplace")
6. **Riscos**: O que pode matar o projeto? (3-6 riscos)
7. **Concorrentes**: Quem mais tenta resolver? Qual seu diferencial?
8. **Processos**: Quais os 2-5 fluxos de negocio principais?
9. **Dominios**: Quais areas logicas o sistema tem?
10. **Tech stack**: Tecnologias decididas? Integracoes externas?
11. **Decisoes**: ADRs ou decisoes tecnicas ja feitas?
```

### 2. Deep Dive (se necessario)

Se o usuario forneceu contexto parcial, usar subagent para pesquisar o dominio:

- Buscar na web sobre o mercado, concorrentes, regulacoes
- Ler documentacao existente no repo (specs/, docs/, README)
- Analisar codigo existente se houver (services/, src/)

Consolidar tudo num entendimento completo antes de gerar.

### 3. Criar Estrutura de Diretorios

Se a plataforma ainda nao existe, usar Copier para scaffoldar:

```bash
copier copy .specify/templates/platform/ platforms/<ProjectName>/ --trust
```

Se ja existe (scaffold anterior), pular este passo.

### 4. Gerar os 6 Artefatos Core (em paralelo)

Lancar 3 subagents em paralelo:

**Agent 1 — Vision + Fluxos:**
- `platforms/<ProjectName>/business/vision.md` — seguir template do knowledge file. DEVE incluir secao `## Linguagem Ubiqua` com tabela de termos do dominio
- `platforms/<ProjectName>/business/solution-overview.md` — solution overview com feature map Now/Next/Later

**Agent 2 — Dominios + Arquitetura:**
- `platforms/<ProjectName>/engineering/domain-model.md` — DDD tatico + SQL fundidos
- `platforms/<ProjectName>/engineering/containers.md` — C4 L2. DEVE incluir secao `## Requisitos Nao-Funcionais` com tabela `| NFR | Target | Mecanismo | Container |`
- `platforms/<ProjectName>/engineering/context-map.md` — Context Map DDD
- `platforms/<ProjectName>/engineering/integrations.md` — diagrama + tabela de integracoes

**Agent 3 — ADRs + LikeC4 Model + Planning:**
- `platforms/<ProjectName>/decisions/ADR-NNN-*.md` — 1 por decisao (template Nygard do knowledge file)
- `platforms/<ProjectName>/epics/NNN-slug/pitch.md` — Shape Up pitches
- `platforms/<ProjectName>/platform.yaml` — manifesto declarativo (ver `platforms/fulano/platform.yaml` como referencia)
- `platforms/<ProjectName>/model/*.likec4` — modelo LikeC4 (spec, actors, platform, externals, infrastructure, ddd-contexts, relationships, views)

**IMPORTANTE para os subagents:**
- Usar Write tool para criar arquivos (NAO worktree)
- Paths absolutos
- Verificar que cada arquivo foi criado
- Seguir templates do knowledge file `.claude/knowledge/architecture-portal-knowledge.md`
- Mermaid para diagramas nos markdowns, LikeC4 para modelo interativo
- Portugues BR para prosa, ingles para codigo/termos tecnicos
- Usar `platforms/fulano/` como referencia de estrutura

### 5. Validar Artefatos

Apos geracao, verificar:

| Check | Como |
|-------|------|
| Vision e solution-overview existem | `ls platforms/<ProjectName>/business/` |
| Engineering docs existem | `ls platforms/<ProjectName>/engineering/` |
| ADRs existem | `ls platforms/<ProjectName>/decisions/ADR-*.md` |
| LikeC4 model valida | `cd platforms/<ProjectName>/model && likec4 build .` |
| platform.yaml existe | `ls platforms/<ProjectName>/platform.yaml` |
| Mermaid syntax valida | Verificar que code blocks usam ` ```mermaid ` |

### 6. Integrar no Portal (se desejado)

Para adicionar a nova plataforma ao portal Astro:

1. Adicionar symlink em `portal/setup.sh`:
   ```bash
   ln -sfn ../../../../platforms/<ProjectName> src/content/docs/<projectname>
   ```

2. Adicionar sidebar entries em `portal/astro.config.mjs`

3. Criar paginas Astro em `portal/src/pages/<projectname>/` (usar `portal/src/pages/fulano/` como referencia)

4. Atualizar `astro.config.mjs` Vite plugin workspace se necessario

5. Testar: `cd portal && npm run dev`

### 7. Apresentar Resultado

```
## Portal de Arquitetura Criado

**Projeto:** <nome>
**Arquivos:** <N> artefatos core + <M> ADRs

### Estrutura
platforms/<ProjectName>/
├── platform.yaml          <- Manifesto
├── business/
│   ├── vision.md          <- Por que existe?
│   └── solution-overview.md <- O que construir?
├── engineering/
│   ├── domain-model.md    <- Objetos + banco?
│   ├── containers.md      <- Pecas tecnicas?
│   ├── context-map.md     <- Quais dominios?
│   └── integrations.md    <- Mundo externo?
├── decisions/ADR-*.md     <- Por que assim?
├── epics/NNN-slug/pitch.md <- Como entregar?
└── model/*.likec4         <- Modelo interativo

### Proximo passo
- `cd portal && npm run dev` para ver no portal
- Revise os artefatos e ajuste conforme necessario
- Para atualizar, rode `/architecture-portal <nome>` novamente
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| likec4 nao instalado | `npm i -g likec4` |
| LikeC4 model nao valida | Verificar syntax nos .likec4 files |
| Subagent falha ao criar arquivo | Verificar path absoluto e que diretorio pai existe |
| Projeto ja existe | Perguntar: sobrescrever, atualizar ou cancelar |
