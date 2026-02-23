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
    teams_file.write_text("""
[Platform] alice bob charlie
[Backend] dave eve
""")
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
    teams_file.write_text("""
Platform: [alice, bob, charlie]
Backend: [dave, eve]
""")
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


def test_load_team_mapping_teams_cfg_multiline(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.cfg with developers on separate lines."""
    teams_file = tmp_path / "teams.cfg"
    teams_file.write_text("""
[Platform]
alice
bob
charlie
[Backend]
dave eve
""")
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
