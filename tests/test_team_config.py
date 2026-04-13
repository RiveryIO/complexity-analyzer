"""Tests for team config module."""

from cli.team_config import (
    get_team_for_developer,
    get_team_for_repo,
    load_team_mapping,
    _parse_team_assignments_text,
)


def test_parse_team_assignments_text():
    """Test parsing [Team] dev1 dev2 format."""
    content = """
[Platform] alice bob charlie
[Backend] dave eve
[Frontend] frank grace
"""
    result = _parse_team_assignments_text(content)
    assert result == {
        "alice": "Platform",
        "bob": "Platform",
        "charlie": "Platform",
        "dave": "Backend",
        "eve": "Backend",
        "frank": "Frontend",
        "grace": "Frontend",
    }


def test_load_team_mapping_empty(tmp_path, monkeypatch):
    """Test load_team_mapping when no config exists."""
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {}


def test_load_team_mapping_text_format(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.yaml with [Team] dev1 dev2 format."""
    teams_file = tmp_path / "teams.yaml"
    teams_file.write_text(
        """
[Platform] alice bob charlie
[Backend] dave eve
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {
        "alice": "Platform",
        "bob": "Platform",
        "charlie": "Platform",
        "dave": "Backend",
        "eve": "Backend",
    }


def test_load_team_mapping_yaml_list_format(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.yaml with TeamName: [dev1, dev2]."""
    teams_file = tmp_path / "teams.yaml"
    teams_file.write_text(
        """
Platform: [alice, bob, charlie]
Backend: [dave, eve]
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {
        "alice": "Platform",
        "bob": "Platform",
        "charlie": "Platform",
        "dave": "Backend",
        "eve": "Backend",
    }


def test_load_team_mapping_teams_txt(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.txt."""
    teams_file = tmp_path / "teams.txt"
    teams_file.write_text("[Platform] alice bob\n[Backend] dave")
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    expected = {"alice": "Platform", "bob": "Platform", "dave": "Backend"}
    assert mapping == expected


def test_load_team_mapping_github_teams_cfg(tmp_path, monkeypatch):
    """Test load_team_mapping from github-teams.cfg (preferred filename)."""
    teams_file = tmp_path / "github-teams.cfg"
    teams_file.write_text(
        """
[Platform]
alice
bob
[Backend]
dave
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    expected = {
        "alice": "Platform",
        "bob": "Platform",
        "dave": "Backend",
    }
    assert mapping == expected


def test_load_team_mapping_merges_multiple_files(tmp_path, monkeypatch):
    """Test that multiple team config files are merged together."""
    (tmp_path / "github-teams.cfg").write_text("[Alpha] alice\n[Beta] bob")
    (tmp_path / "teams.yaml").write_text("[Gamma] charlie\n[Delta] dave")
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    # All developers from all files should be present
    assert mapping["alice"] == "Alpha"
    assert mapping["bob"] == "Beta"
    assert mapping["charlie"] == "Gamma"
    assert mapping["dave"] == "Delta"


def test_load_team_mapping_teams_cfg_multiline(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.cfg with developers on separate lines."""
    teams_file = tmp_path / "teams.cfg"
    teams_file.write_text(
        """
[Platform]
alice
bob
charlie
[Backend]
dave eve
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    expected = {
        "alice": "Platform",
        "bob": "Platform",
        "charlie": "Platform",
        "dave": "Backend",
        "eve": "Backend",
    }
    assert mapping == expected


def test_get_team_for_developer_with_mapping(tmp_path, monkeypatch):
    """Test get_team_for_developer when mapping exists."""
    teams_file = tmp_path / "teams.yaml"
    teams_file.write_text("[Platform] alice bob\n[Backend] dave")
    monkeypatch.chdir(tmp_path)
    assert get_team_for_developer("alice") == "Platform"
    assert get_team_for_developer("dave") == "Backend"


def test_get_team_for_developer_no_mapping(tmp_path, monkeypatch):
    """Test get_team_for_developer when developer not in mapping."""
    monkeypatch.chdir(tmp_path)
    assert get_team_for_developer("unknown") == ""


def test_get_team_for_developer_empty(tmp_path, monkeypatch):
    """Test get_team_for_developer with empty string."""
    monkeypatch.chdir(tmp_path)
    assert get_team_for_developer("") == ""
    assert get_team_for_developer("   ") == ""


def test_get_team_for_developer_explicit_mapping():
    """Test get_team_for_developer with explicit mapping dict."""
    mapping = {"alice": "Platform", "bob": "Backend"}
    assert get_team_for_developer("alice", mapping=mapping) == "Platform"
    assert get_team_for_developer("bob", mapping=mapping) == "Backend"
    assert get_team_for_developer("unknown", mapping=mapping) == ""


def test_get_team_for_repo_deprecated_returns_empty():
    """get_team_for_repo is deprecated; always returns empty string."""
    assert get_team_for_repo("org", "repo") == ""
    assert get_team_for_repo("org", "repo", mapping={"x": "y"}) == ""


def test_load_team_mapping_bitbucket_teams_cfg(tmp_path, monkeypatch):
    """Test load_team_mapping from bitbucket-teams.cfg."""
    teams_file = tmp_path / "bitbucket-teams.cfg"
    teams_file.write_text(
        """
[Core]
alice_bb
bob_bb

[Backend]
charlie_bb
dave_bb
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {
        "alice_bb": "Core",
        "bob_bb": "Core",
        "charlie_bb": "Backend",
        "dave_bb": "Backend",
    }


def test_load_team_mapping_merges_github_and_bitbucket(tmp_path, monkeypatch):
    """Test that both github-teams.cfg and bitbucket-teams.cfg are merged."""
    github_file = tmp_path / "github-teams.cfg"
    github_file.write_text(
        """
[Core]
alice
bob
"""
    )
    bitbucket_file = tmp_path / "bitbucket-teams.cfg"
    bitbucket_file.write_text(
        """
[Core]
alice_bb
bob_bb

[Backend]
charlie_bb
"""
    )
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {
        "alice": "Core",
        "bob": "Core",
        "alice_bb": "Core",
        "bob_bb": "Core",
        "charlie_bb": "Backend",
    }
