"""Tests for verify-settings module."""

import pytest
from pathlib import Path

from cli.verify import run_verify_settings


def test_verify_settings_csv_missing(tmp_path, monkeypatch):
    """Test verify when CSV does not exist and csv_required=True."""
    monkeypatch.chdir(tmp_path)
    results = run_verify_settings(
        csv_path=tmp_path / "nonexistent.csv",
        csv_required=True,
    )
    assert any(name == "CSV path" and not ok for name, ok, _ in results)


def test_verify_settings_csv_missing_optional(tmp_path, monkeypatch):
    """Test verify when CSV does not exist but csv_required=False (default)."""
    monkeypatch.chdir(tmp_path)
    results = run_verify_settings(csv_path=tmp_path / "nonexistent.csv")
    csv_check = next((r for r in results if r[0] == "CSV path"), None)
    assert csv_check is not None
    assert csv_check[1] is True  # Passes when optional


def test_verify_settings_csv_exists(tmp_path, monkeypatch):
    """Test verify when CSV exists with full schema."""
    monkeypatch.chdir(tmp_path)
    csv_file = tmp_path / "report.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,,,100,50,Test\n"
    )
    results = run_verify_settings(csv_path=csv_file)
    csv_check = next((r for r in results if r[0] == "CSV path"), None)
    assert csv_check is not None
    assert csv_check[1] is True
    cols_check = next((r for r in results if r[0] == "CSV columns"), None)
    assert cols_check is not None
    assert cols_check[1] is True


def test_verify_settings_csv_missing_columns(tmp_path, monkeypatch):
    """Test verify when CSV has legacy columns only."""
    monkeypatch.chdir(tmp_path)
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text("pr_url,complexity,explanation,author\nhttps://github.com/org/repo/pull/1,5,Test,alice\n")
    results = run_verify_settings(csv_path=csv_file)
    cols_check = next((r for r in results if r[0] == "CSV columns"), None)
    assert cols_check is not None
    assert cols_check[1] is False
    assert "migrate-csv" in cols_check[2]
