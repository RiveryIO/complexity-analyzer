"""Team-level leadership reports."""

from pathlib import Path
from typing import List, Optional, Union

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from cli.team_config import load_team_mapping
from reports.validation import (
    has_plottable_agg,
    has_plottable_scatter,
    has_plottable_series,
    validate_png_has_content,
)


def _ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns and "merged_at" in df.columns:
        df = df.copy()
        df["date"] = df["merged_at"]
    if "date" in df.columns:
        df = df.dropna(subset=["date"])
    return df


def _gini(x: pd.Series) -> float:
    """Gini coefficient."""
    x = np.array(x.dropna())
    if len(x) == 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * np.sum(x)) / (n * np.sum(x)) if np.sum(x) > 0 else 0


def report_complexity_distribution_by_team(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 4: Complexity Distribution by Team - boxplot."""
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    if df.empty or df["team"].nunique() == 0:
        return None
    if not has_plottable_series(df["complexity"]):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    df.boxplot(column="complexity", by="team", ax=ax)
    ax.set_title(
        "Complexity Distribution by Team\n"
        "What: Boxplot of complexity per team. When: Compare team patterns. How: Wide box = high variance."
    )
    ax.set_ylabel("Complexity")
    plt.suptitle("")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    overview_dir = output_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "04-complexity-distribution-by-team.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_developer_contribution(df: pd.DataFrame, output_dir: Path) -> Optional[Union[str, List[str]]]:
    """Report 5: Developer Complexity Contribution - stacked by week, one per team."""
    mapping = load_team_mapping()
    if not mapping:
        return None
    df = _ensure_date(df)
    if df.empty:
        return None
    df = df.copy()
    dev_col = "developer" if "developer" in df.columns else "author"
    df["developer"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    df["team"] = df["developer"].map(lambda d: mapping.get(d, "") if d else "")
    df = df[df["team"] != ""]
    df = df[df["developer"] != ""]
    if df.empty:
        return None
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    generated = []
    for team in df["team"].unique():
        tdf = df[df["team"] == team]
        pivot = tdf.pivot_table(
            index="week", columns="developer", values="complexity", aggfunc="sum", fill_value=0
        )
        pivot = pivot.reindex(pivot.sum().sort_values(ascending=False).index, axis=1)
        if not has_plottable_agg(pivot):
            continue
        pivot.index = pd.to_datetime(pivot.index).strftime("%Y-%m-%d")
        fig, ax = plt.subplots(figsize=(12, 6))
        pivot.plot(kind="bar", stacked=True, ax=ax, width=0.8, legend=True)
        ax.set_title(
            f"Developer Complexity Contribution — {team} (per Week)\n"
            "What: Who delivered what per week. When: Weekly reviews. How: Compare stacked bars."
        )
        ax.set_ylabel("Complexity")
        ax.set_xlabel("Week")
        ax.tick_params(axis="x", rotation=45)
        ax.legend(bbox_to_anchor=(1.02, 1), ncol=2)
        fig.tight_layout()
        safe_team = "".join(c if c.isalnum() or c in "-_" else "_" for c in team)
        team_dir = output_dir / safe_team
        team_dir.mkdir(parents=True, exist_ok=True)
        out = team_dir / "05-developer-contribution.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        if validate_png_has_content(out):
            generated.append(str(out))
    return generated if generated else None


def report_complexity_per_dev_vs_pr_count(df: pd.DataFrame, output_dir: Path) -> Optional[Union[str, List[str]]]:
    """Report 6: Complexity per Dev vs PR Count - scatter, one per team."""
    mapping = load_team_mapping()
    if not mapping:
        return None
    df = df.copy()
    dev_col = "developer" if "developer" in df.columns else "author"
    df["developer"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    df["team"] = df["developer"].map(lambda d: mapping.get(d, "") if d else "")
    df = df[df["team"] != ""]
    df = df[df["developer"] != ""]
    if df.empty:
        return None
    generated = []
    for team in df["team"].unique():
        tdf = df[df["team"] == team]
        agg = tdf.groupby("developer").agg(
            pr_count=("pr_url", "count"), total_complexity=("complexity", "sum")
        )
        if not has_plottable_agg(agg):
            continue
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.scatter(agg["pr_count"], agg["total_complexity"], alpha=0.7)
        for idx, row in agg.iterrows():
            ax.annotate(idx, (row["pr_count"], row["total_complexity"]), fontsize=8, alpha=0.8)
        ax.set_title(
            f"Complexity per Developer vs PR Count — {team}\n"
            "What: Output vs effort per dev. When: 1:1s. How: Top-right = high output + high complexity."
        )
        ax.set_xlabel("PR Count")
        ax.set_ylabel("Total Complexity")
        fig.tight_layout()
        safe_team = "".join(c if c.isalnum() or c in "-_" else "_" for c in team)
        team_dir = output_dir / safe_team
        team_dir.mkdir(parents=True, exist_ok=True)
        out = team_dir / "06-complexity-per-dev-vs-pr-count.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        if validate_png_has_content(out):
            generated.append(str(out))
    return generated if generated else None


def report_avg_merge_cycle_time_by_team(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report: Average Merge Cycle Time per Team (created_at → merged_at)."""
    if "created_at" not in df.columns or "merged_at" not in df.columns:
        return None
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    df = df.dropna(subset=["created_at", "merged_at"])
    df["cycle_hours"] = (
        pd.to_datetime(df["merged_at"]) - pd.to_datetime(df["created_at"])
    ).dt.total_seconds() / 3600
    df = df[df["cycle_hours"] >= 0]
    if df.empty:
        return None
    team_avg = df.groupby("team")["cycle_hours"].mean().sort_values(ascending=False)
    if not has_plottable_series(team_avg):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    team_avg.plot(kind="bar", ax=ax, color="teal", edgecolor="darkgreen")
    ax.set_title(
        "Average Merge Cycle Time per Team\n"
        "What: Time from PR creation to merge by team. When: Process comparison. How: created_at → merged_at in hours."
    )
    ax.set_ylabel("Avg Cycle Time (hours)")
    ax.set_xlabel("Team")
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    overview_dir = output_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "20-avg-merge-cycle-time-by-team.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_complexity_vs_cycle_time(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 14: Complexity vs Cycle Time - scatter (known teams only)."""
    if "created_at" not in df.columns or "merged_at" not in df.columns:
        return None
    df = df.copy()
    if "team" in df.columns:
        df["team"] = df["team"].fillna("").replace("", "Unknown")
        df = df[df["team"] != "Unknown"]
    else:
        mapping = load_team_mapping()
        if mapping:
            dev_col = "developer" if "developer" in df.columns else "author"
            df["_team"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").map(
                lambda d: mapping.get(d, "") if d else ""
            )
            df = df[df["_team"] != ""]
    df = df.dropna(subset=["created_at", "merged_at"])
    df["cycle_hours"] = (pd.to_datetime(df["merged_at"]) - pd.to_datetime(df["created_at"])).dt.total_seconds() / 3600
    df = df[df["cycle_hours"] >= 0]
    if df.empty:
        return None
    if not has_plottable_scatter(df["complexity"], df["cycle_hours"], min_points=1):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(df["complexity"], df["cycle_hours"], alpha=0.6)
    ax.set_title(
        "Complexity vs Cycle Time (hours)\n"
        "What: PR complexity vs time to merge. When: Process review. How: High complexity + long cycle = bottlenecks."
    )
    ax.set_xlabel("Complexity")
    ax.set_ylabel("Cycle Time (hours)")
    fig.tight_layout()
    overview_dir = output_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "14-complexity-vs-cycle-time.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_complexity_per_team_per_dev(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 17: Complexity per Team per Developer - normalized."""
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    if df.empty:
        return None
    dev_col = "developer" if "developer" in df.columns else "author"
    df["_dev"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    team_total = df.groupby("team")["complexity"].sum()
    team_count = df[df["_dev"] != ""].groupby("team")["_dev"].nunique().reindex(team_total.index, fill_value=1)
    team_count = team_count.replace(0, 1)
    normalized = (team_total / team_count.fillna(1)).sort_values(ascending=False)
    if not has_plottable_series(normalized):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    normalized.plot(kind="bar", ax=ax, color="steelblue")
    ax.set_title(
        "Complexity per Team per Developer (Normalized)\n"
        "What: Team output divided by headcount. When: Fair comparison. How: Higher = more output per person."
    )
    ax.set_ylabel("Complexity / Headcount")
    ax.set_xlabel("Team")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    overview_dir = output_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "17-complexity-per-team-per-dev.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None


def report_team_gini(df: pd.DataFrame, output_dir: Path) -> Optional[str]:
    """Report 12: Team Complexity Gini Coefficient."""
    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    if df.empty:
        return None
    ginis = df.groupby("team")["complexity"].apply(_gini).sort_values(ascending=False)
    if not has_plottable_series(ginis):
        return None
    fig, ax = plt.subplots(figsize=(10, 6))
    ginis.plot(kind="bar", ax=ax, color="purple", alpha=0.8)
    ax.set_title(
        "Team Complexity Gini Coefficient (Concentration)\n"
        "What: How concentrated is complexity within each team. When: Bus factor. How: High Gini = few people carry load."
    )
    ax.set_ylabel("Gini")
    ax.set_xlabel("Team")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    overview_dir = output_dir / "overview"
    overview_dir.mkdir(parents=True, exist_ok=True)
    out = overview_dir / "12-team-gini.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out) if validate_png_has_content(out) else None
