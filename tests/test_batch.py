"""Tests for batch module."""

import csv
import pytest
from datetime import datetime
from unittest.mock import patch
from cli.batch import (
    load_pr_urls_from_file,
    load_repos_from_file,
    generate_pr_list_from_date_range,
    generate_pr_list_from_repos_file,
    get_max_merged_at_from_csv,
    load_completed_prs,
    write_csv_row,
    run_batch_analysis,
)


def test_load_pr_urls_from_file(tmp_path):
    """Test loading PR URLs from file."""
    pr_file = tmp_path / "prs.txt"
    pr_file.write_text(
        "https://github.com/owner/repo/pull/123\n"
        "https://github.com/owner/repo/pull/124\n"
        "https://github.com/owner/repo/pull/125\n"
    )

    urls = load_pr_urls_from_file(pr_file)
    assert len(urls) == 3
    assert urls[0] == "https://github.com/owner/repo/pull/123"
    assert urls[1] == "https://github.com/owner/repo/pull/124"
    assert urls[2] == "https://github.com/owner/repo/pull/125"


def test_load_pr_urls_from_file_not_found(tmp_path):
    """Test loading PR URLs from non-existent file."""
    pr_file = tmp_path / "nonexistent.txt"

    with pytest.raises(FileNotFoundError):
        load_pr_urls_from_file(pr_file)


def test_load_pr_urls_from_file_empty(tmp_path):
    """Test loading PR URLs from empty file."""
    pr_file = tmp_path / "empty.txt"
    pr_file.write_text("")

    with pytest.raises(ValueError):
        load_pr_urls_from_file(pr_file)


def test_load_repos_from_file(tmp_path):
    """Test loading repos from file."""
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text(
        "# Comment line\n"
        "owner/repo-a\n"
        "owner/repo-b\n"
        "\n"
        "  owner/repo-c  \n"
    )

    repos = load_repos_from_file(repos_file)
    assert repos == ["owner/repo-a", "owner/repo-b", "owner/repo-c"]


def test_load_repos_from_file_not_found(tmp_path):
    """Test loading repos from non-existent file."""
    with pytest.raises(FileNotFoundError):
        load_repos_from_file(tmp_path / "nonexistent.txt")


def test_load_repos_from_file_empty(tmp_path):
    """Test loading repos from empty file."""
    repos_file = tmp_path / "empty.txt"
    repos_file.write_text("# Only comments\n\n")

    with pytest.raises(ValueError):
        load_repos_from_file(repos_file)


@patch("cli.batch.search_closed_prs_by_repos")
def test_generate_pr_list_from_repos_file(mock_search, tmp_path):
    """Test generating PR list from repos file."""
    repos_file = tmp_path / "repos.txt"
    repos_file.write_text("owner/repo-a\nowner/repo-b\n")

    mock_search.return_value = [
        "https://github.com/owner/repo-a/pull/1",
        "https://github.com/owner/repo-b/pull/2",
    ]

    urls = generate_pr_list_from_repos_file(
        repos_file=repos_file,
        since=datetime(2024, 1, 1),
        until=datetime(2024, 1, 31),
        cache_file=None,
        github_token="token",
    )

    assert len(urls) == 2
    mock_search.assert_called_once()
    call_kwargs = mock_search.call_args.kwargs
    assert call_kwargs["repos"] == ["owner/repo-a", "owner/repo-b"]
    assert call_kwargs["merged_only"] is True


@patch("cli.batch.search_closed_prs")
def test_generate_pr_list_from_cache(mock_search, tmp_path):
    """Test generating PR list from cache file."""
    cache_file = tmp_path / "cache.txt"
    cache_file.write_text(
        "https://github.com/owner/repo/pull/123\n" "https://github.com/owner/repo/pull/124\n"
    )

    urls = generate_pr_list_from_date_range(
        org="testorg",
        since=datetime(2024, 1, 1),
        until=datetime(2024, 1, 31),
        cache_file=cache_file,
        github_token="token",
    )

    assert len(urls) == 2
    mock_search.assert_not_called()


@patch("cli.batch.search_closed_prs")
def test_generate_pr_list_from_github(mock_search, tmp_path):
    """Test generating PR list from GitHub API."""
    pr_urls = [
        "https://github.com/owner/repo/pull/123",
        "https://github.com/owner/repo/pull/124",
    ]

    def mock_search_with_callback(
        org, since, until, token, sleep_s, on_pr_found, progress_callback, client, **kwargs
    ):
        """Mock that calls the on_pr_found callback for each URL."""
        for url in pr_urls:
            if on_pr_found:
                on_pr_found(url)
        return pr_urls

    mock_search.side_effect = mock_search_with_callback

    cache_file = tmp_path / "cache.txt"

    urls = generate_pr_list_from_date_range(
        org="testorg",
        since=datetime(2024, 1, 1),
        until=datetime(2024, 1, 31),
        cache_file=cache_file,
        github_token="token",
    )

    assert len(urls) == 2
    mock_search.assert_called_once()
    assert cache_file.exists()
    assert "https://github.com/owner/repo/pull/123" in cache_file.read_text()


