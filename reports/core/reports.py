"""Core operational reports."""

from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from reports.validation import has_plottable_agg, has_plottable_series, validate_png_has_content


def _ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure df has valid date column from merged_at or date."""
    if "date" not in df.columns and "merged_at" in df.columns:
        df = df.copy()
        df["date"] = df["merged_at"]
    if "date" in df.columns:
        df = df.dropna(subset=["date"])
    return df


def report_complexity_volume_over_time(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 1: Complexity Volume Over Time - all PRs."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W")
    weekly = df.groupby("week")["complexity"].sum()
    if not has_plottable_series(weekly):
        return None
    # Use week start date labels (e.g. "26 Jan")
    weekly.index = [p.start_time.strftime("%d %b") for p in weekly.index]
    fig, ax = plt.subplots(figsize=(12, 6))
    weekly.plot(kind="bar", ax=ax, width=0.8, color="steelblue", edgecolor="navy")
    ax.set_title(
        "Complexity Volume Over Time (All PRs, by Week)\n"
        "What: Total complexity per week. When: Track velocity and workload. How: Spot busy weeks or slowdowns."
    )
    ax.set_ylabel("Total Complexity")
    ax.set_xlabel("Week")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    out = output_dir / "01-complexity-volume-over-time.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_complexity_volume_by_month(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report: Complexity Volume Over Time - all PRs, by month."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly = df.groupby("month")["complexity"].sum()
    if not has_plottable_series(monthly):
        return None
    # Use YYYY-MM labels (e.g. "2026-02")
    monthly.index = [str(p) for p in monthly.index]
    fig, ax = plt.subplots(figsize=(12, 6))
    monthly.plot(kind="bar", ax=ax, width=0.8, color="steelblue", edgecolor="navy")
    ax.set_title(
        "Complexity Volume Over Time (All PRs, by Month)\n"
        "What: Total complexity per month. When: Monthly reviews. How: Compare months for trends."
    )
    ax.set_ylabel("Total Complexity")
    ax.set_xlabel("Month")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    out = output_dir / "18-complexity-volume-by-month.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_pr_count_vs_complexity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 2: PR Count vs Complexity Over Time - dual line."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly = df.groupby("week").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
    if not has_plottable_agg(weekly):
        return None
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(weekly.index, weekly["pr_count"], "b-", label="PR count")
    ax1.set_ylabel("PR Count", color="b")
    ax2 = ax1.twinx()
    ax2.plot(weekly.index, weekly["total_complexity"], "g-", label="Total complexity")
    ax2.set_ylabel("Total Complexity", color="g")
    ax1.set_title(
        "PR Count vs Complexity Over Time\n"
        "What: PR volume vs total complexity. When: Assess throughput vs effort. How: High count + low complexity = many small PRs."
    )
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    ax1.tick_params(axis="x", rotation=45)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.tight_layout()
    out = output_dir / "02-pr-count-vs-complexity.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_avg_complexity_rolling(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 3: Average Complexity per PR (Rolling 4 weeks)."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly_avg = df.groupby("week")["complexity"].mean()
    rolling = weekly_avg.rolling(4, min_periods=1).mean()
    if not has_plottable_series(rolling, min_points=1):
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(rolling.index, rolling.values, "b-")
    ax.set_title(
        "Average Complexity per PR (Rolling 4 weeks)\n"
        "What: Smoothed avg complexity. When: Spot complexity drift. How: Rising line = PRs getting harder."
    )
    ax.set_ylabel("Rolling Avg Complexity")
    ax.set_xlabel("Week")
    ax.tick_params(axis="x", rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.tight_layout()
    out = output_dir / "03-avg-complexity-rolling.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_avg_merge_cycle_time(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report: Average Merge Cycle Time (created_at → merged_at) by week."""
    if "created_at" not in df.columns or "merged_at" not in df.columns:
        return None
    df = df.copy()
    df = df.dropna(subset=["created_at", "merged_at"])
    df["cycle_hours"] = (
        pd.to_datetime(df["merged_at"]) - pd.to_datetime(df["created_at"])
    ).dt.total_seconds() / 3600
    df = df[df["cycle_hours"] >= 0]
    if df.empty:
        return None
    merged = pd.to_datetime(df["merged_at"])
    if merged.dt.tz is not None:
        merged = merged.dt.tz_localize(None, ambiguous="infer")
    df["week"] = merged.dt.to_period("W").dt.start_time
    weekly = df.groupby("week")["cycle_hours"].mean()
    if not has_plottable_series(weekly):
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(weekly.index, weekly.values, "b-o", markersize=4)
    ax.set_title(
        "Average Merge Cycle Time (by Week)\n"
        "What: Time from PR creation to merge. When: Process health. How: created_at → merged_at in hours."
    )
    ax.set_ylabel("Avg Cycle Time (hours)")
    ax.set_xlabel("Week (merge date)")
    ax.tick_params(axis="x", rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    out = output_dir / "19-avg-merge-cycle-time.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_high_complexity_frequency(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 7: High Complexity PR Frequency (% PRs >= 6 per team)."""
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    if df.empty:
        return None
    high = df[df["complexity"] >= 6]
    total = df.groupby("team").size()
    high_count = high.groupby("team").size()
    pct = (high_count.reindex(total.index, fill_value=0) / total * 100).fillna(0)
    if total.sum() == 0 or not has_plottable_series(total):
        return None
    if not has_plottable_series(pct):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    pct.plot(kind="bar", ax=ax, color="coral", edgecolor="darkred")
    ax.set_ylim(bottom=0)
    ax.set_title(
        "% High-Risk PRs (complexity >= 6) per Team\n"
        "What: Share of risky PRs per team. When: Risk review. How: High % = more review focus needed. "
        "Note: Threshold 6 used for meaningful distribution (8+ often yields sparse data)."
    )
    ax.set_ylabel("% of PRs")
    ax.set_xlabel("Team")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    out = output_dir / "07-high-complexity-frequency.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None
