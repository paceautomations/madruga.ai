---
description: Gera solution overview com feature map priorizado para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Gerar Business Process
    agent: madruga/business-process
    prompt: Gerar fluxos de negocio baseados no vision e solution overview validados
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

Estrategista senior Bain/McKinsey com foco em produto. Valor para o usuario, nao como construir. Portugues BR.

## Uso

- `/solution-overview fulano` — Gera solution overview para plataforma "fulano"
- `/solution-overview` — Pergunta nome da plataforma e coleta contexto

## Diretorio

Salvar em `platforms/<nome>/business/solution-overview.md`. Criar diretorio se nao existir.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill solution-overview` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes e qual skill gera cada uma.
- Se `ready: true`: ler artefatos listados em `available` como contexto adicional.
- Ler `.specify/memory/constitution.md` para validar output contra principios.

### 1. Coletar Contexto + Questionar

**Se `$ARGUMENTS.platform` existe:** usar como nome da plataforma.
**Se vazio:** perguntar nome.

Verificar se ja existe arquivo em `platforms/<nome>/business/solution-overview.md`. Se existir, ler como base.

Verificar se existe `business/vision.md` — se sim, ler para extrair contexto de negocio.
Verificar se existe `research/` — se sim, ler para extrair use cases.

Coletar com o usuario (perguntar tudo de uma vez):

| # | Pergunta | Exemplo |
|---|----------|---------|
| 1 | **O que o usuario faz no produto?** (1-2 frases, ponto de vista do usuario) | "Conecta WhatsApp, configura agente, acompanha metricas" |
| 2 | **Quem usa?** (2-3 personas) | "Dono PME, cliente final, operador" |
| 3 | **Features conhecidas** — lista livre, qualquer nivel de detalhe | "Responder mensagens, transferir para humano, painel admin" |
| 4 | **Prioridades** — o que vem primeiro vs depois vs futuro? | "Primeiro responder, depois painel, depois billing" |

Se ja coletou contexto de docs existentes (vision), apresentar resumo e perguntar se quer ajustar.

Apos receber respostas, identificar premissas implicitas e apresentar perguntas estruturadas:

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo que [Persona X] e o usuario principal. Correto?" |
| **Trade-offs** | "Feature map amplo (mais features, menos profundidade) ou focado (menos features, mais detalhe)?" |
| **Gaps** | "Nao encontrei informacao sobre [jornada Y]. Voce define ou eu proponho?" |
| **Provocacao** | "[Feature Z] parece obvia, mas sera que e realmente Now ou pode ser Later?" |

Aguardar respostas ANTES de gerar.

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
4. **Principios:** max 5. Derivar do vision se existir.
5. **Personas:** max 4. Incluir sempre o usuario final (quem recebe o servico), nao so quem configura.

### 3. Auto-Review

Antes de salvar, verificar:

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Zero termos tecnicos (grep: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module) | Reescrever em linguagem de produto |
| 2 | Toda feature tem descricao E valor | Completar |
| 3 | Toda decisao tem >=2 alternativas documentadas | Adicionar alternativa |
| 4 | Trade-offs explicitos (pros/cons) | Adicionar pros/cons |
| 5 | Premissas marcadas [VALIDAR] ou com dado | Marcar [VALIDAR] |
| 6 | Nenhuma secao > 30 linhas | Cortar |
| 7 | Total < 120 linhas | Condensar |
| 8 | Max 15 features no map | Agrupar features similares |
| 9 | Max 5 principios | Priorizar |

### 4. Gate de Aprovacao (human)

Apresentar ao usuario:

```
## Resumo do Solution Overview

**Personas:** [lista]
**Features:** <N> (Now: <n>, Next: <n>, Later: <n>)
**Principios:** [lista]

### Decisoes tomadas
1. [Decisao]: [justificativa]
2. ...

### Perguntas de validacao
1. As personas cobrem todos os tipos de usuario?
2. A priorizacao Now/Next/Later reflete a realidade?
3. Alguma feature importante esta faltando?
4. Os principios de produto guiam decisoes futuras?
```

Aguardar aprovacao antes de salvar.

### 5. Salvar + Relatorio

1. Salvar em `platforms/<nome>/business/solution-overview.md`
2. Informar ao usuario:

```
## Solution Overview gerado

**Arquivo:** platforms/<nome>/business/solution-overview.md
**Linhas:** <N>
**Features:** <N> (Now: <n>, Next: <n>, Later: <n>)

### Checks
[x] Zero jargao tecnico
[x] Features com descricao e valor
[x] Decisoes com alternativas
[x] Trade-offs explicitos
[x] Premissas marcadas
[x] Secoes <= 30 linhas
[x] Total < 120 linhas
[x] Max 15 features
[x] Max 5 principios

### Proximo passo
`/business-process <nome>`
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Usuario nao sabe as features | Perguntar: "O que seu usuario faz no produto hoje? O que voce gostaria que ele fizesse?" e derivar features |
| Muitas features (>15) | Agrupar similares. Ex: "Evals offline" + "Evals online" = "Medicao de qualidade" |
| Sem prioridades claras | Perguntar: "Sem o que o produto nao funciona?" (Now) / "O que melhora muito?" (Next) / "O que seria legal ter?" (Later) |
| Vision existe mas solution-overview nao | Ler vision e derivar features dos segmentos e batalhas criticas |
| Plataforma ja tem solution-overview | Ler como base, perguntar se quer reescrever ou iterar |
