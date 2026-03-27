---
description: Gera solution overview com feature map priorizado para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Solution Overview — Feature Map Priorizado

Gera um solution overview (~100 linhas) com visao de produto, personas, feature map priorizado (Now/Next/Later) e principios de produto. Output puramente de negocio/produto.

## Regra Cardinal: ZERO Conteudo Tecnico

Este documento descreve **o que o produto faz do ponto de vista do usuario**. Decisoes tecnicas, arquitetura e implementacao pertencem a outros artefatos.

**NUNCA incluir no output:**
- Nomes de tecnologias, frameworks, linguagens, bancos de dados, bibliotecas (ex: Python, FastAPI, Redis, Supabase, pgvector, React, Docker)
- Termos de arquitetura (ex: RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, pipeline, module)
- Referencias a ADRs, specs tecnicas, diagramas C4 ou epicos numerados
- Detalhes de infraestrutura (ex: deploy, CI/CD, server, container, cloud provider)
- Nomes de ferramentas internas de desenvolvimento

**Excecoes permitidas:** nomes proprios de produtos/empresas e termos de negocio comuns (ex: "plataforma", "canal", "automacao", "painel").

**Na duvida:** se uma frase so faz sentido para um engenheiro, reescrever em linguagem que o dono de uma PME entenderia.

## Persona

Product manager senior. Foco em valor para o usuario, nao em como construir. Portugues BR.

## Uso

- `/solution-overview fulano` — Gera solution overview para plataforma "fulano"
- `/solution-overview` — Pergunta nome da plataforma e coleta contexto

## Diretorio

Salvar em `services/vision/platforms/<nome>/business/solution-overview.md`. Criar diretorio se nao existir.

## Instrucoes

### 1. Coletar Contexto

**Se `$ARGUMENTS.platform` existe:** usar como nome da plataforma.
**Se vazio:** perguntar nome.

Verificar se ja existe arquivo em `services/vision/platforms/<nome>/business/solution-overview.md`. Se existir, ler como base.

Verificar se existe `business/vision-brief.md` — se sim, ler para extrair contexto de negocio.
Verificar se existe `planning/roadmap.md` ou `planning/epics.md` — se sim, ler para extrair features.
Verificar se existe `research/` — se sim, ler para extrair use cases.

Coletar com o usuario (perguntar tudo de uma vez):

| # | Pergunta | Exemplo |
|---|----------|---------|
| 1 | **O que o usuario faz no produto?** (1-2 frases, ponto de vista do usuario) | "Conecta WhatsApp, configura agente, acompanha metricas" |
| 2 | **Quem usa?** (2-3 personas) | "Dono PME, cliente final, operador" |
| 3 | **Features conhecidas** — lista livre, qualquer nivel de detalhe | "Responder mensagens, transferir para humano, painel admin" |
| 4 | **Prioridades** — o que vem primeiro vs depois vs futuro? | "Primeiro responder, depois painel, depois billing" |

Se ja coletou contexto de docs existentes (vision-brief, roadmap), apresentar resumo e perguntar se quer ajustar.

### 2. Gerar Solution Overview

Escrever o documento com exatamente **4 secoes**:

```markdown
---
title: "Solution Overview"
updated: YYYY-MM-DD
---
# <Nome> — Solution Overview

> O que vamos construir, para quem, e em que ordem. Ultima atualizacao: YYYY-MM-DD.

---

## Visao de Solucao

[Narrativa do produto do ponto de vista do usuario. O que ele ve, faz, e ganha.
2-3 paragrafos curtos. Linguagem simples — o dono de uma padaria entende.]

---

## Personas x Jornadas

| Persona | O que faz | O que ganha | Jornada principal |
|---------|-----------|-------------|-------------------|
| **[Persona 1]** | ... | ... | ... |
| **[Persona 2]** | ... | ... | ... |
| **[Persona 3]** | ... | ... | ... |

---

## Feature Map

| Prioridade | Feature | Descricao | Valor |
|------------|---------|-----------|-------|
| **Now** | ... | [1-2 linhas, linguagem de usuario] | [por que importa] |
| **Next** | ... | ... | ... |
| **Later** | ... | ... | ... |

---

## Principios de Produto

1. **[Principio]** — [explicacao em 1 linha]
2. ...
```

### Regras de geracao:

1. **Feature Map:** agrupar por prioridade (Now primeiro, Later ultimo). Max 15 features.
2. **Descricao:** sempre do ponto de vista do usuario, nunca do engenheiro. "Agente responde mensagens" nao "webhook recebe payload e envia para pipeline".
3. **Valor:** 1 frase curta sobre por que essa feature importa para o negocio.
4. **Principios:** max 5. Derivar do vision-brief se existir.
5. **Personas:** max 4. Incluir sempre o usuario final (quem recebe o servico), nao so quem configura.

### 3. Auto-Review

Antes de salvar, verificar:

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Zero termos tecnicos (grep: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module) | Reescrever em linguagem de produto |
| 2 | Toda feature tem descricao E valor | Completar |
| 3 | Nenhuma secao > 30 linhas | Cortar |
| 4 | Total < 120 linhas | Condensar |
| 5 | Max 15 features no map | Agrupar features similares |
| 6 | Max 5 principios | Priorizar |
| 7 | Frontmatter MkDocs correto (title + updated) | Corrigir |

### 4. Salvar

1. Salvar em `services/vision/platforms/<nome>/business/solution-overview.md`
2. Informar ao usuario:

```
## Solution Overview gerado

**Arquivo:** services/vision/platforms/<nome>/business/solution-overview.md
**Linhas:** <N>
**Features:** <N> (Now: <n>, Next: <n>, Later: <n>)

### Checks
[x] Zero jargao tecnico
[x] Features com descricao e valor
[x] Secoes <= 30 linhas
[x] Total < 120 linhas
[x] Max 15 features
[x] Max 5 principios
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Usuario nao sabe as features | Perguntar: "O que seu usuario faz no produto hoje? O que voce gostaria que ele fizesse?" e derivar features |
| Muitas features (>15) | Agrupar similares. Ex: "Evals offline" + "Evals online" = "Medicao de qualidade" |
| Sem prioridades claras | Perguntar: "Sem o que o produto nao funciona?" (Now) / "O que melhora muito?" (Next) / "O que seria legal ter?" (Later) |
| Vision-brief existe mas solution-overview nao | Ler vision-brief e derivar features dos segmentos e batalhas criticas |
| Plataforma ja tem solution-overview | Ler como base, perguntar se quer reescrever ou iterar |
