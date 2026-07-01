"""Convert feature plans between the markdown, HTML, and SQLite styles.

Used by ``planager init``/``planager update`` when a project switches styles,
so existing plans carry over instead of being stranded in the old format.
"""

from __future__ import annotations

import html
import re
import sqlite3
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path

SQLITE_SCHEMA = """\
CREATE TABLE IF NOT EXISTS plans (
    feature TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planning',
    context TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    created TEXT NOT NULL,
    updated TEXT NOT NULL,
    archived INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS phases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plan_feature TEXT NOT NULL REFERENCES plans(feature) ON DELETE CASCADE,
    phase_num INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    UNIQUE(plan_feature, phase_num)
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phase_id INTEGER NOT NULL REFERENCES phases(id) ON DELETE CASCADE,
    step_order INTEGER NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
);
"""

STYLE_EXTENSIONS = {"markdown": ".md", "html": ".html"}

_PHASE_HEADING = re.compile(r"^Phase\s+\d+\s*:\s*(.*)$", re.IGNORECASE)
_MD_STEP = re.compile(r"^- \[( |x|X)\] (.*)$")


@dataclass
class Step:
    description: str
    done: bool = False


@dataclass
class Phase:
    title: str
    description: str = ""
    steps: list[Step] = field(default_factory=list)


@dataclass
class Plan:
    feature: str
    title: str
    status: str = "planning"
    context: str = ""
    notes: str = ""
    created: str = ""
    updated: str = ""
    archived: bool = False
    phases: list[Phase] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------


def parse_markdown(text: str, fallback_feature: str = "plan") -> Plan:
    meta: dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    key, value = line.split(":", 1)
                    meta[key.strip()] = value.strip()
            body = text[end + 4 :]

    plan = Plan(
        feature=meta.get("feature", fallback_feature),
        title=meta.get("title", fallback_feature),
        status=meta.get("status", "planning"),
        created=meta.get("created", ""),
        updated=meta.get("updated", ""),
    )

    section: str | None = None
    text_lines: list[str] = []

    def flush() -> None:
        content = "\n".join(text_lines).strip()
        text_lines.clear()
        if not content:
            return
        if section == "context":
            plan.context = content
        elif section == "notes":
            plan.notes = content
        elif section == "phase" and plan.phases:
            plan.phases[-1].description = content

    for line in body.splitlines():
        if line.startswith("## "):
            flush()
            heading = line[3:].strip()
            phase_match = _PHASE_HEADING.match(heading)
            if phase_match:
                section = "phase"
                plan.phases.append(Phase(title=phase_match.group(1).strip()))
            elif heading.lower() == "context":
                section = "context"
            elif heading.lower() == "notes":
                section = "notes"
            else:
                section = None
            continue
        step_match = _MD_STEP.match(line.strip())
        if step_match and section == "phase" and plan.phases:
            flush()
            plan.phases[-1].steps.append(
                Step(step_match.group(2).strip(), step_match.group(1).lower() == "x")
            )
            continue
        text_lines.append(line)
    flush()
    return plan


def render_markdown(plan: Plan) -> str:
    lines = [
        "---",
        f"feature: {plan.feature}",
        f"title: {plan.title}",
        f"status: {plan.status}",
        f"created: {plan.created}",
        f"updated: {plan.updated}",
        "---",
        "",
        "## Context",
        "",
    ]
    if plan.context:
        lines += [plan.context, ""]
    for num, phase in enumerate(plan.phases, 1):
        lines.append(f"## Phase {num}: {phase.title}")
        lines.append("")
        if phase.description:
            lines += [phase.description, ""]
        for step in phase.steps:
            mark = "x" if step.done else " "
            lines.append(f"- [{mark}] {step.description}")
        if phase.steps:
            lines.append("")
    lines += ["## Notes", ""]
    if plan.notes:
        lines += [plan.notes, ""]
    return "\n".join(lines).rstrip() + "\n"


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


