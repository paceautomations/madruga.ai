---
title: "Solution Overview"
updated: 2026-03-31
---
# Madruga AI — Solution Overview

## Visao de Solucao

O arquiteto abre o sistema, escolhe uma plataforma e comeca a documentar: visao de negocio, funcionalidades, decisoes, arquitetura. Cada documento segue uma estrutura padronizada — nao precisa inventar formato nem lembrar o que ja foi feito. O sistema guia o proximo passo.

A partir da documentacao, o arquiteto especifica funcionalidades como ciclos autocontidos. Cada ciclo passa por especificacao, planejamento, implementacao e validacao. O objetivo e que progressivamente o sistema assuma mais etapas sozinho — o arquiteto revisa e aprova em vez de executar tudo manualmente.

Tudo vive em um unico lugar, versionado, consultavel por qualquer membro do time em um portal com diagramas interativos onde da pra clicar, dar zoom e navegar pela arquitetura. Quando implementacao e documentacao divergem, o sistema detecta e alerta.

---

## Implementado — Funcional hoje

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **Criacao rapida de plataformas** | Nova plataforma pronta em minutos com toda a estrutura de documentacao pre-configurada | Elimina setup manual e garante que toda plataforma nasce com a mesma qualidade |
| **Diagramas interativos de arquitetura** | Diagramas navegaveis onde voce clica, da zoom e explora como os componentes se conectam | Qualquer pessoa entende a arquitetura sem precisar ler codigo |
| **Estrutura padronizada** | Toda plataforma herda a mesma organizacao de documentos. Atualizacoes estruturais se propagam automaticamente | Zero divergencia entre plataformas — evolui uma, evolui todas |
| **Portal unificado com dashboard** | Portal navegavel com todas as plataformas, sidebar dinamica, e dashboard visual de progresso por etapa | Um unico lugar para consultar arquitetura, decisoes e status de qualquer plataforma |
| **Fluxo guiado da documentacao ao codigo** | Fluxo continuo de 24 etapas: da visao de negocio ate o codigo. Cada etapa gera um artefato e valida antes de seguir | Nada e pulado, nada e esquecido. O sistema garante a sequencia |
| **Rastreabilidade de progresso e decisoes** | Cada etapa e decisao fica registrada com data e contexto. Dashboard mostra o que falta, o que esta desatualizado, e decisoes sao pesquisaveis por texto livre | Visibilidade total — sabe onde cada plataforma esta e por que cada decisao foi tomada |
| **Mapeamento de processos de negocio** | Fluxos de negocio documentados com diagramas visuais navegaveis | Entende como o negocio funciona antes de decidir o que construir |
| **Implementacao em repositorios externos** | Ciclos de implementacao operam diretamente no repositorio de codigo da plataforma-alvo, criando PRs automaticamente | Documentacao e codigo vivem conectados mesmo quando estao em lugares diferentes |
| **Execucao autonoma do pipeline** | DAG executor processa pipeline L1/L2 automaticamente: topological sort, dispatch via claude -p, human gates com pause/resume, retry com circuit breaker. Operador executa via CLI | O arquiteto foca em decisoes estrategicas — pipeline executa sozinho entre gates |
| **Notificacoes via Telegram** | Bot Telegram com inline keyboard para aprovar/rejeitar human gates do pipeline. Health check, backoff exponencial, offset persistence | Operador nunca perde uma decisao critica — notificacao chega em segundos |

---

## Next — Candidatos para proximos ciclos

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **Revisao multi-perspectiva** | Especificacoes revisadas automaticamente por multiplas perspectivas (arquitetura, bugs, simplicidade) antes de implementar | Pega problemas que uma unica perspectiva nao ve |
| **Deteccao e correcao de divergencias** | Apos implementacao, o sistema compara codigo com documentacao e corrige automaticamente | Documentacao nunca vira ficcao — o ciclo se fecha sozinho |

---

## Later — Visao de longo prazo

| Feature | Descricao | Por que é importante |
|---------|-----------|---------------------|
| **Processamento continuo 24/7** | Sistema funciona ininterruptamente processando ciclos aprovados enquanto o arquiteto dorme | Velocidade de entrega multiplicada — trabalho nao para quando voce para |
| **Governanca automatica de decisoes** | Sistema classifica decisoes por reversibilidade e valida continuamente se o codigo respeita as decisoes tomadas | Decisoes criticas nunca passam sem revisao; divergencias detectadas automaticamente |
| **Roadmap auto-atualizado** | Roadmap gerado automaticamente do estado real dos ciclos | Planejamento sempre reflete a realidade — nunca desatualizado |

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
| **NAO e editor de codigo** | Documenta, especifica e valida — nao substitui onde voce escreve codigo. |
| **NAO faz deploy** | Nao gerencia infraestrutura, nao publica em producao, nao substitui ferramentas de entrega. |
| **NAO e gerenciador de projetos** | Nao substitui ferramentas de tracking operacional como boards de tarefas ou sprints. |
| **NAO e catalogo de servicos** | Nao compete com portais de servicos internos. Foco e documentacao arquitetural ativa, nao inventario. |

---
handoff:
  from: solution-overview
  to: business-process
  context: "Feature map priorizado. Business process deve mapear fluxos core."
  blockers: []
  confidence: Alta
  kill_criteria: "Vision muda fundamentalmente o escopo do produto"
