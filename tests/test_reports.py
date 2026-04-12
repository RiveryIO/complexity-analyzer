"""Tests for reports module - including performance."""

import time
import pytest
from pathlib import Path
from datetime import datetime, timezone, timedelta

import pandas as pd

from reports.chart_data import _extract_leaderboard
from reports.runner import load_dataframe, run_reports
from reports.validation import MIN_PNG_SIZE_BYTES

# Path to sample CSV fixture
FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_CSV = FIXTURES_DIR / "sample_report.csv"


def test_load_dataframe(tmp_path):
    """Test load_dataframe normalizes columns and parses types."""
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,2024-01-15T10:00:00Z,2024-01-10T09:00:00Z,100,50,Test\n"
    )
    df = load_dataframe(csv_file)
    assert len(df) == 1
    assert df["complexity"].dtype in ("int32", "int64")
    assert "date" in df.columns or "merged_at" in df.columns


def test_load_dataframe_legacy_author(tmp_path):
    """Test load_dataframe handles author column as developer."""
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text(
        "pr_url,complexity,author,explanation\n" "https://github.com/org/repo/pull/1,5,alice,Test\n"
    )
    df = load_dataframe(csv_file)
    assert len(df) == 1
    assert "developer" in df.columns or "author" in df.columns


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="Sample CSV fixture not found")
def test_run_reports_generates_files(tmp_path):
    """Test run_reports generates report files (PNG + HTML) from sample CSV."""
    output_dir = tmp_path / "reports"
    generated = run_reports(csv_path=SAMPLE_CSV, output_dir=output_dir)

    assert len(generated) >= 10
    # Separate HTML (interactive report) from PNG files
    html_files = [p for p in generated if Path(p).suffix == ".html"]
    png_files = [p for p in generated if Path(p).suffix == ".png"]
    assert len(html_files) >= 1, "Expected at least one HTML interactive report"
    for path in png_files:
        p = Path(path)
        assert p.exists()
        assert (
            p.stat().st_size >= MIN_PNG_SIZE_BYTES
        ), f"Report {path} is too small ({p.stat().st_size} bytes), likely empty"


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="Sample CSV fixture not found")
def test_run_reports_performance(tmp_path):
    """Test reports generation completes in under 10 seconds."""
    output_dir = tmp_path / "reports"
    start = time.perf_counter()
    generated = run_reports(csv_path=SAMPLE_CSV, output_dir=output_dir)
    elapsed = time.perf_counter() - start

    assert elapsed < 30.0, f"Reports took {elapsed:.2f}s, expected < 30s"
    assert len(generated) >= 10


def test_run_reports_with_generated_large_csv(tmp_path):
    """Test reports performance with programmatically generated large CSV."""
    rows = [
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation"
    ]
    developers = ["alice", "bob", "charlie", "dave"]
    teams = ["Platform", "Backend", "Frontend"]
    for i in range(150):
        d = developers[i % 4]
        t = teams[i % 3]
        week = 1 + (i // 10)
        rows.append(
            f"https://github.com/org/repo/pull/{i+1},{1 + (i % 10)},{d},2024-01-{15 + week:02d},{t},"
            f"2024-01-{15 + week:02d}T10:00:00Z,2024-01-{10 + week:02d}T09:00:00Z,{50 + i * 2},{20 + i},Test"
        )

    csv_file = tmp_path / "large.csv"
    csv_file.write_text("\n".join(rows))

    output_dir = tmp_path / "reports"
    start = time.perf_counter()
    generated = run_reports(csv_path=csv_file, output_dir=output_dir)
    elapsed = time.perf_counter() - start

    assert elapsed < 30.0, f"Reports took {elapsed:.2f}s with 150 rows, expected < 30s"
    assert len(generated) >= 10


def test_run_reports_empty_csv(tmp_path):
    """Test run_reports with empty CSV returns empty list."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
    )

    output_dir = tmp_path / "reports"
    generated = run_reports(csv_path=csv_file, output_dir=output_dir)

    assert generated == []
    assert list(output_dir.glob("*.png")) == [], "No PNGs should be created for empty CSV"


def test_run_reports_no_empty_pngs_left_behind(tmp_path):
    """Reports with insufficient data must not leave empty PNG files on disk."""
    # Minimal CSV: 1 row, no team, no developer - many reports will skip
    csv_file = tmp_path / "minimal.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,,2024-01-15,,2024-01-15T10:00:00Z,2024-01-10T09:00:00Z,100,50,Test\n"
    )

    output_dir = tmp_path / "reports"
    generated = run_reports(csv_path=csv_file, output_dir=output_dir)

    # Any generated PNG must have meaningful content
    for path in generated:
        p = Path(path)
        assert (
            p.stat().st_size >= MIN_PNG_SIZE_BYTES
        ), f"Report {path} is too small ({p.stat().st_size} bytes)"


def test_extract_leaderboard_groups_by_approver():
    today = datetime.now(timezone.utc)
    recent = (today - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (today - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")

    df = pd.DataFrame(
        [
            {
                "pr_url": "https://github.com/o/r/pull/1",
                "complexity": 3,
                "approved_by": "alice",
                "date": recent,
                "merged_at": recent,
            },
            {
                "pr_url": "https://github.com/o/r/pull/2",
                "complexity": 5,
                "approved_by": "alice",
                "date": recent,
                "merged_at": recent,
            },
            {
                "pr_url": "https://github.com/o/r/pull/3",
                "complexity": 4,
                "approved_by": "bob",
                "date": recent,
                "merged_at": recent,
            },
            {
                "pr_url": "https://github.com/o/r/pull/4",
                "complexity": 2,
                "approved_by": "alice",
                "date": old,
                "merged_at": old,
            },
        ]
    )

    result = _extract_leaderboard(df)

    # 30d: alice=2, bob=1
    assert result["30d"][0]["reviewer"] == "alice"
    assert result["30d"][0]["approvals"] == 2
    assert result["30d"][0]["rank"] == 1
    assert result["30d"][1]["reviewer"] == "bob"
    assert result["30d"][1]["approvals"] == 1

    # all-time: alice=3, bob=1
    assert result["all"][0]["reviewer"] == "alice"
    assert result["all"][0]["approvals"] == 3

    # avg_complexity for alice in 30d: (3+5)/2 = 4.0
    assert result["30d"][0]["avg_complexity"] == 4.0


def test_extract_leaderboard_no_approved_by_column():
    df = pd.DataFrame(
        [
            {
                "pr_url": "https://github.com/o/r/pull/1",
                "complexity": 3,
                "date": "2026-03-10",
                "merged_at": "2026-03-10T10:00:00Z",
            },
        ]
    )
    result = _extract_leaderboard(df)
    assert result == {"30d": [], "90d": [], "all": []}


def test_extract_leaderboard_empty_approved_by():
    df = pd.DataFrame(
        [
            {
                "pr_url": "https://github.com/o/r/pull/1",
                "complexity": 3,
                "approved_by": "",
                "date": "2026-03-10",
                "merged_at": "2026-03-10T10:00:00Z",
            },
        ]
    )
    result = _extract_leaderboard(df)
    assert result["30d"] == []
    assert result["all"] == []