class _PlanHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.title = ""
        self.context_parts: list[str] = []
        self.notes_parts: list[str] = []
        self.phases: list[Phase] = []
        self._section: str | None = None
        self._elem: str | None = None
        self._buf: list[str] = []
        self._step_done = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr = {k: (v or "") for k, v in attrs}
        classes = attr.get("class", "").split()
        if tag == "meta" and "name" in attr:
            self.meta[attr["name"]] = attr.get("content", "")
        elif tag == "title":
            self._elem, self._buf = "title", []
        elif tag == "section":
            if attr.get("id") == "context":
                self._section = "context"
            elif attr.get("id") == "notes":
                self._section = "notes"
            elif "phase" in classes:
                self._section = "phase"
                self.phases.append(Phase(title=""))
            else:
                self._section = None
        elif tag == "h2" and self._section:
            self._elem, self._buf = "h2", []
        elif tag == "p" and self._section:
            self._elem, self._buf = "p", []
        elif tag == "div" and self._section == "phase" and "step" in classes:
            self._elem, self._buf = "step", []
            self._step_done = attr.get("data-status") == "done" or "done" in classes

    def handle_endtag(self, tag: str) -> None:
        text = "".join(self._buf).strip()
        if tag == "title" and self._elem == "title":
            self.title = text
        elif tag == "h2" and self._elem == "h2":
            if self._section == "phase" and self.phases:
                match = _PHASE_HEADING.match(text)
                self.phases[-1].title = match.group(1).strip() if match else text
        elif tag == "p" and self._elem == "p":
            if self._section == "context":
                self.context_parts.append(text)
            elif self._section == "notes":
                self.notes_parts.append(text)
            elif self._section == "phase" and self.phases:
                phase = self.phases[-1]
                phase.description = f"{phase.description}\n\n{text}".strip()
        elif tag == "div" and self._elem == "step":
            if self.phases:
                self.phases[-1].steps.append(Step(text, self._step_done))
        elif tag == "section":
            self._section = None
        if tag in ("title", "h2", "p", "div"):
            self._elem, self._buf = None, []

    def handle_data(self, data: str) -> None:
        if self._elem:
            self._buf.append(data)


def parse_html(text: str, fallback_feature: str = "plan") -> Plan:
    parser = _PlanHTMLParser()
    parser.feed(text)
    parser.close()
    return Plan(
        feature=parser.meta.get("feature", fallback_feature),
        title=parser.title or fallback_feature,
        status=parser.meta.get("status", "planning"),
        context="\n\n".join(parser.context_parts),
        notes="\n\n".join(parser.notes_parts),
        created=parser.meta.get("created", ""),
        updated=parser.meta.get("updated", ""),
        phases=parser.phases,
    )


_HTML_CSS = """\
  body { font-family: system-ui, sans-serif; max-width: 48rem; margin: 2rem auto; padding: 0 1rem;
         line-height: 1.6; }
  .phase { margin: 1.5rem 0; }
  .step { padding: 0.25rem 0; }
  .step::before { content: "\\2610"; margin-right: 0.5rem; }
  .step.done::before { content: "\\2611"; }"""


def _paragraphs(text: str) -> str:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    return "\n".join(f"<p>{html.escape(b)}</p>" for b in blocks)


def render_html(plan: Plan) -> str:
    esc = html.escape
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        f"<title>{esc(plan.title)}</title>",
        f'<meta name="feature" content="{esc(plan.feature)}">',
        f'<meta name="status" content="{esc(plan.status)}">',
        f'<meta name="created" content="{esc(plan.created)}">',
        f'<meta name="updated" content="{esc(plan.updated)}">',
        "<style>",
        _HTML_CSS,
        "</style>",
        "</head>",
        "<body>",
        "",
        f"<h1>{esc(plan.title)}</h1>",
        "",
        '<section id="context">',
        "<h2>Context</h2>",
    ]
    if plan.context:
        parts.append(_paragraphs(plan.context))
    parts += ["</section>", ""]
    for num, phase in enumerate(plan.phases, 1):
        parts.append(f'<section class="phase" id="phase-{num}">')
        parts.append(f"<h2>Phase {num}: {esc(phase.title)}</h2>")
        if phase.description:
            parts.append(_paragraphs(phase.description))
        for step in phase.steps:
            cls, status = ("step done", "done") if step.done else ("step", "pending")
            desc = esc(step.description)
            parts.append(f'<div class="{cls}" data-status="{status}">{desc}</div>')
        parts += ["</section>", ""]
    parts += ['<section id="notes">', "<h2>Notes</h2>"]
    if plan.notes:
        parts.append(_paragraphs(plan.notes))
    parts += ["</section>", "", "</body>", "</html>"]
    return "\n".join(parts) + "\n"


# ---------------------------------------------------------------------------
# SQLite
# ---------------------------------------------------------------------------


def load_sqlite(db_path: Path) -> list[Plan]:
    conn = sqlite3.connect(db_path)
    try:
        plans = []
        rows = conn.execute(
            "SELECT feature, title, status, context, notes, created, updated, archived"
            " FROM plans ORDER BY feature"
        ).fetchall()
        for feature, title, status, context, notes, created, updated, archived in rows:
            plan = Plan(
                feature=feature,
                title=title,
                status=status,
                context=context,
                notes=notes,
                created=created,
                updated=updated,
                archived=bool(archived),
            )
            phase_rows = conn.execute(
                "SELECT id, title, description FROM phases"
                " WHERE plan_feature=? ORDER BY phase_num",
                (feature,),
            ).fetchall()
            for phase_id, phase_title, description in phase_rows:
                phase = Phase(title=phase_title, description=description)
                step_rows = conn.execute(
                    "SELECT description, status FROM steps WHERE phase_id=? ORDER BY step_order",
                    (phase_id,),
                ).fetchall()
                phase.steps = [Step(desc, s == "done") for desc, s in step_rows]
                plan.phases.append(phase)
            plans.append(plan)
        return plans
    finally:
        conn.close()


