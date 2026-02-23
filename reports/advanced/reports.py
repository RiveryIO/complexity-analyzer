"""Advanced reports."""

from pathlib import Path
from typing import Optional

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from reports.validation import has_plottable_series, validate_png_has_content


def _ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns and "merged_at" in df.columns:
        df = df.copy()
        df["date"] = df["merged_at"]
    if "date" in df.columns:
        df = df.dropna(subset=["date"])
    return df


def report_complexity_weighted_velocity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 13: Complexity Weighted Velocity - per sprint, total_complexity / #developers."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["sprint"] = pd.to_datetime(df["date"]).dt.to_period("2W").dt.start_time
    sprint_total = df.groupby("sprint")["complexity"].sum()
    dev_col = "developer" if "developer" in df.columns else "author"
    sprint_devs = df.groupby("sprint")[dev_col].nunique().replace(0, 1)
    velocity = (sprint_total / sprint_devs).sort_index()
    if not has_plottable_series(velocity):
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    velocity.index = pd.to_datetime(velocity.index).strftime("%Y-%m-%d")
    velocity.plot(kind="bar", ax=ax, color="green", alpha=0.8)
    ax.set_title(
        "Complexity Weighted Velocity (per Sprint, per Developer)\n"
        "What: Output per sprint normalized by headcount. When: Sprint reviews. How: Compare bars for velocity trends."
    )
    ax.set_ylabel("Complexity / #developers")
    ax.set_xlabel("Sprint")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    out = output_dir / "13-complexity-weighted-velocity.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_complexity_trend_by_team(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 15: Complexity Trend by Team - rolling median."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    teams_with_data = [
        t for t in df["team"].unique()
        if not df[df["team"] == t].groupby("week")["complexity"].median().rolling(4, min_periods=1).mean().dropna().empty
    ]
    if not teams_with_data:
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    df = df[df["team"] != "Unknown"]
    if df.empty:
        return None
    for team in df["team"].unique():
        tdf = df[df["team"] == team].groupby("week")["complexity"].median().rolling(4, min_periods=1).mean()
        if tdf.dropna().empty:
            continue
        ax.plot(tdf.index, tdf.values, label=team)
    ax.set_title(
        "Complexity Trend by Team (Rolling Median 4w)\n"
        "What: Smoothed complexity trend per team. When: Track team evolution. How: Rising line = harder PRs."
    )
    ax.set_ylabel("Rolling Median Complexity")
    ax.set_xlabel("Week")
    ax.legend()
    ax.tick_params(axis="x", rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.tight_layout()
    out = output_dir / "15-complexity-trend-by-team.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_cumulative_complexity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 16: Cumulative Complexity Over Time."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df = df.sort_values("date")
    df["cumulative"] = df["complexity"].cumsum()
    if not has_plottable_series(df["cumulative"]):
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.fill_between(df["date"], df["cumulative"], alpha=0.5)
    ax.plot(df["date"], df["cumulative"], "b-")
    ax.set_title(
        "Cumulative Complexity Over Time\n"
        "What: Running total of complexity. When: Long-term progress. How: Steeper slope = more delivery."
    )
    ax.set_ylabel("Cumulative Complexity")
    ax.set_xlabel("Date")
    ax.tick_params(axis="x", rotation=45)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
    fig.tight_layout()
    out = output_dir / "16-cumulative-complexity.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None
