"""Tests for the plan browsing commands: planager show and planager grep."""

import json

from planager.cli import format_plan, format_plan_list, grep_plans, main
from planager.convert import Plan, render_html, save_sqlite

from tests.test_convert import SAMPLE_MD, sample_plan

# ---------------------------------------------------------------------------
# format_plan
# ---------------------------------------------------------------------------


class TestFormatPlan:
    def test_full_plan(self):
        text = format_plan(sample_plan())
        assert text.startswith("User Authentication (auth) — in-progress")
        assert "Created 2026-04-18 · Updated 2026-04-19" in text
        assert "Phase 1: Schema" in text
        assert "[x] Create users table" in text
        assert "[ ] Add sessions table" in text
        assert "Using bcrypt for hashing." in text

    def test_archived_marker(self):
        plan = sample_plan()
        plan.archived = True
        assert "(archived)" in format_plan(plan).splitlines()[0]

    def test_omits_empty_sections(self):
        text = format_plan(Plan(feature="x", title="X"))
        assert "Context" not in text
        assert "Notes" not in text


class TestFormatPlanList:
    def test_missing_updated_date_shows_dash(self):
        table = format_plan_list([Plan(feature="x", title="X")])
        row = table.splitlines()[2]
        assert row.split()[-1] == "-"

    def test_archived_marker(self):
        plan = sample_plan()
        plan.archived = True
        assert "in-progress (archived)" in format_plan_list([plan])


# ---------------------------------------------------------------------------
# planager show
# ---------------------------------------------------------------------------


class TestShowCommand:
    def _setup(self, tmp_path, capsys):
        main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])
        capsys.readouterr()

    def test_show_plan(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        ret = main(["show", "auth", "--path", str(tmp_path)])
        assert ret == 0
        out = capsys.readouterr().out
        assert "User Authentication (auth)" in out
        assert "[x] Create users table" in out

    def test_show_finds_archived_plan(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        plan = sample_plan()
        plan.archived = True
        save_sqlite(tmp_path / ".plans" / "plans.db", [plan])
        ret = main(["show", "auth", "--path", str(tmp_path)])
        assert ret == 0
        assert "(archived)" in capsys.readouterr().out

    def test_show_unknown_feature_lists_slugs(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        ret = main(["show", "nope", "--path", str(tmp_path)])
        assert ret == 1
        err = capsys.readouterr().err
        assert "No plan named 'nope'" in err
        assert "auth" in err

    def test_show_json(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        ret = main(["show", "auth", "--json", "--path", str(tmp_path)])
        assert ret == 0
        data = json.loads(capsys.readouterr().out)
        assert data["feature"] == "auth"
        assert data["phases"][0]["steps"][0] == {"description": "Create users table", "done": True}

    def test_list_mode(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        ret = main(["show", "--path", str(tmp_path)])
        assert ret == 0
        lines = capsys.readouterr().out.strip().splitlines()
        assert lines[0].split() == ["Feature", "Title", "Status", "Updated"]
        assert set(lines[1]) <= {"─", " "}
        row = lines[2]
        assert row.startswith("auth")
        assert "User Authentication" in row
        assert "in-progress" in row
        assert "2026-04-19" in row
        # columns align between header and rows
        for header in ("Title", "Status", "Updated"):
            col = lines[0].index(header)
            assert row[col - 1] == " " and row[col] != " "

    def test_list_mode_json(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        ret = main(["show", "--json", "--path", str(tmp_path)])
        assert ret == 0
        rows = json.loads(capsys.readouterr().out)
        assert rows == [
            {
                "feature": "auth",
                "title": "User Authentication",
                "status": "in-progress",
                "archived": False,
                "updated": "2026-04-19",
                "done_steps": 1,
                "total_steps": 3,
            }
        ]

    def test_list_mode_hides_archived_without_all(self, tmp_path, capsys):
        self._setup(tmp_path, capsys)
        plan = sample_plan()
        plan.archived = True
        save_sqlite(tmp_path / ".plans" / "plans.db", [plan])

        main(["show", "--path", str(tmp_path)])
        assert "auth" not in capsys.readouterr().out
        main(["show", "--all", "--path", str(tmp_path)])
        assert "auth" in capsys.readouterr().out

    def test_show_reads_file_styles_too(self, tmp_path, capsys):
        main(["init", "claude", "--path", str(tmp_path)])
        (tmp_path / ".plans" / "auth.md").write_text(SAMPLE_MD)
        html_plan = sample_plan()
        html_plan.feature = "ui"
        (tmp_path / ".plans" / "ui.html").write_text(render_html(html_plan))
        capsys.readouterr()

        assert main(["show", "auth", "--path", str(tmp_path)]) == 0
        assert main(["show", "ui", "--path", str(tmp_path)]) == 0

    def test_missing_plans_dir(self, tmp_path, capsys):
        ret = main(["show", "auth", "--path", str(tmp_path)])
        assert ret == 1
        assert "No .plans/ directory" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# planager grep
# ---------------------------------------------------------------------------


class TestGrepPlans:
    def test_matches_all_fields(self):
        matches = grep_plans([sample_plan()], "auth")
        joined = "\n".join(matches)
        assert "auth:feature: auth" in joined
        assert "auth:title: User Authentication" in joined
        assert "auth:context: Email/password auth with sessions." in joined

    def test_matches_steps_and_phases(self):
        matches = grep_plans([sample_plan()], "sessions table")
        assert matches == ["auth:phase 1 step 2: Add sessions table"]
        assert grep_plans([sample_plan()], "schema") == ["auth:phase 1: Schema"]

    def test_case_insensitive(self):
        assert grep_plans([sample_plan()], "BCRYPT") == ["auth:notes: Using bcrypt for hashing."]

    def test_no_match(self):
        assert grep_plans([sample_plan()], "kubernetes") == []


class TestGrepCommand:
    def test_grep_sqlite_plans(self, tmp_path, capsys):
        main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])
        capsys.readouterr()

        ret = main(["grep", "bcrypt", "--path", str(tmp_path)])
        assert ret == 0
        assert "auth:notes: Using bcrypt for hashing." in capsys.readouterr().out

    def test_grep_no_match_exits_nonzero(self, tmp_path, capsys):
        main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        save_sqlite(tmp_path / ".plans" / "plans.db", [sample_plan()])
        ret = main(["grep", "kubernetes", "--path", str(tmp_path)])
        assert ret == 1

    def test_grep_all_includes_archived(self, tmp_path, capsys):
        main(["init", "claude", "--style", "sqlite", "--path", str(tmp_path)])
        plan = sample_plan()
        plan.archived = True
        save_sqlite(tmp_path / ".plans" / "plans.db", [plan])
        capsys.readouterr()

        assert main(["grep", "bcrypt", "--path", str(tmp_path)]) == 1
        assert main(["grep", "bcrypt", "--all", "--path", str(tmp_path)]) == 0

    def test_grep_missing_plans_dir(self, tmp_path, capsys):
        ret = main(["grep", "x", "--path", str(tmp_path)])
        assert ret == 1
        assert "No .plans/ directory" in capsys.readouterr().err
