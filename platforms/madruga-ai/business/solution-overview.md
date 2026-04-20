---
title: "Solution Overview"
updated: 2026-04-20
sidebar:
  order: 2
---
# Madruga AI — Solution Overview

## Visao de Solucao

O arquiteto abre o sistema, escolhe uma plataforma e comeca a documentar: visao de negocio, funcionalidades, decisoes, arquitetura. Cada documento segue uma estrutura padronizada — nao precisa inventar formato nem lembrar o que ja foi feito. O sistema guia o proximo passo.

A partir da documentacao, o arquiteto especifica funcionalidades como ciclos autocontidos. Cada ciclo passa por especificacao, planejamento, implementacao e validacao. O objetivo e que progressivamente o sistema assuma mais etapas sozinho — o arquiteto revisa e aprova em vez de executar tudo manualmente.

Tudo vive em um unico lugar, versionado, consultavel por qualquer membro do time em um portal com diagramas interativos onde da pra clicar, dar zoom e navegar pela arquitetura. Quando implementacao e documentacao divergem, o sistema detecta e alerta.

> Personas e jornadas detalhadas → ver [Vision](./vision/).

---

## Mapa de Features

> Catalogo de funcionalidades user-facing. Cada feature carrega **Status** (✅ live · 🔄 em progresso · 📋 planejado · 🧪 beta), **Para quem** (arquiteto / operador / time) e, quando aplicavel, **Limites** observaveis.

### Criacao e estrutura de documentacao

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Criacao rapida de plataformas** | ✅ epic 001 | arquiteto | Nova plataforma pronta em minutos com toda a estrutura de documentacao pre-configurada. Zero setup manual — toda plataforma nasce com a mesma qualidade. |
| **Estrutura padronizada** | ✅ epic 001 + 007 | arquiteto | Toda plataforma herda a mesma organizacao de documentos. Atualizacoes estruturais se propagam automaticamente — evolui uma, evolui todas. |
| **Portal unificado com dashboard** | ✅ epic 010 | arquiteto + time | Portal navegavel com todas as plataformas, navegacao dinamica e painel visual de progresso por etapa. Um unico lugar para consultar arquitetura, decisoes e status de qualquer plataforma. |
| **Diagramas interativos de arquitetura** | ✅ epic 022 | arquiteto + time | Diagramas navegaveis embutidos nos proprios documentos — da pra clicar, dar zoom e explorar como os componentes se conectam. Qualquer pessoa entende a arquitetura sem ler codigo. |
| **Mapeamento de processos de negocio** | ✅ epic 001 | arquiteto | Fluxos de negocio documentados com diagramas visuais navegaveis. Entende como o negocio funciona antes de decidir o que construir. |

### Fluxo guiado de documentacao ao codigo

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Fluxo continuo de 24 etapas** | ✅ epic 007 | arquiteto | Fluxo da visao de negocio ate o codigo. Cada etapa gera um artefato e valida antes de seguir — nada e pulado, nada e esquecido. |
| **Planejamento antecipado de epics** | ✅ epic 024 | arquiteto | Prepara artefatos de planejamento de multiplos epics enquanto outro esta em execucao. Pensa no futuro sem bloquear o presente. |
| **Revisao multi-perspectiva automatica** | ✅ epic 015 | arquiteto | Especificacoes revisadas por 4 personas paralelas (revisor de arquitetura, cacador de bugs, simplificador, testador de estresse) + 1 juiz que filtra problemas reais. Pega problemas que uma unica perspectiva nao ve, sem overhead manual. |
| **Governanca automatica de decisoes** | ✅ epic 015 | arquiteto | Sistema classifica decisoes em irreversiveis (requer aprovacao humana) e reversiveis (auto-aprovaveis). Decisoes criticas nunca passam sem revisao. |
| **Deteccao e correcao de divergencias** | ✅ epic 008 | arquiteto | Apos implementacao, o sistema compara codigo com documentacao em multiplas categorias de divergencia e propoe correcoes concretas com antes/depois. Documentacao nunca vira ficcao — o ciclo se fecha sozinho. |

### Execucao autonoma do pipeline

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Execucao autonoma com phase dispatch** | ✅ epic 013 + 025 | operador | Pipeline processado automaticamente entre gates humanos, agrupando tarefas por fase — ~45% mais barato por execucao. Arquiteto foca em decisoes estrategicas; sistema executa entre aprovacoes. |
| **Modos de operacao do pipeline** | ✅ epic 016 | operador | Tres modos — manual (pausa em gates, aprovacao via CLI/Telegram), interativo (prompt no terminal), autonomo (aprova tudo, execucao fim a fim). Flexibilidade do controle total ao modo autonomo completo. |
| **Notificacoes via Telegram** | ✅ epic 014 | operador | Bot com botoes aprovar/rejeitar para gates humanos. Operador nunca perde uma decisao critica — notificacao chega em segundos. |
| **Processamento continuo 24/7** | ✅ epic 016 | operador | Servico operando ininterruptamente: agenda o pipeline, recebe aprovacoes, monitora saude, reinicia sozinho em falha. Trabalho nao para quando voce para. |
| **Fila de epics e cascata de branches** | ✅ epic 024 | arquiteto + operador | Enfileira multiplos epics; sistema promove o mais antigo automaticamente quando libera slot. Novo epic parte do codigo do anterior — elimina handoff manual. |
| **Companion de observacao em tempo real** | ✅ epic 024 | operador | Observer classifica cada execucao como saudavel/oportunidade/critica. Intervem cirurgicamente so em problemas criticos — supervisao sem overhead de atencao constante. |
| **Circuit breaker inteligente** | ✅ epic 025 | operador | Classifica erros como deterministicos, transientes ou desconhecidos. Erros deterministicos escalam rapido; erros transientes recebem retry completo. Evita loops de falha repetida. |

