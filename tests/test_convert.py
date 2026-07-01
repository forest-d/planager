"""Tests for plan conversion between markdown, HTML, and SQLite styles."""

from planager.cli import format_status_table, init_project, main, update_project
from planager.convert import (
    Phase,
    Plan,
    Step,
    collect_plans,
    load_sqlite,
    migrate_plans,
    parse_html,
    parse_markdown,
    plan_progress,
    render_html,
    render_markdown,
    save_sqlite,
)

SAMPLE_MD = """\
---
feature: auth
title: User Authentication
status: in-progress
created: 2026-04-18
updated: 2026-04-19
---

## Context

Email/password auth with sessions.

## Phase 1: Schema

Set up the tables.

- [x] Create users table
- [ ] Add sessions table

## Phase 2: API

- [ ] POST /login

## Notes

Using bcrypt for hashing.
"""


def sample_plan() -> Plan:
    return Plan(
        feature="auth",
        title="User Authentication",
        status="in-progress",
        context="Email/password auth with sessions.",
        notes="Using bcrypt for hashing.",
        created="2026-04-18",
        updated="2026-04-19",
        phases=[
            Phase(
                title="Schema",
                description="Set up the tables.",
                steps=[Step("Create users table", done=True), Step("Add sessions table")],
            ),
            Phase(title="API", steps=[Step("POST /login")]),
        ],
    )


# ---------------------------------------------------------------------------
# Parsers and renderers
# ---------------------------------------------------------------------------


class TestMarkdown:
    def test_parse(self):
        plan = parse_markdown(SAMPLE_MD)
        assert plan == sample_plan()

    def test_round_trip(self):
        plan = sample_plan()
        assert parse_markdown(render_markdown(plan)) == plan

    def test_parse_missing_frontmatter_uses_fallback(self):
        plan = parse_markdown("## Context\n\nHi.\n", fallback_feature="mystery")
        assert plan.feature == "mystery"
        assert plan.status == "planning"
        assert plan.context == "Hi."


class TestHtml:
    def test_round_trip(self):
        plan = sample_plan()
        assert parse_html(render_html(plan)) == plan

    def test_render_marks_steps(self):
        html_text = render_html(sample_plan())
        assert '<div class="step done" data-status="done">Create users table</div>' in html_text
        assert '<div class="step" data-status="pending">Add sessions table</div>' in html_text

    def test_render_escapes(self):
        plan = Plan(feature="x", title="a < b", phases=[Phase("P", steps=[Step("use <div>")])])
        html_text = render_html(plan)
        assert "a &lt; b" in html_text
        assert "use &lt;div&gt;" in html_text
        assert parse_html(html_text).phases[0].steps[0].description == "use <div>"

    def test_markdown_to_html_to_markdown(self):
        plan = parse_markdown(SAMPLE_MD)
        assert parse_html(render_html(plan)) == plan


class TestSqlite:
    def test_round_trip(self, tmp_path):
        db = tmp_path / "plans.db"
        plan = sample_plan()
        save_sqlite(db, [plan])
        assert load_sqlite(db) == [plan]

    def test_archived_round_trip(self, tmp_path):
        db = tmp_path / "plans.db"
        plan = sample_plan()
        plan.archived = True
        save_sqlite(db, [plan])
        assert load_sqlite(db)[0].archived is True

    def test_resave_replaces_existing_plan(self, tmp_path):
        db = tmp_path / "plans.db"
        save_sqlite(db, [sample_plan()])
        updated = sample_plan()
        updated.status = "done"
        updated.phases[0].steps[1].done = True
        save_sqlite(db, [updated])
        assert load_sqlite(db) == [updated]


# ---------------------------------------------------------------------------
# migrate_plans
# ---------------------------------------------------------------------------


