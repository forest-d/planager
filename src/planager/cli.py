"""CLI entry point: `planager init <target>` sets up a project for plan-based development."""

from __future__ import annotations

import argparse
import dataclasses
import json
import sqlite3
import sys
from importlib.resources import files
from pathlib import Path

from planager.convert import (
    SQLITE_SCHEMA,
    Plan,
    collect_plans,
    migrate_plans,
    plan_progress,
)

SNIPPET_MARKER = "<!-- planager:start -->"
SNIPPET_END_MARKER = "<!-- planager:end -->"
FORMAT_START_MARKER = "<!-- planager:format-start -->"
FORMAT_END_MARKER = "<!-- planager:format-end -->"

TEMPLATES = files("planager.templates")

HTML_PLAN_EXAMPLE = """\
## Plan format

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Human-Readable Title</title>
<meta name="feature" content="short-slug">
<meta name="status" content="planning">
<meta name="created" content="YYYY-MM-DD">
<meta name="updated" content="YYYY-MM-DD">
<style>
  body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem;
         line-height: 1.6; }
  .phase { margin: 1.5rem 0; }
  .step { padding: 0.25rem 0; }
  .step::before { content: "\\2610"; margin-right: 0.5rem; }
  .step.done::before { content: "\\2611"; }
</style>
</head>
<body>

<h1>Human-Readable Title</h1>

<section id="context">
<h2>Context</h2>
<p>What the feature is, why it matters, constraints, links to issues or docs.</p>
</section>

<section class="phase" id="phase-1">
<h2>Phase 1: &lt;title&gt;</h2>
<p>Brief description of this phase.</p>
<div class="step" data-status="pending">Step description</div>
<div class="step" data-status="pending">Step description</div>
</section>

<section class="phase" id="phase-2">
<h2>Phase 2: &lt;title&gt;</h2>
<div class="step" data-status="pending">Step description</div>
</section>

<section id="notes">
<h2>Notes</h2>
<p>Running log of decisions, blockers, things tried.</p>
</section>

</body>
</html>
```
"""

# Each target: skills directory, instruction file(s), display info
TARGETS = {
    "claude": {
        "skills_dir": ".claude/skills",
        "instruction_files": ["CLAUDE.md"],
        "label": "Claude Code",
        "description": "Anthropic's Claude Code agent",
        "commands": "/planager <description>  or  /planager-status",
    },
    "pi": {
        "skills_dir": ".pi/skills",
        "instruction_files": ["AGENTS.md"],
        "label": "pi.dev",
        "description": "The pi coding agent",
        "commands": "/skill:planager <description>  or  /skill:planager-status",
    },
    "codex": {
        "skills_dir": ".codex/skills",
        "instruction_files": ["AGENTS.md"],
        "label": "Codex",
        "description": "OpenAI's Codex agent",
        "commands": "$planager <description>  or  $planager-status",
    },
}

TARGET_ORDER = ["claude", "pi", "codex"]


def get_template_path() -> Path:
    """Resolve the templates directory to a filesystem path."""
    return Path(str(TEMPLATES))


def _render_template(content: str, style: str) -> str:
    """Apply style-specific substitutions to template content."""
    if style == "markdown":
        return content

    # Replace file extensions and format references
    content = content.replace("<feature-slug>.md", "<feature-slug>.html")
    content = content.replace("<slug>.md", "<slug>.html")
    content = content.replace("*.md", "*.html")
    content = content.replace("markdown files", "HTML files")

    # Replace "- [x]" / "- [ ]" checkbox references with HTML equivalents
    content = content.replace(
        "Check off steps (`- [x]`) as they are completed.",
        'Check off steps (set `data-status="done"` and add class `done`) as they are completed.',
    )
    content = content.replace(
        "Checkbox counts: total `- [ ]` and `- [x]` lines",
        'Checkbox counts: total `data-status="pending"` and `data-status="done"` steps',
    )

    # Replace the plan format example block if format markers are present
    if FORMAT_START_MARKER in content and FORMAT_END_MARKER in content:
        start = content.index(FORMAT_START_MARKER)
        end = content.index(FORMAT_END_MARKER) + len(FORMAT_END_MARKER)
        content = content[:start] + HTML_PLAN_EXAMPLE + content[end:]

    return content


