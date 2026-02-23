"""Advanced reports."""

from pathlib import Path
from typing import Optional

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
    velocity.plot(kind="bar", ax=ax, color="green", alpha=0.8)
    ax.set_title("Complexity Weighted Velocity (per Sprint, per Developer)")
    ax.set_ylabel("Complexity / #developers")
    ax.set_xlabel("Sprint")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "13-complexity-weighted-velocity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out) if validate_png_has_content(out) else None


def report_complexity_trend_by_team(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 15: Complexity Trend by Team - rolling median."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    teams_with_data = [
        t for t in df["team"].unique()
        if not df[df["team"] == t].groupby("week")["complexity"].median().rolling(4, min_periods=1).mean().dropna().empty
    ]
    if not teams_with_data:
        return None
    fig, ax = plt.subplots(figsize=(12, 6))
    for team in df["team"].unique():
        if team == "Unknown" and df["team"].nunique() > 1:
            continue
        tdf = df[df["team"] == team].groupby("week")["complexity"].median().rolling(4, min_periods=1).mean()
        ax.plot(tdf.index, tdf.values, label=team or "Unknown")
    ax.set_title("Complexity Trend by Team (Rolling Median 4w)")
    ax.set_ylabel("Rolling Median Complexity")
    ax.set_xlabel("Week")
    ax.legend()
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "15-complexity-trend-by-team.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
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
    ax.set_title("Cumulative Complexity Over Time")
    ax.set_ylabel("Cumulative Complexity")
    ax.set_xlabel("Date")
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    out = output_dir / "16-cumulative-complexity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out) if validate_png_has_content(out) else None
