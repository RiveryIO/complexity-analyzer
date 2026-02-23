"""Tests for team config module."""

import pytest
from pathlib import Path

from cli.team_config import get_team_for_repo, load_team_mapping


def test_load_team_mapping_empty(tmp_path, monkeypatch):
    """Test load_team_mapping when no config exists."""
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {}


def test_load_team_mapping_yaml(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.yaml."""
    teams_file = tmp_path / "teams.yaml"
    teams_file.write_text("""
org/repo: "Platform"
other-org/backend: "Backend"
""")
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {"org/repo": "Platform", "other-org/backend": "Backend"}


def test_load_team_mapping_json(tmp_path, monkeypatch):
    """Test load_team_mapping from teams.json."""
    teams_file = tmp_path / "teams.json"
    teams_file.write_text('{"org/repo": "Platform", "other/backend": "Backend"}')
    monkeypatch.chdir(tmp_path)
    mapping = load_team_mapping(tmp_path)
    assert mapping == {"org/repo": "Platform", "other/backend": "Backend"}


def test_get_team_for_repo_with_mapping(tmp_path, monkeypatch):
    """Test get_team_for_repo when mapping exists."""
    teams_file = tmp_path / "teams.yaml"
    teams_file.write_text("org/repo: \"Platform\"\n")
    monkeypatch.chdir(tmp_path)
    assert get_team_for_repo("org", "repo") == "Platform"


def test_get_team_for_repo_no_mapping(tmp_path, monkeypatch):
    """Test get_team_for_repo when no mapping."""
    monkeypatch.chdir(tmp_path)
    assert get_team_for_repo("org", "unknown-repo") == ""


def test_get_team_for_repo_explicit_mapping():
    """Test get_team_for_repo with explicit mapping dict."""
    mapping = {"org/repo": "Platform"}
    assert get_team_for_repo("org", "repo", mapping=mapping) == "Platform"
    assert get_team_for_repo("other", "repo", mapping=mapping) == ""
