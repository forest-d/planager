# planager

Feature plans for LLM-assisted development.

One command sets up your project so coding agents automatically create, follow,
and maintain structured feature plans across sessions.

## Prerequisites

planager uses [uv](https://docs.astral.sh/uv/) for installation. If you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

See the [uv installation docs](https://docs.astral.sh/uv/getting-started/installation/) for other methods.

## Install

```bash
cd your-project
uvx planager init
```

You'll see a menu to pick your agent:

```
  Welcome to planager! Which agent are you using?

    1. Claude Code  -  Anthropic's Claude Code agent
    2. pi.dev  -  The pi coding agent
    3. Codex  -  OpenAI's Codex agent

  Select [1-3]:
```

You can also skip the menu by passing the target directly
(`uvx planager init claude`, `uvx planager init pi`, `uvx planager init codex`),
or run multiple targets in the same project - each one only creates the files
its agent needs.

That's it. No runtime dependencies, no background processes.

## What it does

After `planager init`, your project gets:

- **`.plans/`** - directory where feature plans live (markdown files).
- **Agent-specific skill directory** - slash commands for creating and checking plans.
- **Instruction file** - instructions that make the agent automatically discover
  and follow plans without you having to ask.

| Target | Skills directory | Instruction file | Slash commands |
|--------|-----------------|-----------------|----------------|
| `claude` | `.claude/skills/` | `CLAUDE.md` | `/planager`, `/planager-status` |
| `pi` | `.pi/skills/` | `AGENTS.md` | `/skill:planager`, `/skill:planager-status` |
| `codex` | `.codex/skills/` | `AGENTS.md` | `$planager`, `$planager-status` |

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

Using bcrypt for hashing. Decided against JWT - sessions are simpler for now.
```

The instruction file teaches the agent to:

1. **Check for in-progress plans** at the start of each session.
2. **Create plans** before starting non-trivial features.
3. **Update plans** as work progresses (check off steps, add notes).
4. **Mark plans done** when a feature is complete.

No special tools or MCP servers - the agent reads and writes plain markdown files.

## Slash commands

### `/planager` (Claude) / `/skill:planager` (pi) / `$planager` (Codex)

Create a new feature plan or resume an existing one.

- With a description: `/planager add dark mode support` - explores the codebase,
  drafts a phased plan, asks for approval.
- Without: `/planager` - lists in-progress plans and offers to resume or create new.

### `/planager-status` (Claude) / `/skill:planager-status` (pi) / `$planager-status` (Codex)

Show progress across all plans:

```
Feature          Status       Progress
───────────────  ───────────  ────────────────
auth             in-progress  Phase 2: 3/7
dark-mode        planning     Phase 1: 0/4
api-v2           done         5/5
```

## Idempotent

Running `uvx planager init` again is safe - it skips files that already
exist and won't duplicate the instruction file snippet.

## License

MIT
