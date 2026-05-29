---
name: planager
description: Create or resume a structured feature plan. Use when starting a non-trivial feature or when the user asks to plan work.
---

# /planager - Create or resume a feature plan

Plans are stored in `.plans/plans.db` (SQLite). Use the `sqlite3` CLI to read
and write them.

## Schema

```sql
-- plans: feature (PK), title, status, context, notes, created, updated, archived (0/1)
-- phases: id, plan_feature (FK), phase_num, title, description
-- steps: id, phase_id (FK), step_order, description, status (pending|done)
-- status values: planning | in-progress | blocked | done
```

## If given a description (e.g. `/skill:planager add dark mode support`)

1. Choose a short slug from the description (e.g. `dark-mode`).
2. Check if the plan already exists:
   ```bash
   sqlite3 .plans/plans.db "SELECT status FROM plans WHERE feature='dark-mode'"
   ```
   - If it returns `in-progress`, switch to the **resume** flow below.
   - If it returns `done`, tell the user and ask if they want a new plan.
3. Explore the codebase to understand what the feature involves:
   - Read relevant files, check existing patterns, identify what needs to change.
4. Draft a phased plan with concrete steps. Each step should be small enough
   to complete in one action (a file edit, a test run, etc.).
5. Present the plan to the user. Ask for approval or adjustments.
6. Save the approved plan — insert the plan row, then each phase, then its steps:
   ```bash
   sqlite3 .plans/plans.db "INSERT INTO plans (feature, title, status, context, notes, created, updated) VALUES ('dark-mode', 'Dark Mode Support', 'planning', 'Context here.', '', date('now'), date('now'))"

   sqlite3 .plans/plans.db "INSERT INTO phases (plan_feature, phase_num, title, description) VALUES ('dark-mode', 1, 'Phase Title', 'Brief description')"
   PHASE_ID=$(sqlite3 .plans/plans.db "SELECT id FROM phases WHERE plan_feature='dark-mode' AND phase_num=1")
   sqlite3 .plans/plans.db "INSERT INTO steps (phase_id, step_order, description) VALUES ($PHASE_ID, 1, 'Step one'), ($PHASE_ID, 2, 'Step two')"
   ```
   Repeat the phase/steps block for each phase.
7. Ask the user if they want to begin implementation now.
   - If yes, set `status` to `in-progress` and start from Phase 1, step 1.

## If invoked without a description (e.g. just `/skill:planager`)

1. List active plans:
   ```bash
   sqlite3 -separator ' | ' .plans/plans.db "SELECT feature, title, status FROM plans WHERE archived=0"
   ```
2. Filter for `in-progress` or `blocked` plans and present them.
3. If there are in-progress plans, ask the user:
   - Resume one of them? (default if there's only one)
   - Or create a new plan?
4. If creating new, ask for a brief description and follow the flow above.

## Resume flow

1. Read the full plan and its steps:
   ```bash
   sqlite3 .plans/plans.db "SELECT feature, title, status, context, notes FROM plans WHERE feature='dark-mode'"
   sqlite3 -column -header .plans/plans.db "SELECT ph.phase_num, ph.title, s.step_order, s.description, s.status FROM phases ph JOIN steps s ON s.phase_id=ph.id WHERE ph.plan_feature='dark-mode' ORDER BY ph.phase_num, s.step_order"
   ```
2. Summarize current status: which phases are done, what's next.
3. Begin work from the first `pending` step.
4. Follow the standard plan update behavior (mark steps done, append notes,
   update status) as you work.

## On completion

When the user (or you, on their behalf) marks a plan complete:

1. Mark all remaining steps done and archive the plan:
   ```bash
   sqlite3 .plans/plans.db "UPDATE steps SET status='done' WHERE phase_id IN (SELECT id FROM phases WHERE plan_feature='dark-mode') AND status='pending'"
   sqlite3 .plans/plans.db "UPDATE plans SET status='done', archived=1, updated=date('now') WHERE feature='dark-mode'"
   ```
2. Append a brief completion summary to notes:
   ```bash
   sqlite3 .plans/plans.db "UPDATE plans SET notes=notes||char(10)||'- Done: summary here' WHERE feature='dark-mode'"
   ```
3. Archived plans (`archived=1`) are excluded from `/skill:planager-status` and
   session-start checks.
