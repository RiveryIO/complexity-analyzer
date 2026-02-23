"""Core operational reports."""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


def _ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    """Ensure df has valid date column from merged_at or date."""
    if "date" not in df.columns and "merged_at" in df.columns:
        df = df.copy()
        df["date"] = df["merged_at"]
    if "date" in df.columns:
        df = df.dropna(subset=["date"])
    return df


def report_complexity_volume_over_time(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 1: Complexity Volume Over Time - stacked by team."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    agg = df.groupby(["week", "team"])["complexity"].sum().unstack(fill_value=0)
    fig, ax = plt.subplots(figsize=(12, 6))
    agg.plot(kind="bar", stacked=True, ax=ax, width=0.8)
    ax.set_title("Complexity Volume Over Time (by Team)")
    ax.set_ylabel("Total Complexity")
    ax.set_xlabel("Week")
    plt.xticks(rotation=45, ha="right")
    plt.legend(title="Team", bbox_to_anchor=(1.02, 1))
    plt.tight_layout()
    out = output_dir / "01-complexity-volume-over-time.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)


def report_pr_count_vs_complexity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 2: PR Count vs Complexity Over Time - dual line."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly = df.groupby("week").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
    fig, ax1 = plt.subplots(figsize=(12, 6))
    ax1.plot(weekly.index, weekly["pr_count"], "b-", label="PR count")
    ax1.set_ylabel("PR Count", color="b")
    ax2 = ax1.twinx()
    ax2.plot(weekly.index, weekly["total_complexity"], "g-", label="Total complexity")
    ax2.set_ylabel("Total Complexity", color="g")
    ax1.set_title("PR Count vs Complexity Over Time")
    ax1.legend(loc="upper left")
    ax2.legend(loc="upper right")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "02-pr-count-vs-complexity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)


def report_avg_complexity_rolling(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 3: Average Complexity per PR (Rolling 4 weeks)."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly_avg = df.groupby("week")["complexity"].mean()
    rolling = weekly_avg.rolling(4, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.plot(rolling.index, rolling.values, "b-")
    ax.set_title("Average Complexity per PR (Rolling 4 weeks)")
    ax.set_ylabel("Rolling Avg Complexity")
    ax.set_xlabel("Week")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "03-avg-complexity-rolling.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)


def report_high_complexity_frequency(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 7: High Complexity PR Frequency (% PRs >= 8 per team)."""
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    high = df[df["complexity"] >= 8]
    total = df.groupby("team").size()
    high_count = high.groupby("team").size()
    pct = (high_count.reindex(total.index, fill_value=0) / total * 100).fillna(0)
    fig, ax = plt.subplots(figsize=(10, 6))
    pct.plot(kind="bar", ax=ax, color="coral", edgecolor="darkred")
    ax.set_title("% High-Risk PRs (complexity >= 8) per Team")
    ax.set_ylabel("% of PRs")
    ax.set_xlabel("Team")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "07-high-complexity-frequency.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)