def save_sqlite(db_path: Path, plans: list[Plan]) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SQLITE_SCHEMA)
        for plan in plans:
            conn.execute(
                "INSERT OR REPLACE INTO plans"
                " (feature, title, status, context, notes, created, updated, archived)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    plan.feature,
                    plan.title,
                    plan.status,
                    plan.context,
                    plan.notes,
                    plan.created,
                    plan.updated,
                    int(plan.archived),
                ),
            )
            for num, phase in enumerate(plan.phases, 1):
                cur = conn.execute(
                    "INSERT INTO phases (plan_feature, phase_num, title, description)"
                    " VALUES (?, ?, ?, ?)",
                    (plan.feature, num, phase.title, phase.description),
                )
                phase_id = cur.lastrowid
                for order, step in enumerate(phase.steps, 1):
                    conn.execute(
                        "INSERT INTO steps (phase_id, step_order, description, status)"
                        " VALUES (?, ?, ?, ?)",
                        (phase_id, order, step.description, "done" if step.done else "pending"),
                    )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Progress
# ---------------------------------------------------------------------------


def plan_progress(plan: Plan) -> tuple[int, int, int | None]:
    """Return ``(done_steps, total_steps, current_phase_num)``.

    ``current_phase_num`` is the 1-based number of the first phase containing a
    pending step, or ``None`` when every step is done or there are no steps.
    """
    done = total = 0
    current: int | None = None
    for num, phase in enumerate(plan.phases, 1):
        for step in phase.steps:
            total += 1
            if step.done:
                done += 1
            elif current is None:
                current = num
    return done, total, current


def collect_plans(plans_dir: Path, include_archived: bool = False) -> list[Plan]:
    """Load every plan stored in *plans_dir*, regardless of style.

    Reads ``plans.db`` plus any markdown and HTML plan files, so it works for
    all styles and even for a project caught mid-migration.
    """
    plans: list[Plan] = []
    db_path = plans_dir / "plans.db"
    if db_path.exists():
        plans += load_sqlite(db_path)
    for style in STYLE_EXTENSIONS:
        file_plans, _, _ = _load_plan_files(plans_dir, style)
        plans += file_plans
    if not include_archived:
        plans = [p for p in plans if not p.archived]
    return plans


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def _load_plan_files(plans_dir: Path, style: str) -> tuple[list[Plan], list[Path], list[str]]:
    """Load all plans stored as files. Returns (plans, source files, warnings)."""
    ext = STYLE_EXTENSIONS[style]
    parse = parse_markdown if style == "markdown" else parse_html
    plans: list[Plan] = []
    sources: list[Path] = []
    warnings: list[str] = []
    candidates = sorted(plans_dir.glob(f"*{ext}"))
    done_dir = plans_dir / "done"
    if done_dir.is_dir():
        candidates += sorted(done_dir.glob(f"*{ext}"))
    for path in candidates:
        try:
            plan = parse(path.read_text(), fallback_feature=path.stem)
        except Exception:
            warnings.append(f"Skipped {path.name} (could not parse)")
            continue
        plan.archived = path.parent.name == "done"
        plans.append(plan)
        sources.append(path)
    return plans, sources, warnings


def migrate_plans(plans_dir: Path, from_style: str, to_style: str) -> list[str]:
    """Convert every plan in *plans_dir* from one style to another.

    Successfully converted sources are removed; unparseable files are left in
    place and reported. Returns a list of action descriptions.
    """
    if from_style == to_style or not plans_dir.is_dir():
        return []

    actions: list[str] = []
    if from_style == "sqlite":
        db_path = plans_dir / "plans.db"
        if not db_path.exists():
            return []
        plans = load_sqlite(db_path)
        sources = [db_path]
    else:
        plans, sources, warnings = _load_plan_files(plans_dir, from_style)
        actions += warnings

    if to_style == "sqlite":
        if plans or sources:
            save_sqlite(plans_dir / "plans.db", plans)
            actions.append(f"Migrated {len(plans)} plan(s) into .plans/plans.db")
    else:
        ext = STYLE_EXTENSIONS[to_style]
        render = render_markdown if to_style == "markdown" else render_html
        for plan in plans:
            dest_dir = plans_dir / "done" if plan.archived else plans_dir
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{plan.feature}{ext}"
            dest.write_text(render(plan))
            actions.append(f"Migrated .plans/{dest.relative_to(plans_dir)}")

    for src in sources:
        src.unlink()
        if src.name == "plans.db":
            actions.append("Removed .plans/plans.db")

    # A file style -> sqlite switch can leave an empty done/ dir behind
    if to_style == "sqlite":
        done_dir = plans_dir / "done"
        if done_dir.is_dir() and not any(done_dir.iterdir()):
            done_dir.rmdir()

    return actions