def test_load_completed_prs(tmp_path):
    """Test loading completed PRs from CSV."""
    csv_file = tmp_path / "results.csv"
    csv_file.write_text(
        "pr_url,complexity,explanation\n"
        "https://github.com/owner/repo/pull/123,5,Test explanation\n"
        "https://github.com/owner/repo/pull/124,3,Another explanation\n"
    )

    completed = load_completed_prs(csv_file)
    assert len(completed) == 2
    assert "https://github.com/owner/repo/pull/123" in completed
    assert "https://github.com/owner/repo/pull/124" in completed


def test_load_completed_prs_not_exists(tmp_path):
    """Test loading completed PRs from non-existent file."""
    csv_file = tmp_path / "nonexistent.csv"

    completed = load_completed_prs(csv_file)
    assert len(completed) == 0


def test_get_max_merged_at_from_csv_none(tmp_path):
    """Test get_max_merged_at_from_csv when file does not exist."""
    assert get_max_merged_at_from_csv(tmp_path / "nonexistent.csv") is None
    assert get_max_merged_at_from_csv(None) is None


def test_get_max_merged_at_from_csv_no_column(tmp_path):
    """Test get_max_merged_at_from_csv when merged_at column missing."""
    csv_file = tmp_path / "legacy.csv"
    csv_file.write_text("pr_url,complexity,explanation,author\nhttps://github.com/org/repo/pull/1,5,Test,alice\n")
    assert get_max_merged_at_from_csv(csv_file) is None


def test_get_max_merged_at_from_csv_with_dates(tmp_path):
    """Test get_max_merged_at_from_csv returns max merged_at."""
    csv_file = tmp_path / "report.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/org/repo/pull/1,5,alice,2024-01-15,Platform,2024-01-15T10:00:00Z,2024-01-10T09:00:00Z,100,50,Test\n"
        "https://github.com/org/repo/pull/2,3,bob,2024-01-20,Backend,2024-01-20T14:00:00Z,2024-01-18T08:00:00Z,30,20,Fix\n"
    )
    result = get_max_merged_at_from_csv(csv_file)
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 20


def test_write_csv_row_new_file(tmp_path):
    """Test writing CSV row to new file (uses canonical schema)."""
    csv_file = tmp_path / "results.csv"

    write_csv_row(csv_file, "https://github.com/owner/repo/pull/123", 5, "Test explanation", "alice")

    assert csv_file.exists()
    with csv_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["pr_url"] == "https://github.com/owner/repo/pull/123"
        assert rows[0]["complexity"] == "5"
        assert rows[0]["explanation"] == "Test explanation"
        assert "developer" in rows[0] or "author" in reader.fieldnames or "developer" in reader.fieldnames


def test_write_csv_row_existing_file(tmp_path):
    """Test writing CSV row to existing file (normalizes to canonical schema)."""
    csv_file = tmp_path / "results.csv"
    csv_file.write_text(
        "pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation\n"
        "https://github.com/owner/repo/pull/123,5,alice,2024-01-15,Platform,,,100,50,Test explanation\n"
    )

    write_csv_row(csv_file, "https://github.com/owner/repo/pull/124", 3, "Another explanation", "bob")

    with csv_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
        assert rows[0]["pr_url"] == "https://github.com/owner/repo/pull/123"
        assert rows[1]["pr_url"] == "https://github.com/owner/repo/pull/124"


@patch("cli.batch.typer")
def test_run_batch_analysis(mock_typer, tmp_path):
    """Test running batch analysis."""
    output_file = tmp_path / "results.csv"

    pr_urls = [
        "https://github.com/owner/repo/pull/123",
        "https://github.com/owner/repo/pull/124",
    ]

    def analyze_fn(url):
        return {
            "score": 5,
            "explanation": f"Analysis for {url}",
        }

    run_batch_analysis(pr_urls, output_file, analyze_fn, resume=True)

    assert output_file.exists()
    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2


@patch("cli.batch.typer")
def test_run_batch_analysis_resume(mock_typer, tmp_path):
    """Test batch analysis resume capability."""
    output_file = tmp_path / "results.csv"
    output_file.write_text(
        "pr_url,complexity,explanation\n" "https://github.com/owner/repo/pull/123,5,Already done\n"
    )

    pr_urls = [
        "https://github.com/owner/repo/pull/123",
        "https://github.com/owner/repo/pull/124",
    ]

    analyze_count = 0

    def analyze_fn(url):
        nonlocal analyze_count
        analyze_count += 1
        return {
            "score": 5,
            "explanation": f"Analysis for {url}",
        }

    run_batch_analysis(pr_urls, output_file, analyze_fn, resume=True)

    # Should only analyze the second PR (first is already done)
    assert analyze_count == 1
    assert output_file.exists()
    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) == 2
