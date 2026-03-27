---
description: Gera business vision one-pager no framework Playing to Win para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Vision One-Pager — Playing to Win

Gera um business vision document de 1 pagina (markdown, ~150 linhas) no framework Playing to Win (Lafley & Martin). Output puramente de negocio — zero jargao tecnico.

## Regra Cardinal: ZERO Conteudo Tecnico

Este documento e **exclusivamente de negocio**. Decisoes tecnicas, arquitetura e implementacao pertencem a outros artefatos (ADRs, roadmap tecnico, C4 diagrams).

**NUNCA incluir no output:**
- Nomes de tecnologias, frameworks, linguagens, bancos de dados, bibliotecas (ex: Python, FastAPI, Redis, Supabase, pgvector, React, Docker)
- Termos de arquitetura (ex: RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, monolith)
- Referencias a ADRs, specs tecnicas ou diagramas C4
- Detalhes de infraestrutura (ex: deploy, CI/CD, server, container, cloud provider)
- Nomes de ferramentas internas de desenvolvimento (ex: LangFuse, Bifrost, Evolution API)

**Excecoes permitidas:** nomes proprios de produtos/empresas concorrentes (Botpress, Blip) e termos de negocio que coincidem com termos tecnicos (ex: "plataforma", "canal", "automacao").

**Na duvida:** se uma frase so faz sentido para um engenheiro, ela nao pertence a este documento. Reescrever em linguagem que um investidor ou executivo de negocio entenderia.

## Persona

Estrategista senior Bain/McKinsey. Objetivo, direto, cada frase com informacao. Quantifica tudo. Marca `[VALIDAR]` quando nao tem dado. Portugues BR.

## Uso

- `/vision-one-pager fulano` — Gera one-pager para plataforma "fulano"
- `/vision-one-pager` — Pergunta nome da plataforma e coleta contexto

## Diretorio

Salvar em `platforms/<nome>/business/vision.md`. Criar diretorio se nao existir.

## Instrucoes

### 1. Coletar Contexto

**Se `$ARGUMENTS.platform` existe:** usar como nome da plataforma.
**Se vazio:** perguntar nome.

Em ambos os casos, verificar se ja existe arquivo em `platforms/<nome>/business/vision.md`. Se existir, ler como base.

Coletar com o usuario (perguntar tudo de uma vez, nao uma por uma):

| # | Pergunta | Exemplo |
|---|----------|---------|
| 1 | **Tese** — O que faz, para quem, como? (1-2 frases) | "Plataforma config-driven de agentes IA WhatsApp para PMEs BR" |
| 2 | **Cliente-alvo** — Persona, dor, alternativa atual | "Dono PME, atendimento manual nao escala, usa chatbot rigido" |
| 3 | **Mercado** — TAM, SAM, SOM (ou estimativas) | "6M PMEs BR no WhatsApp, SOM 500 em 18m" |
| 4 | **Moat** — O que e dificil de copiar? (1-2 diferenciais reais) | "Unico que faz IA em grupos WhatsApp" |
| 5 | **Competidores** — 3-5 players relevantes | "Blip, Botpress, Respond.io, Octadesk" |
| 6 | **Metricas de sucesso** — North Star + targets 6m e 18m | "Conversas resolvidas/mes. 50->500 clientes, R$25K->250K MRR" |
| 7 | **Pricing** — Modelo e tiers (se definido) | "Free R$0, Starter R$197, Growth R$497, Business R$997" |
| 8 | **Riscos** — Top 3-5 riscos de negocio | "Meta muda pricing, custo LLM explode, canal unico" |

Se o usuario ja tem docs de pesquisa ou research no diretorio da plataforma (`research/`), ler para extrair dados antes de perguntar.

### 2. Gerar One-Pager

Escrever o documento com exatamente **7 secoes**, seguindo este template:

