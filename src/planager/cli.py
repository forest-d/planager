"""CLI entry point: `planager init <target>` sets up a project for plan-based development."""

from __future__ import annotations

import argparse
import sys
from importlib.resources import files
from pathlib import Path

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
    target: Path, filename: str, template_dir: Path, style: str = "markdown",
) -> str:
    """Append a planager snippet to an instruction file. Returns action description."""
    dest = target / filename
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


def init_project(target_dir: Path, target_name: str, style: str = "markdown") -> list[str]:
    """Install planager files into *target_dir* project directory for *target_name*.

    Returns a list of actions taken (for user feedback).
    """
    if target_name not in TARGETS:
        raise ValueError(f"Unknown target: {target_name}")

    actions: list[str] = []
    template_dir = get_template_path()
    config = TARGETS[target_name]

    # 1. Create .plans/ directory
    plans_dir = target_dir / ".plans"
    if not plans_dir.exists():
        plans_dir.mkdir(parents=True)
        actions.append("Created .plans/")
    else:
        actions.append(".plans/ already exists, skipped")

    # 2. Copy skill files for this target
    skills_dir = target_dir / config["skills_dir"]
    for skill_name in ("planager", "planager-status"):
        skill_dest = skills_dir / skill_name / "SKILL.md"
        skill_src = template_dir / target_name / skill_name / "SKILL.md"

        existed = skill_dest.exists()
        skill_dest.parent.mkdir(parents=True, exist_ok=True)
        skill_content = skill_src.read_text()
        skill_dest.write_text(_render_template(skill_content, style))
        verb = "Updated" if existed else "Created"
        actions.append(f"{verb} {config['skills_dir']}/{skill_name}/SKILL.md")

    # 3. Append snippets to instruction files
    for filename in config["instruction_files"]:
        actions.append(_install_snippet(target_dir, filename, template_dir, style))

    return actions


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
        choices=["markdown", "html"],
        default="markdown",
        help="Plan file format: markdown (default) or html.",
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

        actions = init_project(target_dir, target_name, args.style)
        print(f"\n  Initialized planager for {TARGETS[target_name]['label']} in {target_dir}\n")
        for action in actions:
            print(f"    {action}")
        print(f"\n  Done. Your {TARGETS[target_name]['label']} agent will now automatically use plans.")
        print(f"    Commands: {TARGETS[target_name]['commands']}\n")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
