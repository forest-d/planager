# planager

Feature plans for LLM-assisted development.

One command sets up your project so coding agents (Claude Code, Codex, etc.)
automatically create, follow, and maintain structured feature plans across
sessions.

## Install

```bash
cd your-project
uvx planager init
```

That's it. No runtime dependencies, no background processes. The command copies
a few template files into your project and you're done.

## What it does

After `planager init`, your project gets:

- **`.plans/`** — directory where feature plans live (markdown files).
- **`.claude/skills/plan/`** — a `/plan` slash command for creating and resuming plans.
- **`.claude/skills/plan-status/`** — a `/plan-status` slash command for checking progress.
- **CLAUDE.md snippet** — instructions that make the agent automatically discover
  and follow plans without you having to ask.

## How it works

Plans are markdown files with frontmatter, phased steps, and checkboxes:

```markdown
---
feature: auth
title: User Authentication
status: in-progress
created: 2026-04-18
updated: 2026-04-18
---

## Context

Implement email/password authentication with session management.

## Phase 1: Database schema

- [x] Create users table migration
- [x] Add password hashing utility
- [ ] Add session table migration

## Phase 2: API endpoints

- [ ] POST /login
- [ ] POST /register

## Notes

Using bcrypt for hashing. Decided against JWT — sessions are simpler for now.
```

The CLAUDE.md snippet teaches the agent to:

1. **Check for in-progress plans** at the start of each session.
2. **Create plans** before starting non-trivial features.
3. **Update plans** as work progresses (check off steps, add notes).
4. **Mark plans done** when a feature is complete.

No special tools or MCP servers — the agent reads and writes plain markdown files.

## Slash commands

### `/plan`

Create a new feature plan or resume an existing one.

- With a description: `/plan add dark mode support` — explores the codebase,
  drafts a phased plan, asks for approval.
- Without: `/plan` — lists in-progress plans and offers to resume or create new.

### `/plan-status`

Show progress across all plans:

```
Feature          Status       Progress
───────────────  ───────────  ────────────────
auth             in-progress  Phase 2: 3/7
dark-mode        planning     Phase 1: 0/4
api-v2           done         5/5
```

## Idempotent

Running `uvx planager init` again is safe — it skips files that already exist
and won't duplicate the CLAUDE.md snippet.

## License

MIT