class TestMigratePlans:
    def test_same_style_is_noop(self, tmp_path):
        assert migrate_plans(tmp_path, "markdown", "markdown") == []

    def test_missing_dir_is_noop(self, tmp_path):
        assert migrate_plans(tmp_path / "nope", "markdown", "html") == []

    def test_markdown_to_html(self, tmp_path):
        (tmp_path / "auth.md").write_text(SAMPLE_MD)
        actions = migrate_plans(tmp_path, "markdown", "html")
        assert not (tmp_path / "auth.md").exists()
        assert (tmp_path / "auth.html").exists()
        assert any("auth.html" in a for a in actions)
        assert parse_html((tmp_path / "auth.html").read_text()) == parse_markdown(SAMPLE_MD)

    def test_html_to_markdown(self, tmp_path):
        (tmp_path / "auth.html").write_text(render_html(sample_plan()))
        migrate_plans(tmp_path, "html", "markdown")
        assert not (tmp_path / "auth.html").exists()
        assert parse_markdown((tmp_path / "auth.md").read_text()) == sample_plan()

    def test_archived_plans_stay_archived(self, tmp_path):
        done = tmp_path / "done"
        done.mkdir()
        (done / "auth.md").write_text(SAMPLE_MD)
        migrate_plans(tmp_path, "markdown", "html")
        assert (done / "auth.html").exists()
        assert not (done / "auth.md").exists()

    def test_markdown_to_sqlite(self, tmp_path):
        (tmp_path / "auth.md").write_text(SAMPLE_MD)
        done = tmp_path / "done"
        done.mkdir()
        (done / "old.md").write_text(SAMPLE_MD.replace("feature: auth", "feature: old"))
        migrate_plans(tmp_path, "markdown", "sqlite")

        assert not (tmp_path / "auth.md").exists()
        assert not done.exists()  # emptied and removed
        plans = {p.feature: p for p in load_sqlite(tmp_path / "plans.db")}
        assert plans["auth"].archived is False
        assert plans["old"].archived is True
        assert plans["auth"].phases[0].steps[0].done is True

    def test_sqlite_to_markdown(self, tmp_path):
        active = sample_plan()
        archived = sample_plan()
        archived.feature = "old"
        archived.archived = True
        save_sqlite(tmp_path / "plans.db", [active, archived])

        migrate_plans(tmp_path, "sqlite", "markdown")
        assert not (tmp_path / "plans.db").exists()
        assert parse_markdown((tmp_path / "auth.md").read_text()) == active
        assert (tmp_path / "done" / "old.md").exists()


# ---------------------------------------------------------------------------
# CLI style switching
# ---------------------------------------------------------------------------


class TestCliStyleSwitch:
    def test_update_style_switch_migrates_plans(self, tmp_path):
        init_project(tmp_path, "claude", style="markdown")
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)

        installed, actions = update_project(tmp_path, style="html")
        assert installed == ["claude"]
        assert (tmp_path / ".plans" / "auth.html").exists()
        assert not (tmp_path / ".plans" / "auth.md").exists()
        assert "<feature-slug>.html" in (tmp_path / "CLAUDE.md").read_text()

    def test_update_without_style_does_not_migrate(self, tmp_path):
        init_project(tmp_path, "claude", style="markdown")
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)
        update_project(tmp_path)
        assert (tmp_path / ".plans" / "auth.md").exists()

    def test_init_style_switch_migrates_plans(self, tmp_path):
        main(["init", "claude", "--path", str(tmp_path)])
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)

        ret = main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        assert ret == 0
        assert not (tmp_path / ".plans" / "auth.md").exists()
        plans = load_sqlite(tmp_path / ".plans" / "plans.db")
        assert plans[0].feature == "auth"
        assert "plans.db" in (tmp_path / "CLAUDE.md").read_text()

    def test_reinit_without_style_preserves_existing_style(self, tmp_path):
        main(["init", "claude", "--style", "html", "--path", str(tmp_path)])
        (tmp_path / ".plans" / "auth.html").write_text(render_html(sample_plan()))

        ret = main(["init", "claude", "--path", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / ".plans" / "auth.html").exists()
        assert "<feature-slug>.html" in (tmp_path / "CLAUDE.md").read_text()

    def test_init_style_switch_updates_other_targets(self, tmp_path):
        main(["init", "claude", "--path", str(tmp_path)])
        main(["init", "pi", "--path", str(tmp_path)])

        main(["init", "claude", "--style", "html", "--path", str(tmp_path)])
        assert "<feature-slug>.html" in (tmp_path / "CLAUDE.md").read_text()
        assert "<feature-slug>.html" in (tmp_path / "AGENTS.md").read_text()

    def test_sqlite_to_markdown_via_update(self, tmp_path):
        init_project(tmp_path, "claude", style="sqlite")
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])

        update_project(tmp_path, style="markdown")
        assert not (tmp_path / ".plans" / "plans.db").exists()
        assert (tmp_path / ".plans" / "auth.md").exists()
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "plans.db" not in content
        assert "<feature-slug>.md" in content

    def test_sqlite_export_preserves_step_status(self, tmp_path):
        init_project(tmp_path, "claude", style="sqlite")
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])

        update_project(tmp_path, style="markdown")
        plan = parse_markdown((tmp_path / ".plans" / "auth.md").read_text())
        assert plan == sample_plan()

    def test_unparseable_db_style_file_left_in_place(self, tmp_path):
        init_project(tmp_path, "claude", style="markdown")
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)
        (tmp_path / ".plans" / "notes.txt").write_text("not a plan")

        update_project(tmp_path, style="html")
        assert (tmp_path / ".plans" / "notes.txt").exists()


