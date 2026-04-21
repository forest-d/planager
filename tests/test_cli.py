"""Tests for planager init command."""

import textwrap

import pytest

from planager.cli import SNIPPET_MARKER, TARGETS, init_project, main


# ---------------------------------------------------------------------------
# Claude target
# ---------------------------------------------------------------------------


class TestInitClaude:
    def test_creates_plans_dir(self, tmp_path):
        init_project(tmp_path, "claude")
        assert (tmp_path / ".plans").is_dir()

    def test_creates_planager_skill(self, tmp_path):
        init_project(tmp_path, "claude")
        skill = tmp_path / ".claude" / "skills" / "planager" / "SKILL.md"
        assert skill.exists()
        content = skill.read_text()
        assert "/planager" in content

    def test_creates_planager_status_skill(self, tmp_path):
        init_project(tmp_path, "claude")
        skill = tmp_path / ".claude" / "skills" / "planager-status" / "SKILL.md"
        assert skill.exists()
        assert "/planager-status" in skill.read_text()

    def test_claude_skill_has_no_frontmatter(self, tmp_path):
        init_project(tmp_path, "claude")
        skill = tmp_path / ".claude" / "skills" / "planager" / "SKILL.md"
        content = skill.read_text()
        assert not content.startswith("---")

    def test_creates_claude_md(self, tmp_path):
        init_project(tmp_path, "claude")
        claude_md = tmp_path / "CLAUDE.md"
        assert claude_md.exists()
        content = claude_md.read_text()
        assert SNIPPET_MARKER in content
        assert "Feature Plans" in content

    def test_appends_to_existing_claude_md(self, tmp_path):
        claude_md = tmp_path / "CLAUDE.md"
        claude_md.write_text("# My Project\n\nExisting content.\n")
        init_project(tmp_path, "claude")
        content = claude_md.read_text()
        assert content.startswith("# My Project")
        assert "Existing content." in content
        assert SNIPPET_MARKER in content

    def test_idempotent(self, tmp_path):
        actions1 = init_project(tmp_path, "claude")
        actions2 = init_project(tmp_path, "claude")
        assert all("Created" in a for a in actions1)
        assert all("skipped" in a for a in actions2)
        content = (tmp_path / "CLAUDE.md").read_text()
        assert content.count(SNIPPET_MARKER) == 1

    def test_returns_actions(self, tmp_path):
        actions = init_project(tmp_path, "claude")
        assert len(actions) == 4
        assert any(".plans/" in a for a in actions)
        assert any("planager/SKILL.md" in a for a in actions)
        assert any("planager-status/SKILL.md" in a for a in actions)
        assert any("CLAUDE.md" in a for a in actions)


# ---------------------------------------------------------------------------
# Pi target
# ---------------------------------------------------------------------------


class TestInitPi:
    def test_creates_plans_dir(self, tmp_path):
        init_project(tmp_path, "pi")
        assert (tmp_path / ".plans").is_dir()

    def test_creates_planager_skill(self, tmp_path):
        init_project(tmp_path, "pi")
        skill = tmp_path / ".pi" / "skills" / "planager" / "SKILL.md"
        assert skill.exists()
        content = skill.read_text()
        assert "/skill:planager" in content

    def test_creates_planager_status_skill(self, tmp_path):
        init_project(tmp_path, "pi")
        skill = tmp_path / ".pi" / "skills" / "planager-status" / "SKILL.md"
        assert skill.exists()
        assert "/skill:planager-status" in skill.read_text()

    def test_pi_skill_has_frontmatter(self, tmp_path):
        init_project(tmp_path, "pi")
        for skill_name in ("planager", "planager-status"):
            skill = tmp_path / ".pi" / "skills" / skill_name / "SKILL.md"
            content = skill.read_text()
            assert content.startswith("---\n")
            assert "name:" in content
            assert "description:" in content

    def test_pi_skill_name_matches_directory(self, tmp_path):
        init_project(tmp_path, "pi")
        for skill_name in ("planager", "planager-status"):
            skill = tmp_path / ".pi" / "skills" / skill_name / "SKILL.md"
            content = skill.read_text()
            assert f"name: {skill_name}" in content

    def test_creates_agents_md(self, tmp_path):
        init_project(tmp_path, "pi")
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert SNIPPET_MARKER in content
        assert "Feature Plans" in content

    def test_appends_to_existing_agents_md(self, tmp_path):
        agents_md = tmp_path / "AGENTS.md"
        agents_md.write_text("# Agent Instructions\n\nExisting.\n")
        init_project(tmp_path, "pi")
        content = agents_md.read_text()
        assert content.startswith("# Agent Instructions")
        assert "Existing." in content
        assert SNIPPET_MARKER in content

    def test_idempotent(self, tmp_path):
        init_project(tmp_path, "pi")
        init_project(tmp_path, "pi")
        content = (tmp_path / "AGENTS.md").read_text()
        assert content.count(SNIPPET_MARKER) == 1

    def test_returns_actions(self, tmp_path):
        actions = init_project(tmp_path, "pi")
        assert len(actions) == 4
        assert any(".plans/" in a for a in actions)
        assert any("planager/SKILL.md" in a for a in actions)
        assert any("planager-status/SKILL.md" in a for a in actions)
        assert any("AGENTS.md" in a for a in actions)


