---
description: Gera estrutura de pastas anotada com convencoes de nomenclatura e boundaries de modulos
arguments:
  - name: platform
    description: "Nome da plataforma/produto. Se vazio, pergunta."
    required: false
argument-hint: "[nome-da-plataforma]"
---

# Folder Architecture — Estrutura de Pastas

Gera estrutura de pastas anotada (~150 linhas) com proposito de cada diretorio, convencoes de nomenclatura e boundaries de modulos.

## Regra Cardinal: ZERO Pasta sem Proposito

Cada diretorio DEVE ter razao clara de existencia. Se nao consigo explicar em 1 frase por que existe, nao deveria existir.

**NUNCA:**
- Criar pasta vazia "para o futuro"
- Copiar estrutura de outro projeto sem adaptar
- Criar pasta que duplica responsabilidade de outra
- Aninhar mais de 4 niveis sem justificativa

## Persona

Staff Engineer com 15+ anos. Estrutura deve ser navegavel por alguem novo no projeto em 5 minutos. Portugues BR.

## Uso

- `/folder-arch fulano` — Gera folder architecture para "fulano"
- `/folder-arch` — Pergunta nome

## Diretorio

Salvar em `platforms/<nome>/engineering/folder-structure.md`.

## Instrucoes

### 0. Pre-requisitos

Rodar `.specify/scripts/bash/check-platform-prerequisites.sh --json --platform <nome> --skill folder-arch` e parsear JSON.
- Se `ready: false`: ERROR listando dependencias faltantes.
- Se `ready: true`: ler artefatos em `available`.
- Ler `.specify/memory/constitution.md`.

### 1. Coletar Contexto + Questionar

**Leitura obrigatoria:**
- `engineering/blueprint.md` — stack, concerns, topologia
- `decisions/ADR-*.md` — decisoes que impactam estrutura

**Identificar convencoes da stack:**
- A partir dos ADRs, identificar framework/linguagem principal
- Pesquisar via Context7 a estrutura recomendada pelo framework
- Adaptar ao tamanho do projeto (nao usar estrutura enterprise para MVP)

**Perguntas Estruturadas:**

| Categoria | Pergunta |
|-----------|----------|
| **Premissas** | "Assumo monorepo/polyrepo. Correto?" |
| **Trade-offs** | "Feature-based (src/features/X) ou layer-based (src/models, src/services)?" |
| **Gaps** | "Blueprint nao especifica onde ficam [testes/configs/scripts]. Definir?" |
| **Provocacao** | "Estrutura flat (poucos niveis) pode ser melhor que deep nesting para este projeto." |

### 2. Gerar Folder Structure

```markdown
---
title: "Folder Structure"
updated: YYYY-MM-DD
---
# <Nome> — Folder Structure

> Estrutura de pastas anotada. Cada diretorio tem proposito documentado.

---

## Arvore Anotada

[Arvore com max 3-4 niveis, cada diretorio com comentario]

```
<nome>/
├── src/                     # Codigo fonte principal
│   ├── domain/              # Bounded contexts e agregados (DDD)
│   │   ├── [context-a]/     # [Proposito do contexto A]
│   │   └── [context-b]/     # [Proposito do contexto B]
│   ├── infra/               # Adaptadores de infraestrutura
│   │   ├── db/              # Repositories e migrations
│   │   ├── http/            # Controllers e middleware
│   │   └── messaging/       # Event handlers e publishers
│   ├── shared/              # Utilitarios cross-cutting
│   │   ├── errors/          # Error types padronizados
│   │   └── config/          # Configuration loading
│   └── main.[ext]           # Entry point
├── tests/                   # Testes (espelha src/)
│   ├── unit/                # Testes unitarios
│   ├── integration/         # Testes de integracao
│   └── e2e/                 # Testes end-to-end
├── scripts/                 # Scripts de automacao
├── docs/                    # Documentacao tecnica
├── config/                  # Configuracoes (env, deploy)
└── [outros conforme stack]
```

---

## Convencoes de Nomenclatura

| Tipo | Convencao | Exemplo |
|------|-----------|---------|
| Diretorios | kebab-case | `user-auth/` |
| Arquivos [linguagem] | [convencao da linguagem] | `user_service.py` / `UserService.ts` |
| Testes | [convencao] | `test_user_service.py` / `UserService.test.ts` |
| Configs | kebab-case | `docker-compose.yml` |

---

## Boundaries de Modulos

| Modulo | Pode importar de | NAO pode importar de |
|--------|-----------------|---------------------|
| domain/ | shared/ | infra/ |
| infra/ | domain/, shared/ | — |
| shared/ | — (sem deps internas) | domain/, infra/ |

---

## Decisoes de Estrutura

| Decisao | Escolha | Alternativa | Razao |
|---------|---------|-------------|-------|
| Organizacao | [feature/layer] | [outra] | [razao] |
| Nesting max | [N niveis] | [mais/menos] | [razao] |
| Testes | [junto/separado] | [outra] | [razao] |
```

### 3. Auto-Review

| # | Check | Acao se falhar |
|---|-------|---------------|
| 1 | Todo diretorio tem anotacao de proposito? | Adicionar |
| 2 | Nenhuma pasta vazia/sem proposito? | Remover ou justificar |
| 3 | Estrutura compativel com stack dos ADRs? | Ajustar |
| 4 | Max 4 niveis de nesting? | Flatten |
| 5 | Boundaries de modulo claras? | Definir |
| 6 | Convencoes de nomenclatura documentadas? | Adicionar |
| 7 | Max 150 linhas? | Condensar |

### 4. Gate de Aprovacao: Human

Apresentar:
- Arvore resumida (1 nivel)
- Decisoes-chave (feature vs layer, nesting, testes)
- Perguntas: "Faz sentido para sua equipe?", "Alguma pasta faltando?"

### 5. Salvar + Relatorio

```
## Folder Architecture gerada

**Arquivo:** platforms/<nome>/engineering/folder-structure.md
**Linhas:** <N>
**Diretorios top-level:** <N>
**Niveis max:** <N>

### Checks
[x] Todo diretorio com proposito
[x] Zero pastas orfas
[x] Boundaries documentadas
[x] Convencoes definidas
```

## Tratamento de Erros

| Problema | Acao |
|----------|------|
| Framework nao tem estrutura padrao | Propor baseado em best practices da linguagem |
| Projeto muito pequeno | Estrutura flat (2 niveis max) — nao forcar complexidade |
| Conflito com codebase existente (brownfield) | Ler codebase-context.md e propor migracao gradual |
| Equipe nao definiu monorepo/polyrepo | Perguntar — impacta toda a estrutura |
