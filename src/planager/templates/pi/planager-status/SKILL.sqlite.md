---
name: planager-status
description: Show status of all feature plans with progress summary. Use when the user wants to check plan progress.
---

# /planager-status - Show status of all feature plans

When the user invokes `/skill:planager-status`, do the following.

1. Query all active (non-archived) plans with step progress:
   ```bash
   sqlite3 -column -header .plans/plans.db "
     SELECT p.feature, p.title, p.status,
       SUM(CASE WHEN s.status='done' THEN 1 ELSE 0 END) AS done_steps,
       COUNT(s.id) AS total_steps
     FROM plans p
     LEFT JOIN phases ph ON ph.plan_feature = p.feature
     LEFT JOIN steps s ON s.phase_id = ph.id
     WHERE p.archived = 0
     GROUP BY p.feature
     ORDER BY p.status, p.feature
   "
   ```
2. If no rows are returned, say so and exit.
3. Format the results as a summary table, for example:

```
Feature          Status       Progress
───────────────  ───────────  ────────────────
auth             in-progress  3/7
dark-mode        planning     0/4
api-v2           done         5/5
```

4. If any plan is `blocked`, show the reason from its notes field:
   ```bash
   sqlite3 .plans/plans.db "SELECT feature, notes FROM plans WHERE status='blocked' AND archived=0"
   ```