# ---------------------------------------------------------------------------
# Codex target
# ---------------------------------------------------------------------------


class TestInitCodex:
    def test_creates_plans_dir(self, tmp_path):
        init_project(tmp_path, "codex")
        assert (tmp_path / ".plans").is_dir()

    def test_creates_planager_skill(self, tmp_path):
        init_project(tmp_path, "codex")
        skill = tmp_path / ".codex" / "skills" / "planager" / "SKILL.md"
        assert skill.exists()

    def test_creates_planager_status_skill(self, tmp_path):
        init_project(tmp_path, "codex")
        skill = tmp_path / ".codex" / "skills" / "planager-status" / "SKILL.md"
        assert skill.exists()

    def test_codex_skill_has_frontmatter(self, tmp_path):
        init_project(tmp_path, "codex")
        for skill_name in ("planager", "planager-status"):
            skill = tmp_path / ".codex" / "skills" / skill_name / "SKILL.md"
            content = skill.read_text()
            assert content.startswith("---\n")
            assert "name:" in content
            assert "description:" in content

    def test_codex_skill_name_matches_directory(self, tmp_path):
        init_project(tmp_path, "codex")
        for skill_name in ("planager", "planager-status"):
            skill = tmp_path / ".codex" / "skills" / skill_name / "SKILL.md"
            content = skill.read_text()
            assert f"name: {skill_name}" in content

    def test_creates_agents_md(self, tmp_path):
        init_project(tmp_path, "codex")
        agents_md = tmp_path / "AGENTS.md"
        assert agents_md.exists()
        content = agents_md.read_text()
        assert SNIPPET_MARKER in content

    def test_returns_actions(self, tmp_path):
        actions = init_project(tmp_path, "codex")
        assert len(actions) == 4


# ---------------------------------------------------------------------------
# Cross-target additivity
# ---------------------------------------------------------------------------


class TestAdditivity:
    def test_pi_then_claude(self, tmp_path):
        """Both skill dirs exist, both instruction files exist."""
        init_project(tmp_path, "pi")
        init_project(tmp_path, "claude")

        assert (tmp_path / ".pi" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / ".claude" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_pi_then_codex_no_duplicate_agents_md(self, tmp_path):
        """AGENTS.md snippet is not duplicated when both pi and codex init."""
        init_project(tmp_path, "pi")
        init_project(tmp_path, "codex")

        assert (tmp_path / ".pi" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / ".codex" / "skills" / "planager" / "SKILL.md").exists()
        content = (tmp_path / "AGENTS.md").read_text()
        assert content.count(SNIPPET_MARKER) == 1

    def test_all_three(self, tmp_path):
        """All three targets can coexist."""
        init_project(tmp_path, "pi")
        init_project(tmp_path, "claude")
        init_project(tmp_path, "codex")

        assert (tmp_path / ".pi" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / ".claude" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / ".codex" / "skills" / "planager" / "SKILL.md").exists()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / "CLAUDE.md").exists()
        assert (tmp_path / "AGENTS.md").read_text().count(SNIPPET_MARKER) == 1
        assert (tmp_path / "CLAUDE.md").read_text().count(SNIPPET_MARKER) == 1


# ---------------------------------------------------------------------------
# CLI main()
# ---------------------------------------------------------------------------


class TestMain:
    def test_init_claude(self, tmp_path):
        ret = main(["init", "claude", "--path", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / ".plans").is_dir()
        assert (tmp_path / "CLAUDE.md").exists()

    def test_init_pi(self, tmp_path):
        ret = main(["init", "pi", "--path", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / ".plans").is_dir()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".pi" / "skills" / "planager" / "SKILL.md").exists()

    def test_init_codex(self, tmp_path):
        ret = main(["init", "codex", "--path", str(tmp_path)])
        assert ret == 0
        assert (tmp_path / ".plans").is_dir()
        assert (tmp_path / "AGENTS.md").exists()
        assert (tmp_path / ".codex" / "skills" / "planager" / "SKILL.md").exists()

    def test_no_subcommand_shows_help(self, capsys):
        ret = main([])
        assert ret == 1

    def test_no_target_non_tty_returns_error(self, capsys):
        """Without a tty, omitting target should fail gracefully."""
        ret = main(["init"])
        assert ret == 1
        assert "no target specified" in capsys.readouterr().err

    def test_bad_path(self, tmp_path):
        ret = main(["init", "claude", "--path", str(tmp_path / "nonexistent")])
        assert ret == 1

    def test_invalid_target(self, tmp_path):
        with pytest.raises(SystemExit) as exc_info:
            main(["init", "invalid", "--path", str(tmp_path)])
        assert exc_info.value.code != 0
