---
description: Gera mapeamento de fluxos de negocio com diagramas Mermaid para qualquer plataforma
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
handoffs:
  - label: Pesquisar Alternativas Tecnológicas
    agent: madruga/tech-research
    prompt: "Pesquisar alternativas tecnológicas baseadas nos fluxos de negócio validados. ATENÇÃO: Gate 1-way-door — decisões tecnológicas definem toda a arquitetura."
---

# Business Process — Fluxos de Negocio

Gera um mapeamento de 3-5 fluxos de negocio principais como diagramas Mermaid (sequence diagrams), cada um com caminho feliz e excecao. Output puramente de negocio — zero jargao tecnico.

## Regra Cardinal: ZERO Conteudo Tecnico

Este documento descreve **como o negocio funciona do ponto de vista dos atores envolvidos**. Decisoes tecnicas, arquitetura e implementacao pertencem a outros artefatos.

**NUNCA incluir no output:**
- Nomes de tecnologias, frameworks, linguagens, bancos de dados, bibliotecas (ex: Python, FastAPI, Redis, Supabase, pgvector, React, Docker)
- Termos de arquitetura (ex: RLS, API, SDK, middleware, cache, queue, webhook, endpoint, microservice, pipeline, module)
- Referencias a ADRs, specs tecnicas, diagramas C4 ou epicos numerados
- Detalhes de infraestrutura (ex: deploy, CI/CD, server, container, cloud provider)
- Nomes de ferramentas internas de desenvolvimento
- Participantes tecnicos nos diagramas (ex: "Backend", "Database", "Queue", "Cache")

**Excecoes permitidas:** nomes proprios de produtos/empresas e termos de negocio comuns (ex: "plataforma", "canal", "automacao", "painel").

**Na duvida:** se um participante ou passo do fluxo so faz sentido para um engenheiro, reescrever em linguagem que o dono de uma PME entenderia. Ex: "Sistema processa pagamento" em vez de "Payment microservice calls Stripe API".

## Persona

Estrategista senior Bain/McKinsey. Foco em fluxos de valor, gargalos operacionais e excecoes de negocio. Objetivo, direto, cada fluxo justificado. Quantifica impacto quando possivel. Marca `[VALIDAR]` quando nao tem dado. Portugues BR.

## Uso

- `/business-process fulano` — Gera fluxos de negocio para plataforma "fulano"
- `/business-process` — Pergunta nome da plataforma e coleta contexto

## Diretorio

Salvar em `platforms/<nome>/business/process.md`. Criar diretorio se nao existir.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill business-process` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes e qual skill gera cada uma.
- Se `ready: true`: ler artefatos listados em `available` como contexto adicional.
- Ler `.specify/memory/constitution.md` para validar output contra principios.

### 1. Coletar Contexto

**Se `$ARGUMENTS.platform` existe:** usar como nome da plataforma.
**Se vazio:** perguntar nome.

Verificar se ja existe arquivo em `platforms/<nome>/business/process.md`. Se existir, ler como base.

Ler obrigatoriamente:
- `platforms/<nome>/business/vision.md` — extrair personas, batalhas criticas, segmentos
- `platforms/<nome>/business/solution-overview.md` — extrair features, jornadas, prioridades

Identificar premissas implicitas nos documentos e apresentar perguntas estruturadas (perguntar tudo de uma vez):

| Categoria | Pergunta | Exemplo |
|-----------|----------|---------|
| **Premissas** | "No vision, [Persona X] faz [acao Y]. Assumo que o fluxo principal e [Z]. Correto?" | "Assumo que o dono da PME configura o agente sozinho, sem suporte tecnico. Correto?" |
| **Premissas** | "A solution-overview lista [Feature]. Assumo que ela participa do fluxo [W]. Correto?" | "Assumo que 'transferir para humano' interrompe o fluxo automatizado. Correto?" |
| **Trade-offs** | "Fluxo [A] pode ser detalhado (5+ passos) ou resumido (3 passos). Qual nivel?" | "Onboarding: detalhar cada etapa de configuracao ou resumir como 'configura e ativa'?" |
| **Gaps** | "Nao encontrei como [situacao X] e tratada. Voce define ou eu proponho?" | "Nao encontrei o que acontece quando o cliente nao responde. Voce define ou eu proponho?" |
| **Provocacao** | "[Fluxo obvio] parece essencial, mas [alternativa] pode gerar mais valor porque [razao]." | "Fluxo de 'configuracao manual' parece obvio, mas 'configuracao guiada automatica' pode reduzir churn em 40% porque elimina complexidade." |

Apresentar lista candidata de 5-7 fluxos e pedir ao usuario para priorizar 3-5.

Aguardar respostas ANTES de gerar.

### 2. Gerar process.md

Escrever o documento com **3-5 fluxos de negocio**, cada um como diagrama Mermaid sequenceDiagram com caminho feliz e caminho de excecao. Max 120 linhas total.

```markdown
---
title: "Business Process"
updated: YYYY-MM-DD
---
# <Nome> — Fluxos de Negocio

> Mapeamento dos fluxos de negocio principais. Cada fluxo mostra o caminho feliz e as excecoes. Ultima atualizacao: YYYY-MM-DD.

---

## Visao Geral dos Fluxos

