---
name: planager-status
description: Show status of all feature plans with progress summary. Use when the user wants to check plan progress.
---

# /planager-status — Show status of all feature plans

When the user invokes `/skill:planager-status`, do the following.

1. Glob `.plans/*.md` to find all plan files.
2. If no plans exist, say so and exit.
3. For each plan file, read it and extract:
   - `feature` and `title` from frontmatter
   - `status` from frontmatter
   - Checkbox counts: total `- [ ]` and `- [x]` lines per `## Phase N:` section
   - Overall progress: completed steps / total steps
4. Print a summary table, for example:

```
Feature          Status       Progress
───────────────  ───────────  ────────────────
auth             in-progress  Phase 2: 3/7
dark-mode        planning     Phase 1: 0/4
api-v2           done         5/5
```

5. If any plan is `blocked`, show the reason from the Notes section if available.
