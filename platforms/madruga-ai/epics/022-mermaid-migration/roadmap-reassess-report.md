I have a comprehensive picture of epic 022's delivery. Before generating the roadmap reassessment report, I have **Structured Questions**:

---

## Perguntas Estruturadas

### Premissas

**1.** Assumo que o epic 022 deve ser adicionado ao roadmap como "shipped" com appetite planejado 1w e real ~1d (pattern consistente com os epics anteriores). Correto?

**2.** Assumo que os 24 findings UNRESOLVED do QA (refs LikeC4 stale em `.claude/knowledge/`, `.claude/rules/`, `.claude/commands/`, `README.md`, `db_pipeline.py`, `conftest.py`) sao tech debt que deve ser trackado como um proximo candidato de epic (ou quick-fix). Nao bloqueia o merge do 022. Correto?

### Trade-offs

**3.** Para o cleanup dos findings stale (7 skills + 5 knowledge/rules files + 3 scripts/docs):
   - **Opcao A**: Quick-fix individual (`/madruga:quick-fix`) — rapido, mas sem rastreabilidade de epic
   - **Opcao B**: Epic dedicado (023-likec4-cleanup) — overhead de pitch/spec/plan mas rastreavel e com Judge review
   - **Opcao C**: Absorver no proximo epic que tocar esses arquivos — zero overhead mas pode nunca acontecer

   Recomendo **Opcao A** (quick-fix) porque sao edits mecanicos, bem documentados, e nao justificam o overhead de um epic completo.

### Gaps

**4.** O roadmap atual lista 2 candidatos vagos ("ProsaUAI end-to-end" e "Roadmap auto-atualizado"). Voce tem novos epics em mente ou quer que eu proponha candidatos baseados no estado atual do pipeline? Areas que vejo como candidatas:
   - Cleanup LikeC4 refs (quick-fix)
   - Skills updates via `/madruga:skills-mgmt` (para os 7 skills com refs stale)
   - Vision.md drift fix ("diagramas interativos" → "diagramas Mermaid estaticos")
   - ProsaUAI end-to-end validation

### Provocacao

**5.** O `vision.md` (linha 17) ainda diz "o modelo de arquitetura (LikeC4) alimenta diretamente o pipeline de especificacao (SpecKit)". Apos ADR-020, isso nao e mais verdade — agora sao Mermaid inline. Esse drift no documento de visao pode confundir proximos ciclos de planning. Quer que eu inclua isso no escopo do cleanup ou deixa pro reconcile do proximo epic?