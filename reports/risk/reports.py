"""Risk & quality reports."""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd


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
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.bar(avg.index, avg.values, color="teal", alpha=0.8)
    ax.set_title("Average Complexity by Merge Day of Week")
    ax.set_ylabel("Avg Complexity")
    ax.set_xlabel("Weekday")
    plt.tight_layout()
    out = output_dir / "08-complexity-vs-merge-weekday.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)


def report_complexity_histogram(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 9: Complexity Histogram - org-wide."""
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.hist(df["complexity"], bins=range(1, 12), align="left", edgecolor="black", alpha=0.7)
    ax.set_title("Complexity Distribution (Org-wide)")
    ax.set_xlabel("Complexity Score")
    ax.set_ylabel("Count")
    plt.tight_layout()
    out = output_dir / "09-complexity-histogram.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out)
