---
name: planager
description: Create or resume a structured feature plan. Use when starting a non-trivial feature or when the user asks to plan work.
---

# /planager — Create or resume a feature plan

When the user invokes `/skill:planager`, follow this workflow.

## If given a description (e.g. `/skill:planager add dark mode support`)

1. Choose a short slug from the description (e.g. `dark-mode`).
2. Check if `.plans/<slug>.md` already exists.
   - If it does and is `in-progress`, switch to the **resume** flow below.
   - If it does and is `done`, tell the user and ask if they want a new plan.
3. Explore the codebase to understand what the feature involves:
   - Read relevant files, check existing patterns, identify what needs to change.
4. Draft a phased plan with concrete steps. Each step should be small enough
   to complete in one action (a file edit, a test run, etc.).
5. Present the plan to the user. Ask for approval or adjustments.
6. Save the approved plan to `.plans/<slug>.md` with `status: planning`.
7. Ask the user if they want to begin implementation now.
   - If yes, set `status: in-progress` and start from Phase 1, step 1.

## If invoked without a description (e.g. just `/skill:planager`)

1. Glob `.plans/*.md` and read the frontmatter of each.
2. List any `in-progress` or `blocked` plans.
3. If there are in-progress plans, ask the user:
   - Resume one of them? (default if there's only one)
   - Or create a new plan?
4. If creating new, ask for a brief description and follow the flow above.

## Resume flow

1. Read the full plan file.
2. Summarize current status: which phases are done, what's next.
3. Begin work from the first unchecked step.
4. Follow the standard plan update behavior (check steps, add notes, update
   frontmatter) as you work.
