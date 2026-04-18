"""CLI entry point: `planager init` sets up a project for plan-based development."""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib.resources import files
from pathlib import Path

SNIPPET_MARKER = "<!-- planager:start -->"
SNIPPET_END_MARKER = "<!-- planager:end -->"

TEMPLATES = files("planager.templates")


def get_template_path() -> Path:
    """Resolve the templates directory to a filesystem path."""
    return Path(str(TEMPLATES))


def init_project(target: Path) -> list[str]:
    """Install planager files into *target* project directory.

    Returns a list of actions taken (for user feedback).
    """
    actions: list[str] = []
    template_dir = get_template_path()

    # 1. Create .plans/ directory
    plans_dir = target / ".plans"
    if not plans_dir.exists():
        plans_dir.mkdir(parents=True)
        actions.append("Created .plans/")
    else:
        actions.append(".plans/ already exists, skipped")

    # 2. Copy skill files
    skills_dir = target / ".claude" / "skills"
    for skill_name in ("plan", "plan-status"):
        skill_dest = skills_dir / skill_name / "SKILL.md"
        skill_src = template_dir / skill_name / "SKILL.md"

        if skill_dest.exists():
            actions.append(f".claude/skills/{skill_name}/SKILL.md already exists, skipped")
        else:
            skill_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(skill_src), str(skill_dest))
            actions.append(f"Created .claude/skills/{skill_name}/SKILL.md")

    # 3. Append CLAUDE.md snippet
    claude_md = target / "CLAUDE.md"
    snippet = (template_dir / "CLAUDE.md.snippet").read_text()
    wrapped_snippet = f"{SNIPPET_MARKER}\n{snippet}{SNIPPET_END_MARKER}\n"

    if claude_md.exists():
        existing = claude_md.read_text()
        if SNIPPET_MARKER in existing:
            actions.append("CLAUDE.md already has planager snippet, skipped")
        else:
            with claude_md.open("a") as f:
                f.write("\n" + wrapped_snippet)
            actions.append("Appended planager snippet to CLAUDE.md")
    else:
        claude_md.write_text(wrapped_snippet)
        actions.append("Created CLAUDE.md with planager snippet")

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
        "--path",
        type=Path,
        default=Path.cwd(),
        help="Project root directory (default: current directory).",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "init":
        target = args.path.resolve()
        if not target.is_dir():
            print(f"Error: {target} is not a directory.", file=sys.stderr)
            return 1

        actions = init_project(target)
        print(f"Initialized planager in {target}\n")
        for action in actions:
            print(f"  {action}")
        print("\nDone. In Claude Code, try:")
        print("  /plan <description>   — create a feature plan")
        print("  /plan                 — resume an in-progress plan")
        print("  /plan-status          — see progress across all plans")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
