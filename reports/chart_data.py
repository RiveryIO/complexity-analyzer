"""Export all report data as JSON for dynamic ECharts rendering. Reuses report logic."""

from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from cli.team_config import get_weekly_headcounts, load_developer_tenure, load_team_mapping


def _departed_developers(cutoff_days: int = 60) -> "set[str]":
    """Usernames whose tenure ended more than `cutoff_days` ago."""
    tenure = load_developer_tenure()
    cutoff = (pd.Timestamp.now().normalize() - pd.Timedelta(days=cutoff_days)).date()
    return {
        name for name, info in tenure.items()
        if info.get("end") and info["end"] < cutoff
    }


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


def _pr_title_from_url(url: str) -> str:
    """Derive a short display title from a PR URL."""
    try:
        # GitHub: https://github.com/owner/repo/pull/123
        # Bitbucket: https://bitbucket.org/ws/repo/pull-requests/123
        parts = url.rstrip("/").split("/")
        number = parts[-1]
        repo = parts[-3]
        return f"{repo} #{number}"
    except (IndexError, ValueError):
        return url


def _build_team_dev_prs(df: pd.DataFrame) -> Dict[str, Any]:
    """Build lookup: team -> developer -> week_start_str -> list[pr_dict].

    Used by the JS drilldown modal when a user clicks a dot on the
    devVelocityMultiLine chart. Only includes developers with known team
    assignments; Bots excluded.
    """
    mapping = load_team_mapping()
    if not mapping:
        return {}

    df = _ensure_date(df.copy())
    if df.empty:
        return {}

    dev_col = "developer" if "developer" in df.columns else "author"
    df["_dev"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)
    df["_team"] = df["_dev"].map(lambda d: mapping.get(d, "") if d else "")
    df = df[(df["_team"] != "") & (df["_dev"] != "") & (df["_team"] != "Bots")]
    if df.empty:
        return {}

    df["_week"] = (
        pd.to_datetime(df["date"], format="mixed", utc=False, errors="coerce")
        .dt.to_period("W")
        .dt.start_time
    )

    result: Dict[str, Any] = {}
    for _, row in df.iterrows():
        team = row["_team"]
        dev = row["_dev"]
        week = row["_week"]
        if pd.isna(week):
            continue
        week_key = week.strftime("%Y-%m-%d")

        pr_url = str(row.get("pr_url", "") or "")
        merged_at = row.get("merged_at", "")
        if pd.notna(merged_at):
            try:
                merged_at = pd.to_datetime(merged_at).strftime("%Y-%m-%d")
            except Exception:
                merged_at = str(merged_at)
        else:
            merged_at = ""

        # Use explanation column as title, fall back to pr_title or URL-based title
        explanation = row.get("explanation", "")
        # Handle NaN/None values from pandas
        if pd.isna(explanation):
            explanation = ""
        else:
            explanation = str(explanation).strip()

        pr_title = row.get("pr_title", "")
        if pd.isna(pr_title):
            pr_title = ""
        else:
            pr_title = str(pr_title).strip()

        if explanation:
            title = explanation
        elif pr_title:
            title = pr_title
        else:
            title = _pr_title_from_url(pr_url)

        pr_dict = {
            "title": title,
            "url": pr_url,
            "complexity": float(row.get("complexity", 0) or 0),
            "merged_at": merged_at,
        }

        result.setdefault(team, {}).setdefault(dev, {}).setdefault(week_key, []).append(pr_dict)

    return result


