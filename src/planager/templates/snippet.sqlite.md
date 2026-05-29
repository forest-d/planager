
# Feature Plans

This project uses **planager** for structured feature planning. Plans are stored
in `.plans/plans.db` (SQLite) with phased steps tracked in a relational schema.

## Schema reference

```sql
-- plans: feature (PK), title, status, context, notes, created, updated, archived (0/1)
-- phases: id, plan_feature (FK→plans), phase_num, title, description
-- steps: id, phase_id (FK→phases), step_order, description, status (pending|done)
-- status values: planning | in-progress | blocked | done
```

## Automatic behavior

### On session start

Check for in-progress or blocked plans:

```bash
sqlite3 .plans/plans.db "SELECT feature, title, status FROM plans WHERE status IN ('in-progress', 'blocked') AND archived=0"
```

If any exist, briefly note them to the user (e.g. "There's an in-progress plan
for <title>"). If the user's request clearly relates to one, read it and resume
from the first pending step. Don't force it — if the user is asking about
something unrelated, just mention the plan exists and move on.

### When starting new feature work

Before writing code for a non-trivial feature, create a plan:

1. Ask the user for a brief description (if not already provided).
2. Explore the codebase to understand what's involved.
3. Draft a phased plan with concrete, checkable steps.
4. Present the plan to the user for approval.
5. Insert the approved plan into `.plans/plans.db`.
6. Begin implementation from Phase 1.

Skip planning for trivial tasks (single-file fixes, typos, config changes).
Use judgment — if the work spans multiple files or sessions, it deserves a plan.

### While working on a planned feature

Mark a step done:

```bash
sqlite3 .plans/plans.db "UPDATE steps SET status='done' WHERE id=<step_id>"
sqlite3 .plans/plans.db "UPDATE plans SET updated=date('now') WHERE feature='<slug>'"
```

Append to notes:

```bash
sqlite3 .plans/plans.db "UPDATE plans SET notes=notes||char(10)||'- Note text', updated=date('now') WHERE feature='<slug>'"
```

Update plan status to in-progress or blocked:

```bash
sqlite3 .plans/plans.db "UPDATE plans SET status='in-progress', updated=date('now') WHERE feature='<slug>'"
```

If blocked, also record the reason in notes.

### On completion

- Set `status='done'` and `archived=1` in the plans table.
- Append a brief completion summary to the notes field.
- Mark all remaining steps done.
- Archived plans (`archived=1`) are excluded from session-start checks.

```bash
sqlite3 .plans/plans.db "UPDATE steps SET status='done' WHERE phase_id IN (SELECT id FROM phases WHERE plan_feature='<slug>') AND status='pending'"
sqlite3 .plans/plans.db "UPDATE plans SET status='done', archived=1, notes=notes||char(10)||'- Done: summary here', updated=date('now') WHERE feature='<slug>'"
```