# ---------------------------------------------------------------------------
# planager status
# ---------------------------------------------------------------------------


class TestPlanProgress:
    def test_counts_and_current_phase(self):
        assert plan_progress(sample_plan()) == (1, 3, 1)

    def test_all_done(self):
        plan = sample_plan()
        for phase in plan.phases:
            for step in phase.steps:
                step.done = True
        assert plan_progress(plan) == (3, 3, None)

    def test_no_steps(self):
        assert plan_progress(Plan(feature="x", title="X")) == (0, 0, None)

    def test_current_phase_skips_completed_phases(self):
        plan = sample_plan()
        for step in plan.phases[0].steps:
            step.done = True
        assert plan_progress(plan) == (2, 3, 2)


class TestCollectPlans:
    def test_reads_all_styles_together(self, tmp_path):
        (tmp_path / "auth.md").write_text(SAMPLE_MD)
        html_plan = sample_plan()
        html_plan.feature = "ui"
        (tmp_path / "ui.html").write_text(render_html(html_plan))
        db_plan = sample_plan()
        db_plan.feature = "db"
        save_sqlite(tmp_path / "plans.db", [db_plan])

        features = {p.feature for p in collect_plans(tmp_path)}
        assert features == {"auth", "ui", "db"}

    def test_excludes_archived_by_default(self, tmp_path):
        done = tmp_path / "done"
        done.mkdir()
        (done / "old.md").write_text(SAMPLE_MD.replace("feature: auth", "feature: old"))
        archived = sample_plan()
        archived.feature = "shipped"
        archived.archived = True
        save_sqlite(tmp_path / "plans.db", [archived])

        assert collect_plans(tmp_path) == []
        features = {p.feature for p in collect_plans(tmp_path, include_archived=True)}
        assert features == {"old", "shipped"}


class TestStatusCommand:
    def test_table_output(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)
        capsys.readouterr()

        ret = main(["status", "--path", str(tmp_path)])
        assert ret == 0
        out = capsys.readouterr().out
        lines = out.strip().splitlines()
        assert lines[0].split() == ["Feature", "Status", "Progress"]
        assert "auth" in lines[2]
        assert "in-progress" in lines[2]
        assert "Phase 1: 1/3" in lines[2]

    def test_orders_by_status(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        cases = (("zdone", "done"), ("mplan", "planning"), ("awork", "in-progress"))
        for feature, status in cases:
            text = SAMPLE_MD.replace("feature: auth", f"feature: {feature}").replace(
                "status: in-progress", f"status: {status}"
            )
            (tmp_path / ".plans" / f"{feature}.md").write_text(text)

        main(["status", "--path", str(tmp_path)])
        out = capsys.readouterr().out
        assert out.index("awork") < out.index("mplan") < out.index("zdone")

    def test_sqlite_style(self, tmp_path, capsys):
        main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])

        ret = main(["status", "--path", str(tmp_path)])
        assert ret == 0
        assert "auth" in capsys.readouterr().out

    def test_all_flag_includes_archived(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        (tmp_path / ".plans" / "done" / "old.md").write_text(
            SAMPLE_MD.replace("feature: auth", "feature: old")
        )

        main(["status", "--path", str(tmp_path)])
        assert "old" not in capsys.readouterr().out

        main(["status", "--all", "--path", str(tmp_path)])
        out = capsys.readouterr().out
        assert "old" in out
        assert "(archived)" in out

    def test_blocked_plan_shows_last_note(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        text = SAMPLE_MD.replace("status: in-progress", "status: blocked").replace(
            "Using bcrypt for hashing.", "Waiting on the auth vendor API key."
        )
        (tmp_path / ".plans" / "auth.md").write_text(text)

        main(["status", "--path", str(tmp_path)])
        out = capsys.readouterr().out
        assert "auth is blocked: Waiting on the auth vendor API key." in out

    def test_no_plans(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        ret = main(["status", "--path", str(tmp_path)])
        assert ret == 0
        assert "No plans found" in capsys.readouterr().out

    def test_missing_plans_dir(self, tmp_path, capsys):
        ret = main(["status", "--path", str(tmp_path)])
        assert ret == 1
        assert "No .plans/ directory" in capsys.readouterr().err

    def test_format_status_table_alignment(self):
        plans = [sample_plan(), Plan(feature="x", title="X", status="planning")]
        table = format_status_table(plans)
        lines = table.splitlines()
        assert set(lines[1]) <= {"─", " "}
        status_col = lines[0].index("Status")
        assert lines[2][status_col:].startswith("in-progress")  # auth sorts first
        assert lines[3][status_col:].startswith("planning")
        assert "no steps" in table