def _install_snippet(
    target: Path,
    filename: str,
    template_dir: Path,
    style: str = "markdown",
) -> str:
    """Append a planager snippet to an instruction file. Returns action description."""
    dest = target / filename
    if style == "sqlite":
        snippet = (template_dir / "snippet.sqlite.md").read_text()
    else:
        snippet = (template_dir / "snippet.md").read_text()
        snippet = _render_template(snippet, style)
    wrapped_snippet = f"{SNIPPET_MARKER}\n{snippet}{SNIPPET_END_MARKER}\n"

    if dest.exists():
        existing = dest.read_text()
        if SNIPPET_MARKER in existing:
            # Replace existing snippet block
            start = existing.index(SNIPPET_MARKER)
            if SNIPPET_END_MARKER in existing:
                end = existing.index(SNIPPET_END_MARKER) + len(SNIPPET_END_MARKER)
                if end < len(existing) and existing[end] == "\n":
                    end += 1
            else:
                end = len(existing)
            dest.write_text(existing[:start] + wrapped_snippet + existing[end:])
            return f"Updated planager snippet in {filename}"
        with dest.open("a") as f:
            f.write("\n" + wrapped_snippet)
        return f"Appended planager snippet to {filename}"

    dest.write_text(wrapped_snippet)
    return f"Created {filename} with planager snippet"