### Integracao com repositorios de codigo

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Implementacao em repositorios externos** | ✅ epic 012 | arquiteto | Ciclos de implementacao operam diretamente no repositorio de codigo da plataforma-alvo, criando PRs automaticamente. Documentacao e codigo vivem conectados mesmo quando estao em lugares diferentes. |
| **Rastreabilidade de commits** | ✅ epic 023 | arquiteto + time | Cada commit e ligado automaticamente a plataforma e epic que o originou, com painel de historico filtravel. Responde "quais mudancas compoem o epic N?" sem investigacao manual. |
| **Verificacao automatica de cada mudanca** | ✅ epic 011 | arquiteto | Validacoes automaticas de cada alteracao (estilo de codigo, testes, geracao do portal) antes de aceitar no tronco. Nada quebra silenciosamente. |

### Rastreabilidade, observabilidade e qualidade

| Feature | Status | Para | Valor |
|---------|--------|------|-------|
| **Rastreabilidade de progresso e decisoes** | ✅ epic 009 + 010 | arquiteto + time | Cada etapa e decisao registrada com data e contexto. Painel mostra o que falta, o que esta desatualizado; decisoes sao pesquisaveis por texto livre. Visibilidade total do estado de cada plataforma. |
| **Observabilidade e avaliacao de qualidade** | ✅ epic 017 | arquiteto + operador | Historico hierarquico por execucao, pontuacao em 4 dimensoes (qualidade, aderencia, completude, eficiencia de custo), painel de consulta + exportacao, limpeza automatica de dados antigos. | Retencao 90 dias |
| **Inteligencia de pipeline: custo e qualidade** | ✅ epic 021 | arquiteto + operador | Custo por execucao medido; detector de alucinacao (output sem acoes concretas) bloqueia progressao; fast-lane para bugs pequenos (so 3 etapas vs 11). Custo visivel, outputs fabricados bloqueados, correcoes sem overhead. |
| **Governanca de AI infrastructure** | ✅ epic 019 | arquiteto | Review obrigatorio em instrucoes de AI, guia de contribuicao, politica de seguranca, template de PR, deteccao de raio de impacto em mudancas. Governanca minima — mudancas arriscadas nunca passam sem revisao. |
| **Qualidade de codigo e base de testes** | ✅ epic 020 | arquiteto + time | Base de codigo modular com responsabilidades unicas, erros tipados, logs estruturados, +600 testes automatizados. Base sustentavel — cada modulo e compreensivel, erros sao especificos, logs sao consumidos pelas verificacoes automaticas. |

---

## Proximos ciclos e visao de longo prazo

| Feature | Horizonte | Valor |
|---------|-----------|-------|
| **Piramide de testes runtime** | Proximo — epic 026 | Testes automatizados em todos os niveis do pipeline (unidade, integracao, smoke, regressao). Reduz chance de regressao silenciosa em mudancas futuras. |
| **ProsaUAI end-to-end autonomo** | Proximo | Primeiro epic completo processado pelo pipeline autonomo em repositorio externo real. Prova que o sistema funciona fora do self-ref — valor real entregue a outra plataforma. |
| **Roadmap auto-atualizado** | Longo prazo | Roadmap gerado automaticamente do estado real dos ciclos, com pontuacao de divergencia e status de marcos. Planejamento sempre reflete a realidade — nunca desatualizado. |

---

## Principios de Produto

1. **Uma fonte de verdade** — Documentacao, diagramas e codigo partem do mesmo lugar. Nunca existem duas versoes conflitantes.
2. **Pronto em minutos** — Nova plataforma ou funcionalidade comeca com estrutura completa, nao com pagina em branco.
3. **Autonomia progressiva** — Comece fazendo tudo manualmente. Conforme confia no sistema, delegue mais etapas. Decisoes criticas sempre passam por humano.
4. **Qualquer um entende** — Portal navegavel, diagramas interativos, linguagem clara. Nao precisa ser engenheiro para entender a arquitetura.
5. **Sempre atualizado** — Implementacao retroalimenta documentacao automaticamente. O ciclo se fecha sozinho.

---

## O que NAO fazemos

| NAO e... | Porque |
|----------|--------|
| **Editor de codigo** | Documenta, especifica e valida — nao substitui onde voce escreve codigo. |
| **Ferramenta de deploy** | Nao gerencia infraestrutura, nao publica em producao, nao substitui ferramentas de entrega. |
| **Gerenciador de projetos** | Nao substitui ferramentas de tracking operacional como boards de tarefas ou sprints. |
| **Catalogo de servicos** | Nao compete com portais de servicos internos. Foco e documentacao arquitetural ativa, nao inventario. |

---

> **Proximo passo:** `/madruga:business-process madruga-ai` — mapear fluxos core a partir do feature map priorizado.
