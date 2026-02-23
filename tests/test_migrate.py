"""Tests for migrate module."""

import csv
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from cli.migrate import run_migration, _load_csv_rows, _needs_enrichment


def test_load_csv_rows(tmp_path):
    """Test loading CSV rows with normalization."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,2024-01-15T10:00:00Z,2024-01-10T09:00:00Z,100,50,Test\n"
    )
    rows = _load_csv_rows(csv_file)
    assert len(rows) == 1
    assert rows[0]["pr_url"] == "https://github.com/org/repo/pull/1"
    assert rows[0]["complexity"] == "5"
    assert rows[0]["developer"] == "alice"
    assert rows[0]["merged_at"] == "2024-01-15T10:00:00Z"


def test_load_csv_rows_legacy(tmp_path):
    """Test loading legacy CSV (author instead of developer)."""
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text(
        "pr_url,complexity,explanation,author\n"
        "https://github.com/org/repo/pull/1,5,Test,alice\n"
    )
    rows = _load_csv_rows(csv_file)
    assert len(rows) == 1
    assert rows[0].get("developer") == "alice" or rows[0].get("author") == "alice"


def test_needs_enrichment():
    """Test _needs_enrichment logic."""
    assert _needs_enrichment({"merged_at": "", "created_at": "", "lines_added": "", "lines_deleted": ""}) is True
    assert _needs_enrichment({"merged_at": "x", "created_at": "x", "lines_added": "10", "lines_deleted": "5"}) is False
    assert _needs_enrichment({"merged_at": "x", "created_at": "", "lines_added": "10", "lines_deleted": "5"}) is True


@patch("cli.migrate.fetch_pr_metadata")
@patch("cli.migrate.wait_for_rate_limit")
def test_run_migration_enriches_rows(mock_wait, mock_fetch, tmp_path):
    """Test run_migration enriches rows with GitHub metadata."""
    mock_wait.return_value = None
    mock_fetch.return_value = {
        "merged_at": "2024-01-15T10:00:00Z",
        "created_at": "2024-01-10T09:00:00Z",
        "additions": 100,
        "deletions": 50,
    }

    input_file = tmp_path / "input.csv"
    input_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,,,,,,,Test\n"
    )
    output_file = tmp_path / "output.csv"

    enriched = run_migration(
        input_path=input_file,
        output_path=output_file,
        token="test-token",
        sleep_seconds=0,
    )

    assert enriched == 1
    assert output_file.exists()
    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["merged_at"] == "2024-01-15T10:00:00Z"
        assert rows[0]["created_at"] == "2024-01-10T09:00:00Z"
        assert rows[0]["lines_added"] == "100"
        assert rows[0]["lines_deleted"] == "50"


@patch("cli.migrate.fetch_pr_metadata")
@patch("cli.migrate.wait_for_rate_limit")
def test_run_migration_skips_complete_rows(mock_wait, mock_fetch, tmp_path):
    """Test run_migration skips rows that already have all data."""
    mock_wait.return_value = None

    input_file = tmp_path / "input.csv"
    input_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,2024-01-15T10:00:00Z,2024-01-10T09:00:00Z,100,50,Test\n"
    )
    output_file = tmp_path / "output.csv"

    enriched = run_migration(
        input_path=input_file,
        output_path=output_file,
        token="test-token",
        sleep_seconds=0,
    )

    assert enriched == 0
    mock_fetch.assert_not_called()


def test_run_migration_file_not_found(tmp_path):
    """Test run_migration raises when input does not exist."""
    with pytest.raises(FileNotFoundError):
        run_migration(
            input_path=tmp_path / "nonexistent.csv",
            output_path=tmp_path / "output.csv",
        )
