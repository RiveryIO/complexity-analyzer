"""Parallel report runner - loads CSV once, generates all reports in parallel."""

import matplotlib
matplotlib.use("Agg")  # Non-GUI backend for parallel/headless use

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, List, Optional, Union

import pandas as pd


def load_dataframe(csv_path: Path) -> pd.DataFrame:
    """Load and normalize CSV to DataFrame."""
    df = pd.read_csv(csv_path)
    # Normalize column names
    col_map = {
        "pr_url": "pr_url",
        "PR link": "pr_url",
        "complexity": "complexity",
        "developer": "developer",
        "author": "developer",
        "date": "date",
        "team": "team",
        "merged_at": "merged_at",
        "created_at": "created_at",
        "lines_added": "lines_added",
        "lines_deleted": "lines_deleted",
    }
    for old, new in col_map.items():
        if old in df.columns and new not in df.columns:
            df[new] = df[old]
    # Parse dates
    for col in ("merged_at", "created_at", "date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    # Parse numeric
    for col in ("complexity", "lines_added", "lines_deleted"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    # Use merged_at for date if date missing
    if "date" not in df.columns and "merged_at" in df.columns:
        df["date"] = df["merged_at"]
    elif "date" in df.columns and df["date"].isna().all() and "merged_at" in df.columns:
        df["date"] = df["merged_at"]
    return df


def run_reports(
    csv_path: Path,
    output_dir: Path,
    report_fns: Optional[List[Callable[[pd.DataFrame, Path], Optional[str]]]] = None,
    max_workers: int = 8,
) -> List[str]:
    """
    Load CSV once and run all report functions in parallel.

    Returns list of generated file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = load_dataframe(csv_path)
    if df.empty:
        return []

    if report_fns is None:
        from reports.core import report_complexity_volume_by_month
        from reports.core import report_complexity_volume_over_time
        from reports.core import report_pr_count_vs_complexity
        from reports.core import report_avg_complexity_rolling
        from reports.core import report_high_complexity_frequency
        from reports.team import report_complexity_distribution_by_team
        from reports.team import report_developer_contribution
        from reports.team import report_complexity_per_dev_vs_pr_count
        from reports.team import report_complexity_vs_cycle_time
        from reports.team import report_complexity_per_team_per_dev
        from reports.team import report_team_gini
        from reports.risk import report_complexity_vs_merge_weekday
        from reports.risk import report_complexity_histogram
        from reports.fairness import report_pr_size_vs_complexity
        from reports.fairness import report_pr_count_vs_avg_complexity
        from reports.advanced import report_complexity_weighted_velocity
        from reports.advanced import report_complexity_trend_by_team
        from reports.advanced import report_cumulative_complexity

        report_fns = [
            (report_complexity_volume_over_time, "core"),
            (report_complexity_volume_by_month, "core"),
            (report_pr_count_vs_complexity, "core"),
            (report_avg_complexity_rolling, "core"),
            (report_high_complexity_frequency, "core"),
            (report_complexity_distribution_by_team, "team"),
            (report_developer_contribution, "team"),
            (report_complexity_per_dev_vs_pr_count, "team"),
            (report_complexity_vs_cycle_time, "team"),
            (report_complexity_per_team_per_dev, "team"),
            (report_team_gini, "team"),
            (report_complexity_vs_merge_weekday, "risk"),
            (report_complexity_histogram, "risk"),
            (report_pr_size_vs_complexity, "fairness"),
            (report_pr_count_vs_avg_complexity, "fairness"),
            (report_complexity_weighted_velocity, "advanced"),
            (report_complexity_trend_by_team, "advanced"),
            (report_cumulative_complexity, "advanced"),
        ]
    else:
        # Normalize: (fn, subdir) or plain fn -> (fn, ".")
        normalized = []
        for item in report_fns:
            if isinstance(item, tuple):
                normalized.append(item)
            else:
                normalized.append((item, "."))
        report_fns = normalized

    generated: List[str] = []

    def run_one(item: tuple) -> Optional[Union[str, List[str]]]:
        fn, subdir = item
        topic_dir = output_dir / subdir
        topic_dir.mkdir(parents=True, exist_ok=True)
        try:
            return fn(df.copy(), topic_dir)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(run_one, item): item for item in report_fns}
        for future in as_completed(futures):
            result = future.result()
            if result:
                if isinstance(result, list):
                    generated.extend(result)
                else:
                    generated.append(result)

    return generated
