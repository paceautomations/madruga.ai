---
description: Gera blueprint de engenharia com concerns transversais, NFRs e topologia de deploy para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Definir Folder Architecture
    agent: madruga/folder-arch
    prompt: Definir estrutura de pastas baseada no blueprint aprovado
  - label: Gerar Domain Model (DDD)
    agent: madruga/domain-model
    prompt: Gerar modelo de dominio DDD baseado no blueprint e fluxos de negocio
---

# Blueprint — Engenharia de Plataforma

Gera blueprint de engenharia (~200 linhas) com concerns transversais, NFRs, topologia de deploy, data map e glossario tecnico. Referencia ADRs e business layer.

## Regra Cardinal: ZERO Over-Engineering

Se nao consigo explicar uma decisao em 1 paragrafo, esta complexo demais. Toda escolha arquitetural deve ser **a coisa mais simples que funciona** para o contexto atual.

**NUNCA:**
- Adicionar camada de abstracao "para o futuro"
- Escolher tecnologia complexa quando simples resolve
- Copiar arquitetura de FAANG sem justificar para o tamanho do projeto
- Incluir concern transversal sem problema real que resolve

**SEMPRE perguntar:** "Isso e a coisa mais simples que funciona?"

## Persona

Staff Engineer com 15+ anos. Obcecado por simplicidade. Referencia patterns reais (Netflix, Shopify, Stripe) mas adapta ao tamanho do projeto. Portugues BR.

## Uso

- `/blueprint fulano` — Gera blueprint para plataforma "fulano"
- `/blueprint` — Pergunta nome da plataforma

## Diretorio

Salvar em `platforms/<nome>/engineering/blueprint.md`.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill blueprint` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available`.
- Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Questionar

**Leitura obrigatoria:**
- `decisions/ADR-*.md` — todas as decisoes tecnologicas aprovadas
- `business/*` — vision, solution-overview, process
- `research/codebase-context.md` — se existir (brownfield)

**Para cada concern transversal:**
- Usar Context7 para pesquisar best practices da stack escolhida (nos ADRs)
- Web search: "[tecnologia] [concern] best practices 2026"

**Perguntas Estruturadas:**

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo que [concern X] e necessario porque [razao]. Correto?" |
| **Trade-offs** | "Para logging: [structured JSON] (simples, busca facil) ou [ELK stack] (poderoso, complexo). Qual?" |
| **Gaps** | "ADRs nao cobrem [observabilidade/seguranca]. Definir agora?" |
| **Provocacao** | "Voce realmente precisa de [concern]? Netflix tem, mas com 100x sua escala." |

Aguardar respostas ANTES de gerar.

### 2. Gerar Blueprint

Verificar se template existe em `.specify/templates/platform/template/engineering/blueprint.md.jinja` e usar sua estrutura.

```markdown
---
title: "Engineering Blueprint"
updated: YYYY-MM-DD
---
# <Nome> — Engineering Blueprint

> Decisoes de engenharia, concerns transversais e topologia. Ultima atualizacao: YYYY-MM-DD.

---

## Stack Tecnologico

[Tabela resumo derivada dos ADRs — nao repetir detalhes, referenciar ADR-NNN]

| Categoria | Escolha | ADR |
|-----------|---------|-----|
| ... | ... | ADR-NNN |

---

## Concerns Transversais

### Autenticacao & Autorizacao
[Approach, padrao, referencia a ADR se aplicavel]

### Logging & Observabilidade
[Structured logging, metricas, tracing — o minimo necessario]

### Tratamento de Erros
[Padrao de error handling, error codes, retry policy]

### Configuracao
[Como configs sao gerenciadas — env vars, config files, feature flags]

### Seguranca
[OWASP top 10 relevantes, input validation, secrets management]

[Adicionar apenas concerns que o projeto REALMENTE precisa]

---

## NFRs (Non-Functional Requirements)

| NFR | Target | Metrica | Como Medir |
|-----|--------|---------|-----------|
| Latencia P95 | < Xms | response time | [ferramenta] |
| Disponibilidade | X% | uptime | [ferramenta] |
| Throughput | X req/s | requests/sec | [ferramenta] |
| Recovery | RTO Xmin | time to recover | [processo] |

---

## Topologia de Deploy

[Diagrama Mermaid com containers/servicos e como se conectam]

```mermaid
graph LR
  ...
```

| Container | Tecnologia | Responsabilidade |
|-----------|-----------|-----------------|
| ... | ... | ... |

---

## Data Map

| Store | Tipo | Dados | Tamanho estimado |
|-------|------|-------|-----------------|
| ... | ... | ... | ... |

---

## Glossario Tecnico

| Termo | Definicao |
|-------|-----------|
| ... | ... |
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo NFR tem target mensuravel? | Adicionar numero |
| 2 | Todo concern tem justificativa ("porque precisamos")? | Justificar ou remover |
| 3 | Nenhum over-engineering ("para o futuro")? | Simplificar |
| 4 | Referencia ADRs para decisoes de stack? | Adicionar referencia |
| 5 | Max 200 linhas? | Condensar |
| 6 | Referencia patterns reais (empresas/projetos)? | Adicionar |
| 7 | Topologia tem diagrama Mermaid? | Adicionar |
| 8 | Cada decisao responde "e a coisa mais simples que funciona?"? | Revalidar |

### 4. Gate de Aprovacao: Human

Apresentar ao usuario:

**Resumo do Blueprint:**
- Stack: [resumo]
- Concerns: [N] transversais incluidos
- NFRs: [lista com targets]
- Containers: [N]

**Decisoes-chave:**
| # | Decisao | Alternativa mais simples | Alternativa mais robusta | Escolha |
|---|---------|------------------------|------------------------|---------|
| 1 | ... | ... | ... | ... |

**Perguntas de validacao:**
1. O blueprint reflete a complexidade NECESSARIA (nao mais)?
2. Algum concern e desnecessario para o momento atual?
3. NFR targets sao realistas?
4. Posso seguir para folder-arch e domain-model?

### 5. Salvar + Relatorio

1. Salvar em `platforms/<nome>/engineering/blueprint.md`
2. Informar:

```
## Blueprint gerado

**Arquivo:** platforms/<nome>/engineering/blueprint.md
**Linhas:** <N>
**Concerns:** <N> transversais
**NFRs:** <N> com targets

### Checks
[x] NFRs com targets mensuraveis
[x] Concerns justificados
[x] Zero over-engineering
[x] ADRs referenciados
[x] Max 200 linhas
[x] Diagrama de topologia presente

### Proximos Passos (paralelos)
- `/folder-arch <nome>` — Definir estrutura de pastas
- `/domain-model <nome>` — Gerar modelo de dominio DDD
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| ADRs incompletos ou conflitantes | Listar conflitos, pedir resolucao antes de gerar |
| Projeto muito simples (1 servico) | Gerar blueprint minimo — nao forcar complexidade |
| Muitos concerns (>7) | Perguntar: "Quais sao os 5 mais criticos agora?" |
| NFRs sem baseline | Marcar [DEFINIR] e sugerir defaults por tipo de app |
| Sem codebase-context | OK — tratar como greenfield |
