"""Export all report data as JSON for dynamic ECharts rendering. Reuses report logic."""

from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from cli.team_config import load_team_mapping


def _ensure_date(df: pd.DataFrame) -> pd.DataFrame:
    if "date" not in df.columns and "merged_at" in df.columns:
        df = df.copy()
        df["date"] = df["merged_at"]
    if "date" in df.columns:
        df = df.dropna(subset=["date"])
    return df


def _gini(x: pd.Series) -> float:
    x = np.array(x.dropna())
    if len(x) == 0:
        return 0.0
    x = np.sort(x)
    n = len(x)
    return (2 * np.sum((np.arange(1, n + 1)) * x) - (n + 1) * np.sum(x)) / (n * np.sum(x)) if np.sum(x) > 0 else 0


def _extract_basic(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    df = _ensure_date(df)
    if df.empty:
        return charts

    # 01: Complexity volume over time (bar)
    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W")
    weekly = df.groupby("week")["complexity"].sum()
    if not weekly.empty:
        labels = [p.start_time.strftime("%Y-%m-%d") for p in weekly.index]
        charts.append({
            "id": "01",
            "type": "bar",
            "title": "Velocity Over Time (by Week)",
            "subtitle": "Total complexity per week",
            "x": labels,
            "y": weekly.tolist(),
        })

    # 18: Volume by month (bar)
    df["month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    monthly = df.groupby("month")["complexity"].sum()
    if not monthly.empty:
        charts.append({
            "id": "18",
            "type": "bar",
            "title": "Velocity by Month",
            "subtitle": "Total complexity per month",
            "x": [str(p) for p in monthly.index],
            "y": monthly.tolist(),
        })

    # 02: PR count vs complexity (dual line)
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly_agg = df.groupby("week").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
    if not weekly_agg.empty:
        labels = [d.strftime("%Y-%m-%d") for d in weekly_agg.index]
        charts.append({
            "id": "02",
            "type": "dualLine",
            "title": "PR Count vs Velocity Over Time",
            "subtitle": "Volume vs total complexity",
            "x": labels,
            "y1": weekly_agg["pr_count"].tolist(),
            "y1Name": "PR Count",
            "y2": weekly_agg["total_complexity"].tolist(),
            "y2Name": "Total Complexity",
        })

    # 03: Avg complexity rolling (line)
    weekly_avg = df.groupby("week")["complexity"].mean()
    rolling = weekly_avg.rolling(4, min_periods=1).mean()
    if not rolling.empty:
        labels = [d.strftime("%Y-%m-%d") for d in rolling.index]
        charts.append({
            "id": "03",
            "type": "line",
            "title": "Average Complexity per PR (Rolling 4w)",
            "subtitle": "Smoothed avg complexity",
            "x": labels,
            "y": rolling.tolist(),
        })

    # 19: Avg merge cycle time (line)
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"]) - pd.to_datetime(cdf["created_at"])).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if not cdf.empty:
            merged = pd.to_datetime(cdf["merged_at"])
            if merged.dt.tz is not None:
                merged = merged.dt.tz_localize(None, ambiguous="infer")
            cdf["week"] = merged.dt.to_period("W").dt.start_time
            weekly_cycle = cdf.groupby("week")["cycle_hours"].mean()
            if not weekly_cycle.empty:
                labels = [d.strftime("%Y-%m-%d") for d in weekly_cycle.index]
                charts.append({
                    "id": "19",
                    "type": "line",
                    "title": "Average Merge Cycle Time (by Week)",
                    "subtitle": "created_at → merged_at in hours",
                    "x": labels,
                    "y": weekly_cycle.tolist(),
                })

    # 07: High complexity frequency (bar)
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    tdf = df[df["team"] != "Unknown"]
    if not tdf.empty:
        high = tdf[tdf["complexity"] >= 6]
        total = tdf.groupby("team").size()
        high_count = high.groupby("team").size()
        pct = (high_count.reindex(total.index, fill_value=0) / total * 100).fillna(0)
        if total.sum() > 0:
            charts.append({
                "id": "07",
                "type": "bar",
                "title": "% High-Risk PRs (complexity ≥ 6) per Team",
                "subtitle": "Share of risky PRs per team",
                "x": pct.index.tolist(),
                "y": pct.tolist(),
            })

    return charts


def _extract_team(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    mapping = load_team_mapping()
    if not mapping:
        return charts

    df = df.copy()
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    df = df[df["team"] != "Unknown"]
    if df.empty:
        return charts

    # 04: Complexity distribution by team (boxplot)
    if not df["complexity"].empty:
        teams = df["team"].unique().tolist()
        box_data = []
        for t in teams:
            vals = df[df["team"] == t]["complexity"].dropna()
            if len(vals) >= 2:
                q = np.percentile(vals, [0, 25, 50, 75, 100])
                box_data.append([float(q[0]), float(q[1]), float(q[2]), float(q[3]), float(q[4])])
            elif len(vals) == 1:
                v = float(vals.iloc[0])
                box_data.append([v, v, v, v, v])
            else:
                box_data.append([0, 0, 0, 0, 0])
        if box_data:
            charts.append({
                "id": "04",
                "type": "boxplot",
                "title": "Complexity Distribution by Team",
                "subtitle": "Boxplot per team",
                "x": teams,
                "data": box_data,
            })

    # 12: Team Gini
    ginis = df.groupby("team")["complexity"].apply(_gini).sort_values(ascending=False)
    if not ginis.empty:
        charts.append({
            "id": "12",
            "type": "bar",
            "title": "Team Complexity Gini Coefficient",
            "subtitle": "Concentration within each team",
            "x": ginis.index.tolist(),
            "y": ginis.tolist(),
        })

    # 17: Complexity per team per dev
    dev_col = "developer" if "developer" in df.columns else "author"
    df["_dev"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    team_total = df.groupby("team")["complexity"].sum()
    team_count = df[df["_dev"] != ""].groupby("team")["_dev"].nunique().reindex(team_total.index, fill_value=1).replace(0, 1)
    normalized = (team_total / team_count.fillna(1)).sort_values(ascending=False)
    if not normalized.empty:
        charts.append({
            "id": "17",
            "type": "bar",
            "title": "Velocity per Team per Developer",
            "subtitle": "Complexity output divided by headcount",
            "x": normalized.index.tolist(),
            "y": normalized.tolist(),
        })

    # 20: Avg merge cycle time by team
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"]) - pd.to_datetime(cdf["created_at"])).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if not cdf.empty:
            team_avg = cdf.groupby("team")["cycle_hours"].mean().sort_values(ascending=False)
            charts.append({
                "id": "20",
                "type": "bar",
                "title": "Average Merge Cycle Time per Team",
                "subtitle": "Hours from creation to merge",
                "x": team_avg.index.tolist(),
                "y": team_avg.tolist(),
            })

    # 14: Complexity vs cycle time (scatter)
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"]) - pd.to_datetime(cdf["created_at"])).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if len(cdf) >= 2:
            charts.append({
                "id": "14",
                "type": "scatter",
                "title": "Complexity vs Cycle Time",
                "subtitle": "PR complexity vs hours to merge",
                "data": [[float(r["complexity"]), float(r["cycle_hours"])] for _, r in cdf.iterrows()],
                "xAxisName": "Complexity",
                "yAxisName": "Cycle Time (hours)",
            })

    # 05, 06: Per-team (developer contribution, complexity vs pr count)
    df_full = _ensure_date(df.copy())
    dev_col = "developer" if "developer" in df_full.columns else "author"
    df_full["developer"] = df_full.get(dev_col, pd.Series([""] * len(df_full))).fillna("").astype(str)
    df_full["team"] = df_full["developer"].map(lambda d: mapping.get(d, "") if d else "")
    df_full = df_full[(df_full["team"] != "") & (df_full["developer"] != "")]
    if df_full.empty:
        return charts

    for team in df_full["team"].unique():
        tdf = df_full[df_full["team"] == team].copy()
        # 05: Stacked bar
        tdf["week"] = pd.to_datetime(tdf["date"]).dt.to_period("W").dt.start_time
        pivot = tdf.pivot_table(index="week", columns="developer", values="complexity", aggfunc="sum", fill_value=0)
        pivot = pivot.reindex(pivot.sum().sort_values(ascending=False).index, axis=1)
        # Drop weeks with no activity so sparse teams don't show empty charts
        pivot = pivot.loc[(pivot != 0).any(axis=1)]
        if not pivot.empty and pivot.sum().sum() > 0:
            weeks = [d.strftime("%Y-%m-%d") for d in pivot.index]
            series = [{"name": c, "data": pivot[c].tolist()} for c in pivot.columns]
            charts.append({
                "id": f"05-{team}",
                "type": "stackedBar",
                "title": f"Developer Velocity — {team}",
                "subtitle": "Complexity per week",
                "x": weeks,
                "series": series,
            })
        # 06: Scatter
        agg = tdf.groupby("developer").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
        if len(agg) >= 2:
            charts.append({
                "id": f"06-{team}",
                "type": "scatterLabel",
                "title": f"Complexity vs PR Count — {team}",
                "subtitle": "Per developer",
                "data": [{"name": idx, "value": [row["pr_count"], row["total_complexity"]]} for idx, row in agg.iterrows()],
                "xAxisName": "PR Count",
                "yAxisName": "Total Complexity",
            })

    return charts


def _extract_risk(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    df = _ensure_date(df)
    if df.empty:
        return charts

    # 08: Complexity by weekday (bar)
    df = df.copy()
    df["weekday"] = pd.to_datetime(df["date"]).dt.dayofweek
    df["weekday_name"] = df["weekday"].map({0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri", 5: "Sat", 6: "Sun"})
    avg = df.groupby("weekday_name")["complexity"].mean().reindex(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
    if not avg.isna().all():
        avg = avg.fillna(0)
        charts.append({
            "id": "08",
            "type": "bar",
            "title": "Average Complexity by Merge Day",
            "subtitle": "When do complex PRs get merged",
            "x": avg.index.tolist(),
            "y": avg.tolist(),
        })

    # 09: Histogram
    if "complexity" in df.columns and not df["complexity"].empty:
        counts, _ = np.histogram(df["complexity"], bins=range(1, 12))
        charts.append({
            "id": "09",
            "type": "bar",
            "title": "Complexity Distribution (Org-wide)",
            "subtitle": "Count per complexity level",
            "x": [str(i) for i in range(1, 11)],
            "y": counts.tolist(),
        })

    return charts


def _extract_fairness(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    df = df.copy()
    df["lines_changed"] = df.get("lines_added", 0).fillna(0) + df.get("lines_deleted", 0).fillna(0)
    df = df[df["lines_changed"] > 0]
    if df.empty or len(df) < 2:
        return charts

    # 10: PR size vs complexity (scatter)
    corr = df["lines_changed"].corr(df["complexity"])
    if pd.isna(corr):
        corr = 0.0
    passed = abs(corr) < 0.3
    verdict = "PASS" if passed else "FAIL"
    charts.append({
        "id": "10",
        "type": "scatter",
        "title": f"PR Size vs Complexity — {verdict} (r={corr:.2f})",
        "subtitle": "Lines changed vs complexity score",
        "data": [[float(r["lines_changed"]), float(r["complexity"])] for _, r in df.iterrows()],
        "xAxisName": "Lines Changed",
        "yAxisName": "Complexity",
    })

    # 11: PR count vs avg complexity (scatter with labels)
    df["developer"] = df.get("developer", df.get("author", "")).fillna("").astype(str)
    df = df[df["developer"] != ""]
    if len(df) >= 2:
        agg = df.groupby("developer").agg(pr_count=("pr_url", "count"), avg_complexity=("complexity", "mean"))
        if len(agg) >= 2:
            charts.append({
                "id": "11",
                "type": "scatterLabel",
                "title": "PR Count vs Avg Complexity (Anti-splitting)",
                "subtitle": "Volume vs avg complexity per dev",
                "data": [{"name": idx, "value": [row["pr_count"], row["avg_complexity"]]} for idx, row in agg.iterrows()],
                "xAxisName": "PR Count",
                "yAxisName": "Avg Complexity",
            })

    return charts


def _extract_advanced(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    df = _ensure_date(df)
    if df.empty:
        return charts

    df = df.copy()
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time

    # 21: Developer line velocity (multi-line)
    dev_col = "developer" if "developer" in df.columns else "author"
    df["developer"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    tdf = df[df["developer"] != ""]
    if not tdf.empty:
        weekly = tdf.groupby(["week", "developer"])["complexity"].sum().unstack(fill_value=0)
        weekly = weekly.reindex(weekly.sum().sort_values(ascending=False).index, axis=1)
        if not weekly.empty:
            weeks = [d.strftime("%Y-%m-%d") for d in weekly.index]
            mapping = load_team_mapping()
            series = [
                {
                    "name": c,
                    "data": weekly[c].tolist(),
                    "team": mapping.get(c, ""),
                }
                for c in weekly.columns
            ]
            charts.append({
                "id": "21",
                "type": "multiLine",
                "title": "Developer Velocity by Week",
                "subtitle": "Complexity per developer per week",
                "x": weeks,
                "series": series,
                "hasPicker": True,
            })

    # 15: Complexity trend by team (multi-line)
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")
    tdf = df[df["team"] != "Unknown"]
    if not tdf.empty:
        all_weeks = sorted(tdf["week"].unique())
        x_labels = [d.strftime("%Y-%m-%d") for d in all_weeks]
        series_list = []
        for team in tdf["team"].unique():
            team_weekly = tdf[tdf["team"] == team].groupby("week")["complexity"].median()
            rolling = team_weekly.rolling(4, min_periods=1).mean()
            aligned = rolling.reindex(all_weeks).tolist()
            if any(pd.notna(v) for v in aligned):
                series_list.append({"name": team, "data": [None if pd.isna(v) else float(v) for v in aligned]})
        if series_list:
            charts.append({
                "id": "15",
                "type": "multiLine",
            "title": "Velocity Trend by Team (Rolling 4w)",
            "subtitle": "Smoothed median complexity per team",
                "x": x_labels,
                "series": series_list,
            })

    # 16: Cumulative complexity by week (area/line)
    df_cum = df.copy()
    df_cum["week"] = pd.to_datetime(df_cum["date"]).dt.to_period("W").dt.start_time
    weekly_sum = df_cum.groupby("week")["complexity"].sum().sort_index()
    cumulative = weekly_sum.cumsum()
    if not cumulative.empty:
        weeks = [d.strftime("%Y-%m-%d") for d in cumulative.index]
        charts.append({
            "id": "16",
            "type": "area",
            "title": "Cumulative Velocity Over Time",
            "subtitle": "Running total of complexity (by week)",
            "x": weeks,
            "y": cumulative.tolist(),
        })

    return charts


def build_all_chart_data(df: pd.DataFrame) -> Dict[str, List[Dict[str, Any]]]:
    """Build chart data for all tabs. Returns {tab: [chart_data, ...]}."""
    return {
        "basic": _extract_basic(df),
        "team": _extract_team(df),
        "risk": _extract_risk(df),
        "fairness": _extract_fairness(df),
        "advanced": _extract_advanced(df),
    }
