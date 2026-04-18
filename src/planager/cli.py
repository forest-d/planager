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

INSTRUCTION_FILES = {
    "CLAUDE.md": "CLAUDE.md.snippet",
    "AGENTS.md": "AGENTS.md.snippet",
}


def get_template_path() -> Path:
    """Resolve the templates directory to a filesystem path."""
    return Path(str(TEMPLATES))


def _install_snippet(target: Path, filename: str, template_name: str, template_dir: Path) -> str:
    """Append a planager snippet to an instruction file. Returns action description."""
    dest = target / filename
    snippet = (template_dir / template_name).read_text()
    wrapped_snippet = f"{SNIPPET_MARKER}\n{snippet}{SNIPPET_END_MARKER}\n"

    if dest.exists():
        existing = dest.read_text()
        if SNIPPET_MARKER in existing:
            return f"{filename} already has planager snippet, skipped"
        with dest.open("a") as f:
            f.write("\n" + wrapped_snippet)
        return f"Appended planager snippet to {filename}"

    dest.write_text(wrapped_snippet)
    return f"Created {filename} with planager snippet"


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

    # 2. Copy skill files (Claude Code only)
    skills_dir = target / ".claude" / "skills"
    for skill_name in ("planager", "planager-status"):
        skill_dest = skills_dir / skill_name / "SKILL.md"
        skill_src = template_dir / skill_name / "SKILL.md"

        if skill_dest.exists():
            actions.append(f".claude/skills/{skill_name}/SKILL.md already exists, skipped")
        else:
            skill_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(skill_src), str(skill_dest))
            actions.append(f"Created .claude/skills/{skill_name}/SKILL.md")

    # 3. Append snippets to instruction files
    for filename, template_name in INSTRUCTION_FILES.items():
        actions.append(_install_snippet(target, filename, template_name, template_dir))

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
        print("\nDone. Your coding agent will now automatically use plans.")
        print("  Claude Code:  /planager <description>  or  /planager-status")
        print("  Any agent:    ask it to create a plan for your feature")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