def _prompt_target() -> str | None:
    """Show an interactive target picker. Returns the target key or None on failure."""
    if not sys.stdin.isatty():
        print("Error: no target specified. Usage: planager init <target>", file=sys.stderr)
        return None

    print("\n  Welcome to planager! Which agent are you using?\n")
    for i, key in enumerate(TARGET_ORDER, 1):
        cfg = TARGETS[key]
        print(f"    {i}. {cfg['label']}")
    print()

    while True:
        try:
            choice = input("  Select [1-3] (default: 1): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return None

        if not choice:
            return TARGET_ORDER[0]

        if choice in (str(i) for i in range(1, len(TARGET_ORDER) + 1)):
            return TARGET_ORDER[int(choice) - 1]

        # Also accept the target name directly
        if choice in TARGETS:
            return choice

        print("  Invalid choice. Enter a number 1-3.")


def _detect_installed_targets(target_dir: Path) -> list[str]:
    """Return the list of targets that appear to be installed in *target_dir*."""
    installed = []
    for name in TARGET_ORDER:
        skill_file = target_dir / TARGETS[name]["skills_dir"] / "planager" / "SKILL.md"
        if skill_file.exists():
            installed.append(name)
    return installed


def _detect_style(target_dir: Path, installed: list[str]) -> str:
    """Detect the current plan style (markdown or html) from existing snippet content."""
    for name in installed:
        for filename in TARGETS[name]["instruction_files"]:
            f = target_dir / filename
            if not f.exists():
                continue
            content = f.read_text()
            if SNIPPET_MARKER not in content:
                continue
            start = content.index(SNIPPET_MARKER)
            end = (
                content.index(SNIPPET_END_MARKER)
                if SNIPPET_END_MARKER in content
                else len(content)
            )
            snippet = content[start:end]
            if "HTML files" in snippet or "<feature-slug>.html" in snippet:
                return "html"
            if "plans.db" in snippet:
                return "sqlite"
            return "markdown"
    return "markdown"


def update_project(target_dir: Path, style: str | None = None) -> tuple[list[str], list[str]]:
    """Re-install planager files for whichever targets are already set up in *target_dir*.

    If *style* differs from the currently installed style, existing plans are
    migrated to the new format. Returns ``(installed_targets, actions)``. If no
    targets are installed, both lists are empty.
    """
    installed = _detect_installed_targets(target_dir)
    if not installed:
        return [], []

    current_style = _detect_style(target_dir, installed)
    if style is None:
        style = current_style

    actions: list[str] = []
    if style != current_style:
        actions.extend(migrate_plans(target_dir / ".plans", current_style, style))
    for name in installed:
        actions.extend(init_project(target_dir, name, style))
    return installed, actions


def init_project(target_dir: Path, target_name: str, style: str = "markdown") -> list[str]:
    """Install planager files into *target_dir* project directory for *target_name*.

    Returns a list of actions taken (for user feedback).
    """
    if target_name not in TARGETS:
        raise ValueError(f"Unknown target: {target_name}")

    actions: list[str] = []
    template_dir = get_template_path()
    config = TARGETS[target_name]

    # 1. Create .plans/ directory and either plans.db (sqlite) or done/ subdir
    plans_dir = target_dir / ".plans"
    if not plans_dir.exists():
        plans_dir.mkdir(parents=True)
        actions.append("Created .plans/")
    else:
        actions.append(".plans/ already exists, skipped")

    if style == "sqlite":
        db_path = plans_dir / "plans.db"
        if not db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.executescript(SQLITE_SCHEMA)
            conn.commit()
            conn.close()
            actions.append("Created .plans/plans.db")
        else:
            actions.append(".plans/plans.db already exists, skipped")
    else:
        done_dir = plans_dir / "done"
        if not done_dir.exists():
            done_dir.mkdir(parents=True)
            actions.append("Created .plans/done/")

    # 2. Copy skill files for this target
    skills_dir = target_dir / config["skills_dir"]
    for skill_name in ("planager", "planager-status"):
        skill_dest = skills_dir / skill_name / "SKILL.md"
        if style == "sqlite":
            skill_src = template_dir / target_name / skill_name / "SKILL.sqlite.md"
        else:
            skill_src = template_dir / target_name / skill_name / "SKILL.md"

        existed = skill_dest.exists()
        skill_dest.parent.mkdir(parents=True, exist_ok=True)
        skill_content = skill_src.read_text()
        if style != "sqlite":
            skill_content = _render_template(skill_content, style)
        skill_dest.write_text(skill_content)
        verb = "Updated" if existed else "Created"
        actions.append(f"{verb} {config['skills_dir']}/{skill_name}/SKILL.md")

    # 3. Append snippets to instruction files
    for filename in config["instruction_files"]:
        actions.append(_install_snippet(target_dir, filename, template_dir, style))

    return actions


_STATUS_ORDER = {"in-progress": 0, "blocked": 1, "planning": 2, "done": 3}


def _render_table(headers: tuple[str, ...], rows: list[tuple[str, ...]]) -> str:
    """Render rows as aligned columns with a header and rule line."""
    widths = [max(len(h), *(len(row[i]) for row in rows)) for i, h in enumerate(headers)]
    lines = [
        "  ".join(h.ljust(w) for h, w in zip(headers, widths)).rstrip(),
        "  ".join("─" * w for w in widths),
    ]
    lines += ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in rows]
    return "\n".join(lines)


def _display_status(plan) -> str:
    return f"{plan.status} (archived)" if plan.archived else plan.status


def format_status_table(plans) -> str:
    """Render plans as the aligned Feature/Status/Progress table."""
    rows = []
    for plan in sorted(plans, key=lambda p: (_STATUS_ORDER.get(p.status, 4), p.feature)):
        done, total, current = plan_progress(plan)
        if total == 0:
            progress = "no steps"
        elif current is None:
            progress = f"{done}/{total}"
        else:
            progress = f"Phase {current}: {done}/{total}"
        rows.append((plan.feature, _display_status(plan), progress))
    return _render_table(("Feature", "Status", "Progress"), rows)


def format_plan_list(plans) -> str:
    """Render plans as the aligned Feature/Title/Status/Updated table."""
    rows = [
        (plan.feature, plan.title, _display_status(plan), plan.updated or "-")
        for plan in sorted(plans, key=lambda p: p.feature)
    ]
    return _render_table(("Feature", "Title", "Status", "Updated"), rows)


