"""Risk & quality reports."""

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


def report_complexity_vs_merge_weekday(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 8: Complexity vs Merge Day of Week - heatmap."""
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    df["weekday"] = pd.to_datetime(df["date"]).dt.dayofweek
    df["weekday_name"] = df["weekday"].map(
        {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"}
    )
    avg = df.groupby("weekday_name")["complexity"].mean().reindex(
        ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    )
    if not has_plottable_series(avg):
        return None
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(avg.index, avg.values, color="teal", alpha=0.8)
    ax.set_title(
        "Average Complexity by Merge Day of Week\n"
        "What: When do complex PRs get merged. When: Schedule planning. How: Friday merges may need more review."
    )
    ax.set_ylabel("Avg Complexity")
    ax.set_xlabel("Weekday")
    fig.tight_layout()
    out = output_dir / "08-complexity-vs-merge-weekday.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_complexity_histogram(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 9: Complexity Histogram - org-wide."""
    if df.empty or "complexity" not in df.columns:
        return None
    if not has_plottable_series(df["complexity"]):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["complexity"], bins=range(1, 12), align="left", edgecolor="black", alpha=0.7)
    ax.set_title(
        "Complexity Distribution (Org-wide)\n"
        "What: How many PRs at each complexity level. When: Calibration. How: Most PRs should be 1–5."
    )
    ax.set_xlabel("Complexity Score")
    ax.set_ylabel("Count")
    fig.tight_layout()
    out = output_dir / "09-complexity-histogram.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None
