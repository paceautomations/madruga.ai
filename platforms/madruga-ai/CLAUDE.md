# Madruga AI — Architecture Documentation & Spec-to-Code System

## Platform Identity

- **Platform**: madruga-ai
- **Description**: Sistema de documentacao arquitetural e pipeline spec-to-code para plataformas digitais
- **Lifecycle**: development
- **Repo**: paceautomations/madruga.ai (este repo)
- **Branch base**: main
- **Epic branches**: epic/madruga-ai/<NNN-slug>
- **Tags**: architecture, documentation, spec-to-code

## Context for AI

This is the documentation directory for the **madruga-ai** platform. Code and documentation live in the same repository.

When working on this platform:
1. Use `platform.py use madruga-ai` to set as active
2. L1 skills operate on files in this directory (platforms/madruga-ai/)
3. L2 epic cycle creates branches with prefix `epic/madruga-ai/`
4. Code changes happen in the same repo (.specify/scripts/, .claude/, portal/, etc.)
5. See root CLAUDE.md for pipeline documentation and commands

## Stack

- Python 3.11+ (stdlib only: sqlite3, pathlib, json, hashlib)
- SQLite WAL mode (.pipeline/madruga.db)
- Astro + Starlight (portal)
- LikeC4 (architecture models)
- Copier (platform templates)