def _build_cycle_time_prs(df: pd.DataFrame) -> Dict[str, Any]:
    """Lookup: scope -> week_start_str -> list[pr_dict] for merge cycle time drilldown.

    Scope is "_all" for the org-wide chart and team name for per-team charts.
    """
    if "created_at" not in df.columns or "merged_at" not in df.columns:
        return {}

    mapping = load_team_mapping()
    cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
    if cdf.empty:
        return {}

    created = pd.to_datetime(cdf["created_at"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
    merged = pd.to_datetime(cdf["merged_at"], format="mixed", utc=True, errors="coerce").dt.tz_localize(None)
    cdf["_cycle_hours"] = (merged - created).dt.total_seconds() / 3600
    cdf = cdf[cdf["_cycle_hours"] >= 0]
    if cdf.empty:
        return {}
    cdf["_week"] = merged.dt.to_period("W").dt.start_time

    dev_col = "developer" if "developer" in cdf.columns else "author"
    cdf["_dev"] = cdf.get(dev_col, pd.Series([""] * len(cdf))).fillna("").astype(str)
    cdf["_team"] = cdf.get("team", pd.Series([""] * len(cdf))).fillna("")
    cdf["_team"] = cdf.apply(
        lambda row: mapping.get(row["_dev"], "") if not row["_team"] or row["_team"] == "" else row["_team"],
        axis=1,
    )

    result: Dict[str, Any] = {}
    for _, row in cdf.iterrows():
        week = row["_week"]
        if pd.isna(week):
            continue
        week_key = week.strftime("%Y-%m-%d")

        explanation = row.get("explanation", "")
        if pd.isna(explanation):
            explanation = ""
        else:
            explanation = str(explanation).strip()

        pr_title = row.get("pr_title", "")
        if pd.isna(pr_title):
            pr_title = ""
        else:
            pr_title = str(pr_title).strip()

        pr_url = str(row.get("pr_url", "") or "")
        if explanation:
            title = explanation
        elif pr_title:
            title = pr_title
        else:
            title = _pr_title_from_url(pr_url)

        pr_dict = {
            "title": title,
            "url": pr_url,
            "complexity": float(row.get("complexity", 0) or 0),
            "cycle_hours": round(float(row["_cycle_hours"]), 1),
            "developer": row["_dev"],
        }

        result.setdefault("_all", {}).setdefault(week_key, []).append(pr_dict)
        team = row["_team"]
        if team:
            result.setdefault(team, {}).setdefault(week_key, []).append(pr_dict)

    return result


def _build_velocity_prs(df: pd.DataFrame) -> Dict[str, Any]:
    """Lookup: scope -> week_start_str -> list[pr_dict] for velocity drilldown.

    Scope is "_all" for the org-wide chart (excludes Bots/Unknown).
    """
    if df.empty or "date" not in df.columns:
        return {}

    vdf = df.copy()
    vdf["_dt"] = pd.to_datetime(vdf["date"], format="mixed", utc=False, errors="coerce")
    vdf = vdf.dropna(subset=["_dt"])
    if vdf.empty:
        return {}

    vdf["_week"] = vdf["_dt"].dt.to_period("W").dt.start_time
    vdf["_team"] = vdf.get("team", pd.Series([""] * len(vdf))).fillna("").replace("", "Unknown")
    vdf = vdf[~vdf["_team"].isin(["Bots", "Unknown"])]
    if vdf.empty:
        return {}

    dev_col = "developer" if "developer" in vdf.columns else "author"
    vdf["_dev"] = vdf.get(dev_col, pd.Series([""] * len(vdf))).fillna("").astype(str)

    result: Dict[str, Any] = {}
    for _, row in vdf.iterrows():
        week = row["_week"]
        if pd.isna(week):
            continue
        week_key = week.strftime("%Y-%m-%d")

        explanation = row.get("explanation", "")
        explanation = "" if pd.isna(explanation) else str(explanation).strip()
        pr_title = row.get("pr_title", "")
        pr_title = "" if pd.isna(pr_title) else str(pr_title).strip()
        pr_url = str(row.get("pr_url", "") or "")
        title = explanation or pr_title or _pr_title_from_url(pr_url)

        pr_dict = {
            "title": title,
            "url": pr_url,
            "complexity": float(row.get("complexity", 0) or 0),
            "developer": row["_dev"],
            "team": row["_team"],
        }
        result.setdefault("_all", {}).setdefault(week_key, []).append(pr_dict)

    return result


def _extract_basic(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    df = _ensure_date(df)
    if df.empty:
        return charts

    df = df.copy()
    df["_dt"] = pd.to_datetime(df["date"], format="mixed", utc=False, errors="coerce")
    df["week"] = df["_dt"].dt.to_period("W")
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("").replace("", "Unknown")

    # 22: Velocity per capita – org-wide total (first chart)
    non_bot_df = df[~df["team"].isin(["Bots", "Unknown", ""])]
    df["week_ts"] = df["_dt"].dt.to_period("W").dt.start_time
    non_bot_df_ts = non_bot_df.copy()
    non_bot_df_ts["week_ts"] = non_bot_df_ts["_dt"].dt.to_period("W").dt.start_time
    weekly_vel = non_bot_df_ts.groupby("week_ts")["complexity"].sum() if not non_bot_df_ts.empty else pd.Series(dtype=float)
    if not weekly_vel.empty:
        week_dates = sorted(weekly_vel.index)
        week_as_date = [w.date() if hasattr(w, "date") else w for w in week_dates]
        headcounts = get_weekly_headcounts(week_as_date)
        hc_all = headcounts.get("All Teams", [])
        if hc_all:
            per_capita = [
                round(float(weekly_vel.get(w, 0)) / max(h, 1), 2)
                for w, h in zip(week_dates, hc_all)
            ]
            non_zero = [v for v in per_capita if v > 0]
            avg_pc = round(sum(non_zero) / len(non_zero), 1) if non_zero else 0
            week_labels = [w.strftime("%Y-%m-%d") for w in week_dates]
            charts.append({
                "id": "22",
                "type": "line",
                "title": "Velocity Per Capita (by Week)",
                "subtitle": "Org-wide: total complexity / active developers · click a dot to see PRs",
                "overall_avg": avg_pc,
                "overall_avg_unit": "avg / week",
                "x": week_labels,
                "y": per_capita,
                "_section": "Velocity Metrics",
                "_velocity_scope": "_all",
            })

    # 01: Complexity volume over time (bar)
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
            "_section": "Velocity Metrics",
        })

    # 18: Volume by month (bar)
    df["month"] = df["_dt"].dt.to_period("M")
    monthly = df.groupby("month")["complexity"].sum()
    if not monthly.empty:
        charts.append({
            "id": "18",
            "type": "bar",
            "title": "Velocity by Month",
            "subtitle": "Total complexity per month",
            "x": [str(p) for p in monthly.index],
            "y": monthly.tolist(),
            "_section": "Velocity Metrics",
        })

    # 02: PR count vs complexity (dual line)
    weekly_agg = df.groupby("week_ts").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
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
            "_section": "Velocity Metrics",
        })

    # 03: Avg complexity rolling (line)
    weekly_avg = df.groupby("week_ts")["complexity"].mean()
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
            "_section": "Quality & Cycle Time",
        })

    # 19: Avg merge cycle time (line)
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"], format="mixed", utc=False, errors="coerce") - pd.to_datetime(cdf["created_at"], format="mixed", utc=False, errors="coerce")).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if not cdf.empty:
            merged = pd.to_datetime(cdf["merged_at"], format="mixed", utc=False, errors="coerce")
            if merged.dt.tz is not None:
                merged = merged.dt.tz_localize(None, ambiguous="infer")
            cdf["week"] = merged.dt.to_period("W").dt.start_time
            weekly_cycle = cdf.groupby("week")["cycle_hours"].mean()
            if not weekly_cycle.empty:
                labels = [d.strftime("%Y-%m-%d") for d in weekly_cycle.index]
                overall_avg = round(float(weekly_cycle.mean()), 1)
                charts.append({
                    "id": "19",
                    "type": "line",
                    "title": "Average Merge Cycle Time (by Week)",
                    "subtitle": "created_at → merged_at in hours · click a dot to see PRs",
                    "overall_avg": overall_avg,
                    "x": labels,
                    "y": weekly_cycle.tolist(),
                    "_section": "Quality & Cycle Time",
                    "_cycle_scope": "_all",
                })

    # 16: Cumulative complexity by week (area/line)
    df_cum = df.copy()
    df_cum["week_ts"] = pd.to_datetime(df_cum["date"], format="mixed", utc=False, errors="coerce").dt.to_period("W").dt.start_time
    weekly_sum = df_cum.groupby("week_ts")["complexity"].sum().sort_index()
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
            "_section": "Cumulative Trends",
        })

    return charts