| # | Fluxo | Atores | Frequencia | Impacto |
|---|-------|--------|------------|---------|
| 1 | **[Nome do Fluxo]** | [quem participa] | [estimativa] | [por que importa] |
| 2 | ... | ... | ... | ... |

---

## Fluxo 1: [Nome]

> [1 frase: o que esse fluxo resolve e por que e critico]

### Caminho Feliz

```mermaid
sequenceDiagram
    participant [Ator 1]
    participant [Ator 2]
    participant [Plataforma]
    [Ator 1]->>+[Plataforma]: [acao de negocio]
    [Plataforma]->>-[Ator 1]: [resultado]
```

### Excecoes

```mermaid
sequenceDiagram
    participant [Ator 1]
    participant [Plataforma]
    [Ator 1]->>+[Plataforma]: [acao]
    alt [condicao de excecao]
        [Plataforma]->>-[Ator 1]: [tratamento]
    end
```

**Premissas deste fluxo:**
- [premissa 1] `[VALIDAR]` se nao confirmada
- [premissa 2]

---

## Fluxo 2: [Nome]
[mesmo padrao]

---

## Premissas Globais

| # | Premissa | Status |
|---|----------|--------|
| 1 | [premissa que afeta multiplos fluxos] | [VALIDAR] ou Confirmada |

---

## Glossario de Atores

| Ator | Quem e | Aparece nos fluxos |
|------|--------|-------------------|
| **[Ator 1]** | [descricao curta] | 1, 2, 3 |
```

### Regras de geracao:

1. **Participantes:** somente atores de negocio (pessoas, papeis, "Plataforma" como caixa-preta). NUNCA componentes tecnicos.
2. **Acoes:** linguagem de negocio. "Envia mensagem", nao "POST /api/messages". "Verifica pagamento", nao "Queries payment_status table".
3. **Excecoes:** toda excecao deve ter tratamento claro do ponto de vista do usuario. "O que acontece quando X falha?"
4. **Frequencia/Impacto:** quantificar quando possivel. Marcar `[VALIDAR]` se estimativa.
5. **Max 120 linhas:** se precisar de mais, os fluxos estao detalhados demais. Abstrair.
6. **3-5 fluxos:** priorizados por impacto no negocio. O fluxo mais critico primeiro.

### 3. Auto-Review

Antes de salvar, verificar:

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Zero termos tecnicos (grep: API, SDK, framework, database, backend, frontend, deploy, server, endpoint, middleware, cache, queue, Python, Redis, Docker, Supabase, pgvector, webhook, microservice, CI/CD, ADR, pipeline, module, POST, GET, SQL, JSON) | Reescrever em linguagem de negocio |
| 2 | Todo fluxo tem caminho feliz E caminho de excecao | Adicionar o que falta |
| 3 | Participantes sao atores de negocio, nao componentes tecnicos | Renomear para papel de negocio |
| 4 | Total < 120 linhas | Condensar — abstrair passos detalhados demais |
| 5 | 3-5 fluxos (nem mais, nem menos sem justificativa) | Agrupar ou expandir |
| 6 | Toda premissa marcada [VALIDAR] ou confirmada | Marcar |
| 7 | Tabela Visao Geral presente com frequencia e impacto | Completar |
| 8 | Glossario de Atores presente | Adicionar |

### 4. Gate de Aprovacao (human)

Apresentar ao usuario:

```
## Resumo dos Fluxos de Negocio

**Fluxos mapeados:** <N>
**Atores identificados:** [lista]
**Excecoes cobertas:** <N>

### Decisoes tomadas
1. [Decisao]: [justificativa]
2. ...

### Perguntas de validacao
1. Os fluxos cobrem os cenarios mais criticos do negocio?
2. Algum ator esta faltando ou sobrando?
3. As excecoes refletem o que acontece na pratica?
4. A priorizacao (ordem dos fluxos) faz sentido?
```

Aguardar aprovacao antes de salvar.

### 5. Salvar + Relatorio

1. Salvar em `platforms/<nome>/business/process.md`
2. Informar ao usuario:

```
## Business Process gerado

**Arquivo:** platforms/<nome>/business/process.md
**Linhas:** <N>
**Fluxos:** <N> (cada um com happy path + excecao)

### Checks
[x] Zero jargao tecnico
[x] Todo fluxo com happy path + excecao
[x] Participantes sao atores de negocio
[x] Total < 120 linhas
[x] Premissas marcadas
[x] Visao Geral e Glossario presentes

### Proximo passo
/tech-research <nome>
⚠️ ATENCAO: tech-research e um gate 1-way-door — decisoes tecnologicas definem toda a arquitetura downstream.
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Usuario nao sabe quais fluxos priorizar | Perguntar: "Sem qual fluxo o negocio para de funcionar?" (prioridade 1) / "Qual fluxo diferencia voce dos concorrentes?" (prioridade 2) |
| Muitos fluxos candidatos (>7) | Agrupar similares. Ex: "Cadastro" + "Ativacao" = "Onboarding completo" |
| Fluxo muito complexo (>15 passos) | Abstrair em sub-fluxos. Manter max 8-10 passos por diagrama |
| Vision/solution-overview nao existem | ERROR: dependencias faltantes. Rodar `/solution-overview <nome>` primeiro |
| Plataforma ja tem process.md | Ler como base, perguntar se quer reescrever do zero ou iterar |
| Excecao sem tratamento claro | Perguntar ao usuario: "Quando [X] acontece, o que o [ator] faz?" |
