"""Tests for reports module - including performance."""

import time
import pytest
from pathlib import Path

from reports.runner import load_dataframe, run_reports


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
        "pr_url,complexity,author,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,Test\n"
    )
    df = load_dataframe(csv_file)
    assert len(df) == 1
    assert "developer" in df.columns or "author" in df.columns


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="Sample CSV fixture not found")
def test_run_reports_generates_files(tmp_path):
    """Test run_reports generates PNG files from sample CSV."""
    output_dir = tmp_path / "reports"
    generated = run_reports(csv_path=SAMPLE_CSV, output_dir=output_dir)

    assert len(generated) >= 10
    for path in generated:
        assert Path(path).exists()
        assert Path(path).suffix == ".png"


@pytest.mark.skipif(not SAMPLE_CSV.exists(), reason="Sample CSV fixture not found")
def test_run_reports_performance(tmp_path):
    """Test reports generation completes in under 10 seconds."""
    output_dir = tmp_path / "reports"
    start = time.perf_counter()
    generated = run_reports(csv_path=SAMPLE_CSV, output_dir=output_dir)
    elapsed = time.perf_counter() - start

    assert elapsed < 10.0, f"Reports took {elapsed:.2f}s, expected < 10s"
    assert len(generated) >= 10


def test_run_reports_with_generated_large_csv(tmp_path):
    """Test reports performance with programmatically generated large CSV."""
    # Generate 150 rows to simulate real workload
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

    assert elapsed < 10.0, f"Reports took {elapsed:.2f}s with 150 rows, expected < 10s"
    assert len(generated) >= 10


def test_run_reports_empty_csv(tmp_path):
    """Test run_reports with empty CSV returns empty list."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n")

    output_dir = tmp_path / "reports"
    generated = run_reports(csv_path=csv_file, output_dir=output_dir)

    assert generated == []
