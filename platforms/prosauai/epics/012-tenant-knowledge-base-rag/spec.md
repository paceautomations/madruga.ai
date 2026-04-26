# Feature Specification: Tenant Knowledge Base — RAG pgvector + Upload Admin

**Feature Branch**: `epic/prosauai/012-tenant-knowledge-base-rag`
**Created**: 2026-04-26
**Status**: Draft
**Input**: Epic pitch `012-tenant-knowledge-base-rag/pitch.md` (escopo integral, decisoes capturadas e cronograma de 3 semanas / 3 PRs preservados no pitch).

## Contexto do problema

A vision de ProsaUAI ([business/vision.md L88](../../business/vision.md#L88)) promete **self-service onboarding em <15 minutos** como Batalha Critica #2. Hoje isso e estruturalmente impossivel: cada tenant novo (Ariel, ResenhAI) precisa de um dev da Pace escrevendo YAML manual com persona, system prompt, regras de negocio, catalogo de produtos e estatisticas. O bot funciona porque o time **conhece o negocio**; um cliente externo entrar exigiria dias de onboarding manual, nao minutos.

Os gaps concretos em producao:

1. **Agente nao sabe nada alem do `system_prompt`** — sem RAG, a unica forma do bot responder "qual o horario de funcionamento?" ou "voces tem produto X?" e hardcoded no prompt; nao escala alem de 5-10 FAQs.
2. **Tenants enviam PDFs por WhatsApp para os devs** — workflow real observado em ResenhAI: cliente manda PDF de FAQ, dev copia trechos pro system_prompt e commita. Overhead humano absurdo.
3. **ADR-013 (Aceito 2026-03-25) decidiu pgvector + schema `knowledge_chunks`** mas a tabela **nunca foi criada** — schema vive so no ADR. Todo o plano de RAG ficou no papel.
4. **Risco aberto no [roadmap](../../planning/roadmap.md#L185)** — "Onboarding <15min impossivel sem RAG" — endereca em 012.
5. **Baseline de resolucao autonoma (North Star 70%)** nao sobe sem o agente ter contexto de negocio especifico. Epic 011 (em curso) **mede** o numero; epic 012 e o que **faz subir**.

Este epic **materializa** o que ADR-013 prometeu: migration `documents` + `knowledge_chunks` + HNSW index + extensao Bifrost para `/embeddings` + API admin de upload + tool `search_knowledge` no agente + UI de gestao no admin. Escopo v1 deliberadamente enxuto: **Markdown/text/PDF apenas**, upload sync ate 10MB, per-tenant com `agent_id` opcional, retrieval como tool opcional acionada pelo LLM. Reversivel via `rag.enabled: false` per-tenant em <=60s.

Dividido em 3 PRs sequenciais mergeaveis em `develop`, cada um reversivel via feature flag — ver `pitch.md` para cronograma e decisoes capturadas.

## Clarifications

### Session 2026-04-24 (epic-context draft)

> Decisoes tentativas em draft mode (`/madruga:epic-context --draft`). Promocao normal mode pode revisar via delta review e marcar com `[REVISADO YYYY-MM-DD]`.

- Q: Quais formatos de arquivo aceitos no upload em v1? → A: **Markdown + text + PDF apenas**. DOCX/HTML/URL crawl adiados para 012.1. PDF reusa PyMuPDF ja dependencia do epic 009 (content processing). Trade-off aceito: tenant converte DOCX/PDF estranho no site de sua escolha antes (modo 2026 — qualquer AI converte).
- Q: Embedding provider e modelo? → A: **OpenAI `text-embedding-3-small` (1536 dim) via Bifrost extension**. Alinha com schema ADR-013 (`VECTOR(1536)`). Custo ~R$0.0001/chunk (~R$0.10 por tenant onboarding completo). BGE self-hosted rejeitado: quebraria schema (1024 dim != 1536) + nova infra. Bifrost ganha provider OpenAI para `/v1/embeddings` com mesmo rate limiting + spend tracking do chat completions (ADR-042 novo).
- Q: Estrategia de chunking? → A: **MD header-aware** para `.md` (chunka em `##`/`###`); **fixed-size 512 tokens + 50 overlap** para PDF/text. Stdlib only, <100 LOC. Semantic chunking rejeitado: complexidade + vendor lock sem ganho proporcional para v1.
- Q: Como o agente usa o KB? Retrieval automatico em toda mensagem ou tool opcional? → A: **RAG como tool opcional** — `search_knowledge(query: str, top_k: int = 5)` registrado em `tools/registry.py`. LLM decide quando chamar via function calling. Retrieval automatico em toda msg rejeitado: custo/ruido em msgs triviais ("oi", "obrigado") + risco de hallucination com chunks irrelevantes injetados. Alinha com epic 013 (Agent Tools v2) futuro.
- Q: Escopo do KB — per-tenant ou per-agent? → A: **Per-tenant default com `agent_id` opcional**. Coluna `knowledge_chunks.agent_id UUID NULL` permite filtrar para agente especifico se tenant quiser; `agent_id IS NULL` = compartilhado entre todos os agentes. Per-agent strict rejeitado: duplica docs comuns (FAQ, sobre a empresa) + UX complexo. Per-tenant only rejeitado: sem flex futura.
- Q: Upload UX — sync ou async? → A: **Sync ate 10MB**. Chunk count tipico <200, embedding paralelo via Bifrost ~10s; usuario aguarda e ve resultado inline. Async (ARQ) rejeitado: puxa componente proprio; FastAPI BackgroundTasks rejeitado: nao persistente em restart. >10MB retorna 413.
- Q: Document lifecycle — replace by source_name ou versionamento? → A: **Replace by source_name (atomic)**. Upload com `source_name` que ja existe -> transaction: DELETE chunks antigos + DELETE Storage + INSERT novo document + chunks. Sem versionamento em v1 (overengineering para PME). Diff-based rejeitado: complexidade enorme por ganho minimo (re-embed total custa R$0.005). ADR-041 novo.
- Q: Onde armazenar o arquivo raw? → A: **Supabase Storage bucket `knowledge`** path `{tenant_id}/{document_id}.{ext}`. Permite re-chunking/re-embedding futuro sem exigir re-upload do tenant. "So chunks no DB" rejeitado: amarra em decisoes de chunking. "raw_content TEXT" rejeitado: perde layout original do PDF.
- Q: Como lidar com upgrade de embedding model no futuro? → A: **CLI `python -m prosauai.rag.reembed --tenant <slug>`** le raw do Storage e re-embeda chunks. Coluna `knowledge_chunks.embedding_model TEXT NOT NULL` para audit + query isolation (um tenant tem todos chunks do mesmo `embedding_model`). Zero acao do tenant.
- Q: Retrieval params em v1? → A: **`top_k=5` default; sem distance threshold em v1** (retorna sempre top-5 mesmo que distantes — LLM filtra no contexto). Threshold `rag.min_distance_threshold` per-tenant em `tenants.yaml` adiado para 012.1.
- Q: Feature flag e rollout per-tenant? → A: **Bloco `rag: {enabled, top_k, max_upload_mb}`** em `tenants.yaml`. Default `enabled: false`. Config_poller do epic 010 re-le em <=60s sem deploy. Rollout: Ariel `disabled -> enabled` com 1 FAQ MD curto (smoke) -> ResenhAI 7d depois com catalogo PDF real. Sem shadow mode (RAG ligado = tool disponivel; LLM escolhe).
- Q: Tool toggle por agente? → A: Quando `rag.enabled=true` no tenant, admin tem **toggle per-agente** (UI epic 008 endpoint existente) para adicionar `search_knowledge` em `tools_enabled`. Nem todo agente do tenant precisa usar RAG (ex.: agente de onboarding pode nao precisar).
- Q: Comportamento em downtime? → A: **Bifrost /embeddings down em upload**: falha com erro claro (HTTP 503). **OpenAI rate-limit via Bifrost**: retry exponencial 3x. **Retrieval em runtime down**: tool retorna `[]` (lista vazia) + log warning — agente responde sem contexto ao inves de quebrar pipeline (graceful degradation).
- Q: LGPD / SAR? → A: SAR existing endpoint (ADR-018) **estendido** para listar `documents` do tenant. `DELETE /admin/knowledge/documents/{id}` faz cascade DB (`ON DELETE CASCADE` em chunks) + DELETE Supabase Storage. Cross-tenant embedding **explicitamente proibido via RLS** em `knowledge_chunks` + `documents`.
- Q: Observabilidade? → A: Tool execucao vira span OTel `rag.search` com atributos `rag.query_tokens`, `rag.chunks_returned`, `rag.distance_top1`, `rag.cost_usd`. Aparece no Trace Explorer do epic 008. Quando tool e chamada, fato "response used RAG" marca `eval_scores.details.rag_used=true` (epic 011 hook).
- Q: Surface de prompt injection nos chunks? → A: Chunks retornados podem conter instrucoes injetadas (OWASP #1 RAG injection). **Safety Layer A do epic 005 valida chunks antes de envio ao LLM** (sandwich pattern). V1 confia em ADR-016 existente; hardening especifico de RAG (ex.: semantic guard) adiado para 012.1.

### Session 2026-04-26 (clarify)

> Sessao autonoma do `/speckit.clarify` cobrindo 5 gaps de impacto que escaparam da Session 2026-04-24. Decisoes tomadas com base em best-practice + escopo v1 enxuto + reversibilidade. Cada decisao e tracavel a um FR explicito abaixo.

- Q: Como `documents.source_hash` (SHA-256) e usado em v1 — integrity-check, dedup automatica per-tenant ou cross-tenant? → A: **Integrity-check apenas em v1, sem dedup automatica**. Hash e calculado no upload e armazenado para (a) verificar integridade futura (re-hash do raw em Storage = `source_hash` original — detecta corrupcao silenciosa); (b) base para feature futura de dedup-warning per-tenant ("Esse arquivo parece duplicado de `source_name=X`"). Cross-tenant dedup explicitamente proibido (privacy/RLS). Dedup automatica per-tenant rejeitada em v1: complexa (fluxo de "merge" ambiguo) por ganho marginal — replace-by-source_name ja e o contrato. Hash agora = baseline para 012.1. `pgvector_text-embedding-3-small` ja garante semantic dedup naturalmente via cosine distance no retrieval. [FR-072 novo]
- Q: Existe quota de documentos/chunks per tenant em v1? Sem limite, um tenant unico pode dominar HNSW + custos. → A: **Sim, soft limits per-tenant configuraveis em `tenants.yaml`** — default `rag.max_documents_per_tenant: 200`, `rag.max_chunks_per_tenant: 10000`. Limite atingido retorna 413 com `{error: 'tenant_quota_exceeded', current: N, limit: M, hint: 'delete old documents or contact ops'}`. Limites generosos para v1 (Ariel/ResenhAI ficam em <50 docs/<2000 chunks tipicamente); evitam abuso futuro. Override per-tenant para clientes enterprise. Hard limit absoluto `max_chunks_per_tenant <= 50000` enforced server-side independente de config (proteje HNSW perf). [FR-073 novo + extensao FR-044]
- Q: Como tratar arquivos que produzem zero chunks (vazio, PDF scanned sem texto, MD so com whitespace)? Tratamento especifico ou genericos 422? → A: **Validacao em duas camadas**: (1) tamanho bruto `size_bytes >= 1` rejeita vazios com 400 antes de qualquer processamento; (2) **apos extraction + chunking, `chunks_count == 0` rejeita com 422 `{error: 'no_chunks_extracted', source_type, hint}`** sem chamar embedder (zero custo OpenAI). Hint especifico por tipo: PDF -> "PDF parece scanned (sem texto extraivel); OCR nao suportado em v1"; MD/TXT -> "Arquivo parece vazio ou so whitespace"; minimum tokens `MIN_CHUNK_TOKENS=10` evita chunks degenerate. Nenhum INSERT em `documents` ou Storage para conteudo vazio (rollback). [FR-074 novo + edge cases existentes ampliados]
- Q: Quando admin deleta um documento, spans de `rag.search` que referenciam seus chunks ficam orfaos. Apagar spans, manter dangling, ou mostrar "(deleted)" na UI? → A: **Spans append-only, retidos pela politica de retention do epic 002 (default 90d).** Document delete **NAO** toca spans (audit integrity). UI Trace Explorer renderiza chunk reference como `source_name: "(deleted)"` quando `JOIN documents ON document_id` retorna nulo. SAR tenant-delete cascadeia spans via filtro `tenant_id` (pattern existente epic 002 retention). Justificativa: deletar spans seria perda de audit + nao escala (impacto cross-table imenso); manter dangling e "the right thing" — usuario que deletou doc e quem assume a perda de contexto historico de trace. [FR-075 novo + extensao FR-067]
- Q: Per-tenant uploads/deletes geram audit trail para compliance — log estruturado e suficiente ou precisa tabela `audit_log`? → A: **Logs estruturados (structlog) com schema canonico sao suficientes em v1**, sem tabela `audit_log` dedicada. Eventos `knowledge_document_uploaded`, `knowledge_document_deleted`, `knowledge_document_downloaded` (signed URL emitida), `knowledge_search_executed` com campos obrigatorios `tenant_id`, `actor_user_id`, `document_id`, `source_name`, `action_result` (success/failed), `timestamp`, `request_id` para correlacao. Trade-off: query/agregacao via stack de logs (Datadog/Loki/etc) — sem JOIN SQL com outras tabelas. Tabela dedicada promove ao 012.1 SE LGPD/auditoria externa exigir export estruturado em SQL ou retencao especifica diferente da retencao geral de logs. Cross-tenant access (FR-068) ja seguia este pattern; v1 amplia para per-tenant. [FR-076 novo]

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Tenant operator faz upload de FAQ em PDF e admin ve chunks indexados (Priority: P1)

Operator do tenant **Ariel** (ou Pace ops representando o tenant) abre a aba **"Base de Conhecimento"** no admin do ProsaUAI, clica em "Adicionar documento", arrasta o arquivo `faq.pdf` (3MB) para a zona de drop. UI mostra spinner ~10s. Quando termina, tabela atualiza com nova linha: `source_name=faq.pdf, source_type=pdf, chunks_count=42, size=3.0MB, uploaded_at=now`. Admin pode ver via "Download original" o PDF intacto e via "Detalhes" os primeiros 3 chunks indexados.

**Why this priority**: e a **porta de entrada** do epic. Sem upload funcional, o KB nao tem dados, o tool retorna `[]`, e nada do resto do epic entrega valor. Todos os outros user stories pressupoem que documentos foram corretamente extraidos, chunkados, embedados e persistidos. Sem esta historia, o epic nao existe.

**Independent Test**: em staging, autenticado como admin Pace, abrir "Base de Conhecimento" do tenant Ariel, fazer upload de um MD curto (~5 KB) com 3 secoes `##`. Verificar (a) HTTP 201 com `{document_id, chunks_created: 3, total_tokens: ~600, cost_usd: ~0.00001}`; (b) tabela admin mostra nova linha; (c) `SELECT count(*) FROM knowledge_chunks WHERE tenant_id=ariel.id` retorna 3; (d) Supabase Storage `knowledge/{ariel_id}/{document_id}.md` existe; (e) `documents.embedding_model='text-embedding-3-small'`.

**Acceptance Scenarios**:

1. **Given** tenant Ariel com `rag.enabled=true` e admin autenticado, **When** upload `faq.md` (5KB, 3 secoes `##`), **Then** API responde 201 em <15s com `{document_id, chunks_created: 3, total_tokens, cost_usd}`; chunker MD-aware criou exatamente 1 chunk por secao `##`; cada chunk tem `embedding_model='text-embedding-3-small'`, `embedding VECTOR(1536) NOT NULL`, `tenant_id=ariel.id`, `agent_id=NULL` (shared default), `chunk_index=0..2`.
2. **Given** mesmo tenant, **When** upload `catalog.pdf` (3MB, 12 paginas), **Then** PyMuPDF extrai texto, chunker fixed-size 512 tokens + 50 overlap produz ~30 chunks, embedder Bifrost retorna 1536-dim vectors, transaction commit atomico em <30s, `documents.chunks_count` reflete o numero real.
3. **Given** upload bem-sucedido, **When** admin clica "Download original" na linha da tabela, **Then** API redireciona para signed URL Supabase Storage com TTL 5min; arquivo baixado e byte-identico ao enviado.
4. **Given** tenant com `rag.enabled=false`, **When** chamada a `POST /admin/knowledge/documents` mesmo via curl/admin, **Then** API responde 403 Forbidden com `{error: 'rag_not_enabled_for_tenant'}` — feature flag respeitada server-side.
5. **Given** arquivo >10MB enviado, **When** request chega, **Then** API responde 413 Payload Too Large com `{error: 'max_upload_mb_exceeded', limit_mb: 10}`. UI mostra mensagem antes mesmo de enviar (validacao client-side).
6. **Given** formato nao suportado (`.docx`, `.html`, `.epub`), **When** upload, **Then** API responde 415 Unsupported Media Type com `{error: 'unsupported_format', accepted: ['md','txt','pdf']}`.
7. **Given** Bifrost `/v1/embeddings` indisponivel (circuit breaker aberto ou OpenAI rate-limited apos 3 retries), **When** upload, **Then** API responde 503 Service Unavailable com `{error: 'embeddings_provider_down'}`; **nenhuma** linha de `documents` ou `knowledge_chunks` foi inserida (transaction rollback); **nenhum** arquivo persiste em Supabase Storage (rollback Storage upload tambem).

---

### User Story 2 — Agente usa tool `search_knowledge` e responde com contexto do tenant (Priority: P1)

Cliente da comunidade ResenhAI manda mensagem via WhatsApp: "qual o horario do treino de quarta?". Agente do ResenhAI (com `tools_enabled=['search_knowledge']` e `rag.enabled=true` no tenant) recebe inbound. Pipeline executa step `agent.generate`: LLM (gpt-5.4-mini via Bifrost) decide chamar `search_knowledge(query='horario treino quarta', top_k=5)`. Tool roda SELECT cosine distance no `knowledge_chunks` filtrado por `tenant_id=resenhai.id` e retorna top 5 chunks com texto + distance. LLM compoe resposta final citando o chunk relevante: "Os treinos de quarta sao das 19h as 21h, segundo o regulamento da comunidade." Cliente recebe via WhatsApp em <5s p95.

**Why this priority**: e o **valor user-facing** do epic. Sem isso, o KB e dado morto. North Star (resolucao autonoma 70%) nao sobe sem agente ter contexto. P1 paralelo ao US-1 — ambos sao mandatorios para entregar qualquer valor; sem upload o tool nao tem dados, sem tool o upload nao da fruto.

**Independent Test**: em staging com Ariel ja com 1 documento de FAQ uploaded (resultado do US-1), agente Ariel com `tools_enabled=['search_knowledge']`. Enviar mensagem do cliente "qual o horario de funcionamento?". Verificar via Trace Explorer (epic 008): (a) span `agent.generate` contem subspan `tool_call.search_knowledge` com `query`, `top_k=5`; (b) subspan `rag.search` mostra `chunks_returned=5`, `distance_top1<0.4`; (c) resposta final do agente cita literalmente trecho do FAQ. Verificar SQL: `SELECT * FROM knowledge_chunks WHERE tenant_id=ariel.id AND embedding <=> $query LIMIT 5` retorna mesmos chunks.

**Acceptance Scenarios**:

1. **Given** tenant Ariel com 1 documento uploaded e agente com `tools_enabled=['search_knowledge']`, **When** cliente manda mensagem que requer contexto do KB, **Then** LLM decide chamar a tool, executor roda SELECT com cosine distance ordenado, retorna lista de 5 chunks com `{text, source_name, source_type, distance, document_id}` no formato esperado pelo function calling.
2. **Given** tool e chamada, **When** roda no executor, **Then** `tenant_id` e injetado **server-side** via pydantic-ai deps (NUNCA confiando no LLM). Query SQL inclui clausula `WHERE tenant_id=$1` mesmo se LLM tentar passar `tenant_id` no input. Cross-tenant query retorna zero por RLS + injection.
3. **Given** resposta da tool, **When** chunks sao concatenados no contexto do LLM, **Then** Safety Layer A (epic 005) valida cada chunk via regex/heuristica antes do envio ao LLM (mitigacao OWASP #1 RAG injection). Chunk reprovado e descartado com log `rag_chunk_rejected`.
4. **Given** Bifrost `/v1/embeddings` indisponivel em runtime (circuit breaker aberto), **When** tool e chamada, **Then** tool retorna `[]` (lista vazia) + log estruturado `rag_embedder_unavailable` em level WARN; agente responde sem contexto do KB ao inves de quebrar pipeline (graceful degradation).
5. **Given** tenant com `rag.enabled=false` ou agente sem `search_knowledge` em `tools_enabled`, **When** mensagem chega, **Then** tool **nao aparece** no schema de tools enviado ao LLM; LLM nao tenta chamar; comportamento identico ao pre-epic.
6. **Given** agente com `agent_id=X` e tenant com chunks de `agent_id=NULL` (shared) + chunks de `agent_id=X` (especificos), **When** tool roda, **Then** SELECT inclui `WHERE agent_id IS NULL OR agent_id=$X` — agente ve seus proprios chunks + os shared. Chunks de outros agentes do mesmo tenant nao aparecem.
7. **Given** zero documentos uploaded para o tenant, **When** tool e chamada, **Then** retorna `[]` + log `rag_kb_empty`; LLM responde sem contexto de forma apropriada.
8. **Given** tool execucao bem-sucedida, **When** trace persiste, **Then** span `rag.search` contem atributos `rag.query_tokens`, `rag.chunks_returned`, `rag.distance_top1`, `rag.cost_usd`; aparece no Trace Explorer do epic 008.
9. **Given** tool foi chamada, **When** epic 011 (em curso) computa `eval_scores`, **Then** `eval_scores.details.rag_used=true` para a mensagem; permite correlacionar RAG vs quality score.

---

### User Story 3 — Admin lista, deleta e substitui documentos do KB (Priority: P1)

Admin Pace abre "Base de Conhecimento" do tenant Ariel. Tabela renderiza com 5 documentos (`faq.md`, `regulamento.pdf`, `produtos.txt`, `politicas.md`, `historia.pdf`). Admin filtra por `source_type=pdf` (badge filter), 2 linhas restam. Admin clica menu de acoes em `regulamento.pdf` -> "Excluir" -> modal de confirmacao "Esta acao remove o documento e seus 18 chunks. Confirmar?" -> click confirma. Tabela atualiza, badge sumio. Em paralelo, admin faz upload de novo `faq.md` (mesmo `source_name` de um existente) — sistema detecta replace, modal alerta "Documento existente sera substituido (atomic). Os 12 chunks atuais serao removidos e substituidos pelos novos." Admin confirma. Apos ~10s, tabela mostra `chunks_count=15` (novo) no lugar de 12 (antigo).

**Why this priority**: documentos sao mutaveis no mundo real (FAQ atualiza, catalogo muda, regulamento revisa). Sem delete + replace, o KB acumula lixo + duplicatas; tenant operator nunca confia no que o agente esta vendo. Replace by source_name (ADR-041) e contrato fundamental — versionamento adiado para 012.1, mas atomic replace e mandatorio.

**Independent Test**: em staging com Ariel ja com 3 documentos uploaded. (a) `GET /admin/knowledge/documents?tenant=ariel` retorna 3. (b) `DELETE /admin/knowledge/documents/{id_do_regulamento}` retorna 204; recheck retorna 2 documentos; verificar Supabase Storage o arquivo nao existe mais; `SELECT count(*) FROM knowledge_chunks WHERE document_id=<deleted>` retorna 0 (cascade). (c) Upload `faq.md` com mesmo `source_name` de um existente — verificar via SQL: `documents.id` mudou, antigo deletado; chunks antigos deletados; chunks novos com novo `document_id`. Tudo em uma transaction.

**Acceptance Scenarios**:

1. **Given** admin autenticado e tenant com 5 documentos, **When** `GET /admin/knowledge/documents?tenant=ariel`, **Then** API retorna lista paginada (default page_size=50) com `{document_id, source_name, source_type, chunks_count, size_bytes, uploaded_at, uploaded_by_user_id, embedding_model}` para cada documento. Tempo de resposta <500ms p95.
2. **Given** mesma lista, **When** admin filtra por `source_type=pdf` na UI, **Then** tabela renderiza so PDFs em <100ms (filtro client-side); query API support `?source_type=pdf` para filtrar server-side se necessario para datasets grandes.
3. **Given** admin clica delete em um documento, **When** confirma o modal, **Then** `DELETE /admin/knowledge/documents/{id}` executa transaction: (a) DELETE FROM Supabase Storage `knowledge/{tenant_id}/{document_id}.{ext}`, (b) DELETE FROM `knowledge_chunks WHERE document_id=$1` (cascade automatico via FK ON DELETE CASCADE), (c) DELETE FROM `documents WHERE id=$1`. API responde 204; falha em qualquer step faz rollback total.
4. **Given** admin faz upload de documento com `source_name` ja existente para o tenant, **When** request chega, **Then** sistema detecta via `UNIQUE(tenant_id, source_name)`, executa transaction atomica: (a) DELETE chunks do antigo, (b) DELETE Storage do antigo, (c) DELETE document antigo, (d) INSERT novo document, (e) INSERT chunks novos. Falha em qualquer step rollback total — tenant **nunca** fica em estado intermediario (sem chunks, com document).
5. **Given** admin tenta delete em documento de outro tenant (escopo violado), **When** request chega, **Then** RLS rejeita silenciosamente (zero rows affected) e API responde 404 Not Found — sem vazar existencia.
6. **Given** Pace ops com `pool_admin` BYPASSRLS (ADR-027), **When** lista documents cross-tenant via `GET /admin/knowledge/documents` sem filtro de tenant, **Then** retorna documentos de todos os tenants; resposta inclui `tenant_id` em cada linha; auditoria registra acesso cross-tenant em logs.
7. **Given** delete bem-sucedido, **When** existir referencia a esse documento em chunks de outros tenants (impossivel por design — `tenant_id` em ambos), **Then** RLS garante isolamento. Test invariant: cross-tenant query retorna zero.
8. **Given** SAR endpoint (ADR-018) chamado para tenant, **When** retorna dados pessoais, **Then** lista inclui documents do tenant + chunks correspondentes (cascadeia consequente). Endpoint de delete completo do tenant cascadeia documents + chunks + Storage prefix `knowledge/{tenant_id}/`.

---

### User Story 4 — Admin/operator toga RAG por agente e ve impacto no Trace Explorer (Priority: P2)

Admin abre aba **Agentes** (epic 008) do tenant ResenhAI. Para cada agente da tabela, ve coluna "RAG enabled" com toggle Switch shadcn. Para o agente `agent-aulas`, toggle esta off. Admin clica para ligar — confirmacao modal "Adicionar `search_knowledge` aos tools_enabled deste agente?" -> ok. UI atualiza. Admin envia mensagem teste pelo whatsapp simulator (epic 008), abre Trace Explorer, ve span `agent.generate` -> subspan `tool_call.search_knowledge` -> subspan `rag.search` com chunks retornados. Para um segundo agente (`agent-comercial`) com toggle off, mesma mensagem teste nao tem subspan de tool — agente respondeu so com system_prompt.

**Why this priority**: granularidade per-agente e **valor importante** para tenants com multiplos agentes. ResenhAI tem `agent-aulas`, `agent-comercial`, `agent-onboarding`; nem todos precisam de RAG (onboarding pode ser puro system_prompt). Sem isso, admin tem que escolher all-or-nothing por tenant. Mas e P2 porque o caminho default ja funciona (tenant com 1 agente = ligar tudo no tenant flag).

**Independent Test**: em staging com ResenhAI com 2 agentes e `rag.enabled=true`. (a) Toggle on no `agent-aulas` via UI -> verificar via SQL `agents.tools_enabled @> '["search_knowledge"]'`. (b) Toggle off no `agent-comercial` -> verificar `agents.tools_enabled NOT @> '["search_knowledge"]'`. (c) Pipeline com `agent-aulas`: schema de tools enviado ao LLM contem `search_knowledge`. (d) Pipeline com `agent-comercial`: schema nao contem. (e) Trace Explorer mostra span de tool so para mensagens roteadas para `agent-aulas`.

**Acceptance Scenarios**:

1. **Given** tenant com `rag.enabled=true` e 2 agentes, **When** admin abre aba Agentes, **Then** cada linha exibe coluna "RAG enabled" com Switch toggle. Estado reflete `'search_knowledge' IN agents.tools_enabled`.
2. **Given** admin toga RAG on para um agente, **When** confirma, **Then** API endpoint existing do epic 008 (`PATCH /admin/agents/{id}`) atualiza `tools_enabled` adicionando `search_knowledge` se nao existe. UI atualiza Switch visualmente.
3. **Given** admin toga RAG off para um agente, **When** confirma, **Then** mesma API remove `search_knowledge` de `tools_enabled`. Mensagens subsequentes para esse agente nao tem `search_knowledge` no schema de tools enviado ao LLM.
4. **Given** tenant com `rag.enabled=false` (feature flag global off), **When** admin abre aba Agentes, **Then** coluna "RAG enabled" mostra Switch desabilitado (greyed out) com tooltip "Habilitar RAG no tenant primeiro". Toggle nao aceita interacao.
5. **Given** agente com `search_knowledge` em `tools_enabled` mas tenant ficou com `rag.enabled=false` posteriormente, **When** mensagem chega, **Then** pipeline filtra tools por feature flag do tenant — `search_knowledge` removido do schema mesmo estando em `tools_enabled` do agente. Defesa em profundidade contra inconsistencia de config.

---

### User Story 5 — Pace ops re-embeda KB de tenant apos upgrade de modelo via CLI (Priority: P2)

Daqui a 6 meses, OpenAI lanca `text-embedding-4-small` (1536 dim mantidos, mas qualidade superior). Pace decide migrar todos os tenants. Engenheiro abre terminal, roda `python -m prosauai.rag.reembed --tenant ariel --target-model text-embedding-4-small`. CLI le todos os documentos do tenant via Supabase Storage (raw files preservados pelo upload), re-chunka, re-embeda batch via Bifrost, executa transaction atomica: DELETE chunks antigos + INSERT chunks novos + UPDATE `documents.embedding_model`. Tenant nao precisa fazer nada; agente continua respondendo durante o processo (chunks antigos servem ate o swap final).

**Why this priority**: re-embed e **operacao rara** mas critica quando acontece. Sem CLI, upgrade de modelo exige re-upload manual por todos os tenants — operacionalmente inviavel. Com Storage preservado (Q8-II decision), re-embed e transparente. P2 porque nao e usado no rollout v1; e investimento operacional que paga em 6-12 meses.

**Independent Test**: em staging com Ariel ja com 3 documentos uploaded em `text-embedding-3-small`. Rodar `python -m prosauai.rag.reembed --tenant ariel --target-model text-embedding-4-small` (mock provider para teste). Verificar (a) CLI le 3 raws do Storage; (b) re-chunka com mesma estrategia (header-aware MD, fixed-size PDF); (c) embed batch via Bifrost; (d) DELETE 75 chunks antigos + INSERT 75 chunks novos em transaction; (e) `documents.embedding_model='text-embedding-4-small'` para todos os 3; (f) tool `search_knowledge` funciona normalmente apos a operacao com novos embeddings.

**Acceptance Scenarios**:

1. **Given** tenant com N documentos em modelo X, **When** CLI `reembed --tenant {slug} --target-model Y`, **Then** CLI baixa raw de cada documento do Supabase Storage, re-chunka, re-embeda em batch (ate 100 textos por call Bifrost), executa transaction atomica por documento (DELETE chunks + INSERT chunks + UPDATE documents.embedding_model).
2. **Given** mesma operacao, **When** roda, **Then** tenant continua respondendo via tool `search_knowledge` durante todo o processo — operacao por documento e atomica, mas nao bloqueia leitura de chunks de outros documentos.
3. **Given** modelo target tem dim diferente (ex.: 1536 -> 3072), **When** CLI tenta rodar, **Then** valida dim contra schema (`VECTOR(1536)` fixo em ADR-013) e aborta com erro claro `dim_mismatch` antes de tocar em qualquer dado. Migration de dim exigiria mudanca de schema (epic futuro).
4. **Given** Bifrost ou OpenAI down durante reembed, **When** falha intermitente, **Then** CLI faz retry exponencial 3x por batch; falha persistente aborta apenas o documento corrente (nao os anteriores ja completados); retry manual via `--from-document {id}` permite continuar.
5. **Given** reembed bem-sucedido, **When** tool roda apos, **Then** SELECT continua usando o mesmo `WHERE embedding_model = $tenant.current_model`. Mas como CLI atualiza `documents.embedding_model` e injeta em todas as queries, transicao e transparente.

---

### User Story 6 — Operator habilita RAG para um tenant via tenants.yaml e poller hot-reload (Priority: P2)

Pace ops decide habilitar RAG para o tenant ResenhAI. Edita `tenants.yaml`:

```yaml
tenants:
  resenhai:
    # ...config existente
    rag:
      enabled: true
      top_k: 5
      max_upload_mb: 10
```

Commita e da deploy. Em <=60s, config_poller (epic 010) re-le o YAML em todas as replicas; nenhum restart necessario. A partir desse instante: (a) endpoint `POST /admin/knowledge/documents?tenant=resenhai` aceita uploads (antes retornava 403); (b) toggle "RAG enabled" no admin Agentes vira interativo; (c) qualquer agente com `search_knowledge` em `tools_enabled` passa a ter a tool no schema do LLM. Reverter e setar `enabled: false` e esperar 60s — toda funcionalidade some sem deploy.

**Why this priority**: feature flag e **kill switch operacional**. Sem ela, ligar RAG para um tenant exige deploy + revert e migration. Com hot-reload via poller existente, o controle e <=60s e zero downtime. P2 porque o pattern ja existe (epic 010 tem o poller); o trabalho aqui e so adicionar o bloco `rag` ao schema validado.

**Independent Test**: em staging, modificar `tenants.yaml` adicionando `rag: {enabled: true}` para um tenant. Aguardar <=60s. (a) Verificar log `tenant_config_reloaded{tenant=X}`. (b) Tentar upload — sucesso (antes era 403). (c) Modificar para `enabled: false`. Aguardar <=60s. (d) Tentar upload — 403. Verificar via metric `tenant_config_reload_total` que o reload aconteceu.

**Acceptance Scenarios**:

1. **Given** tenant com bloco `rag: {enabled: false}` ou bloco ausente em `tenants.yaml`, **When** admin/curl chama `POST /admin/knowledge/documents`, **Then** API responde 403 Forbidden com `{error: 'rag_not_enabled_for_tenant', tenant: 'X'}`.
2. **Given** mudanca em `tenants.yaml` para `rag: {enabled: true, top_k: 5, max_upload_mb: 10}`, **When** config_poller (cadencia 60s) detecta delta, **Then** todas as replicas atualizam config in-memory; logs `tenant_config_reloaded{tenant}`; metric `tenant_config_reload_total` incrementa.
3. **Given** reload bem-sucedido, **When** chamada subsequente a `POST /admin/knowledge/documents`, **Then** passa a aceitar (sem 403). Mesmo para `GET /documents` que era acessivel ja como admin. Sem necessidade de restart.
4. **Given** YAML invalido (ex.: `top_k` nao numerico, `max_upload_mb` negativo), **When** poller tenta reload, **Then** rejeita com log `tenant_config_reload_failed{tenant, reason}` + metric do mesmo nome; configuracao **anterior** permanece ativa (fail-safe).
5. **Given** `rag.enabled=true` -> mudanca para `enabled=false`, **When** poller aplica em <=60s, **Then** uploads passam a retornar 403; tool `search_knowledge` removida do schema enviado ao LLM em mensagens subsequentes. Documentos e chunks ja persistidos **NAO** sao deletados (operacao de retomar e simplesmente flipar enabled de volta).

---

### User Story 7 — Bifrost roteia `/v1/embeddings` para OpenAI com mesmo rate limit + spend tracking (Priority: P3)

Bifrost (proxy/gateway interno do epic 005) hoje so roteia `/v1/chat/completions`. Epic 012 estende: arquivo de config Bifrost ganha novo provider OpenAI para `/v1/embeddings` com mesmas chaves de rate limit (`requests_per_minute`, `tokens_per_minute`) e mesmo tracking de spend (custo por chamada gravado em tabela `bifrost_spend`). Quando upload acontece, `prosauai/rag/embedder.py` faz POST para `bifrost.local/v1/embeddings` em vez de OpenAI direto. Bifrost aplica rate limit, autenticacao com API key da Pace (nao do tenant), e contabiliza custo no tenant via header `X-ProsaUAI-Tenant`.

**Why this priority**: Bifrost extension e **infra mandatoria** (sem ela, embedder seria call direto na OpenAI -> sem rate limiting + sem spend tracking + multiplas API keys ou bypass). MAS e P3 porque (a) e backend infra invisivel ao usuario; (b) o resto do epic e bloqueado por isso, mas nao e o "valor" — e o sustento. Estimativa pitch: 2-3 dias.

**Independent Test**: em staging, mockar Bifrost rodando localmente com config OpenAI embeddings. Embedder ProsaUAI chama Bifrost via httpx. Verificar (a) Bifrost recebe POST `/v1/embeddings`; (b) repassa para OpenAI (ou mock); (c) tabela `bifrost_spend` ganha linha com `tenant_id`, `provider='openai'`, `endpoint='embeddings'`, `cost_usd`, `tokens_used`; (d) rate limit 1000 req/min funciona (req 1001 retorna 429).

**Acceptance Scenarios**:

1. **Given** Bifrost rodando com config OpenAI embeddings, **When** ProsaUAI chama `bifrost.local/v1/embeddings` com `model=text-embedding-3-small`, body `{input: [text], encoding_format: 'float'}`, **Then** Bifrost roteia para OpenAI, retorna response 1:1 (vector 1536-dim), incrementa metric `bifrost_request_total{provider='openai',endpoint='embeddings'}`.
2. **Given** chamada com header `X-ProsaUAI-Tenant: ariel`, **When** Bifrost processa, **Then** registra spend em `bifrost_spend` com `tenant_id=ariel.id`, `cost_usd` calculado por `tokens_used * R$0.00002 / 1000` (alinhado ADR-012).
3. **Given** Bifrost atinge rate limit OpenAI (configurado `requests_per_minute: 3500`), **When** chamada extra chega, **Then** Bifrost responde 429 com header `Retry-After`; ProsaUAI embedder faz retry exponencial 3x antes de falhar upload.
4. **Given** OpenAI down (timeout ou 503), **When** Bifrost tenta repassar, **Then** Bifrost retorna 503 ao caller; circuit breaker abre apos 5 falhas consecutivas em 60s; metric `bifrost_breaker_open{provider='openai'}` emitida.
5. **Given** chamada inicial bem-sucedida, **When** Bifrost grava spend, **Then** `bifrost_spend` tem novo registro acessivel via admin Pace (cross-tenant) para visibilidade de custo de embedding por tenant.

---

### Edge Cases

- **PDF scanned (image-only, sem texto extraivel)**: PyMuPDF retorna texto vazio. Sistema detecta apos extraction e retorna 422 Unprocessable Entity com `{error: 'pdf_no_extractable_text', hint: 'OCR not supported in v1'}`. OCR adiado para 012.1.
- **PDF criptografado / com password**: PyMuPDF levanta exception. Sistema captura, retorna 422 com `{error: 'pdf_encrypted'}`.
- **Upload concorrente do mesmo `source_name`**: `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))` serializa. Segundo upload espera o primeiro completar; nenhum estado intermediario.
- **Document gigante (~10MB de Markdown / >2000 chunks)**: chunker atinge limite, sistema rejeita com 413 antes de tentar embed. Hard limit `max_chunks_per_document=2000` para evitar custo descontrolado de embedding.
- **Embedding parcialmente falho (50% dos chunks embedados, 50% timeout)**: transaction rollback total — nenhum chunk inserido, Storage limpo. Tenant ve "embeddings_provider_unavailable" e tenta novamente.
- **Tenant exclui documento, agente em meio a uma execucao de tool**: tool ja tem chunks em memoria do executor; resposta corrente usa chunks "obsoletos". Aceito — proxima mensagem ja nao verao. Sem garantia transacional cross-request (overengineering).
- **Storage URL signed expira durante download**: TTL 5min cobre 99% dos casos. Falha rara, admin recarrega listagem.
- **Cross-tenant leak via tool input manipulation**: LLM **nao** tem acesso ao parametro `tenant_id`. Apenas `query` e `top_k`. Server-side injection via pydantic-ai deps. Test: payload malicioso `{query: "DROP TABLE...", top_k: 5}` falha porque `query` e parameterizado em SQL e nao tem semantica especial.
- **HNSW index sem `ANALYZE` apos massive insert**: `ANALYZE knowledge_chunks` em nightly cron (reuso do retention-cron do epic 006). Garante query planner usa o index.
- **`agent_id` toggle muda no meio da operacao**: tool snapshot ja foi composto. Aceito — proxima mensagem ja respeita.
- **Upload com BOM UTF-8 ou encoding misto**: extractor normaliza para UTF-8 strict; bytes invalidos sao discarded com log warning. Texto resultante e usado.
- **Markdown com tabela ou code block enorme atravessando chunks**: chunker MD-aware respeita boundaries de header (`##`/`###`). Tabela/code block dentro de uma secao fica inteira em 1 chunk se cabe; senao, fixed-size split com overlap. Aceito perda de contexto em casos extremos.
- **Limite de `top_k` muito alto (ex.: usuario configura 50)**: API valida `top_k` <= 20 (hard cap server-side); valores acima clampa para 20. Evita custo + ruido excessivo.
- **Concurrent upload por 2 admins no mesmo tenant**: ambos podem subir docs paralelos com source_names diferentes. Quando colidem em `source_name`, advisory lock serializa.
- **Bug Bifrost-side perde `X-ProsaUAI-Tenant` header**: Bifrost falha-fechado (rejeita request). Sem header = sem cobranca = bug; falhar e melhor que faturar errado.
- **Upload de arquivo 0 bytes ou so whitespace** (Session 2026-04-26): rejeitado em duas camadas — (1) `size_bytes < 1` -> 400 `{error: 'empty_file'}` antes de qualquer processamento; (2) apos extraction + chunking, `chunks_count == 0` -> 422 `{error: 'no_chunks_extracted'}` antes de chamar embedder (custo OpenAI zero). Hint especifico por tipo: PDF scanned, MD/TXT vazio.
- **Upload faz tenant exceder quota de documents ou chunks** (Session 2026-04-26): retorna 413 `{error: 'tenant_quota_exceeded', dimension: 'documents'|'chunks', current, limit, hint}` antes do embed. Replace por `source_name` deduz chunks antigos do calculo (atomic: nao bloqueia replace por chegar no limite). Override per-tenant em `tenants.yaml` resolve. Hard cap absoluto 50000 chunks/tenant aplica mesmo com override (proteje HNSW).
- **Document deletado deixa spans `rag.search` historicos com `document_id` orfao** (Session 2026-04-26): comportamento esperado — spans sao append-only (audit). Trace Explorer renderiza `source_name = "(deleted)"` quando JOIN nulo. Spans seguem retention do epic 002 (default 90d). Sem FK enforcement entre spans e documents (cross-table cascade nao escala).
- **Storage corrupcao silenciosa (raw file alterado fora de banda)** (Session 2026-04-26): detectado em re-embed CLI (US-5) ou cron de integrity-check (futuro) — re-hash do Storage compara com `documents.source_hash`; mismatch loga `knowledge_document_integrity_violation` + alerta ops. Nao quebra runtime (tool continua funcionando com chunks ja persistidos).

## Requirements *(mandatory)*

### Functional Requirements

#### Schema (data model)

- **FR-001**: Sistema MUST criar nova tabela `documents` em schema `prosauai` com colunas: `id UUID PK DEFAULT gen_random_uuid()`, `tenant_id UUID NOT NULL REFERENCES tenants(id)`, `source_name TEXT NOT NULL`, `source_hash TEXT NOT NULL`, `source_type TEXT NOT NULL CHECK (source_type IN ('md','txt','pdf'))`, `storage_path TEXT NOT NULL`, `size_bytes BIGINT NOT NULL`, `uploaded_by_user_id UUID NULL`, `uploaded_at TIMESTAMPTZ NOT NULL DEFAULT now()`, `chunks_count INT NOT NULL DEFAULT 0`, `embedding_model TEXT NOT NULL`, `UNIQUE(tenant_id, source_name)`.
- **FR-002**: Sistema MUST criar tabela `knowledge_chunks` (alinhada com ADR-013, expandida): `id UUID PK`, `tenant_id UUID NOT NULL`, `agent_id UUID NULL` (NULL = shared, valor = especifico daquele agente), `document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE`, `chunk_index INT NOT NULL`, `content TEXT NOT NULL`, `tokens INT NOT NULL`, `embedding VECTOR(1536) NOT NULL`, `embedding_model TEXT NOT NULL`, `metadata JSONB NOT NULL DEFAULT '{}'::jsonb`, `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`.
- **FR-003**: Sistema MUST criar HNSW index `CREATE INDEX knowledge_chunks_embedding_hnsw_idx ON knowledge_chunks USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);` (alinhado ADR-013).
- **FR-004**: Sistema MUST criar indices secundarios: `(tenant_id, agent_id)` em `knowledge_chunks`, `(document_id, chunk_index)` em `knowledge_chunks`, `(tenant_id, uploaded_at DESC)` em `documents`.
- **FR-005**: Ambas as tabelas MUST ter RLS ativo com policy `tenant_isolation` (alinhada ADR-011). Nenhuma query sem `WHERE tenant_id=$current_setting('app.tenant_id')` retorna linhas.
- **FR-006**: Sistema MUST habilitar extension pgvector no Supabase via SQL `CREATE EXTENSION IF NOT EXISTS vector;` antes de aplicar migrations. Operacao manual via Supabase SQL editor (uma vez).

#### Supabase Storage

- **FR-007**: Sistema MUST criar bucket `knowledge` no Supabase Storage com policy de leitura/escrita restrita ao service-role da Pace (admin API). Path convention: `knowledge/{tenant_id}/{document_id}.{ext}`.
- **FR-008**: Upload bem-sucedido MUST persistir o arquivo raw em Storage **antes** do INSERT em `documents`. Falha de upload Storage rollback toda a transaction (sem registro DB orfao).
- **FR-009**: Delete de documento MUST cascadear: (a) DELETE Storage `knowledge/{tenant_id}/{document_id}.{ext}`, (b) DELETE `documents WHERE id=$1` (chunks via FK CASCADE). Falha em qualquer step rollback total.
- **FR-010**: SAR delete de tenant (ADR-018) MUST cascadear: DELETE Storage prefix `knowledge/{tenant_id}/`, DELETE all `documents WHERE tenant_id=$1` (chunks cascadeiam).

#### Document upload (admin API)

- **FR-011**: Sistema MUST expor endpoint `POST /admin/knowledge/documents` com `multipart/form-data` body containing `tenant_id` (UUID, query param ou form field) + `file` (binary). Auth via JWT admin (mesmo middleware do epic 008). Retorna 201 com `{document_id, source_name, source_type, chunks_created, total_tokens, cost_usd, embedding_model}`.
- **FR-012**: Endpoint MUST validar formato (`md`, `txt`, `pdf` apenas) — rejeita 415 outros.
- **FR-013**: Endpoint MUST validar tamanho `1 <= size_bytes <= rag.max_upload_mb` (default 10MB upper) — rejeita 400 `{error: 'empty_file'}` se 0 bytes; rejeita 413 `{error: 'max_upload_mb_exceeded'}` se acima do upper.
- **FR-014**: Endpoint MUST validar `rag.enabled=true` no tenant — rejeita 403 se desabilitado.
- **FR-015**: Endpoint MUST executar transaction atomic-replace por `source_name`: se ja existe `documents WHERE tenant_id=$1 AND source_name=$2`, primeiro DELETE chunks + DELETE Storage + DELETE document antigo, depois INSERT document novo + chunks novos. Tudo em uma transaction. Falha em qualquer step rollback total (DB + Storage).
- **FR-016**: Endpoint MUST usar `pg_advisory_xact_lock(hashtext('doc:{tenant_id}:{source_name}'))` para serializar uploads concorrentes do mesmo `source_name`.
- **FR-017**: Endpoint MUST responder em <=15s p95 para arquivos <=10MB (chunk count tipico <=200 + embedding paralelo). Response inline (sync); >10MB ja foi rejeitado pelo FR-013.

#### Document management

- **FR-018**: Sistema MUST expor `GET /admin/knowledge/documents` com query params `?tenant_id=<id>` (mandatory para non-Pace-ops; opcional para Pace ops cross-tenant), `?source_type=md|txt|pdf`, `?page=1`, `?page_size=50`. Retorna lista paginada.
- **FR-019**: Sistema MUST expor `DELETE /admin/knowledge/documents/{id}` que executa cascade FR-009 e responde 204. Cross-tenant proibido por RLS (responde 404 se tentado).
- **FR-020**: Sistema MUST expor `GET /admin/knowledge/documents/{id}/raw` que retorna 302 Redirect para signed URL Supabase Storage com TTL 5min. Permite download original sem proxy server-side.
- **FR-021**: Sistema MUST expor `GET /admin/knowledge/documents/{id}/chunks?limit=10` para preview. Retorna lista de chunks (text, chunk_index, tokens) — usado pela UI para mostrar "primeiros 3 chunks" no detalhe.

#### Chunking

- **FR-022**: Sistema MUST implementar chunker MD-aware (`prosauai/rag/chunker.py`): para `.md`, identifica headers `#`, `##`, `###` e cria 1 chunk por secao. Texto antes do primeiro header (preamble) e seu proprio chunk.
- **FR-023**: Para `.txt` e `.pdf` (apos extraction), chunker MUST usar fixed-size 512 tokens com overlap 50 tokens. Token count via tiktoken (cl100k_base, alinhado com modelo OpenAI).
- **FR-024**: Chunker MUST limitar `max_chunks_per_document=2000` — documentos que produzem mais sao rejeitados pelo upload com 413 + log.
- **FR-025**: Chunker MUST ser stdlib-only + tiktoken (ja dependencia do epic 005), <100 LOC funcional.

#### Embedding

- **FR-026**: Sistema MUST implementar embedder (`prosauai/rag/embedder.py`) que faz POST para `bifrost.local/v1/embeddings` com `model=text-embedding-3-small`, body `{input: [batch_de_textos], encoding_format: 'float'}`, header `X-ProsaUAI-Tenant: {slug}`.
- **FR-027**: Embedder MUST agrupar em batch de ate 100 textos por chamada Bifrost (limite OpenAI batch API).
- **FR-028**: Embedder MUST aplicar retry exponencial 3x em falhas transientes (429, 503, timeout); falha persistente propaga exception (rollback transaction upload).
- **FR-029**: Embedder MUST emitir span OTel `rag.embed` com atributos `embed.batch_size`, `embed.tokens_total`, `embed.cost_usd`, `embed.model`.

#### Bifrost extension

- **FR-030**: Bifrost MUST aceitar requests para `/v1/embeddings` com mesmo schema OpenAI API.
- **FR-031**: Bifrost MUST aplicar rate limit OpenAI configurado (default 3500 req/min, alinhado plano corporativo). Em rate limit retorna 429 com header `Retry-After`.
- **FR-032**: Bifrost MUST gravar `bifrost_spend` (tabela existente do epic 005, estendida) com `endpoint='embeddings'`, `provider='openai'`, `tenant_id`, `tokens_used`, `cost_usd`, `created_at`.
- **FR-033**: Bifrost MUST circuit breaker per-provider: 5 falhas em 60s -> aberto 30s -> meia-aberto -> 1 sucesso fecha.

#### Search tool (`search_knowledge`)

- **FR-034**: Sistema MUST registrar tool `search_knowledge` em `prosauai/tools/registry.py` com schema pydantic `SearchKnowledgeInput(query: str, top_k: int = 5)`. `top_k` MUST ser clampado a max 20 server-side.
- **FR-035**: Tool MUST executar SELECT cosine distance: `SELECT id, content, document_id, embedding <=> $query_vector AS distance FROM knowledge_chunks WHERE tenant_id=$1 AND (agent_id IS NULL OR agent_id=$2) AND embedding_model=$3 ORDER BY distance LIMIT $4`. Server-side injection de `tenant_id`, `agent_id`, `embedding_model` via pydantic-ai deps; LLM **nunca** controla esses campos.
- **FR-036**: Tool MUST retornar lista de chunks no formato `[{text, source_name, source_type, distance, document_id}]` para o LLM.
- **FR-037**: Tool MUST embedar a query do LLM via embedder (FR-026) com mesmo `model` do tenant — total roundtrip <=2s p95 (1 call Bifrost embed + 1 query SQL).
- **FR-038**: Tool MUST graceful degradation: se embedder retorna erro (Bifrost down, etc), tool retorna `[]` + log warning `rag_embedder_unavailable`. Pipeline nao quebra; agente responde sem contexto.
- **FR-039**: Tool MUST emitir span OTel `rag.search` com atributos `rag.query_tokens`, `rag.chunks_returned`, `rag.distance_top1`, `rag.cost_usd`.
- **FR-040**: Cada chunk retornado MUST passar por Safety Layer A do epic 005 (regex/heuristica anti-prompt-injection) antes de envio ao LLM. Chunk reprovado e descartado com log `rag_chunk_rejected`.

#### Pipeline integration

- **FR-041**: Pipeline step `agent.generate` MUST montar schema de tools dinamicamente: para cada tool em `agents.tools_enabled`, busca em `tools/registry.py`. Se tool nao existe ou `tenant.rag.enabled=false`, **filtra** (defesa em profundidade — nao confiar so no admin).
- **FR-042**: Pipeline MUST suportar function calling do LLM (pydantic-ai ja suporta nativamente). Tool execucao roda no executor com `tenant_id`/`agent_id` injetados via deps.
- **FR-043**: Quando tool e chamada, eval scoring (epic 011) MUST receber sinal `details.rag_used=true` para a mensagem.

#### Per-tenant feature flag

- **FR-044**: `tenants.yaml` schema MUST aceitar bloco `rag: {enabled: bool, top_k: int, max_upload_mb: int, max_documents_per_tenant: int, max_chunks_per_tenant: int, min_distance_threshold: float?}`. Default: `enabled: false`. `top_k` default 5 (range 1..20). `max_upload_mb` default 10 (range 1..50). `max_documents_per_tenant` default 200 (range 1..1000). `max_chunks_per_tenant` default 10000 (range 100..50000). Hard cap absoluto server-side: `max_chunks_per_tenant <= 50000` mesmo via override (proteje HNSW perf).
- **FR-045**: Config_poller (epic 010) MUST detectar mudancas em <=60s e atualizar config in-memory em todas as replicas. Sem deploy/restart necessarios.
- **FR-046**: Config invalida (ex.: `top_k` fora de range) MUST ser rejeitada pelo poller com log `tenant_config_reload_failed{tenant, reason}`. Configuracao **anterior** permanece (fail-safe).
- **FR-047**: Default `enabled: false` MUST garantir que tenants sem o bloco continuem com comportamento pre-epic — feature opt-in.

#### Per-agent toggle

- **FR-048**: Admin endpoint do epic 008 (`PATCH /admin/agents/{id}`) MUST aceitar mudancas em `tools_enabled` (array de strings). Valores validos sao chaves do `tools/registry.py`.
- **FR-049**: Admin UI (aba Agentes) MUST exibir Switch shadcn por agente para `search_knowledge`. Estado on/off reflete `'search_knowledge' IN agents.tools_enabled`.
- **FR-050**: Switch MUST estar greyed out (desabilitado) quando `tenant.rag.enabled=false`. Tooltip explica "Habilitar RAG no tenant primeiro".

#### Admin UI — aba "Base de Conhecimento"

- **FR-051**: Sidebar admin (epic 008) MUST adicionar nova entry "Base de Conhecimento" com icon `BookOpen` (lucide). Rota `/admin/knowledge`.
- **FR-052**: Pagina lista MUST exibir tabela shadcn Table com colunas: `source_name`, `source_type` (badge colorido), `chunks_count`, `size` (formatado MB/KB), `uploaded_at` (relativo), actions menu (Download original, Excluir, Ver detalhes).
- **FR-053**: Pagina MUST suportar filtros client-side por `source_type` e search por `source_name`. Para datasets >100 docs, query API com params (server-side filtering) — paginacao 50/pagina default.
- **FR-054**: "Adicionar documento" MUST abrir Dialog shadcn com drag-drop zone + file picker. Validacao client-side de formato e size antes do envio. Progress spinner durante upload. Resposta inline com `chunks_created` + cost.
- **FR-055**: Click em linha MUST abrir Sheet shadcn com detalhes: metadata + lista dos primeiros 10 chunks (via FR-021).
- **FR-056**: Delete MUST abrir AlertDialog confirm "Esta acao remove o documento e seus N chunks. Confirmar?". Apos confirm, atualiza tabela em <2s.
- **FR-057**: Replace (upload com `source_name` existente) MUST abrir AlertDialog warning "Documento existente sera substituido. Os N chunks atuais serao removidos." Apos confirm, prosegue.

#### Re-embedding CLI

- **FR-058**: Sistema MUST prover CLI `python -m prosauai.rag.reembed --tenant {slug} --target-model {model}`. CLI le todos os documentos do tenant via Storage, re-chunka, re-embeda em batch, executa transaction atomica por documento.
- **FR-059**: CLI MUST validar dim do target model contra schema (`VECTOR(1536)` fixo). Mismatch aborta antes de tocar dados.
- **FR-060**: CLI MUST suportar `--from-document {id}` para retomar apos falha parcial.
- **FR-061**: CLI MUST atualizar `documents.embedding_model` apos completar re-embed por documento.

#### Observabilidade

- **FR-062**: `tenant_id`, `agent_id`, `document_id` MUST ser propagados em OpenTelemetry baggage da request inbound do upload ate o INSERT em `knowledge_chunks`.
- **FR-063**: Sistema MUST expor metricas Prometheus: `rag_documents_uploaded_total{tenant, source_type}`, `rag_chunks_total{tenant}`, `rag_search_invocations_total{tenant}`, `rag_search_duration_seconds_bucket{tenant}`, `rag_embedder_failures_total{provider, reason}`.
- **FR-064**: Logs MUST ser estruturados (structlog) com campos: `tenant_id`, `agent_id` (quando aplicavel), `document_id`, `event_type`, `chunks_count`, `tokens`, `cost_usd`.
- **FR-065**: Trace Explorer (epic 008) MUST renderizar spans `rag.search`, `rag.embed`, `tool_call.search_knowledge` com atributos completos.

#### LGPD / Privacy

- **FR-066**: Endpoint SAR existente (ADR-018) MUST ser estendido para listar documents do tenant. Cross-tenant embedding **proibido via RLS** + injection server-side.
- **FR-067**: SAR delete cascade MUST incluir DELETE Storage prefix `knowledge/{tenant_id}/` + DELETE all `documents WHERE tenant_id=$1` (chunks via cascade).
- **FR-068**: Admin Pace cross-tenant (`pool_admin` BYPASSRLS) MUST registrar acesso em audit log estruturado quando lista documents/chunks fora do tenant proprio.

#### Defesas (security)

- **FR-069**: Tool `search_knowledge` MUST injetar `tenant_id` e `agent_id` server-side via pydantic-ai deps. LLM input restrito a `query` + `top_k`.
- **FR-070**: SQL queries MUST usar parameter binding (asyncpg `$1, $2, ...`). Nenhum string interpolation. Defesa contra injection mesmo sob input adversarial via LLM.
- **FR-071**: Cada chunk retornado pela tool MUST passar por Safety Layer A (epic 005) antes do envio ao LLM. Chunks reprovados sao descartados.

#### Document integrity, quotas, audit (Session 2026-04-26)

- **FR-072**: `documents.source_hash` MUST ser SHA-256 do raw file calculado no upload e gravado junto da row. Em v1 e usado apenas para **integrity-check** (futuras CLIs / cron de verificacao podem re-hash do Storage e comparar). **Nao ha dedup automatica** em v1 — upload com mesmo hash mas `source_name` diferente cria documento separado normalmente. Cross-tenant dedup explicitamente proibido (privacy/RLS). Feature de "warning de duplicado" per-tenant adiada para 012.1.
- **FR-073**: Endpoint upload MUST validar quotas per-tenant antes de processar:
  - `(SELECT count(*) FROM documents WHERE tenant_id=$1) < tenant.rag.max_documents_per_tenant`
  - `(SELECT coalesce(sum(chunks_count),0) FROM documents WHERE tenant_id=$1) + estimated_chunks <= tenant.rag.max_chunks_per_tenant`
  Estouro retorna 413 `{error: 'tenant_quota_exceeded', dimension: 'documents'|'chunks', current, limit, hint: 'delete old documents or contact ops to raise quota'}`. Replace por `source_name` deduz chunks antigos do calculo (subtract-then-add).
- **FR-074**: Endpoint upload MUST rejeitar conteudo zero apos extraction + chunking (antes de chamar embedder, custo zero):
  - `chunks_count == 0` apos chunker -> 422 `{error: 'no_chunks_extracted', source_type, hint}` com hint especifico por tipo (PDF: "PDF parece scanned; OCR nao suportado em v1"; MD/TXT: "arquivo parece vazio ou so whitespace").
  - `MIN_CHUNK_TOKENS=10` enforced no chunker — chunks com <10 tokens sao mergeados ao chunk vizinho ou descartados. Documento que produz **so** chunks <10 tokens dispara o mesmo 422.
  Nenhum INSERT em `documents` ou Storage para conteudo vazio (rollback).
- **FR-075**: Document delete (FR-019) e replace (FR-015) **NAO** apagam spans `rag.search` historicos. Spans sao append-only e seguem politica de retention do epic 002 (default 90d). Trace Explorer (epic 008) MUST renderizar `source_name = "(deleted)"` quando `JOIN documents ON document_id` retorna nulo, preservando audit integrity. SAR tenant-delete (FR-067) cascadeia spans via filtro `tenant_id` (pattern existente epic 002 retention) — **nao** via FK.
- **FR-076**: Cada operacao de upload/delete/download/search MUST emitir log estruturado (structlog) com schema canonico:
  - `event_type IN ('knowledge_document_uploaded', 'knowledge_document_deleted', 'knowledge_document_downloaded', 'knowledge_search_executed', 'knowledge_document_replace_detected')`
  - Campos obrigatorios: `tenant_id`, `actor_user_id` (nullable se Pace ops via service-role), `document_id` (quando aplicavel), `source_name`, `action_result IN ('success','failed','rejected')`, `timestamp`, `request_id` (correlation).
  - Campos opcionais por evento: `chunks_count`, `tokens`, `cost_usd`, `failure_reason`.
  - Sem tabela `audit_log` dedicada em v1 — query via stack de logs (estrutura canonica permite filtro/agregacao). Tabela dedicada promove ao 012.1 SE compliance externa exigir export SQL ou retention diferente.

### Key Entities

- **Document**: nova entidade. Representa um arquivo raw uploaded por tenant. Atributos: `id`, `tenant_id`, `source_name` (nome logico, unique by tenant), `source_hash` (SHA-256 do raw — uso v1: **integrity-check apenas, sem dedup automatica**, ver FR-072), `source_type` (md/txt/pdf), `storage_path` (Supabase Storage), `size_bytes` (>=1 enforced), `uploaded_by_user_id` (nullable se admin Pace via service-role), `uploaded_at`, `chunks_count` (>=1 enforced apos chunking), `embedding_model`. Replace by `source_name` (atomic).
- **KnowledgeChunk**: alinhado ADR-013 + expandido. Representa um trecho indexado para retrieval. Atributos: `id`, `tenant_id`, `agent_id` (opcional), `document_id` (FK CASCADE), `chunk_index`, `content`, `tokens`, `embedding VECTOR(1536)`, `embedding_model`, `metadata JSONB`, `created_at`. HNSW index sobre `embedding` cosine.
- **TenantRagConfig**: bloco em `tenants.yaml`. Governa `enabled`, `top_k`, `max_upload_mb`, `min_distance_threshold` (futuro). Hot-reload <=60s via config_poller.
- **AgentToolEnabled**: relacao existente `agents.tools_enabled JSONB ARRAY`. Recebe `'search_knowledge'` como primeiro tool real do registry. Toggle UI per-agente.
- **EmbedderClient**: novo modulo `prosauai/rag/embedder.py`. Cliente httpx para Bifrost `/v1/embeddings`. Retry + batch + spans OTel.
- **Chunker**: novo modulo `prosauai/rag/chunker.py`. Stdlib + tiktoken. MD-aware + fixed-size fallback.
- **Extractor**: novo modulo `prosauai/rag/extractor.py`. Reusa PyMuPDF (epic 009). MD/text passthrough.
- **SearchKnowledgeTool**: nova entrada em `tools/registry.py`. Pydantic schema input, executor com SQL cosine + tenant injection.
- **BifrostEmbeddingsProvider**: extensao Bifrost (config + adapter Go). Mesmo pattern do chat completions.
- **ReembedCLI**: novo modulo `prosauai/rag/reembed.py`. Operacao operacional rara mas critica.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: **Onboarding de tenant novo (do zero ao agente respondendo com contexto) sob 30 min** — em piloto com tenant proxy (Pace cria tenant fake), tempo medio entre `tenants.yaml` publicado com `rag.enabled=true` e primeira mensagem de cliente respondida com chunk citado e <=30 minutos. Inclui upload de 1-3 documentos pequenos via UI admin. (Reduzir para <15 min e meta vision; v1 entrega 30 min com margem.)
- **SC-002**: **Zero cross-tenant leak de chunks** — em periodo de 30d pos-rollout full em Ariel + ResenhAI, numero de chunks de um tenant retornados em query de outro tenant e zero. Medido via test invariant noturno: para cada tenant T, query `SELECT * FROM knowledge_chunks WHERE tenant_id != T.id` executada como service-role com `app.tenant_id=T.id` retorna zero rows. Defesa em profundidade: RLS + server-side injection.
- **SC-003**: **Latencia de upload <=15s p95 para arquivos <=10MB** — media medida via metric `rag_documents_uploaded_total` + `histogram_quantile(0.95, rag_upload_duration_seconds_bucket)`. Cobre extraction + chunking + embedding paralelo + transaction.
- **SC-004**: **Tool `search_knowledge` p95 <=2s** — embed query + SELECT cosine + return. Medido via histogram `rag_search_duration_seconds_bucket`. Inclui Bifrost embedding call.
- **SC-005**: **Custo de embedding <=R$0.50 por tenant onboarding completo** (definido como ate 10 documentos PDF mediums totalizando ~50K tokens). Medido via `bifrost_spend` agregado por tenant + endpoint=embeddings em primeira semana de uso.
- **SC-006**: **ResenhAI agente cita chunk em respostas reais** — em 7d pos-rollout com FAQ uploaded, >=20% das respostas do agente para perguntas sobre regulamento/horario/produto contem texto extraido de chunks (medido via match parcial entre `messages.content` outbound e `knowledge_chunks.content`). Indica adocao real do tool.
- **SC-007**: **Reversao via flag <=60s** — flipar `rag.enabled=false` em `tenants.yaml`, commit e poller pega em <=60s, uploads passam a 403, tool sumir do schema. Medido em smoke test de rollback no rollout.
- **SC-008**: **Retrieval relevance: distance top-1 <0.4 em 80% das queries reais** — para queries reais do agente (medido via `rag.distance_top1` no span), 80% delas retornam chunk com distance <0.4 (cosine), indicando match semantico real. Threshold para `min_distance_threshold` opcional sera derivado deste numero. Falha aqui sinaliza problema de qualidade do chunking ou modelo.
- **SC-009**: **Eval correlation: agentes com `rag_used=true` tem score medio >= sem-RAG** — epic 011 computa eval scores; correlacao positiva (ou neutra) entre uso de RAG e qualidade. Negativa indicaria que RAG injecta ruido — sinal para revisar chunking/threshold.
- **SC-010**: **Bifrost spend tracking 100% accurate** — comparacao mensal: soma `bifrost_spend WHERE endpoint='embeddings'` vs. invoice OpenAI delta atribuido a embeddings. Diff <=2% (precisao de billing).
- **SC-011**: **Quota enforcement zero false-positive em 30d** (Session 2026-04-26) — em rollout Ariel + ResenhAI, nenhum upload legitimo (dentro de defaults 200 docs / 10000 chunks) e rejeitado por quota. Falha indica bug em contagem (concorrencia ou stale cache). Medido via comparacao de `rag_documents_uploaded_total` vs `rag_uploads_rejected_total{reason='tenant_quota_exceeded'}`.
- **SC-012**: **Audit trail completeness** (Session 2026-04-26) — para 100% das operacoes upload/delete/download/search em um periodo de 7d pos-rollout, existe evento estruturado correspondente em logs com `tenant_id`, `actor_user_id`, `document_id`, `action_result`. Auditavel via grep/query no stack de logs. Falha aqui sinaliza brecha de compliance.

## Assumptions

- **Existem tenants ativos para validar valor end-to-end** — Ariel e ResenhAI em producao com volume real (~100-500 mensagens/dia/tenant). Sem trafego, smoke test e syntetico — validacao parcial.
- **Supabase pgvector extension disponivel sem custo extra** — Supabase managed inclui pgvector no plano corrente. Se nao, ops liga via SQL editor (uma vez).
- **OpenAI `text-embedding-3-small` mantido** — modelo estavel, sem deprecation prevista. Se OpenAI deprecar, CLI re-embed (US-5) cobre migracao para sucessor.
- **Bifrost extension complexity ~2-3 dias** — estimativa pitch. Se exceder, US-7 (P3) e cut-line para 012.1; resto do epic continua usando OpenAI direto temporariamente (sem rate limit Bifrost) ate extension pronta. Trade-off aceito.
- **PyMuPDF cobre maioria dos PDFs reais** — epic 009 ja valida em msgs reais. Edge cases (encrypted, scanned) explicitamente rejeitados em v1.
- **Volume de documents/tenant fica baixo em v1** — ate 50 documentos/tenant, ~1000 chunks/tenant. HNSW handle facilmente. Caso exceda, performance degrada graciosamente; re-tune `m` e `ef_construction` em epic futuro.
- **`tools/registry.py` esta acessivel** — scaffold mantido pos-epic 010 conforme descrito no pitch. Se foi removido, US-2 fica bloqueado por dependencia adicional (epic 013 antes de 012). Validar no PR-A.
- **Safety Layer A existe e cobre RAG injection adequadamente em v1** — epic 005 entregou layer; mesma regra (regex + heuristica) aplica em chunks RAG. Hardening especifico (semantic guard, vector poisoning detection) adiado para 012.1.
- **Admin Pace e tenant operator usam o mesmo admin UI** — epic 008 entregou UI unificada com permission scopes. Tenant operator vê seus documentos, Pace ops ve cross-tenant.
- **Custo de OpenAI embeddings aceitavel** — ~R$0.0001/chunk. 1000 chunks/tenant = ~R$0.10 onboarding. Re-embed total = ~R$0.10. Nao requer aprovacao de orcamento.
- **`agent_id IS NULL` significa shared (default)** — semantica acordada ADR-013. Documents tem `agent_id` implicito? **Nao** — documents sao always per-tenant; agent scoping vive nos chunks. Se uma feature futura precisar marcar document como per-agent, adiciona-se `agent_id NULL` em `documents` tambem.
- **Quotas defaults sao generosos para v1** (Session 2026-04-26) — 200 docs / 10000 chunks/tenant cobrem cenarios reais (Ariel/ResenhAI esperados em <50/<2000). Tenants enterprise com necessidades maiores dispararao tooling de override + alerta para ops; assumido que 0-2 casos em 90d. Se tenant atinge 80% de qualquer quota, log warning para ops triarem antes de bloqueio total.
- **Spans `rag.search` historicos referenciando documents deletados sao aceitaveis** (Session 2026-04-26) — Trace Explorer renderiza "(deleted)" gracefully; nao e bug nem perda de privacy (chunks nao sao exibidos no span — apenas `document_id` e `distance_top1`). Auditoria preserve. Caso contrario seria necessario cascade DELETE cross-table que nao escala.
- **Stack de logs estruturados ja existe** (Session 2026-04-26) — assumido Datadog/Loki/CloudWatch (epic 002 ja entregou observability stack). Logs `event_type=knowledge_*` sao queryable por `tenant_id` e `actor_user_id`. Sem stack, audit fica em arquivo local — degrada compliance mas nao bloqueia entrega.

---
handoff:
  from: speckit.clarify
  to: speckit.plan
  context: "Spec clarificada — Session 2026-04-26 resolveu 5 gaps de impacto: source_hash semantica (integrity-only, sem dedup auto), quotas per-tenant (200 docs / 10000 chunks com override), validacao zero-chunk (400/422 antes de embed), span retention em delete (append-only via epic 002), audit logs estruturados (sem tabela dedicada). Total 7 user stories + 76 FRs + 12 SCs + 13 assumptions. Pronto para plan."
  blockers: []
  confidence: Alta
  kill_criteria: "Bifrost extension /embeddings prova ser inviavel (>1 semana de esforco) -> recuar para chamada direta OpenAI sem spend tracking (degrade SC-010); ou pgvector nao habilitavel no Supabase managed -> bloqueio total, escalation para infra; ou quotas defaults estouram em piloto Ariel (sinaliza dimensionamento errado)."
