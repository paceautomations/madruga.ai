I now have a comprehensive picture of the epic's changes and current documentation state. Before generating the reconcile report, I have **Structured Questions** for you:

---

## Perguntas Estruturadas

### Premissas

**1.** Assumo que a migracao LikeC4 → Mermaid esta completa e que o branch ja foi merged a main (vejo 2 merge commits: `6ebee31` e `4bbf69c`). As correcoes dos findings do Judge (B2-B7) e QA (W1-W4) em arquivos `.claude/` **ja foram aplicadas** no merge — confirmei via grep que esses arquivos estao limpos. Correto?

**2.** Assumo que o epic 022 deve ser adicionado ao roadmap como "shipped" com status `done`, appetite planejado 1w e real ~1d (como os epics anteriores). Correto?

### Gaps

**3.** Encontrei 3 documentos de negocio com drift ("diagramas interativos") que descrevem features que nao existem mais:
   - `solution-overview.md` (linhas 15, 24, 67): "diagramas interativos onde da pra clicar, dar zoom"
   - `process.md` (linhas 366, 402): "Diagrama interativo (zoom, pan, click-through)" e "Diagramas LikeC4 sao interativos"
   - `vision.md` (linha 42): "diagramas interativos"
   
   Voce quer que eu proponha diffs concretos para todos eles ou marca como "proxima rodada de cleanup"?

**4.** `db_pipeline.py:736` ainda extrai keys `views`, `serve`, `build` do platform.yaml — essas keys foram removidas, entao o metadata sempre sera `{}`. E `conftest.py:63` inclui `model: model/` no fixture. Corrigir agora ou deixar como tech debt menor?

### Provocacao

**5.** O CI perdeu um job (`likec4 build`), mas nenhum job novo foi adicionado para validar sintaxe Mermaid. O `portal build` via `astro-mermaid` pega erros de syntax, mas so na fase de build completo (~40s). Um lint Mermaid rapido no CI (e.g., `npx @mermaid-js/mermaid-cli -validate`) pegaria erros antes. Vale a pena adicionar ou o portal build ja cobre suficientemente?