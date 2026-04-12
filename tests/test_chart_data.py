"""Unit tests for chart_data module."""

import pandas as pd
import pytest
from unittest.mock import patch

from reports.chart_data import _build_team_dev_prs, build_all_chart_data


TEAM_MAPPING = {"alice": "Alpha", "bob": "Alpha", "carol": "Beta"}


def _make_df():
    return pd.DataFrame([
        {
            "pr_url": "https://github.com/org/repo/pull/1",
            "complexity": 3.0,
            "developer": "alice",
            "merged_at": "2026-01-06",
            "date": "2026-01-06",
            "team": "",
            "created_at": "2026-01-05",
            "lines_added": 10,
            "lines_deleted": 5,
        },
        {
            "pr_url": "https://github.com/org/repo/pull/2",
            "complexity": 5.0,
            "developer": "alice",
            "merged_at": "2026-01-07",
            "date": "2026-01-07",
            "team": "",
            "created_at": "2026-01-06",
            "lines_added": 20,
            "lines_deleted": 0,
        },
        {
            "pr_url": "https://github.com/org/repo/pull/3",
            "complexity": 8.0,
            "developer": "bob",
            "merged_at": "2026-01-13",
            "date": "2026-01-13",
            "team": "",
            "created_at": "2026-01-12",
            "lines_added": 30,
            "lines_deleted": 10,
        },
    ])


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_structure(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Top-level keys are teams
    assert "Alpha" in result
    assert "Beta" not in result  # carol has no PRs
    # Second level: developers
    assert "alice" in result["Alpha"]
    assert "bob" in result["Alpha"]
    # Third level: week start date strings
    alpha_alice = result["Alpha"]["alice"]
    assert len(alpha_alice) >= 1
    # Each week maps to a list of PR dicts
    for week_key, prs in alpha_alice.items():
        assert isinstance(prs, list)
        for pr in prs:
            assert "title" in pr
            assert "url" in pr
            assert "complexity" in pr
            assert "merged_at" in pr


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_pr_fields(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Alice has 2 PRs in the same week (Jan 5-11)
    alice_weeks = result["Alpha"]["alice"]
    all_prs = [pr for prs in alice_weeks.values() for pr in prs]
    assert len(all_prs) == 2
    pr1 = all_prs[0]
    assert pr1["url"] == "https://github.com/org/repo/pull/1" or pr1["url"] == "https://github.com/org/repo/pull/2"
    assert isinstance(pr1["complexity"], float)
    assert isinstance(pr1["merged_at"], str)
    # Title is derived as "repo #N"
    assert "repo" in pr1["title"]
    assert "#1" in pr1["title"] or "#2" in pr1["title"]


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_week_key_matches_monday(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Week keys must be ISO date strings in YYYY-MM-DD format for week starts
    for team, devs in result.items():
        for dev, weeks in devs.items():
            for week_key in weeks:
                import datetime
                d = datetime.date.fromisoformat(week_key)
                # Must be a Monday (weekday() == 0)
                assert d.weekday() == 0, f"{week_key} is not a Monday"


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
@patch("reports.chart_data.get_weekly_headcounts", return_value={})
def test_build_all_chart_data_includes_team_dev_prs(mock_hc, mock_mapping):
    df = _make_df()
    result = build_all_chart_data(df)
    assert "_team_dev_prs" in result
    assert isinstance(result["_team_dev_prs"], dict)


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
@patch("reports.chart_data.get_weekly_headcounts", return_value={})
def test_extract_team_includes_dev_velocity_chart(mock_hc, mock_mapping):
    df = _make_df()
    result = build_all_chart_data(df)
    team_charts = result["team"]
    dev_vel_charts = [c for c in team_charts if c.get("type") == "devVelocityMultiLine"]
    assert len(dev_vel_charts) >= 1
    chart = dev_vel_charts[0]
    assert chart["_subtab"] == "Alpha"
    assert "series" in chart
    assert "x" in chart
    # Each series has name, data, prCounts of equal length
    for s in chart["series"]:
        assert "name" in s
        assert "data" in s
        assert "prCounts" in s
        assert len(s["data"]) == len(chart["x"])
        assert len(s["prCounts"]) == len(chart["x"])
