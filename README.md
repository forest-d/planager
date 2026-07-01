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

  Select [1-3] (default: 1):
```

You can also skip the menu by passing the target directly
(`uvx planager init claude`, `uvx planager init pi`, `uvx planager init codex`),
or run multiple targets in the same project - each one only creates the files
its agent needs.

Options:

```
uvx planager init [target] [--path DIR] [--style markdown|html|sqlite]
```

| Flag | Default | Description |
|------|---------|-------------|
| `target` | *(interactive)* | Agent to set up: `claude`, `pi`, or `codex` |
| `--path` | `.` | Project root directory |
| `--style` | *(existing style, else `markdown`)* | Plan format: `markdown`, `html`, or `sqlite` |

That's it. No runtime dependencies, no background processes.

## What it does

After `planager init`, your project gets:

- **`.plans/`** - directory where feature plans live (markdown or HTML files,
  or a single `plans.db` with `--style sqlite`).
- **`.plans/done/`** - archive for completed plans. Excluded from
  `/planager-status` and session-start checks. (SQLite plans use an `archived`
  flag instead.)
- **Agent-specific skill directory** - slash commands for creating and checking plans.
- **Instruction file** - instructions that make the agent automatically discover
  and follow plans without you having to ask.

| Target | Skills directory | Instruction file | Slash commands |
|--------|-----------------|-----------------|----------------|
| `claude` | `.claude/skills/` | `CLAUDE.md` | `/planager`, `/planager-status` |
| `pi` | `.pi/skills/` | `AGENTS.md` | `/skill:planager`, `/skill:planager-status` |
| `codex` | `.codex/skills/` | `AGENTS.md` | `$planager`, `$planager-status` |

## Plan styles

By default, plans are markdown files. You can also use HTML or SQLite:

```bash
uvx planager init claude --style html
uvx planager init claude --style sqlite
```

**HTML** plans are standalone files with zero JavaScript dependencies — just HTML
and CSS. They use `<meta>` tags for metadata and `data-status` attributes for
step tracking, viewable directly in a browser.

**SQLite** plans live in a single `.plans/plans.db` that the agent queries and
updates with the `sqlite3` CLI (which must be installed). Completed plans are
archived with a flag instead of a `done/` directory. Trade-offs: plans become
queryable and structurally consistent, but the database is a binary file — git
diffs won't show what changed between sessions, and you can't read or edit
plans without the `sqlite3` CLI. Prefer markdown or HTML if human-readable,
diffable plans matter to you.

## Switching styles

To switch an existing project to a different style, pass `--style` to `update`
(or re-run `init`):

```bash
uvx planager update --style html
```

This rewrites the instruction snippet and skill files for every installed agent
**and migrates your existing plans** to the new format — markdown and HTML files
are converted in place (including archived plans in `.plans/done/`), and
switching to or from SQLite imports or exports the database. Any file that
can't be parsed as a plan is left untouched and reported. Running `init` or
`update` without `--style` always keeps the style you already have.

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
4. **Mark plans done** when a feature is complete, and offer to archive them to
   `.plans/done/`.

No special tools or MCP servers - the agent reads and writes plain files. (The
opt-in `sqlite` style is the one exception: it relies on the `sqlite3` CLI.)

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

## Check status from the terminal

You don't need an agent session to see where things stand:

```bash
uvx planager status
```

This prints the same progress table directly, reading whatever is in `.plans/`
(markdown, HTML, or SQLite — it works for every style). Plans are ordered
in-progress, blocked, planning, done; blocked plans also show their most recent
note so you can see what they're waiting on. Pass `--all` to include archived
plans, and `--path DIR` to point at another project. Handy for a quick check
before starting a session, or from scripts and CI.

## Contributing

This project uses [just](https://github.com/casey/just) for dev workflows.
Run `just` to see available recipes:

```
just ruff       # lint and format
just test       # run tests
just check      # lint, format, then test
just build      # clean dist/ and build
just publish    # clean, build, and publish
just docs       # open docs in the browser
```

## Updating

When new planager versions ship updated skill files or instruction snippets,
upgrade an existing project with:

```bash
uvx planager update
```

This detects which agents you've already set up (and the `--style` you chose),
and refreshes their skill files and instruction snippets to the latest version.
Pass `--style markdown|html|sqlite` to switch formats at the same time — see
[Switching styles](#switching-styles).

## Idempotent

Running `uvx planager init` again is safe. It updates skill files and the
instruction snippet in place without duplicating anything, and keeps whatever
style you already chose. Re-initializing with a different `--style` cleanly
replaces the previous configuration and migrates existing plans.

## License

MIT