def _extract_team(df: pd.DataFrame) -> List[Dict[str, Any]]:
    charts = []
    mapping = load_team_mapping()
    if not mapping:
        return charts

    df = df.copy()
    # First, ensure we have a developer column
    dev_col = "developer" if "developer" in df.columns else "author"
    df["developer"] = df.get(dev_col, pd.Series([""] * len(df))).fillna("").astype(str)

    # Fill in team from developer mapping BEFORE filtering
    # For rows with no team or empty team, map from developer
    df["team"] = df.get("team", pd.Series([""] * len(df))).fillna("")
    df["team"] = df.apply(
        lambda row: mapping.get(row["developer"], "") if not row["team"] or row["team"] == "" else row["team"],
        axis=1
    )

    # Now filter out rows that still have no team
    df = df[df["team"] != ""]
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
                "_subtab": "All",
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
            "_subtab": "All",
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
            "_subtab": "All",
            "x": normalized.index.tolist(),
            "y": normalized.tolist(),
        })

    # 20: Avg merge cycle time by team
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"], format="mixed", utc=False, errors="coerce") - pd.to_datetime(cdf["created_at"], format="mixed", utc=False, errors="coerce")).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if not cdf.empty:
            team_avg = cdf.groupby("team")["cycle_hours"].mean().sort_values(ascending=False)
            charts.append({
                "id": "20",
                "type": "bar",
                "title": "Average Merge Cycle Time per Team",
                "subtitle": "Hours from creation to merge",
                "_subtab": "All",
                "x": team_avg.index.tolist(),
                "y": team_avg.tolist(),
            })

    # 14: Complexity vs cycle time (scatter)
    if "created_at" in df.columns and "merged_at" in df.columns:
        cdf = df.dropna(subset=["created_at", "merged_at"]).copy()
        cdf["cycle_hours"] = (pd.to_datetime(cdf["merged_at"], format="mixed", utc=False, errors="coerce") - pd.to_datetime(cdf["created_at"], format="mixed", utc=False, errors="coerce")).dt.total_seconds() / 3600
        cdf = cdf[cdf["cycle_hours"] >= 0]
        if len(cdf) >= 2:
            charts.append({
                "id": "14",
                "type": "scatter",
                "title": "Complexity vs Cycle Time",
                "subtitle": "PR complexity vs hours to merge",
                "_subtab": "All",
                "data": [[float(r["complexity"]), float(r["cycle_hours"])] for _, r in cdf.iterrows()],
                "xAxisName": "Complexity",
                "yAxisName": "Cycle Time (hours)",
            })

    # 05, 06, 22-T: Per-team charts
    df_full = _ensure_date(df.copy())
    dev_col = "developer" if "developer" in df_full.columns else "author"
    df_full["developer"] = df_full.get(dev_col, pd.Series([""] * len(df_full))).fillna("").astype(str)
    df_full["team"] = df_full["developer"].map(lambda d: mapping.get(d, "") if d else "")
    df_full = df_full[(df_full["team"] != "") & (df_full["developer"] != "")]
    if df_full.empty:
        return charts

    # Pre-compute headcounts for per-team velocity per capita
    all_teams = sorted(t for t in df_full["team"].unique() if t != "Bots")
    df_full_weeks = pd.to_datetime(df_full["date"], format="mixed", utc=False, errors="coerce").dt.to_period("W").dt.start_time
    all_week_dates = sorted(df_full_weeks.unique())
    week_as_date = [w.date() if hasattr(w, "date") else w for w in all_week_dates]
    headcounts = get_weekly_headcounts(week_as_date, teams=all_teams)

    for team in all_teams:
        tdf = df_full[df_full["team"] == team].copy()
        tdf["week"] = pd.to_datetime(tdf["date"], format="mixed", utc=False, errors="coerce").dt.to_period("W").dt.start_time

        # 22-T: Velocity per capita (first in each team sub-tab)
        team_weekly = tdf.groupby("week")["complexity"].sum()
        hc_team = headcounts.get(team, [])
        if not team_weekly.empty and hc_team:
            per_capita = [
                round(float(team_weekly.get(w, 0)) / max(h, 1), 2)
                for w, h in zip(all_week_dates, hc_team)
            ]
            non_zero = [v for v in per_capita if v > 0]
            avg_pc = round(sum(non_zero) / len(non_zero), 1) if non_zero else 0
            week_labels = [w.strftime("%Y-%m-%d") for w in all_week_dates]
            charts.append({
                "id": f"22-{team}",
                "type": "line",
                "title": f"Velocity Per Capita — {team}",
                "subtitle": "Complexity / active developers per week",
                "_subtab": team,
                "overall_avg": avg_pc,
                "overall_avg_unit": "avg / week",
                "x": week_labels,
                "y": per_capita,
            })

        # 30: Developer velocity multi-line (per-dev complexity, clickable dots)
        if not tdf.empty:
            dev_week_cx = tdf.pivot_table(
                index="week",
                columns="developer",
                values="complexity",
                aggfunc="sum",
                fill_value=0,
            )
            dev_week_cnt = tdf.pivot_table(
                index="week",
                columns="developer",
                values="pr_url",
                aggfunc="count",
                fill_value=0,
            )
            dev_week_cx = dev_week_cx.reindex(all_week_dates, fill_value=0)
            dev_week_cnt = dev_week_cnt.reindex(all_week_dates, fill_value=0)
            week_labels_30 = [w.strftime("%Y-%m-%d") for w in all_week_dates]
            departed = _departed_developers()
            devs_sorted = sorted(
                (d for d in dev_week_cx.columns if d not in departed),
                key=lambda x: str(x).lower(),
            )
            series_30 = []
            for dev in devs_sorted:
                cx_vals = [round(float(v), 2) for v in dev_week_cx[dev].tolist()]
                if dev in dev_week_cnt.columns:
                    cnt_vals = [int(v) for v in dev_week_cnt[dev].tolist()]
                else:
                    cnt_vals = [0] * len(all_week_dates)
                series_30.append({
                    "name": dev,
                    "data": cx_vals,
                    "prCounts": cnt_vals,
                })
            if series_30:
                charts.append({
                    "id": f"30-{team}",
                    "type": "devVelocityMultiLine",
                    "title": f"Developer Velocity \u2014 {team}",
                    "subtitle": "Weekly complexity per developer \u00b7 click a dot to see PRs",
                    "_subtab": team,
                    "x": week_labels_30,
                    "series": series_30,
                })

        # 19-T: Avg merge cycle time (by week) for this team
        if "created_at" in tdf.columns and "merged_at" in tdf.columns:
            ctdf = tdf.dropna(subset=["created_at", "merged_at"]).copy()
            ctdf["cycle_hours"] = (
                pd.to_datetime(ctdf["merged_at"], format="mixed", utc=False, errors="coerce")
                - pd.to_datetime(ctdf["created_at"], format="mixed", utc=False, errors="coerce")
            ).dt.total_seconds() / 3600
            ctdf = ctdf[ctdf["cycle_hours"] >= 0]
            if not ctdf.empty:
                merged = pd.to_datetime(ctdf["merged_at"], format="mixed", utc=False, errors="coerce")
                if merged.dt.tz is not None:
                    merged = merged.dt.tz_localize(None, ambiguous="infer")
                ctdf["week"] = merged.dt.to_period("W").dt.start_time
                weekly_cycle = ctdf.groupby("week")["cycle_hours"].mean()
                if not weekly_cycle.empty:
                    labels = [d.strftime("%Y-%m-%d") for d in weekly_cycle.index]
                    overall_avg = round(float(weekly_cycle.mean()), 1)
                    charts.append({
                        "id": f"19-{team}",
                        "type": "line",
                        "title": f"Average Merge Cycle Time — {team}",
                        "subtitle": "created_at → merged_at in hours · click a dot to see PRs",
                        "_subtab": team,
                        "overall_avg": overall_avg,
                        "x": labels,
                        "y": [round(float(v), 1) for v in weekly_cycle.tolist()],
                        "_cycle_scope": team,
                    })

        # 06: Scatter
        agg = tdf.groupby("developer").agg(pr_count=("pr_url", "count"), total_complexity=("complexity", "sum"))
        if len(agg) >= 2:
            charts.append({
                "id": f"06-{team}",
                "type": "scatterLabel",
                "title": f"Complexity vs PR Count — {team}",
                "subtitle": "Per developer",
                "_subtab": team,
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
    df["weekday"] = pd.to_datetime(df["date"], format="mixed", utc=False, errors="coerce").dt.dayofweek
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

    # 10: PR size vs complexity (scatter) - remove outliers using IQR
    # Filter outliers on both axes
    q1_lines = df["lines_changed"].quantile(0.25)
    q3_lines = df["lines_changed"].quantile(0.75)
    iqr_lines = q3_lines - q1_lines
    lines_lower = q1_lines - 1.5 * iqr_lines
    lines_upper = q3_lines + 1.5 * iqr_lines

    q1_complexity = df["complexity"].quantile(0.25)
    q3_complexity = df["complexity"].quantile(0.75)
    iqr_complexity = q3_complexity - q1_complexity
    complexity_lower = q1_complexity - 1.5 * iqr_complexity
    complexity_upper = q3_complexity + 1.5 * iqr_complexity

    df_filtered = df[
        (df["lines_changed"] >= lines_lower) & (df["lines_changed"] <= lines_upper) &
        (df["complexity"] >= complexity_lower) & (df["complexity"] <= complexity_upper)
    ]

    if df_filtered.empty or len(df_filtered) < 2:
        df_filtered = df  # Fall back to original if filtering removes everything

    corr = df_filtered["lines_changed"].corr(df_filtered["complexity"])
    if pd.isna(corr):
        corr = 0.0
    passed = abs(corr) < 0.3
    verdict = "PASS" if passed else "FAIL"

    # Build PR examples for each data point (bucket by complexity and size ranges)
    pr_examples = {}
    for _, row in df_filtered.iterrows():
        complexity_bucket = int(row["complexity"])
        size_bucket = int(row["lines_changed"] // 100) * 100  # Bucket by 100s
        key = f"{complexity_bucket}_{size_bucket}"

        if key not in pr_examples:
            pr_examples[key] = []

        pr_url = row.get("pr_url", "")
        explanation = row.get("explanation", "")
        if pd.isna(explanation):
            explanation = ""
        else:
            explanation = str(explanation).strip()

        pr_title_val = row.get("pr_title", "")
        if pd.isna(pr_title_val):
            pr_title_val = ""
        else:
            pr_title_val = str(pr_title_val).strip()

        if explanation:
            title = explanation
        elif pr_title_val:
            title = pr_title_val
        else:
            title = _pr_title_from_url(pr_url) if pr_url else "Unknown PR"

        pr_examples[key].append({
            "title": title,
            "url": pr_url,
            "complexity": float(row.get("complexity", 0) or 0),
            "lines_changed": int(row.get("lines_changed", 0) or 0),
        })

    charts.append({
        "id": "10",
        "type": "scatter",
        "title": f"PR Size vs Complexity — {verdict} (r={corr:.2f})",
        "subtitle": "Lines changed vs complexity score",
        "data": [[float(r["lines_changed"]), float(r["complexity"])] for _, r in df_filtered.iterrows()],
        "xAxisName": "Lines Changed",
        "yAxisName": "Complexity",
        "_pr_examples": pr_examples,  # Add PR examples for modal
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


def _extract_features() -> Dict[str, Any]:
    """Build chart data + raw table data from features-released.csv."""
    csv_path = Path(__file__).resolve().parent.parent / "features-released.csv"
    if not csv_path.exists():
        return {"charts": [], "rows": []}

    df = pd.read_csv(csv_path, dtype=str).fillna("")
    if df.empty:
        return {"charts": [], "rows": []}

    df["released_date"] = pd.to_datetime(df["released_date"], errors="coerce")
    df = df.dropna(subset=["released_date"])
    df["month"] = df["released_date"].dt.to_period("M")

    rows_for_table = []
    for _, r in df.iterrows():
        rows_for_table.append({
            "feature_id": r.get("feature_id", ""),
            "feature_name": r.get("feature_name", ""),
            "jira_keys": r.get("jira_keys", ""),
            "team": r.get("team", ""),
            "category": r.get("category", ""),
            "is_user_facing": r.get("is_user_facing", ""),
            "released_date": r["released_date"].strftime("%Y-%m-%d"),
            "month": str(r["month"]),
            "ticket_count": r.get("ticket_count", ""),
            "lead_time_days": r.get("lead_time_days", ""),
            "story_points": r.get("story_points", ""),
            "description": r.get("description", ""),
        })

    charts: List[Dict[str, Any]] = []

    # Exclude bug_fix from charts — bugs are tracked in the summary tiles
    # but are not user-facing features for graph purposes.
    df_feat = df[df["category"] != "bug_fix"]

    # 1: Features per month — All teams
    monthly = df_feat.groupby("month").size()
    if not monthly.empty:
        labels = [str(p) for p in monthly.index]
        charts.append({
            "id": "feat-monthly-all",
            "type": "bar",
            "title": "Features Released per Month — All Teams",
            "subtitle": "Click a bar to see the features for that month",
            "x": labels,
            "y": monthly.tolist(),
            "drilldown": True,
        })

    teams = sorted(df_feat["team"].unique())

    # 2: Category breakdown per month (stacked bar — all categories)
    categories = ["feature", "improvement", "tech_debt", "bug_fix"]
    all_months_full = sorted(df["month"].unique())
    cat_series = []
    for cat in categories:
        cdf = df[df["category"] == cat]
        counts = cdf.groupby("month").size().reindex(all_months_full, fill_value=0)
        cat_series.append({"name": cat, "data": counts.tolist()})
    charts.append({
        "id": "feat-category-monthly",
        "type": "stackedBar",
        "title": "Feature Categories per Month",
        "subtitle": "Feature vs improvement vs tech_debt vs bug_fix",
        "x": [str(m) for m in all_months_full],
        "series": cat_series,
        "drilldown": True,
    })

    # 5: Per-team monthly line charts
    for team in teams:
        tdf = df_feat[df_feat["team"] == team]
        t_monthly = tdf.groupby("month").size()
        if not t_monthly.empty:
            charts.append({
                "id": f"feat-monthly-{team.lower()}",
                "type": "bar",
                "title": f"Features Released per Month — {team}",
                "subtitle": f"Click a bar to drill into {team}'s features",
                "x": [str(p) for p in t_monthly.index],
                "y": t_monthly.tolist(),
                "drilldown": True,
                "filter": {"team": team},
            })

    # 6: Average lead time per month (features only, no bug fixes)
    df_lt = df_feat[df_feat["lead_time_days"] != ""].copy()
    df_lt["lead_time_days"] = pd.to_numeric(df_lt["lead_time_days"], errors="coerce")
    df_lt = df_lt.dropna(subset=["lead_time_days"])
    if not df_lt.empty:
        avg_lt = df_lt.groupby("month")["lead_time_days"].mean()
        charts.append({
            "id": "feat-lead-time",
            "type": "line",
            "title": "Average Lead Time per Month",
            "subtitle": "Days from first ticket created to feature released",
            "x": [str(p) for p in avg_lt.index],
            "y": [round(v, 1) for v in avg_lt.tolist()],
        })

    return {"charts": charts, "rows": rows_for_table}


def _extract_leaderboard(df: pd.DataFrame) -> Dict[str, Any]:
    """Build approver leaderboard for three time windows: 30d, 90d, all-time.

    Returns dict with keys '30d', '90d', 'all'. Each value is a list of dicts:
    {rank, reviewer, team, approvals, avg_complexity}, sorted by approvals desc.
    """
    empty: Dict[str, Any] = {"30d": [], "90d": [], "all": []}
    if "approved_by" not in df.columns:
        return empty

    df = _ensure_date(df)
    if df.empty:
        return empty

    df = df.copy()
    df["_date"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["_date"])
    df["approved_by"] = df["approved_by"].fillna("").astype(str).str.strip()
    df["complexity"] = pd.to_numeric(df["complexity"], errors="coerce").fillna(0)

    mapping = load_team_mapping()
    now = pd.Timestamp.now(tz="UTC")

    cutoffs: Dict[str, Any] = {
        "30d": now - pd.Timedelta(days=30),
        "90d": now - pd.Timedelta(days=90),
        "all": None,
    }

    result: Dict[str, Any] = {}
    for period, cutoff in cutoffs.items():
        sub = df[df["approved_by"] != ""].copy()
        if cutoff is not None:
            sub = sub[sub["_date"] >= cutoff]

        if sub.empty:
            result[period] = []
            continue

        agg = (
            sub.groupby("approved_by")
            .agg(approvals=("pr_url", "count"), avg_complexity=("complexity", "mean"))
            .sort_values("approvals", ascending=False)
            .reset_index()
        )

        rows = []
        for rank, (_, row) in enumerate(agg.iterrows(), 1):
            reviewer = row["approved_by"]
            rows.append({
                "rank": rank,
                "reviewer": reviewer,
                "team": mapping.get(reviewer, ""),
                "approvals": int(row["approvals"]),
                "avg_complexity": round(float(row["avg_complexity"]), 1),
            })
        result[period] = rows

    return result


def _extract_hero_stats(df: pd.DataFrame) -> Dict[str, Any]:
    """Extract hero dashboard stats for Overview tab."""
    df = _ensure_date(df)
    if df.empty:
        return {
            "velocity_per_capita": 0,
            "active_developers": 0,
            "total_prs": 0,
            "avg_complexity": 0,
        }

    # Calculate per-capita velocity
    df["week"] = pd.to_datetime(df["date"]).dt.to_period("W").dt.start_time
    weekly = df.groupby("week")["complexity"].sum()
    weeks = sorted([w.date() for w in weekly.index])
    headcounts_dict = get_weekly_headcounts(weeks)
    all_hc = headcounts_dict.get("All Teams", [])
    per_capita = []
    for i, (week, total_cx) in enumerate(weekly.items()):
        hc = all_hc[i] if i < len(all_hc) else 0
        if hc > 0:
            per_capita.append(total_cx / hc)
    velocity = round(np.mean(per_capita), 1) if per_capita else 0

    # Active developers (unique in last 30 days)
    last_30d = df[df["date"] >= (pd.Timestamp.now() - pd.Timedelta(days=30))]
    dev_col = "developer" if "developer" in df.columns else "author"
    active_devs = last_30d[dev_col].nunique() if not last_30d.empty else 0

    # Top active devs in the last 30 days (for the Active Devs tile modal).
    active_devs_list: list[dict] = []
    if not last_30d.empty and dev_col in last_30d.columns:
        grouped = last_30d.groupby(dev_col).agg(
            prs=(dev_col, "size"),
            complexity=("complexity", "sum") if "complexity" in last_30d.columns else (dev_col, "size"),
        )
        if "team" in last_30d.columns:
            team_map = last_30d.groupby(dev_col)["team"].agg(
                lambda s: s.dropna().iloc[0] if not s.dropna().empty else ""
            )
            grouped["team"] = team_map
        grouped = grouped.sort_values("prs", ascending=False)
        for name, row in grouped.iterrows():
            active_devs_list.append({
                "developer": str(name),
                "team": str(row.get("team", "")) if "team" in grouped.columns else "",
                "prs": int(row["prs"]),
                "complexity": round(float(row["complexity"]), 1),
            })

    # 20 most recent merged PRs (for the Total PRs tile modal).
    recent_prs_list: list[dict] = []
    sort_col = "merged_at" if "merged_at" in df.columns and df["merged_at"].notna().any() else "date"
    recent_df = df.sort_values(sort_col, ascending=False).head(20)
    for _, row in recent_df.iterrows():
        merged_at = row.get(sort_col)
        merged_str = ""
        if pd.notna(merged_at):
            try:
                merged_str = pd.to_datetime(merged_at).strftime("%Y-%m-%d")
            except Exception:
                merged_str = str(merged_at)[:10]
        recent_prs_list.append({
            "title": str(row.get("pr_title", "") or ""),
            "url": str(row.get("pr_url", "") or ""),
            "developer": str(row.get(dev_col, "") or ""),
            "team": str(row.get("team", "") or ""),
            "complexity": round(float(row.get("complexity", 0) or 0), 1),
            "merged_at": merged_str,
        })

    # Total PRs and avg complexity
    total_prs = len(df)
    avg_cx = round(df["complexity"].mean(), 1) if "complexity" in df.columns else 0

    return {
        "velocity_per_capita": velocity,
        "active_developers": active_devs,
        "total_prs": total_prs,
        "avg_complexity": avg_cx,
        "active_devs_list": active_devs_list,
        "recent_prs_list": recent_prs_list,
    }


def build_all_chart_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Build chart data for all tabs. Returns {tab: [chart_data, ...]}."""
    # Ensure numeric and date columns are properly typed regardless of how the df was loaded
    df = df.copy()
    for col in ("complexity", "lines_added", "lines_deleted"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    for col in ("date", "merged_at", "created_at"):
        if col in df.columns and not pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = pd.to_datetime(df[col], format="mixed", utc=False, errors="coerce")
    features_data = _extract_features()
    return {
        "basic": _extract_basic(df),
        "team": _extract_team(df),
        "risk": _extract_risk(df),
        "fairness": _extract_fairness(df),
        "features": features_data.get("charts", []),
        "_features_rows": features_data.get("rows", []),
        "leaderboard": _extract_leaderboard(df),
        "_team_dev_prs": _build_team_dev_prs(df),
        "_cycle_time_prs": _build_cycle_time_prs(df),
        "_velocity_prs": _build_velocity_prs(df),
        "_hero_stats": _extract_hero_stats(df),
    }
