"""CLI entry point: `planager init <target>` sets up a project for plan-based development."""

from __future__ import annotations

import argparse
import shutil
import sys
from importlib.resources import files
from pathlib import Path

SNIPPET_MARKER = "<!-- planager:start -->"
SNIPPET_END_MARKER = "<!-- planager:end -->"

TEMPLATES = files("planager.templates")

# Each target: skills directory, instruction file(s)
TARGETS = {
    "claude": {
        "skills_dir": ".claude/skills",
        "instruction_files": ["CLAUDE.md"],
    },
    "pi": {
        "skills_dir": ".pi/skills",
        "instruction_files": ["AGENTS.md"],
    },
    "codex": {
        "skills_dir": ".codex/skills",
        "instruction_files": ["AGENTS.md"],
    },
}


def get_template_path() -> Path:
    """Resolve the templates directory to a filesystem path."""
    return Path(str(TEMPLATES))


def _install_snippet(target: Path, filename: str, template_dir: Path) -> str:
    """Append a planager snippet to an instruction file. Returns action description."""
    dest = target / filename
    snippet = (template_dir / "snippet.md").read_text()
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


def init_project(target_dir: Path, target_name: str) -> list[str]:
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

        if skill_dest.exists():
            actions.append(f"{config['skills_dir']}/{skill_name}/SKILL.md already exists, skipped")
        else:
            skill_dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(skill_src), str(skill_dest))
            actions.append(f"Created {config['skills_dir']}/{skill_name}/SKILL.md")

    # 3. Append snippets to instruction files
    for filename in config["instruction_files"]:
        actions.append(_install_snippet(target_dir, filename, template_dir))

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
        choices=sorted(TARGETS.keys()),
        help="Agent to set up: claude, pi, or codex.",
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
        target_dir = args.path.resolve()
        if not target_dir.is_dir():
            print(f"Error: {target_dir} is not a directory.", file=sys.stderr)
            return 1

        actions = init_project(target_dir, args.target)
        print(f"Initialized planager for {args.target} in {target_dir}\n")
        for action in actions:
            print(f"  {action}")
        print(f"\nDone. Your {args.target} agent will now automatically use plans.")
        if args.target == "claude":
            print("  Slash commands: /planager <description>  or  /planager-status")
        elif args.target == "pi":
            print("  Slash commands: /skill:planager <description>  or  /skill:planager-status")
        elif args.target == "codex":
            print("  Invoke with: $planager <description>  or  $planager-status")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
