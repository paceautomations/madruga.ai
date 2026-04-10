### T042 — DONE
- [US7] Update `README.md` — document: (a) dev setup with Tailscale, (b) prod Fase 1 with Docker network, (c) new tenant onboarding step-by-step (copy template, edit YAML, generate secret via `python3 -
- Files: README.md
- Tokens in/out: 1348217/10176

### T043 — DONE
- Run `ruff check prosauai/` and `ruff format prosauai/` — fix all lint/format issues across modified files
- Tokens in/out: 1672658/4761

### T044 — DONE
- Run full test suite `pytest -v` — verify all unit and integration tests pass (captured fixtures + auth + router + debounce + webhook + idempotency)
- Tokens in/out: 3244135/13174

### T045 — DONE
- Run quickstart.md validation — follow quickstart steps, verify local dev setup works with `curl` commands
- Tokens in/out: 2218844/9610

### T046 — DONE
- End-to-end real validation (manual) — Evolution envia webhook para `http://<tailscale-ip>:8050/webhook/whatsapp/Ariel` com X-Webhook-Secret correto, verify: processes successfully, sends echo, duplica
- Tokens in/out: 2113135/12767

