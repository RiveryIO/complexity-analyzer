"""Fairness / anti-gaming reports."""

from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import pandas as pd

from reports.validation import has_plottable_agg, has_plottable_scatter, validate_png_has_content


def report_pr_size_vs_complexity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 10: PR Size vs Complexity Correlation - scatter."""
    df = df.copy()
    df["lines_changed"] = df.get("lines_added", 0).fillna(0) + df.get("lines_deleted", 0).fillna(0)
    df = df[df["lines_changed"] > 0]
    if df.empty:
        return None
    if not has_plottable_scatter(df["lines_changed"], df["complexity"], min_points=1):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(df["lines_changed"], df["complexity"], alpha=0.5)
    ax.set_title("PR Size (lines changed) vs Complexity")
    ax.set_xlabel("Lines Changed")
    ax.set_ylabel("Complexity")
    plt.tight_layout()
    out = output_dir / "10-pr-size-vs-complexity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out) if validate_png_has_content(out) else None


def report_pr_count_vs_avg_complexity(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 11: PR Count per Dev vs Avg Complexity - scatter."""
    df = df.copy()
    df["developer"] = df.get("developer", df.get("author", "")).fillna("").astype(str)
    df = df[df["developer"] != ""]
    if df.empty:
        return None
    agg = df.groupby("developer").agg(pr_count=("pr_url", "count"), avg_complexity=("complexity", "mean"))
    if not has_plottable_agg(agg):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(agg["pr_count"], agg["avg_complexity"], alpha=0.7)
    for idx, row in agg.iterrows():
        ax.annotate(idx, (row["pr_count"], row["avg_complexity"]), fontsize=8, alpha=0.8)
    ax.set_title("PR Count per Dev vs Avg Complexity (Anti-splitting)")
    ax.set_xlabel("PR Count")
    ax.set_ylabel("Avg Complexity")
    plt.tight_layout()
    out = output_dir / "11-pr-count-vs-avg-complexity.png"
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close()
    return str(out) if validate_png_has_content(out) else None
