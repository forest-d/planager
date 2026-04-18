"""Tests for planager init command."""


from planager.cli import SNIPPET_MARKER, init_project, main


class TestInitProject:
    def test_creates_plans_dir(self, tmp_path):
        init_project(tmp_path)
        assert (tmp_path / ".plans").is_dir()

    def test_creates_plan_skill(self, tmp_path):
        init_project(tmp_path)
        skill = tmp_path / ".claude" / "skills" / "plan" / "SKILL.md"
        assert skill.exists()
        assert "/plan" in skill.read_text()

    def test_creates_plan_status_skill(self, tmp_path):
        init_project(tmp_path)
        skill = tmp_path / ".claude" / "skills" / "plan-status" / "SKILL.md"
        assert skill.exists()
        assert "/plan-status" in skill.read_text()

    def test_creates_claude_md(self, tmp_path):
        init_project(tmp_path)
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert SNIPPET_MARKER in content
        assert "Feature Plans" in content

    def test_creates_agents_md(self, tmp_path):
        init_project(tmp_path)
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert SNIPPET_MARKER in content
        assert "Feature Plans" in content

    def test_appends_to_existing_claude_md(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nExisting content.\n")

        init_project(tmp_path)

        content = claude_md.read_text()
        assert content.startswith("# My Project")
        assert "Existing content." in content
        assert SNIPPET_MARKER in content

    def test_appends_to_existing_agents_md(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Agent Instructions\n\nExisting.\n")

        init_project(tmp_path)

        content = agents_md.read_text()
        assert content.startswith("# Agent Instructions")
        assert "Existing." in content
        assert SNIPPET_MARKER in content

    def test_idempotent(self, tmp_path):
        actions1 = init_project(tmp_path)
        actions2 = init_project(tmp_path)

        assert all("Created" in a for a in actions1)
        assert all("skipped" in a for a in actions2)

        # Content not duplicated
        for filename in ("CLAUDE.md", "AGENTS.md"):
            content = (tmp_path / filename).read_text()
            assert content.count(SNIPPET_MARKER) == 1

    def test_returns_actions(self, tmp_path):
        actions = init_project(tmp_path)
        assert len(actions) == 5
        assert any(".plans/" in a for a in actions)
        assert any("plan/SKILL.md" in a for a in actions)
        assert any("plan-status/SKILL.md" in a for a in actions)
        assert any("CLAUDE.md" in a for a in actions)
        assert any("AGENTS.md" in a for a in actions)


class TestMain:
    def test_init_subcommand(self, tmp_path):
        ret = main(["init", "--path", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / ".plans").is_dir()
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").exists()

    def test_no_subcommand_shows_help(self, capsys):
        ret = main([])
        assert ret == 1

    def test_bad_path(self, tmp_path):
        ret = main(["init", "--path", str(tmp_path / "nonexistent")])
        assert ret == 1
