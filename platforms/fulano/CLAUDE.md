# Fulano — Agentes WhatsApp

## Platform Identity

- **Platform**: fulano
- **Description**: Plataforma multi-tenant de agentes conversacionais WhatsApp para PMEs brasileiras
- **Lifecycle**: design
- **Repo**: paceautomations/fulano-api
- **Branch base**: main
- **Epic branches**: epic/fulano/<NNN-slug>
- **Tags**: whatsapp, conversational-ai, multi-tenant

## Context for AI

This is the documentation directory for the **fulano** platform within the madruga.ai architecture documentation system.
Documentation lives here; code lives in the paceautomations/fulano-api repository.

When working on this platform:
1. Use `platform_cli.py use fulano` to set as active
2. L1 skills (vision, domain-model, etc.) operate on files in this directory
3. L2 epic cycle creates branches with prefix `epic/fulano/`
4. See root CLAUDE.md for pipeline documentation and commands

## Stack

- Python 3.12 + FastAPI + PydanticAI
- Redis Streams (messaging)
- PostgreSQL + pgvector (multi-tenant, RLS)
- Evolution API (WhatsApp)
- Langfuse (observability)