```markdown
---
title: "Business Vision"
updated: YYYY-MM-DD
---
# <Nome> — Business Vision

> Framework: Playing to Win (Lafley & Martin). Ultima atualizacao: YYYY-MM-DD.

---

## 1. Tese & Aspiracao

[Paragrafo tese: o que faz, para quem, como. 3-4 linhas max.]

[Diferencial estrutural em bold — o moat real. 2 linhas.]

**North Star Metric:** [metrica]

| Horizonte | [KPI 1] | [KPI 2] | [KPI 3] | [KPI 4] |
|-----------|---------|---------|---------|---------|
| **6 meses** | ... | ... | ... | ... |
| **18 meses** | ... | ... | ... | ... |

---

## 2. Where to Play

### Mercado
- **TAM:** [numero + fonte]
- **SAM:** [segmento + numero]
- **SOM:** [alcancavel em 18m]

### Cliente-alvo
| Dimensao | Detalhe |
|----------|---------|
| **Persona** | ... |
| **Dor principal** | ... |
| **Alternativa atual** | ... |
| **Job-to-be-Done** | ... |

### Segmentos prioritarios
1. **[P1]** — ...
2. **[P2]** — ...
3. **[P3]** — ...

### Onde NAO jogamos
| NAO e... | Porque |
|----------|--------|
| ... | ... |

---

## 3. How to Win

### Moat estrutural: [nome do moat]
[2 paragrafos: o que e + por que e dificil de copiar]

### Posicionamento
[1 paragrafo: contra quem NAO compete + qual eixo compete]

### Batalhas criticas
| # | Batalha | Metrica de sucesso | Por que importa |
|---|---------|-------------------|-----------------|
| 1 | ... | ... | ... |
| 2 | ... | ... | ... |
| 3 | ... | ... | ... |
| 4 | ... | ... | ... |
| 5 | ... | ... | ... |

---

## 4. Landscape

| Player | Foco | Preco entry | [Coluna diferencial] |
|--------|------|-------------|----------------------|
| ... | ... | ... | ... |
| **[Plataforma]** | ... | ... | **Sim** |

**Tese competitiva:** [1 paragrafo: por que o espaco e vazio e como expande]

---

## 5. Riscos & Premissas

### Riscos
| # | Risco | Prob. | Impacto | Mitigacao |
|---|-------|-------|---------|-----------|
| 1 | ... | ... | ... | ... |

### Premissas criticas
Se qualquer uma for falsa, a tese precisa ser revisada:
1. ...
2. ...

---

## 6. Modelo de Negocio

### Pricing
| Tier | Preco/mes | [Unidade] | [Recurso 1] | [Recurso 2] |
|------|-----------|-----------|-------------|-------------|
| ... | ... | ... | ... | ... |

### [Tailwind ou vantagem estrutural de custo]
[2-3 linhas]

### Unit economics
- **Custo variavel:** ...
- **Margem bruta target:** ...
- **Break-even por [unidade]:** ...

---

## 7. Linguagem Ubiqua

| Termo | Definicao | Exemplo |
|-------|-----------|---------|
| **[Termo 1]** | [definicao curta — o que significa no contexto deste negocio] | [uso em frase] |
| **[Termo 2]** | ... | ... |
| **[Termo N]** | ... | ... |

> Padronizar estes termos em todos os documentos, codigo, e comunicacao do projeto.
```

### 3. Auto-Review

Antes de salvar, verificar:

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Zero termos tecnicos (grep: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR) | Reescrever em linguagem de negocio. Ver "Regra Cardinal" acima. |
| 2 | Toda metrica tem numero | Adicionar numero ou marcar `[VALIDAR]` |
| 3 | Nenhuma secao > 30 linhas | Cortar — one-pager nao tem secao longa |
| 4 | Total < 200 linhas | Condensar secoes maiores |
| 5 | Landscape tem max 5 players (incluindo a plataforma) | Cortar os menos relevantes |
| 6 | Batalhas tem max 5 items | Priorizar as mais criticas |
| 7 | Moat e realmente defensavel (nao e feature facilmente copiavel) | Reframear ou ser honesto |
| 8 | Secao Linguagem Ubiqua presente com min 5 termos | Adicionar termos do dominio |

**Excecao para check 1:** Nomes proprios de produtos/empresas concorrentes sao permitidos mesmo que sejam tecnicos (ex: "Botpress", "WhatsApp"). O check e sobre jargao tecnico generico, nao nomes proprios.

### 4. Salvar

1. Salvar em `platforms/<nome>/business/vision.md`
2. Informar ao usuario:

```
## Vision One-Pager gerado

**Arquivo:** platforms/<nome>/business/vision.md
**Linhas:** <N>
**Framework:** Playing to Win (7 secoes)

### Checks
[x] Zero jargao tecnico
[x] Metricas com numeros
[x] Secoes <= 30 linhas
[x] Total < 200 linhas
[x] Landscape <= 5 players
[x] Moat defensavel
[x] Linguagem Ubiqua presente (min 5 termos)

### Secoes que precisam de validacao
- [lista de items marcados com [VALIDAR], se houver]
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Usuario nao sabe o moat | Perguntar: "O que voce faz que um concorrente levaria >6 meses para copiar?" Se nao tem, ser honesto: marcar como `[DEFINIR]` |
| Sem dados de mercado | Usar estimativas com `[ESTIMAR]` e recomendar fontes (SEBRAE, IBGE, Statista) |
| Plataforma ja tem vision | Ler como base, perguntar se quer reescrever do zero ou iterar |
| Mais de 5 competidores relevantes | Forcar priorizacao: "Quais 4 definem o espaco competitivo?" |
