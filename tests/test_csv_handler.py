"""Tests for CSV handler module."""

import csv
import pytest
from pathlib import Path

from cli.csv_handler import (
    CSV_FIELDNAMES,
    CSVBatchWriter,
    load_completed_prs_from_csv,
)


def test_csv_fieldnames():
    """Test canonical schema includes all required columns."""
    required = [
        "pr_url", "complexity", "developer", "date", "team",
        "merged_at", "created_at", "lines_added", "lines_deleted", "explanation"
    ]
    for col in required:
        assert col in CSV_FIELDNAMES


def test_csv_batch_writer_add_row_full_schema(tmp_path):
    """Test add_row with full schema (new columns)."""
    output_file = tmp_path / "output.csv"
    writer = CSVBatchWriter(output_file)
    writer.add_row(
        "https://github.com/org/repo/pull/1",
        5,
        "Test explanation",
        "alice",
        developer="alice",
        date="2024-01-15",
        team="Platform",
        merged_at="2024-01-15T10:00:00Z",
        created_at="2024-01-10T09:00:00Z",
        lines_added=100,
        lines_deleted=50,
    )
    writer.close()

    assert output_file.exists()
    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["pr_url"] == "https://github.com/org/repo/pull/1"
        assert rows[0]["complexity"] == "5"
        assert rows[0]["developer"] == "alice"
        assert rows[0]["date"] == "2024-01-15"
        assert rows[0]["team"] == "Platform"
        assert rows[0]["merged_at"] == "2024-01-15T10:00:00Z"
        assert rows[0]["created_at"] == "2024-01-10T09:00:00Z"
        assert rows[0]["lines_added"] == "100"
        assert rows[0]["lines_deleted"] == "50"


def test_csv_batch_writer_add_row_legacy_signature(tmp_path):
    """Test add_row with legacy signature (author only)."""
    output_file = tmp_path / "output.csv"
    writer = CSVBatchWriter(output_file)
    writer.add_row(
        "https://github.com/org/repo/pull/2",
        3,
        "Legacy",
        "bob",
    )
    writer.close()

    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["developer"] == "bob"
        assert rows[0]["pr_url"] == "https://github.com/org/repo/pull/2"


def test_load_completed_prs_from_csv(tmp_path):
    """Test loading completed PRs from CSV with new schema."""
    csv_file = tmp_path / "report.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,,,100,50,Test\n"
        "https://github.com/org/repo/pull/2,3,bob,2024-01-16,Backend,,,30,20,Test\n"
    )

    completed = load_completed_prs_from_csv(csv_file)
    assert len(completed) == 2
    assert "https://github.com/org/repo/pull/1" in completed
    assert "https://github.com/org/repo/pull/2" in completed


def test_load_completed_prs_from_csv_legacy_columns(tmp_path):
    """Test loading from CSV with legacy column names."""
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text(
        "PR link,complexity,explanation,author\n"
        "https://github.com/org/repo/pull/1,5,Test,alice\n"
    )

    completed = load_completed_prs_from_csv(csv_file)
    assert len(completed) == 1
    assert "https://github.com/org/repo/pull/1" in completed


def test_load_completed_prs_from_csv_not_exists(tmp_path):
    """Test loading from non-existent file."""
    completed = load_completed_prs_from_csv(tmp_path / "nonexistent.csv")
    assert len(completed) == 0