def _indent(text: str) -> str:
    return "\n".join(f"  {line}" if line.strip() else "" for line in text.splitlines())


def format_plan(plan: Plan) -> str:
    """Render a full plan as human-readable text."""
    status = f"{plan.status} (archived)" if plan.archived else plan.status
    lines = [f"{plan.title} ({plan.feature}) — {status}"]
    dates = " · ".join(
        part
        for part in (
            f"Created {plan.created}" if plan.created else "",
            f"Updated {plan.updated}" if plan.updated else "",
        )
        if part
    )
    if dates:
        lines.append(dates)
    if plan.context:
        lines += ["", "Context", "", _indent(plan.context)]
    for num, phase in enumerate(plan.phases, 1):
        lines += ["", f"Phase {num}: {phase.title}"]
        if phase.description:
            lines.append(_indent(phase.description))
        for step in phase.steps:
            mark = "x" if step.done else " "
            lines.append(f"  [{mark}] {step.description}")
    if plan.notes:
        lines += ["", "Notes", "", _indent(plan.notes)]
    return "\n".join(lines)


def grep_plans(plans: list[Plan], term: str) -> list[str]:
    """Case-insensitively search plans, returning grep-style match lines."""
    needle = term.lower()
    matches: list[str] = []

    def check(location: str, text: str) -> None:
        for line in text.splitlines():
            if needle in line.lower():
                matches.append(f"{plan.feature}:{location}: {line.strip()}")

    for plan in plans:
        if needle in plan.feature.lower():
            matches.append(f"{plan.feature}:feature: {plan.feature}")
        check("title", plan.title)
        check("context", plan.context)
        for num, phase in enumerate(plan.phases, 1):
            check(f"phase {num}", phase.title)
            check(f"phase {num}", phase.description)
            for order, step in enumerate(phase.steps, 1):
                check(f"phase {num} step {order}", step.description)
        check("notes", plan.notes)
    return matches


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="planager",
        description="Feature plans for LLM-assisted development.",
    )
    sub = parser.add_subparsers(dest="command")

    init_parser = sub.add_parser(
        "init",
        help="Set up the current project for plan-based development.",
    )
    init_parser.add_argument(
        "target",
        nargs="?",
        choices=sorted(TARGETS.keys()),
        help="Agent to set up: claude, pi, or codex. Omit to choose interactively.",
    )
    init_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )
    init_parser.add_argument(
        "--style",
        choices=["markdown", "html", "sqlite"],
        default=None,
        help="Plan format: markdown, html, or sqlite. Defaults to the style already"
        " in use if the project is initialized, else markdown. Existing plans are"
        " migrated when the style changes.",
    )

    update_parser = sub.add_parser(
        "update",
        help="Update an existing planager setup to the latest skill files.",
    )
    update_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )
    update_parser.add_argument(
        "--style",
        choices=["markdown", "html", "sqlite"],
        default=None,
        help="Switch to a different plan format, migrating existing plans."
        " Defaults to auto-detect from existing setup.",
    )

    status_parser = sub.add_parser(
        "status",
        help="Show progress across all feature plans, no agent required.",
    )
    status_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )
    status_parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Include archived plans.",
    )

    show_parser = sub.add_parser(
        "show",
        help="Print a plan's full contents (or list all plans), no agent required.",
    )
    show_parser.add_argument(
        "feature",
        nargs="?",
        help="Plan slug to show. Omit to list all plans.",
    )
    show_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )
    show_parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Include archived plans when listing.",
    )
    show_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output JSON instead of text.",
    )

    grep_parser = sub.add_parser(
        "grep",
        help="Search all plans for a term (works even for the SQLite style).",
    )
    grep_parser.add_argument("term", help="Case-insensitive search term.")
    grep_parser.add_argument(
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )
    grep_parser.add_argument(
        "--all",
        action="store_true",
        dest="show_all",
        help="Include archived plans.",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "init":
        target_name = args.target
        if target_name is None:
            target_name = _prompt_target()
            if target_name is None:
                return 1

        target_dir = args.path.resolve()
        if not target_dir.is_dir():
            print(f"Error: {target_dir} is not a directory.", file=sys.stderr)
            return 1

        installed = _detect_installed_targets(target_dir)
        current_style = _detect_style(target_dir, installed) if installed else None
        style = args.style
        if style is None:
            style = current_style or "markdown"

        actions: list[str] = []
        if current_style is not None and style != current_style:
            actions.extend(migrate_plans(target_dir / ".plans", current_style, style))
        actions.extend(init_project(target_dir, target_name, style))
        # Keep any other already-installed targets on the same style
        if current_style is not None and style != current_style:
            for name in installed:
                if name != target_name:
                    actions.extend(init_project(target_dir, name, style))
        print(f"\n  Initialized planager for {TARGETS[target_name]['label']} in {target_dir}\n")
        for action in actions:
            print(f"    {action}")
        print(
            f"\n  Done. Your {TARGETS[target_name]['label']} agent will "
            f"now automatically use plans."
        )
        print(f"    Commands: {TARGETS[target_name]['commands']}\n")
        return 0

    if args.command == "update":
        target_dir = args.path.resolve()
        if not target_dir.is_dir():
            print(f"Error: {target_dir} is not a directory.", file=sys.stderr)
            return 1

        installed, actions = update_project(target_dir, args.style)
        if not installed:
            print(
                "No planager setup detected in this project. Run `planager init` first.",
                file=sys.stderr,
            )
            return 1

        labels = ", ".join(TARGETS[name]["label"] for name in installed)
        print(f"\n  Updated planager for {labels} in {target_dir}\n")
        for action in actions:
            print(f"    {action}")
        print("\n  Done.\n")
        return 0

    if args.command == "status":
        plans_dir = args.path.resolve() / ".plans"
        if not plans_dir.is_dir():
            print("No .plans/ directory found. Run `planager init` first.", file=sys.stderr)
            return 1

        plans = collect_plans(plans_dir, include_archived=args.show_all)
        if not plans:
            print("No plans found in .plans/.")
            return 0

        print(format_status_table(plans))
        for plan in plans:
            if plan.status == "blocked" and plan.notes:
                last_note = plan.notes.strip().splitlines()[-1].strip()
                print(f"\n{plan.feature} is blocked: {last_note}")
        return 0

    if args.command == "show":
        plans_dir = args.path.resolve() / ".plans"
        if not plans_dir.is_dir():
            print("No .plans/ directory found. Run `planager init` first.", file=sys.stderr)
            return 1

        if args.feature is None:
            plans = collect_plans(plans_dir, include_archived=args.show_all)
            if not plans:
                print("No plans found in .plans/.")
                return 0
            if args.as_json:
                rows = []
                for plan in plans:
                    done, total, _ = plan_progress(plan)
                    rows.append(
                        {
                            "feature": plan.feature,
                            "title": plan.title,
                            "status": plan.status,
                            "archived": plan.archived,
                            "updated": plan.updated,
                            "done_steps": done,
                            "total_steps": total,
                        }
                    )
                print(json.dumps(rows, indent=2))
            else:
                print(format_plan_list(plans))
            return 0

        # Direct lookup always includes archived plans
        plans = collect_plans(plans_dir, include_archived=True)
        matches = [p for p in plans if p.feature == args.feature]
        if not matches:
            slugs = ", ".join(sorted(p.feature for p in plans)) or "none"
            print(f"No plan named '{args.feature}'. Available: {slugs}", file=sys.stderr)
            return 1
        if args.as_json:
            print(json.dumps(dataclasses.asdict(matches[0]), indent=2))
        else:
            print(format_plan(matches[0]))
        return 0

    if args.command == "grep":
        plans_dir = args.path.resolve() / ".plans"
        if not plans_dir.is_dir():
            print("No .plans/ directory found. Run `planager init` first.", file=sys.stderr)
            return 1

        plans = collect_plans(plans_dir, include_archived=args.show_all)
        matches = grep_plans(plans, args.term)
        if not matches:
            return 1
        print("\n".join(matches))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
