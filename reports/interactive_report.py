"""Interactive HTML report - tabbed dashboard with dynamic ECharts (no PNGs)."""

import json
import subprocess
from collections import OrderedDict
from pathlib import Path
from typing import List, Optional

import pandas as pd

from cli.team_config import load_developer_tenure, load_team_mapping
from reports.chart_data import build_all_chart_data

_SKIP_PREFIXES = ("chore: daily sync", "Merge pull request")
_SKIP_MESSAGES = {"wip", "push", "key", "teams", "png ingore", "master report"}

_TYPE_LABELS = {
    "feat": "Feature",
    "fix": "Fix",
    "refactor": "Refactor",
    "chore": "Chore",
    "style": "Style",
    "docs": "Docs",
    "test": "Test",
    "perf": "Perf",
    "ci": "CI",
}


def _build_changelog_data(cwd: Optional[Path] = None) -> list:
    """Build changelog from git history, grouped by week (newest first)."""
    repo = cwd or Path.cwd()
    try:
        raw = subprocess.check_output(
            ["git", "log", "--format=%as|%an|%s", "--since=3 months ago"],
            cwd=repo,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    if not raw:
        return []

    entries = []
    for line in raw.splitlines():
        parts = line.split("|", 2)
        if len(parts) != 3:
            continue
        date_str, author, message = parts
        msg_lower = message.strip().lower()
        if msg_lower in _SKIP_MESSAGES:
            continue
        if any(message.startswith(p) for p in _SKIP_PREFIXES):
            continue
        commit_type = "other"
        display_msg = message
        for prefix, label in _TYPE_LABELS.items():
            if msg_lower.startswith(prefix + ":") or msg_lower.startswith(prefix + "("):
                commit_type = prefix
                colon_idx = message.find(":")
                if colon_idx != -1:
                    display_msg = message[colon_idx + 1:].strip()
                break

        entries.append({
            "date": date_str,
            "author": author,
            "message": display_msg,
            "type": commit_type,
            "typeLabel": _TYPE_LABELS.get(commit_type, "Other"),
        })

    weeks: OrderedDict = OrderedDict()
    for e in entries:
        from datetime import date as _date, timedelta
        d = _date.fromisoformat(e["date"])
        week_start = d - timedelta(days=d.weekday())
        week_key = week_start.isoformat()
        weeks.setdefault(week_key, []).append(e)

    result = []
    for week_key, items in weeks.items():
        result.append({"week": week_key, "entries": items})
    return result


def _build_engineers_data() -> list:
    """Merge team mapping + tenure into a list of dicts for the Engineers tab."""
    team_mapping = load_team_mapping()
    tenure = load_developer_tenure()
    devs_by_team: dict = {}
    for dev, team in team_mapping.items():
        if team == "Bots":
            continue
        info = tenure.get(dev, {})
        entry = {
            "username": dev,
            "team": team,
            "start": str(info["start"]) if info.get("start") else None,
            "end": str(info["end"]) if info.get("end") else None,
            "leaves": [
                {"from": str(lv["from"]), "to": str(lv["to"])}
                for lv in info.get("leaves", [])
            ],
            "active": info.get("end") is None if info.get("start") else None,
        }
        devs_by_team.setdefault(team, []).append(entry)
    result = []
    for team in sorted(devs_by_team):
        members = sorted(devs_by_team[team], key=lambda d: d["username"].lower())
        result.append({"team": team, "members": members})
    return result


def build_interactive_report(
    df: pd.DataFrame,
    output_dir: Path,
    generated_paths: Optional[List[str]] = None,
    csv_path: Optional[Path] = None,
) -> str:
    """Build tabbed HTML dashboard with dynamic ECharts. Returns path to index.html."""
    output_dir = Path(output_dir)
    chart_data = build_all_chart_data(df)
    last_synced = ""
    if csv_path is not None:
        try:
            mtime = Path(csv_path).stat().st_mtime
            from datetime import datetime as _dt
            last_synced = _dt.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
        except OSError:
            last_synced = ""
    hero = chart_data.setdefault("_hero_stats", {})
    hero["last_synced"] = last_synced
    data_json = json.dumps(chart_data, default=str)
    engineers_json = json.dumps(_build_engineers_data(), default=str)
    changelog_json = json.dumps(_build_changelog_data(), default=str)

    out = output_dir / "index.html"
    html = _HTML_TEMPLATE.format(
        chart_data_json=data_json,
        engineers_json=engineers_json,
        changelog_json=changelog_json,
    )
    out.write_text(html, encoding="utf-8")
    return str(out)


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Engineering Velocity — Complexity Analyzer</title>
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%23b45309'/%3E%3Crect x='5' y='18' width='5' height='9' rx='1.5' fill='%23fff' opacity='.85'/%3E%3Crect x='13.5' y='11' width='5' height='16' rx='1.5' fill='%23fff'/%3E%3Crect x='22' y='5' width='5' height='22' rx='1.5' fill='%23fff' opacity='.85'/%3E%3C/svg%3E">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;500;600;700&family=IBM+Plex+Sans:wght@400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
  <style>
    :root {{
      --bg-deep: #f8f9fa;
      --bg-card: #ffffff;
      --bg-elevated: #f1f3f5;
      --border: #e9ecef;
      --border-light: #f1f3f5;
      --text: #212529;
      --text-muted: #6c757d;
      --accent: #b45309;
      --accent-dim: rgba(180, 83, 9, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      margin: 0;
      background: var(--bg-deep);
      color: var(--text);
      min-height: 100vh;
      line-height: 1.5;
    }}
    .page {{ max-width: 1440px; margin: 0 auto; padding: 3rem 3rem 5rem; }}
    header {{ margin-bottom: 1.5rem; padding-bottom: 1.5rem; border-bottom: 1px solid var(--border-light); }}
    .header-row {{ display: flex; align-items: flex-start; justify-content: space-between; gap: 2rem; }}
    .header-text {{ flex: 1; }}
    h1 {{ font-family: 'Syne', sans-serif; font-size: 2.25rem; font-weight: 700; letter-spacing: -0.04em; margin: 0 0 0.5rem; color: var(--text); }}
    .subtitle {{ font-size: 0.95rem; color: var(--text-muted); }}
    .global-search {{
      position: relative;
      width: 280px;
      flex-shrink: 0;
      margin-top: 0.2rem;
    }}
    .global-search input {{
      width: 100%;
      padding: 0.55rem 0.75rem 0.55rem 2.2rem;
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      font-size: 0.85rem;
      border: 1.5px solid var(--border);
      border-radius: 9px;
      background: var(--bg-card);
      color: var(--text);
      outline: none;
      transition: border-color 0.2s, box-shadow 0.2s;
    }}
    .global-search input:focus {{
      border-color: var(--accent);
      box-shadow: 0 0 0 3px var(--accent-dim);
    }}
    .global-search input::placeholder {{ color: var(--text-muted); opacity: 0.6; }}
    .global-search svg {{
      position: absolute;
      left: 0.65rem;
      top: 50%;
      transform: translateY(-50%);
      width: 16px;
      height: 16px;
      color: var(--text-muted);
      pointer-events: none;
    }}
    .global-search .clear-btn {{
      position: absolute;
      right: 0.5rem;
      top: 50%;
      transform: translateY(-50%);
      width: 20px;
      height: 20px;
      border: none;
      background: var(--bg-elevated);
      border-radius: 50%;
      font-size: 0.7rem;
      color: var(--text-muted);
      cursor: pointer;
      display: none;
      align-items: center;
      justify-content: center;
      transition: background 0.15s, color 0.15s;
    }}
    .global-search .clear-btn:hover {{ background: var(--accent-dim); color: var(--accent); }}
    .global-search.has-value .clear-btn {{ display: flex; }}
    .search-count {{
      font-family: 'Syne', sans-serif;
      font-size: 0.8rem;
      font-weight: 500;
      color: var(--text-muted);
      padding: 0.6rem 0 0.2rem;
    }}
    .search-count span {{ color: var(--accent); font-weight: 600; }}
    #search-results {{ display: none; animation: fadeIn 0.25s ease; }}
    #search-results.active {{ display: block; }}
    #search-results .grid {{ grid-template-columns: repeat(auto-fill, minmax(480px, 1fr)); }}
    .tabs {{
      display: flex; gap: 0.5rem; margin-bottom: 1.5rem; padding: 0.75rem 0;
      border-bottom: 2px solid var(--border-light); overflow-x: auto;
      position: sticky; top: 0; z-index: 100;
      background: rgba(248, 249, 250, 0.92); backdrop-filter: blur(8px);
      box-shadow: 0 2px 8px rgba(0,0,0,0.02);
    }}
    .tab {{
      padding: 0.75rem 1.5rem; font-family: 'Syne', sans-serif; font-size: 1rem; font-weight: 600;
      background: transparent; color: var(--text-muted); border: none; border-bottom: 3px solid transparent;
      cursor: pointer; transition: color 0.2s, border-color 0.2s; margin-bottom: -2px;
    }}
    .tab:hover {{ color: var(--text); }}
    .tab.active {{ color: var(--accent); border-bottom-color: var(--accent); }}
    .panel {{ display: none; animation: fadeIn 0.25s ease; }}
    .panel.active {{ display: block; }}
    @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
    .subtabs {{
      display: flex; gap: 0.5rem; margin-bottom: 2.5rem; padding: 0.75rem 0;
      border-bottom: 1px solid var(--border-light); overflow-x: auto;
      position: sticky; top: 60px; z-index: 99;
      background: rgba(248, 249, 250, 0.92); backdrop-filter: blur(8px);
      box-shadow: 0 2px 6px rgba(0,0,0,0.02);
    }}
    .subtab {{
      padding: 0.5rem 1rem; font-family: 'IBM Plex Sans', system-ui, sans-serif; font-size: 0.9rem; font-weight: 500;
      background: transparent; color: var(--text-muted); border: none; border-radius: 6px;
      cursor: pointer; transition: color 0.15s, background 0.15s; white-space: nowrap;
    }}
    .subtab:hover {{ color: var(--text); background: var(--bg-elevated); }}
    .subtab.active {{ color: var(--text); background: var(--accent-dim); font-weight: 600; }}
    .subpanel {{ display: none; animation: fadeIn 0.2s ease; }}
    .subpanel.active {{ display: block; }}
    .grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr)); gap: 2rem;
    }}
    .section-divider {{
      grid-column: 1 / -1;
      margin: 2rem 0 1rem;
      padding-top: 1.5rem;
      border-top: 2px solid var(--border-light);
    }}
    .section-title {{
      font-family: 'Syne', sans-serif;
      font-size: 1.1rem;
      font-weight: 700;
      color: var(--text);
      margin: 0 0 1rem;
      display: flex;
      align-items: center;
      gap: 0.5rem;
    }}
    .section-title::before {{
      content: '';
      width: 4px;
      height: 1.1rem;
      background: var(--accent);
      border-radius: 2px;
    }}
    .jump-nav {{
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.25rem;
      margin-bottom: 2rem;
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
    }}
    .jump-nav-label {{
      font-family: 'Syne', sans-serif;
      font-size: 0.85rem;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-right: 0.5rem;
    }}
    .jump-link {{
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      font-size: 0.85rem;
      color: var(--accent);
      background: transparent;
      border: 1px solid var(--border);
      border-radius: 6px;
      padding: 0.4rem 0.8rem;
      cursor: pointer;
      transition: background 0.15s, border-color 0.15s;
      text-decoration: none;
    }}
    .jump-link:hover {{
      background: var(--accent-dim);
      border-color: var(--accent);
    }}
    .chart-card {{
      background: var(--bg-card); border: 1px solid var(--border-light); border-radius: 12px;
      overflow: hidden; padding: 1.5rem; transition: box-shadow 0.2s, border-color 0.2s;
      scroll-margin-top: 140px;
    }}
    .chart-card:hover {{ box-shadow: 0 8px 24px rgba(0,0,0,0.06); border-color: var(--border); }}
    .chart-card h3 {{ font-family: 'Syne', sans-serif; font-size: 1.05rem; font-weight: 700; margin: 0 0 0.4rem; color: var(--text); }}
    .chart-card .sub {{ font-size: 0.85rem; color: var(--text-muted); margin-bottom: 1rem; line-height: 1.5; }}
    .chart-card .sub .hero-stat {{
      display: inline-flex; align-items: baseline; gap: 0.4rem;
      margin-left: 0.75rem; padding: 0.3rem 0.9rem;
      background: var(--accent-dim);
      border: 1px solid rgba(180,83,9,0.15);
      border-radius: 8px; font-family: 'IBM Plex Mono', monospace;
      letter-spacing: -0.01em; line-height: 1;
    }}
    .chart-card .sub .hero-stat .hero-val {{
      font-size: 1.35rem; font-weight: 700; color: var(--accent);
    }}
    .chart-card .sub .hero-stat .hero-unit {{
      font-size: 0.75rem; font-weight: 500; color: var(--accent); opacity: 0.7;
    }}
    .chart-container {{ width: 100%; height: 320px; }}

    /* Hero dashboard stats */
    .hero-section {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 1.5rem;
      margin-bottom: 3rem;
      padding: 2rem 0 0;
    }}
    .hero-card {{
      background: linear-gradient(135deg, var(--bg-card) 0%, var(--bg-elevated) 100%);
      border: 1px solid var(--border-light);
      border-radius: 16px;
      padding: 2rem 1.75rem;
      text-align: center;
      transition: transform 0.2s, box-shadow 0.2s;
      position: relative;
      overflow: hidden;
    }}
    .hero-card:hover {{
      transform: translateY(-2px);
      box-shadow: 0 12px 32px rgba(0,0,0,0.08);
    }}
    .hero-card::before {{
      content: '';
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      height: 4px;
      background: linear-gradient(90deg, var(--accent) 0%, #d97706 100%);
      opacity: 0;
      transition: opacity 0.2s;
    }}
    .hero-card:hover::before {{
      opacity: 1;
    }}
    .hero-card.hero-clickable {{ cursor: pointer; }}
    .hero-card.hero-clickable:hover {{ box-shadow: 0 16px 40px rgba(0,0,0,0.12); }}
    .hero-value {{
      font-family: 'Syne', sans-serif;
      font-size: 3rem;
      font-weight: 800;
      line-height: 1;
      color: var(--accent);
      margin-bottom: 0.5rem;
      letter-spacing: -0.04em;
    }}
    .hero-label {{
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      font-size: 0.9rem;
      font-weight: 500;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .hero-sublabel {{
      font-size: 0.75rem;
      color: var(--text-muted);
      margin-top: 0.25rem;
      opacity: 0.7;
    }}

    /* Developer picker for multiLine charts */
    .chart-card.has-picker {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: 1fr 230px;
      grid-template-rows: auto auto 1fr;
      gap: 0;
    }}
    .chart-card.has-picker h3 {{ grid-column: 1 / -1; }}
    .chart-card.has-picker .sub {{ grid-column: 1 / -1; }}
    .chart-card.has-picker .chart-container {{ height: 420px; }}
    .picker-panel {{
      border-left: 1px solid var(--border);
      padding: 0.5rem;
      display: flex;
      flex-direction: column;
      gap: 0.4rem;
      min-height: 0;
    }}
    .picker-search {{
      width: 100%;
      padding: 0.4rem 0.6rem;
      border: 1px solid var(--border);
      border-radius: 6px;
      font-size: 0.78rem;
      font-family: 'IBM Plex Sans', system-ui, sans-serif;
      background: var(--bg-elevated);
      color: var(--text);
      outline: none;
      transition: border-color 0.2s;
    }}
    .picker-search:focus {{ border-color: var(--accent); }}
    .picker-search::placeholder {{ color: var(--text-muted); opacity: 0.7; }}
    .picker-actions {{
      display: flex;
      gap: 0.3rem;
      flex-wrap: wrap;
    }}
    .picker-actions button {{
      padding: 0.2rem 0.5rem;
      font-size: 0.68rem;
      font-family: 'Syne', sans-serif;
      font-weight: 500;
      border: 1px solid var(--border);
      border-radius: 5px;
      background: var(--bg-card);
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.15s;
      white-space: nowrap;
    }}
    .picker-actions button:hover {{ background: var(--accent-dim); color: var(--accent); border-color: var(--accent); }}
    .picker-actions button.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}
    .picker-list {{
      flex: 1;
      overflow-y: auto;
      min-height: 0;
    }}
    .picker-list::-webkit-scrollbar {{ width: 4px; }}
    .picker-list::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 2px; }}
    .picker-team-label {{
      font-family: 'Syne', sans-serif;
      font-size: 0.65rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      color: var(--text-muted);
      padding: 0.4rem 0.3rem 0.15rem;
      margin-top: 0.1rem;
    }}
    .picker-item {{
      display: flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.25rem 0.3rem;
      border-radius: 5px;
      cursor: pointer;
      transition: background 0.12s;
      font-size: 0.76rem;
    }}
    .picker-item:hover {{ background: var(--bg-elevated); }}
    .picker-item.hidden {{ display: none; }}
    .picker-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 3px;
      flex-shrink: 0;
      opacity: 0.3;
      transition: opacity 0.15s;
    }}
    .picker-item.selected .picker-swatch {{ opacity: 1; }}
    .picker-name {{
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      color: var(--text-muted);
      transition: color 0.15s;
    }}
    .picker-item.selected .picker-name {{ color: var(--text); font-weight: 500; }}

    /* Todo / Roadmap tab */
    .todo-panel {{
      max-width: 720px;
      margin: 0 auto;
      padding: 0.5rem 0 2rem;
    }}
    .todo-header {{
      margin-bottom: 2rem;
    }}
    .todo-header h2 {{
      font-family: 'Syne', sans-serif;
      font-size: 1.25rem;
      font-weight: 700;
      letter-spacing: -0.02em;
      margin: 0 0 0.35rem;
    }}
    .todo-header p {{
      font-size: 0.875rem;
      color: var(--text-muted);
      margin: 0;
    }}
    .todo-list {{
      display: flex;
      flex-direction: column;
      gap: 0.875rem;
    }}
    .todo-item {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1.1rem 1.25rem;
      display: flex;
      align-items: flex-start;
      gap: 1rem;
      transition: box-shadow 0.2s, border-color 0.2s;
      cursor: default;
    }}
    .todo-item:hover {{
      box-shadow: 0 3px 16px rgba(0,0,0,0.07);
      border-color: rgba(180,83,9,0.2);
    }}
    .todo-number {{
      font-family: 'Syne', sans-serif;
      font-size: 0.75rem;
      font-weight: 700;
      color: var(--accent);
      background: var(--accent-dim);
      border-radius: 6px;
      width: 26px;
      height: 26px;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      margin-top: 0.1rem;
    }}
    .todo-body {{ flex: 1; min-width: 0; }}
    .todo-title {{
      font-family: 'Syne', sans-serif;
      font-size: 0.95rem;
      font-weight: 600;
      margin: 0 0 0.3rem;
      line-height: 1.3;
    }}
    .todo-desc {{
      font-size: 0.82rem;
      color: var(--text-muted);
      margin: 0 0 0.6rem;
      line-height: 1.5;
    }}
    .todo-badge {{
      display: inline-block;
      font-size: 0.67rem;
      font-family: 'Syne', sans-serif;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 0.15rem 0.5rem;
      border-radius: 4px;
      background: var(--bg-elevated);
      color: var(--text-muted);
      border: 1px solid var(--border);
    }}

    /* Engineers tab */
    .eng-panel {{ max-width: 960px; margin: 0 auto; padding: 0 0 3rem; }}
    .eng-header {{ margin-bottom: 1.5rem; }}
    .eng-header h2 {{
      font-family: 'Syne', sans-serif; font-size: 1.25rem;
      font-weight: 700; color: var(--text); margin: 0 0 0.3rem;
    }}
    .eng-header p {{ font-size: 0.85rem; color: var(--text-muted); margin: 0; }}
    .eng-stats {{
      display: flex; gap: 0.75rem; margin-bottom: 1.75rem; flex-wrap: wrap;
    }}
    .eng-stat {{
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
      padding: 0.7rem 1.1rem; min-width: 100px; text-align: center;
    }}
    .eng-stat-val {{
      font-family: 'IBM Plex Mono', monospace; font-size: 1.4rem;
      font-weight: 600; color: var(--accent); line-height: 1;
    }}
    .eng-stat-lbl {{
      font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem;
      text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .eng-team {{
      margin-bottom: 1.25rem; background: var(--bg-card);
      border: 1px solid var(--border); border-radius: 10px; overflow: hidden;
    }}
    .eng-team-hdr {{
      display: flex; align-items: center; gap: 0.6rem;
      padding: 0.75rem 1rem; background: var(--bg-elevated);
      border-bottom: 1px solid var(--border); cursor: pointer;
      user-select: none; transition: background 0.15s;
    }}
    .eng-team-hdr:hover {{ background: var(--accent-dim); }}
    .eng-team-name {{
      font-family: 'Syne', sans-serif; font-size: 0.95rem;
      font-weight: 600; color: var(--text);
    }}
    .eng-team-count {{
      font-family: 'IBM Plex Mono', monospace; font-size: 0.72rem;
      color: var(--accent); background: var(--accent-dim); padding: 0.15rem 0.45rem;
      border-radius: 4px; font-weight: 500;
    }}
    .eng-team-chevron {{
      margin-left: auto; font-size: 0.7rem; color: var(--text-muted);
      transition: transform 0.2s;
    }}
    .eng-team.open .eng-team-chevron {{ transform: rotate(90deg); }}
    .eng-team-body {{ display: none; }}
    .eng-team.open .eng-team-body {{ display: block; }}
    .eng-tbl {{
      width: 100%; border-collapse: collapse; font-size: 0.82rem;
    }}
    .eng-tbl th {{
      text-align: left; padding: 0.5rem 1rem; font-family: 'IBM Plex Mono', monospace;
      font-size: 0.7rem; font-weight: 500; text-transform: uppercase;
      letter-spacing: 0.06em; color: var(--text-muted);
      border-bottom: 1px solid var(--border);
    }}
    .eng-tbl td {{
      padding: 0.45rem 1rem; border-bottom: 1px solid var(--bg-elevated);
      color: var(--text); vertical-align: middle;
    }}
    .eng-tbl tr:last-child td {{ border-bottom: none; }}
    .eng-tbl tr:hover td {{ background: var(--bg-elevated); }}
    .eng-badge {{
      display: inline-block; font-size: 0.65rem; font-family: 'IBM Plex Mono', monospace;
      font-weight: 500; padding: 0.12rem 0.4rem; border-radius: 3px;
      letter-spacing: 0.03em;
    }}
    .eng-badge.active {{ background: #d1fae5; color: #065f46; }}
    .eng-badge.ended {{ background: #fee2e2; color: #991b1b; }}
    .eng-badge.on-leave {{ background: #fef3c7; color: #92400e; }}
    .eng-badge.no-data {{ background: var(--bg-elevated); color: var(--text-muted); }}
    .eng-leave-tag {{
      display: inline-block; font-size: 0.62rem; font-family: 'IBM Plex Mono', monospace;
      padding: 0.1rem 0.35rem; border-radius: 3px; margin-left: 0.3rem;
      background: #fef3c7; color: #92400e;
    }}
    .eng-timeline {{
      height: 6px; background: var(--bg-elevated); border-radius: 3px;
      position: relative; min-width: 120px; overflow: visible;
    }}
    .eng-timeline-bar {{
      position: absolute; height: 100%; border-radius: 3px; background: var(--accent);
      opacity: 0.7; min-width: 2px;
    }}
    .eng-timeline-leave {{
      position: absolute; height: 100%; border-radius: 2px;
      background: repeating-linear-gradient(45deg, #fbbf24, #fbbf24 2px, #fef3c7 2px, #fef3c7 4px);
    }}

    /* Changelog tab */
    .cl-panel {{ max-width: 960px; margin: 0 auto; padding: 0 0 3rem; }}
    .cl-header {{ margin-bottom: 1.5rem; }}
    .cl-header h2 {{
      font-family: 'Syne', sans-serif; font-size: 1.25rem;
      font-weight: 700; color: var(--text); margin: 0 0 0.3rem;
    }}
    .cl-header p {{ font-size: 0.85rem; color: var(--text-muted); margin: 0; }}
    .cl-stats {{
      display: flex; gap: 0.75rem; margin-bottom: 1.75rem; flex-wrap: wrap;
    }}
    .cl-stat {{
      background: var(--bg-card); border: 1px solid var(--border); border-radius: 8px;
      padding: 0.7rem 1.1rem; min-width: 90px; text-align: center;
    }}
    .cl-stat-val {{
      font-family: 'IBM Plex Mono', monospace; font-size: 1.4rem;
      font-weight: 600; color: var(--accent); line-height: 1;
    }}
    .cl-stat-lbl {{
      font-size: 0.7rem; color: var(--text-muted); margin-top: 0.25rem;
      text-transform: uppercase; letter-spacing: 0.05em;
    }}
    .cl-week {{
      margin-bottom: 1.5rem;
    }}
    .cl-week-hdr {{
      display: flex; align-items: center; gap: 0.6rem;
      margin-bottom: 0.5rem; padding-bottom: 0.4rem;
      border-bottom: 2px solid var(--accent-dim);
    }}
    .cl-week-label {{
      font-family: 'Syne', sans-serif; font-size: 0.95rem;
      font-weight: 700; color: var(--text);
    }}
    .cl-week-count {{
      font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
      color: var(--accent); background: var(--accent-dim); padding: 0.12rem 0.4rem;
      border-radius: 4px; font-weight: 500;
    }}
    .cl-entry {{
      display: flex; align-items: flex-start; gap: 0.6rem;
      padding: 0.4rem 0; position: relative;
    }}
    .cl-entry + .cl-entry {{ border-top: 1px solid var(--bg-elevated); }}
    .cl-type-badge {{
      display: inline-block; font-size: 0.6rem; font-family: 'IBM Plex Mono', monospace;
      font-weight: 600; padding: 0.12rem 0.4rem; border-radius: 3px;
      letter-spacing: 0.03em; text-transform: uppercase; white-space: nowrap;
      min-width: 52px; text-align: center; flex-shrink: 0; margin-top: 0.15rem;
    }}
    .cl-type-badge.feat {{ background: #dbeafe; color: #1e40af; }}
    .cl-type-badge.fix {{ background: #fee2e2; color: #991b1b; }}
    .cl-type-badge.refactor {{ background: #ede9fe; color: #5b21b6; }}
    .cl-type-badge.chore {{ background: var(--bg-elevated); color: var(--text-muted); }}
    .cl-type-badge.style {{ background: #fce7f3; color: #9d174d; }}
    .cl-type-badge.docs {{ background: #d1fae5; color: #065f46; }}
    .cl-type-badge.test {{ background: #fef3c7; color: #92400e; }}
    .cl-type-badge.perf {{ background: #ccfbf1; color: #134e4a; }}
    .cl-type-badge.ci {{ background: #e0e7ff; color: #3730a3; }}
    .cl-type-badge.other {{ background: var(--bg-elevated); color: var(--text-muted); }}
    .cl-msg {{
      font-size: 0.85rem; color: var(--text); flex: 1; line-height: 1.5;
    }}
    .cl-meta {{
      font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
      color: var(--text-muted); white-space: nowrap; flex-shrink: 0;
      margin-top: 0.2rem;
    }}
    .cl-filter-bar {{
      display: flex; gap: 0.4rem; flex-wrap: wrap; margin-bottom: 1.25rem;
    }}
    .cl-filter {{
      font-family: 'IBM Plex Mono', monospace; font-size: 0.68rem;
      padding: 0.25rem 0.6rem; border-radius: 4px; border: 1px solid var(--border);
      background: var(--bg-card); color: var(--text-muted); cursor: pointer;
      transition: all 0.15s;
    }}
    .cl-filter:hover {{ border-color: var(--accent); color: var(--accent); }}
    .cl-filter.active {{ background: var(--accent); color: #fff; border-color: var(--accent); }}

    /* Drilldown modal overlay */
    .drilldown-overlay {{
      position: fixed; inset: 0; z-index: 1000;
      background: rgba(20, 22, 28, 0.55);
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
      display: flex; align-items: flex-start; justify-content: center;
      padding: 4vh 2rem;
      opacity: 0;
      pointer-events: none;
      transition: opacity 0.25s ease;
    }}
    .drilldown-overlay.open {{
      opacity: 1;
      pointer-events: auto;
    }}
    .drilldown-modal {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 14px;
      width: 100%;
      max-width: 1280px;
      max-height: 88vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 24px 80px rgba(0,0,0,0.18), 0 2px 6px rgba(0,0,0,0.06);
      transform: translateY(12px);
      transition: transform 0.25s ease;
    }}
    .drilldown-overlay.open .drilldown-modal {{
      transform: translateY(0);
    }}
    .drilldown-header {{
      display: flex; align-items: center; justify-content: space-between;
      padding: 1.2rem 1.5rem;
      border-bottom: 1px solid var(--border);
      flex-shrink: 0;
    }}
    .drilldown-header h2 {{
      font-family: 'Syne', sans-serif;
      font-size: 1.1rem;
      font-weight: 700;
      margin: 0;
      letter-spacing: -0.02em;
    }}
    .drilldown-header .dd-count {{
      font-size: 0.8rem;
      color: var(--text-muted);
      margin-left: 0.6rem;
      font-weight: 400;
    }}
    .drilldown-close {{
      width: 32px; height: 32px;
      border: 1px solid var(--border);
      border-radius: 8px;
      background: var(--bg-elevated);
      color: var(--text-muted);
      font-size: 1.1rem;
      cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      transition: all 0.15s;
    }}
    .drilldown-close:hover {{
      background: var(--accent-dim);
      color: var(--accent);
      border-color: var(--accent);
    }}
    .drilldown-body {{
      flex: 1;
      overflow: auto;
      padding: 0;
    }}
    .dd-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 0.82rem;
    }}
    .dd-table thead {{
      position: sticky; top: 0;
      background: var(--bg-elevated);
      z-index: 1;
    }}
    .dd-table th {{
      font-family: 'Syne', sans-serif;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      padding: 0.7rem 0.8rem;
      text-align: left;
      white-space: nowrap;
      border-bottom: 2px solid var(--border);
    }}
    .dd-table td {{
      padding: 0.6rem 0.8rem;
      border-bottom: 1px solid var(--border);
      vertical-align: top;
      max-width: 300px;
    }}
    .dd-table tr:hover td {{
      background: rgba(180, 83, 9, 0.04);
    }}
    .dd-table .cell-id {{
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.78rem;
      font-weight: 500;
      white-space: nowrap;
    }}
    .dd-table .cell-id a {{
      color: var(--accent);
      text-decoration: none;
      transition: color 0.15s, background 0.15s;
      padding: 0.1rem 0.3rem;
      border-radius: 4px;
      margin: -0.1rem -0.3rem;
    }}
    .dd-table .cell-id a:hover {{
      background: var(--accent-dim);
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .dd-table .cell-id a::after {{
      content: '\u2009\u2197';
      font-size: 0.65rem;
      opacity: 0;
      transition: opacity 0.15s;
    }}
    .dd-table .cell-id a:hover::after {{
      opacity: 0.7;
    }}
    .cell-tickets {{
      max-width: 260px;
    }}
    .ticket-pill {{
      display: inline-block;
      font-family: 'IBM Plex Mono', monospace;
      font-size: 0.68rem;
      font-weight: 500;
      color: #0d9488;
      background: rgba(13, 148, 136, 0.08);
      border: 1px solid rgba(13, 148, 136, 0.15);
      padding: 0.08rem 0.35rem;
      border-radius: 4px;
      margin: 0.1rem 0.15rem 0.1rem 0;
      text-decoration: none;
      transition: all 0.15s;
      white-space: nowrap;
    }}
    .ticket-pill:hover {{
      background: rgba(13, 148, 136, 0.16);
      border-color: rgba(13, 148, 136, 0.35);
      color: #065f46;
      text-decoration: underline;
      text-underline-offset: 2px;
    }}
    .ticket-overflow {{
      display: inline-block;
      font-family: 'Syne', sans-serif;
      font-size: 0.65rem;
      font-weight: 600;
      color: var(--text-muted);
      background: var(--bg-elevated);
      border: 1px solid var(--border);
      padding: 0.08rem 0.35rem;
      border-radius: 4px;
      margin: 0.1rem 0;
      cursor: default;
    }}
    .dd-table .cell-name {{
      font-weight: 500;
      color: var(--text);
      max-width: 420px;
      position: relative;
    }}
    .dd-table .cell-name .name-text {{
      display: -webkit-box;
      -webkit-line-clamp: 1;
      -webkit-box-orient: vertical;
      overflow: hidden;
      transition: all 0.2s ease;
      cursor: default;
    }}
    .dd-table tr:hover .cell-name .name-text {{
      -webkit-line-clamp: unset;
      overflow: visible;
      color: var(--accent);
    }}
    .dd-badge {{
      display: inline-block;
      font-size: 0.65rem;
      font-family: 'Syne', sans-serif;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      padding: 0.12rem 0.45rem;
      border-radius: 4px;
      white-space: nowrap;
    }}
    .dd-badge.cat-feature {{ background: #dbeafe; color: #1e40af; }}
    .dd-badge.cat-bug_fix {{ background: #fee2e2; color: #991b1b; }}
    .dd-badge.cat-improvement {{ background: #d1fae5; color: #065f46; }}
    .dd-badge.cat-tech_debt {{ background: #e5e7eb; color: #374151; }}
    .dd-badge.uf-true {{ background: #fef3c7; color: #92400e; }}
    .dd-badge.uf-false {{ background: #f3f4f6; color: #6b7280; }}
    .chart-card.drilldown-enabled {{
      cursor: pointer;
    }}
    .chart-card.drilldown-enabled:hover {{
      border-color: rgba(180, 83, 9, 0.35);
      box-shadow: 0 4px 20px rgba(180, 83, 9, 0.10);
    }}
    .chart-card .drill-hint {{
      font-size: 0.7rem;
      color: var(--accent);
      opacity: 0.6;
      font-family: 'Syne', sans-serif;
      font-weight: 500;
      letter-spacing: 0.02em;
      margin-top: 0.4rem;
      transition: opacity 0.2s;
    }}
    .chart-card.drilldown-enabled:hover .drill-hint {{
      opacity: 1;
    }}

    /* Features summary cards */
    .feat-summary {{
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
      gap: 1rem;
      margin-bottom: 2rem;
    }}
    .feat-stat {{
      background: var(--bg-card);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 1rem 1.1rem;
      transition: box-shadow 0.2s;
    }}
    .feat-stat:hover {{
      box-shadow: 0 4px 16px rgba(0,0,0,0.06);
    }}
    .feat-stat .stat-value {{
      font-family: 'Syne', sans-serif;
      font-size: 1.6rem;
      font-weight: 700;
      color: var(--text);
      letter-spacing: -0.03em;
      line-height: 1;
    }}
    .feat-stat .stat-label {{
      font-size: 0.78rem;
      color: var(--text-muted);
      margin-top: 0.3rem;
    }}
    /* Leaderboard tab */
    .lb-panel {{ padding: 1.5rem 0; }}
    .lb-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; flex-wrap: wrap; gap: 1rem; }}
    .lb-header h2 {{ font-family: 'Syne', sans-serif; font-size: 1.3rem; font-weight: 700; margin: 0; }}
    .lb-periods {{ display: flex; gap: 0.5rem; }}
    .lb-period {{ padding: 0.4rem 1rem; border: 1.5px solid var(--border); border-radius: 8px; background: var(--bg-card); cursor: pointer; font-family: inherit; font-size: 0.85rem; color: var(--text-muted); transition: border-color 0.15s, color 0.15s, background 0.15s; }}
    .lb-period.active {{ border-color: var(--accent); color: var(--accent); background: var(--accent-dim); }}
    .lb-rank {{ font-family: 'IBM Plex Mono', monospace; font-size: 1.05rem; text-align: center; width: 2.5rem; }}
    .lb-count {{ font-family: 'IBM Plex Mono', monospace; font-weight: 500; color: var(--accent); }}
    .lb-reviewer {{ font-weight: 500; }}
    .gold-row td   {{ background: rgba(251, 191, 36, 0.10) !important; }}
    .silver-row td {{ background: rgba(156, 163, 175, 0.12) !important; }}
    .bronze-row td {{ background: rgba(180, 83, 9, 0.07) !important; }}
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="header-row">
        <div class="header-text">
          <h1>Engineering Velocity</h1>
          <p class="subtitle">Rivery Data Integration engineering velocity</p>
        </div>
        <div class="global-search" id="global-search">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
          <input type="text" id="chart-search" placeholder="Filter charts by title..." autocomplete="off" spellcheck="false">
          <button class="clear-btn" id="search-clear">&times;</button>
        </div>
      </div>
    </header>
    <div class="tabs" id="tabs"></div>
    <div class="subtabs" id="subtabs-nav" style="display: none;"></div>
    <div id="panels"></div>
    <div id="search-results"></div>
  </div>

  <!-- Drilldown modal -->
  <div class="drilldown-overlay" id="drilldown-overlay">
    <div class="drilldown-modal">
      <div class="drilldown-header">
        <h2 id="dd-title">Features</h2>
        <button class="drilldown-close" id="dd-close">&times;</button>
      </div>
      <div class="drilldown-body" id="dd-body"></div>
    </div>
  </div>

  <!-- Developer drill modal -->
  <div class="drilldown-overlay" id="dev-drill-overlay">
    <div class="drilldown-modal">
      <div class="drilldown-header">
        <h2 id="dev-drill-title">Developer PRs</h2>
        <button class="drilldown-close" id="dev-drill-close">&times;</button>
      </div>
      <div class="drilldown-body" id="dev-drill-body"></div>
    </div>
  </div>

  <script>
    const chartData = {chart_data_json};
    const engineersData = {engineers_json};
    const changelogData = {changelog_json};
    const heroStats = chartData._hero_stats || {{}};
    // Tab groups: consolidate 10 tabs → 4 main groups
    const tabGroups = {{
      overview: {{ label: '📊 Overview', tabs: ['basic', 'team'] }},
      analytics: {{ label: '🔍 Analytics', tabs: ['features', 'risk', 'fairness'] }},
      people: {{ label: '👥 People', tabs: ['engineers', 'leaderboard'] }},
      planning: {{ label: '📋 Planning', tabs: ['todo', 'changelog'] }}
    }};
    const groupOrder = ['overview', 'analytics', 'people', 'planning'];
    const tabLabels = {{ basic: 'Basic', team: 'Team', risk: 'Risk', fairness: 'Fairness', features: 'Features', leaderboard: 'Leaderboard', todo: 'Roadmap', engineers: 'Engineers', changelog: 'Changelog' }};
    // Flatten for backwards compat
    const tabOrder = groupOrder.flatMap(g => tabGroups[g].tabs);

    const CHART_THEME = {{
      backgroundColor: 'transparent',
      textStyle: {{ color: '#6b7280', fontFamily: 'IBM Plex Sans' }},
      title: {{ textStyle: {{ color: '#1a1d24' }}, subtextStyle: {{ color: '#6b7280' }} }},
      legend: {{ textStyle: {{ color: '#6b7280' }} }},
      axisLine: {{ lineStyle: {{ color: '#e2e4e8' }} }},
      axisLabel: {{ color: '#6b7280' }},
      splitLine: {{ lineStyle: {{ color: '#eef0f2' }} }},
    }};

    function syncURL() {{
      const params = new URLSearchParams();
      const firstTab = tabGroups[groupOrder[0]].tabs[0];
      if (activeTab && activeTab !== firstTab) {{
        params.set('tab', activeTab);
      }}
      // Include active subtab (e.g. team name) if the active panel has subtabs
      const activePanel = document.querySelector('.panel.active');
      if (activePanel) {{
        const activeSubtabBtn = activePanel.querySelector('.subtab.active');
        if (activeSubtabBtn && activeSubtabBtn.dataset.subtab) {{
          const allSubtabBtns = activePanel.querySelectorAll('.subtab');
          const firstSubtab = allSubtabBtns[0] && allSubtabBtns[0].dataset.subtab;
          if (activeSubtabBtn.dataset.subtab !== firstSubtab) {{
            params.set('subtab', activeSubtabBtn.dataset.subtab);
          }}
        }}
      }}
      const q = document.getElementById('chart-search').value.trim();
      if (q) params.set('q', q);
      const qs = params.toString();
      history.replaceState(null, '', window.location.pathname + (qs ? '?' + qs : ''));
    }}

    const COLORS = ['#b45309', '#0d9488', '#7c3aed', '#2563eb', '#ea580c', '#16a34a', '#dc2626', '#6b7280'];

    function applyTimeZoom(opt, options) {{
      // Adds wheel/pinch zoom + a slider mini-map to time-series category charts.
      // topSlider=true places the slider above the grid (use when legend is at bottom).
      options = options || {{}};
      const topSlider = !!options.topSlider;
      const inside = {{ type: 'inside', xAxisIndex: 0, throttle: 30, zoomOnMouseWheel: 'shift', moveOnMouseWheel: false, moveOnMouseMove: false }};
      const grid = opt.grid || {{}};
      let slider;
      if (topSlider) {{
        slider = {{ type: 'slider', xAxisIndex: 0, top: 6, height: 14, brushSelect: false, showDetail: false }};
        opt.grid = {{ ...grid, top: Math.max(grid.top || 40, 56) }};
      }} else {{
        const curBottom = grid.bottom != null ? grid.bottom : 60;
        slider = {{ type: 'slider', xAxisIndex: 0, bottom: 8, height: 14, brushSelect: false, showDetail: false }};
        opt.grid = {{ ...grid, bottom: curBottom + 28 }};
      }}
      opt.dataZoom = [inside, slider];
      return opt;
    }}

    function renderBar(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'bar', data: c.y, barWidth: '50%', barMinWidth: 20, barMaxWidth: 100, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      applyTimeZoom(opt);
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderLine(container, c) {{
      const seriesItem = {{ type: 'line', data: c.y, smooth: true, symbol: 'circle', symbolSize: 6, itemStyle: {{ color: COLORS[0] }} }};
      if (c.overall_avg != null) {{
        seriesItem.markLine = {{
          silent: true,
          symbol: 'none',
          lineStyle: {{ type: 'dashed', color: '#b45309', width: 1.5, opacity: 0.6 }},
          label: {{ formatter: c.overall_avg + 'h avg', fontSize: 11, color: '#b45309', fontFamily: 'IBM Plex Mono, monospace' }},
          data: [{{ yAxis: c.overall_avg }}],
        }};
      }}
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [seriesItem],
      }};
      applyTimeZoom(opt);
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderDualLine(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: [c.y1Name, c.y2Name] }},
        grid: {{ left: 50, right: 50, top: 50, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: [
          {{ type: 'value', name: c.y1Name, position: 'left', axisLine: {{ show: true, lineStyle: {{ color: COLORS[0] }} }} }},
          {{ type: 'value', name: c.y2Name, position: 'right', axisLine: {{ show: true, lineStyle: {{ color: COLORS[1] }} }} }},
        ],
        series: [
          {{ type: 'line', name: c.y1Name, data: c.y1, smooth: true, yAxisIndex: 0, itemStyle: {{ color: COLORS[0] }} }},
          {{ type: 'line', name: c.y2Name, data: c.y2, smooth: true, yAxisIndex: 1, itemStyle: {{ color: COLORS[1] }} }},
        ],
      }};
      applyTimeZoom(opt);
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderMultiLine(container, c) {{
      const hasPicker = c.hasPicker && c.series && c.series.length > 6;
      const allSeries = (c.series || []);
      const colorMap = {{}};
      allSeries.forEach((s, i) => {{ colorMap[s.name] = COLORS[i % COLORS.length]; }});

      const series = allSeries.map((s, i) => ({{
        type: 'line', name: s.name, data: s.data, smooth: true, symbol: 'circle', symbolSize: 4,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));

      const legendCfg = hasPicker
        ? {{ show: false }}
        : {{
            type: 'scroll', bottom: 0, selectedMode: 'single', selector: true,
            pageIconSize: 10, pageTextStyle: {{ fontSize: 10 }},
            pageFormatter: ({{ current, total }}) => `${{current}}/${{total}}`,
            pageButtonItemGap: 4, itemGap: 8, itemWidth: 14, itemHeight: 10, textStyle: {{ fontSize: 10 }},
          }};

      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis', confine: true,
          formatter: function(params) {{
            const active = params.filter(p => p.value != null && p.value !== 0);
            if (!active.length) return '';
            active.sort((a, b) => (b.value || 0) - (a.value || 0));
            let s = `<b>${{active[0].axisValue}}</b><br/>`;
            active.forEach(p => {{
              s += `${{p.marker}} ${{p.seriesName}}: <b>${{p.value}}</b><br/>`;
            }});
            return s;
          }}
        }},
        legend: legendCfg,
        grid: {{ left: 50, right: 20, top: 30, bottom: hasPicker ? 30 : 80 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series,
      }};
      applyTimeZoom(opt, {{ topSlider: true }});
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());

      if (hasPicker) {{
        const pickerId = container.id + '-picker';
        const pickerEl = document.getElementById(pickerId);
        if (pickerEl) buildPicker(pickerEl, chart, allSeries, colorMap);
      }}

      return chart;
    }}

    function buildPicker(pickerEl, chart, allSeries, colorMap) {{
      const teams = {{}};
      const noTeam = [];
      allSeries.forEach(s => {{
        const t = s.team || '';
        if (t) {{
          if (!teams[t]) teams[t] = [];
          teams[t].push(s.name);
        }} else {{
          noTeam.push(s.name);
        }}
      }});
      const teamOrder = Object.keys(teams).sort();
      const selected = new Set();
      allSeries.forEach(s => selected.add(s.name));

      const searchInput = document.createElement('input');
      searchInput.className = 'picker-search';
      searchInput.placeholder = 'Search developers...';
      pickerEl.appendChild(searchInput);

      const actionsDiv = document.createElement('div');
      actionsDiv.className = 'picker-actions';
      pickerEl.appendChild(actionsDiv);

      const listDiv = document.createElement('div');
      listDiv.className = 'picker-list';
      pickerEl.appendChild(listDiv);

      const itemEls = {{}};

      function addTeamSection(teamName, devs) {{
        const label = document.createElement('div');
        label.className = 'picker-team-label';
        label.textContent = teamName;
        label.dataset.teamlabel = teamName;
        listDiv.appendChild(label);
        devs.forEach(name => {{
          const item = document.createElement('div');
          item.className = 'picker-item' + (selected.has(name) ? ' selected' : '');
          item.dataset.name = name.toLowerCase();
          item.dataset.team = teamName;
          const swatch = document.createElement('span');
          swatch.className = 'picker-swatch';
          swatch.style.background = colorMap[name] || '#999';
          const nameEl = document.createElement('span');
          nameEl.className = 'picker-name';
          nameEl.textContent = name;
          nameEl.title = name;
          item.appendChild(swatch);
          item.appendChild(nameEl);
          item.addEventListener('click', () => toggleDev(name));
          listDiv.appendChild(item);
          itemEls[name] = item;
        }});
      }}

      teamOrder.forEach(t => addTeamSection(t, teams[t]));
      if (noTeam.length) addTeamSection('Other', noTeam);

      // team filter buttons
      const allBtn = document.createElement('button');
      allBtn.textContent = 'All';
      allBtn.addEventListener('click', () => {{
        selected.clear();
        allSeries.forEach(s => selected.add(s.name));
        syncChart();
      }});
      actionsDiv.appendChild(allBtn);

      const noneBtn = document.createElement('button');
      noneBtn.textContent = 'None';
      noneBtn.addEventListener('click', () => {{
        selected.clear();
        syncChart();
      }});
      actionsDiv.appendChild(noneBtn);

      teamOrder.forEach(t => {{
        const btn = document.createElement('button');
        btn.textContent = t;
        btn.addEventListener('click', () => {{
          selected.clear();
          teams[t].forEach(d => selected.add(d));
          syncChart();
        }});
        actionsDiv.appendChild(btn);
      }});

      searchInput.addEventListener('input', () => {{
        const q = searchInput.value.toLowerCase();
        const labels = listDiv.querySelectorAll('.picker-team-label');
        labels.forEach(l => {{ l.style.display = 'none'; }});
        const visibleTeams = new Set();
        Object.entries(itemEls).forEach(([name, el]) => {{
          const match = name.toLowerCase().includes(q);
          el.classList.toggle('hidden', !match);
          if (match) visibleTeams.add(el.dataset.team);
        }});
        labels.forEach(l => {{
          if (visibleTeams.has(l.dataset.teamlabel)) l.style.display = '';
        }});
      }});

      function toggleDev(name) {{
        if (selected.has(name)) selected.delete(name);
        else selected.add(name);
        syncChart();
      }}

      function syncChart() {{
        const legend = {{}};
        allSeries.forEach(s => {{ legend[s.name] = selected.has(s.name); }});
        chart.setOption({{ legend: {{ selected: legend }} }});
        Object.entries(itemEls).forEach(([name, el]) => {{
          el.classList.toggle('selected', selected.has(name));
        }});
      }}

      syncChart();
    }}

    function renderStackedBar(container, c) {{
      const series = (c.series || []).map((s, i) => ({{
        type: 'bar', name: s.name, stack: 'total', data: s.data,
        barMinWidth: 12, barMaxWidth: 60,
        itemStyle: {{ color: COLORS[i % COLORS.length] }},
      }}));
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        legend: {{
          type: 'scroll',
          bottom: 0,
          selectedMode: 'single',
          selector: true,
          pageIconSize: 10,
          pageTextStyle: {{ fontSize: 10 }},
          pageFormatter: ({{ current, total }}) => `${{current}}/${{total}}`,
          pageButtonItemGap: 4,
          itemGap: 8,
          itemWidth: 14,
          itemHeight: 10,
          textStyle: {{ fontSize: 10 }},
        }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 80 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series,
      }};
      applyTimeZoom(opt, {{ topSlider: true }});
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderScatter(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'value', name: c.xAxisName || 'X' }},
        yAxis: {{ type: 'value', name: c.yAxisName || 'Y' }},
        series: [{{ type: 'scatter', data: c.data, symbolSize: 8, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderScatterLabel(container, c) {{
      const data = (c.data || []).map(d => ({{ name: d.name, value: d.value }}));
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'value', name: c.xAxisName || 'PR Count' }},
        yAxis: {{ type: 'value', name: c.yAxisName || 'Y' }},
        series: [{{
          type: 'scatter', data, symbolSize: 12,
          itemStyle: {{ color: COLORS[0] }},
          label: {{ show: true, formatter: '{{b}}', position: 'right', fontSize: 10 }},
        }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderBoxplot(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'item' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'boxplot', data: c.data, boxWidth: '50%', itemStyle: {{ color: COLORS[0] }} }}],
      }};
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderArea(container, c) {{
      const opt = {{
        ...CHART_THEME,
        tooltip: {{ trigger: 'axis' }},
        grid: {{ left: 50, right: 30, top: 40, bottom: 60 }},
        xAxis: {{ type: 'category', data: c.x, axisLabel: {{ rotate: 45 }} }},
        yAxis: {{ type: 'value', minInterval: 0 }},
        series: [{{ type: 'line', data: c.y, areaStyle: {{}}, smooth: true, itemStyle: {{ color: COLORS[0] }} }}],
      }};
      applyTimeZoom(opt);
      const chart = echarts.init(container);
      chart.setOption(opt);
      window.addEventListener('resize', () => chart.resize());
      return chart;
    }}

    function renderDevVelocityMultiLine(container, c) {{
      const chart = echarts.init(container, null, {{renderer: 'canvas'}});
      const weeks = c.x || [];
      const series = (c.series || []).map(s => ({{
        name: s.name,
        type: 'line',
        data: s.data,
        _prCounts: s.prCounts,
        symbol: 'circle',
        symbolSize: 8,
        emphasis: {{ scale: 1.5 }},
        smooth: false,
        connectNulls: false,
      }}));
      const defaultSelected = {{}};
      series.forEach((s, i) => {{ defaultSelected[s.name] = i === 0; }});
      chart.setOption({{
        ...CHART_THEME,
        legend: {{
          type: 'scroll',
          bottom: 0,
          textStyle: {{fontSize: 11}},
          selected: defaultSelected,
        }},
        dataZoom: [
          {{ type: 'inside', xAxisIndex: 0, throttle: 30, zoomOnMouseWheel: 'shift', moveOnMouseWheel: false, moveOnMouseMove: false }},
          {{ type: 'slider', xAxisIndex: 0, top: 6, height: 14, brushSelect: false, showDetail: false }},
        ],
        grid: {{top: 56, right: 16, bottom: 60, left: 48, containLabel: false}},
        xAxis: {{
          type: 'category',
          data: weeks,
          axisLabel: {{rotate: 45, fontSize: 10}},
        }},
        yAxis: {{
          type: 'value',
          name: 'Complexity',
          nameTextStyle: {{fontSize: 10}},
        }},
        tooltip: {{
          trigger: 'axis',
          axisPointer: {{type: 'cross'}},
          formatter: function(params) {{
            let out = `<div style="font-weight:600;margin-bottom:4px">${{params[0].axisValue}}</div>`;
            params.forEach(p => {{
              const s = series.find(x => x.name === p.seriesName);
              const cnt = s && s._prCounts ? s._prCounts[p.dataIndex] : 0;
              if (cnt === 0) return;
              out += `<div>${{p.marker}}${{p.seriesName}}: <b>${{p.value}}</b> <span style="color:var(--text-muted);font-size:0.85em">(${{cnt}} PR${{cnt !== 1 ? 's' : ''}})</span></div>`;
            }});
            return out || params[0].axisValue;
          }},
        }},
        series,
      }});
      return chart;
    }}

    function renderChart(container, c) {{
      const type = c.type || 'bar';
      if (type === 'bar') return renderBar(container, c);
      if (type === 'line') return renderLine(container, c);
      if (type === 'dualLine') return renderDualLine(container, c);
      if (type === 'multiLine') return renderMultiLine(container, c);
      if (type === 'stackedBar') return renderStackedBar(container, c);
      if (type === 'scatter') return renderScatter(container, c);
      if (type === 'scatterLabel') return renderScatterLabel(container, c);
      if (type === 'boxplot') return renderBoxplot(container, c);
      if (type === 'area') return renderArea(container, c);
      if (type === 'devVelocityMultiLine') return renderDevVelocityMultiLine(container, c);
      return renderBar(container, c);
    }}

    const tabsEl = document.getElementById('tabs');
    const subtabsEl = document.getElementById('subtabs-nav');
    const panelsEl = document.getElementById('panels');

    const chartInstances = {{}};
    let activeGroup = groupOrder[0];
    let activeTab = tabGroups[activeGroup].tabs[0];

    // Render main tab groups
    groupOrder.forEach((groupKey, i) => {{
      const group = tabGroups[groupKey];
      const btn = document.createElement('button');
      btn.className = 'tab' + (i === 0 ? ' active' : '');
      btn.textContent = group.label;
      btn.dataset.group = groupKey;
      btn.onclick = () => {{
        activeGroup = groupKey;
        activeTab = group.tabs[0];
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        btn.classList.add('active');
        renderSubtabs();
        showPanel(activeTab);
        syncURL();
      }};
      tabsEl.appendChild(btn);
    }});

    function renderSubtabs() {{
      const group = tabGroups[activeGroup];
      if (group.tabs.length === 1) {{
        subtabsEl.style.display = 'none';
        return;
      }}
      subtabsEl.style.display = 'flex';
      subtabsEl.innerHTML = '';
      group.tabs.forEach((tabKey, i) => {{
        const btn = document.createElement('button');
        btn.className = 'subtab' + (tabKey === activeTab ? ' active' : '');
        btn.textContent = tabLabels[tabKey];
        btn.dataset.tab = tabKey;
        btn.onclick = () => {{
          activeTab = tabKey;
          document.querySelectorAll('.subtab').forEach(t => t.classList.remove('active'));
          btn.classList.add('active');
          showPanel(tabKey);
          syncURL();
        }};
        subtabsEl.appendChild(btn);
      }});
    }}

    function showPanel(tabKey) {{
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      const panel = document.getElementById('panel-' + tabKey);
      if (panel) {{
        panel.classList.add('active');
        (chartInstances[tabKey] || []).forEach(ch => ch.resize());
      }}
    }}

    renderSubtabs();

    const TODO_ITEMS = [
      {{
        title: 'Deployment Success Rate',
        desc: 'Track the percentage of deployments that succeed without rollbacks or hotfixes. Surface trends per service and team to identify reliability gaps.'
      }},
      {{
        title: 'Support Tickets \u2014 Defect Escape Rate',
        desc: 'Correlate inbound support tickets and production defects with the PRs that introduced them, measuring how often changes escape QA and reach users.'
      }}
    ];

    const featuresRows = chartData['_features_rows'] || [];
    const teamDevPrs = chartData['_team_dev_prs'] || {{}};
    const cycleTimePrs = chartData['_cycle_time_prs'] || {{}};
    const velocityPrs = chartData['_velocity_prs'] || {{}};

    tabOrder.forEach((key, i) => {{
      const panel = document.createElement('div');
      panel.id = 'panel-' + key;
      panel.className = 'panel' + (i === 0 ? ' active' : '');

      if (key === 'todo') {{
        const items = TODO_ITEMS.map((item, n) =>
          `<div class="todo-item">
            <div class="todo-number">${{n + 1}}</div>
            <div class="todo-body">
              <div class="todo-title">${{item.title}}</div>
              <div class="todo-desc">${{item.desc}}</div>
              <span class="todo-badge">Planned</span>
            </div>
          </div>`
        ).join('');
        panel.innerHTML = `<div class="todo-panel">
          <div class="todo-header">
            <h2>Upcoming Metrics Roadmap</h2>
            <p>Planned data sources and analytics to be added to this dashboard.</p>
          </div>
          <div class="todo-list">${{items}}</div>
        </div>`;
        panelsEl.appendChild(panel);
        return;
      }}

      if (key === 'leaderboard') {{
        const lbData = (chartData['leaderboard'] || {{}});
        let activePeriod = '30d';

        function renderLbTable(period) {{
          const rows = lbData[period] || [];
          const medals = ['\U0001F947', '\U0001F948', '\U0001F949'];
          const rowClasses = ['gold-row', 'silver-row', 'bronze-row'];
          if (!rows.length) {{
            panel.querySelector('#lb-tbody').innerHTML =
              '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted)">No approval data for this period</td></tr>';
            return;
          }}
          panel.querySelector('#lb-tbody').innerHTML = rows.map((r, i) => {{
            const cls = i < 3 ? rowClasses[i] : '';
            const rank = i < 3 ? medals[i] : (i + 1);
            return `<tr class="${{cls}}">
              <td class="lb-rank">${{rank}}</td>
              <td class="lb-reviewer">${{r.reviewer}}</td>
              <td>${{r.team || '\u2014'}}</td>
              <td class="lb-count">${{r.approvals}}</td>
              <td>${{r.avg_complexity.toFixed(1)}}</td>
            </tr>`;
          }}).join('');
        }}

        panel.innerHTML = `<div class="lb-panel">
          <div class="lb-header">
            <h2>Top Reviewers</h2>
            <div class="lb-periods">
              <button class="lb-period active" data-period="30d">Last Month</button>
              <button class="lb-period" data-period="90d">Last Quarter</button>
              <button class="lb-period" data-period="all">All Time</button>
            </div>
          </div>
          <table class="dd-table">
            <thead>
              <tr>
                <th style="width:3rem">#</th>
                <th>Reviewer</th>
                <th>Team</th>
                <th>Approvals</th>
                <th>Avg Complexity</th>
              </tr>
            </thead>
            <tbody id="lb-tbody"></tbody>
          </table>
        </div>`;

        panel.querySelectorAll('.lb-period').forEach(btn => {{
          btn.addEventListener('click', () => {{
            panel.querySelectorAll('.lb-period').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderLbTable(btn.dataset.period);
          }});
        }});

        renderLbTable(activePeriod);
        panelsEl.appendChild(panel);
        return;
      }}

      if (key === 'engineers') {{
        // Drop members who left more than 2 months ago from the current-state roster.
        // Historical charts/leaderboards keep their PRs — this only filters the People view.
        const cutoffMs = Date.now() - 60 * 24 * 60 * 60 * 1000;
        const teamsView = engineersData
          .map(t => {{
            const members = (t.members || [])
              .filter(m => !m.end || new Date(m.end + 'T00:00:00').getTime() >= cutoffMs)
              .slice()
              .sort((a, b) => {{
                const aEnded = a.end != null;
                const bEnded = b.end != null;
                if (aEnded !== bEnded) return aEnded ? 1 : -1; // active first
                if (aEnded && bEnded) return b.end.localeCompare(a.end); // most recent end first
                return (a.username || '').localeCompare(b.username || '');
              }});
            return {{ ...t, members }};
          }})
          .filter(t => t.members.length > 0);

        const allMembers = teamsView.flatMap(t => t.members);
        const totalActive = allMembers.filter(m => m.active === true).length;
        const totalEnded = allMembers.filter(m => m.end != null).length;
        const totalOnLeave = allMembers.filter(m => m.leaves && m.leaves.length > 0).length;
        const totalNoData = allMembers.filter(m => m.start == null).length;
        const totalTeams = teamsView.length;

        const earliest = allMembers.filter(m => m.start).map(m => m.start).sort()[0] || '2024-01-01';
        const today = new Date().toISOString().slice(0, 10);
        const tlStart = new Date(earliest).getTime();
        const tlEnd = new Date(today).getTime();
        const tlSpan = Math.max(tlEnd - tlStart, 1);
        function tlPct(d) {{ return Math.max(0, Math.min(100, ((new Date(d).getTime() - tlStart) / tlSpan) * 100)); }}

        function renderTimeline(m) {{
          if (!m.start) return '<span style="color:var(--text-muted);font-size:0.75rem;">\u2014</span>';
          const left = tlPct(m.start);
          const right = m.end ? tlPct(m.end) : 100;
          const width = Math.max(right - left, 0.5);
          let leaves = '';
          (m.leaves || []).forEach(lv => {{
            const ll = tlPct(lv.from);
            const lr = tlPct(lv.to);
            const lw = Math.max(lr - ll, 0.5);
            leaves += `<div class="eng-timeline-leave" style="left:${{ll}}%;width:${{lw}}%" title="Leave: ${{lv.from}} \u2192 ${{lv.to}}"></div>`;
          }});
          return `<div class="eng-timeline"><div class="eng-timeline-bar" style="left:${{left}}%;width:${{width}}%"></div>${{leaves}}</div>`;
        }}

        function statusBadge(m) {{
          if (!m.start) return '<span class="eng-badge no-data">No data</span>';
          if (m.end) return `<span class="eng-badge ended">Left ${{m.end}}</span>`;
          const onLeaveNow = (m.leaves || []).some(lv => lv.from <= today && lv.to >= today);
          if (onLeaveNow) return '<span class="eng-badge on-leave">On leave</span>';
          return '<span class="eng-badge active">Active</span>';
        }}

        function leaveTags(m) {{
          if (!m.leaves || m.leaves.length === 0) return '\u2014';
          return m.leaves.map(lv => `<span class="eng-leave-tag">${{lv.from}} \u2192 ${{lv.to}}</span>`).join(' ');
        }}

        let teamCards = '';
        teamsView.forEach((t, ti) => {{
          const active = t.members.filter(m => m.active === true).length;
          const rows = t.members.map(m => `
            <tr>
              <td style="font-family:'IBM Plex Mono',monospace;font-weight:500;">${{m.username}}</td>
              <td>${{statusBadge(m)}}</td>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;">${{m.start || '\u2014'}}</td>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem;">${{m.end || '\u2014'}}</td>
              <td>${{leaveTags(m)}}</td>
              <td style="width:140px;">${{renderTimeline(m)}}</td>
            </tr>`).join('');
          teamCards += `
            <div class="eng-team${{ti < 2 ? ' open' : ''}}" id="eng-team-${{ti}}">
              <div class="eng-team-hdr" onclick="this.parentElement.classList.toggle('open')">
                <span class="eng-team-name">${{t.team}}</span>
                <span class="eng-team-count">${{active}} / ${{t.members.length}}</span>
                <span class="eng-team-chevron">\u25B6</span>
              </div>
              <div class="eng-team-body">
                <table class="eng-tbl">
                  <thead><tr>
                    <th>Username</th><th>Status</th><th>Start</th><th>End</th><th>Leaves</th><th>Timeline</th>
                  </tr></thead>
                  <tbody>${{rows}}</tbody>
                </table>
              </div>
            </div>`;
        }});

        panel.innerHTML = `<div class="eng-panel">
          <div class="eng-header">
            <h2>Engineering Team Roster</h2>
            <p>Developer tenure, status, and leave data used for per-capita velocity calculations.</p>
          </div>
          <div class="eng-stats">
            <div class="eng-stat"><div class="eng-stat-val">${{allMembers.length}}</div><div class="eng-stat-lbl">Total</div></div>
            <div class="eng-stat"><div class="eng-stat-val">${{totalActive}}</div><div class="eng-stat-lbl">Active</div></div>
            <div class="eng-stat"><div class="eng-stat-val">${{totalEnded}}</div><div class="eng-stat-lbl">Left</div></div>
            <div class="eng-stat"><div class="eng-stat-val">${{totalOnLeave}}</div><div class="eng-stat-lbl">Has Leave</div></div>
            <div class="eng-stat"><div class="eng-stat-val">${{totalTeams}}</div><div class="eng-stat-lbl">Teams</div></div>
          </div>
          ${{teamCards}}
        </div>`;
        panelsEl.appendChild(panel);
        return;
      }}

      if (key === 'changelog') {{
        const allEntries = changelogData.flatMap(w => w.entries);
        const totalCommits = allEntries.length;
        const totalWeeks = changelogData.length;
        const authors = [...new Set(allEntries.map(e => e.author))];
        const typeCounts = {{}};
        allEntries.forEach(e => {{ typeCounts[e.typeLabel] = (typeCounts[e.typeLabel] || 0) + 1; }});
        const topType = Object.entries(typeCounts).sort((a,b) => b[1] - a[1])[0];
        const typeKeys = ['all', ...Object.keys(typeCounts).sort()];

        let filterBar = '<div class="cl-filter-bar">';
        typeKeys.forEach(t => {{
          const label = t === 'all' ? `All (${{totalCommits}})` : `${{t}} (${{typeCounts[t]}})`;
          filterBar += `<button class="cl-filter${{t === 'all' ? ' active' : ''}}" data-cl-type="${{t}}">${{label}}</button>`;
        }});
        filterBar += '</div>';

        function weekLabel(w) {{
          const d = new Date(w + 'T00:00:00');
          const end = new Date(d); end.setDate(end.getDate() + 6);
          const fmt = (dt) => dt.toLocaleDateString('en-US', {{ month: 'short', day: 'numeric' }});
          return fmt(d) + ' \u2013 ' + fmt(end);
        }}

        let weeksHtml = '';
        changelogData.forEach(w => {{
          let entriesHtml = '';
          w.entries.forEach(e => {{
            entriesHtml += `
              <div class="cl-entry" data-entry-type="${{e.typeLabel}}">
                <span class="cl-type-badge ${{e.type}}">${{e.typeLabel}}</span>
                <span class="cl-msg">${{e.message}}</span>
                <span class="cl-meta">${{e.author}} &middot; ${{e.date}}</span>
              </div>`;
          }});
          weeksHtml += `
            <div class="cl-week" data-week="${{w.week}}">
              <div class="cl-week-hdr">
                <span class="cl-week-label">${{weekLabel(w.week)}}</span>
                <span class="cl-week-count">${{w.entries.length}} commits</span>
              </div>
              ${{entriesHtml}}
            </div>`;
        }});

        panel.innerHTML = `<div class="cl-panel">
          <div class="cl-header">
            <h2>Changelog</h2>
            <p>All meaningful commits since the project fork, grouped by week.</p>
          </div>
          <div class="cl-stats">
            <div class="cl-stat"><div class="cl-stat-val">${{totalCommits}}</div><div class="cl-stat-lbl">Commits</div></div>
            <div class="cl-stat"><div class="cl-stat-val">${{totalWeeks}}</div><div class="cl-stat-lbl">Weeks</div></div>
            <div class="cl-stat"><div class="cl-stat-val">${{authors.length}}</div><div class="cl-stat-lbl">Contributors</div></div>
            <div class="cl-stat"><div class="cl-stat-val">${{topType ? topType[1] : 0}}</div><div class="cl-stat-lbl">${{topType ? topType[0] : ''}}</div></div>
          </div>
          ${{filterBar}}
          ${{weeksHtml}}
        </div>`;
        panelsEl.appendChild(panel);

        panel.querySelectorAll('.cl-filter').forEach(btn => {{
          btn.onclick = () => {{
            panel.querySelectorAll('.cl-filter').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            const filterType = btn.dataset.clType;
            panel.querySelectorAll('.cl-entry').forEach(entry => {{
              entry.style.display = (filterType === 'all' || entry.dataset.entryType === filterType) ? '' : 'none';
            }});
            panel.querySelectorAll('.cl-week').forEach(week => {{
              const visible = [...week.querySelectorAll('.cl-entry')].some(e => e.style.display !== 'none');
              week.style.display = visible ? '' : 'none';
            }});
          }};
        }});
        return;
      }}

      const charts = chartData[key] || [];

      let summaryHtml = '';
      if (key === 'basic') {{
        summaryHtml = `<div class="hero-section">
          <div class="hero-card">
            <div class="hero-value">${{heroStats.velocity_per_capita || 0}}</div>
            <div class="hero-label">Velocity/Dev</div>
            <div class="hero-sublabel">Complexity per capita per week</div>
          </div>
          <div class="hero-card hero-clickable" data-hero="active_devs">
            <div class="hero-value">${{heroStats.active_developers || 0}}</div>
            <div class="hero-label">Active Devs</div>
            <div class="hero-sublabel">Last 30 days &middot; click to view</div>
          </div>
          <div class="hero-card hero-clickable" data-hero="total_prs">
            <div class="hero-value">${{heroStats.total_prs || 0}}</div>
            <div class="hero-label">Total PRs</div>
            <div class="hero-sublabel">${{heroStats.last_synced ? `Last synced ${{heroStats.last_synced}} &middot; click to view recent` : 'All time &middot; click to view recent'}}</div>
          </div>
          <div class="hero-card">
            <div class="hero-value">${{heroStats.avg_complexity || 0}}</div>
            <div class="hero-label">Avg Complexity</div>
            <div class="hero-sublabel">Per PR</div>
          </div>
        </div>`;
      }} else if (key === 'features' && featuresRows.length) {{
        const noBugs = featuresRows.filter(r => r.category !== 'bug_fix');
        const total = noBugs.length;
        const uf = noBugs.filter(r => r.is_user_facing === 'true').length;
        const feats = noBugs.filter(r => r.category === 'feature').length;
        const impr = noBugs.filter(r => r.category === 'improvement').length;
        const bugs = featuresRows.filter(r => r.category === 'bug_fix').length;
        const teams = [...new Set(noBugs.map(r => r.team))].length;
        summaryHtml = `<div class="feat-summary">
          <div class="feat-stat"><div class="stat-value">${{total}}</div><div class="stat-label">Total shipped</div></div>
          <div class="feat-stat"><div class="stat-value">${{uf}}</div><div class="stat-label">User-facing</div></div>
          <div class="feat-stat"><div class="stat-value">${{feats}}</div><div class="stat-label">New features</div></div>
          <div class="feat-stat"><div class="stat-value">${{impr}}</div><div class="stat-label">Improvements</div></div>
          <div class="feat-stat"><div class="stat-value">${{bugs}}</div><div class="stat-label">Bug fixes</div></div>
          <div class="feat-stat"><div class="stat-value">${{teams}}</div><div class="stat-label">Teams</div></div>
        </div>
        <div style="background:#fef3c7;border:1px solid #f59e0b;border-radius:8px;padding:10px 16px;margin:0 0 16px;display:flex;align-items:center;gap:8px;font-size:13px;color:#92400e;">
          <span style="font-size:16px;">&#9888;&#65039;</span>
          <span><strong>Alpha</strong> &mdash; Feature data is AI-classified and may contain inaccuracies. Please validate before drawing conclusions.</span>
        </div>`;
      }}

      function buildCardHtml(c, idx, key) {{
        const id = 'chart-' + key + '-' + idx;
        const anchorId = 'anchor-' + key + '-' + idx;
        const hasPicker = c.hasPicker && c.series && c.series.length > 6;
        const isDrill = c.drilldown === true;
        let cardClass = hasPicker ? 'chart-card has-picker' : 'chart-card';
        if (isDrill) cardClass += ' drilldown-enabled';
        const pickerHtml = hasPicker
          ? `<div class="picker-panel" id="${{id}}-picker"></div>`
          : '';
        const spanStyle = hasPicker ? ' style="grid-column:1/-1"' : '';
        const drillHint = isDrill ? '<div class="drill-hint">\u25B6 Click chart to view features</div>' : '';
        const heroUnit = c.overall_avg_unit || 'hrs avg';
        const heroStat = c.overall_avg != null
          ? `<span class="hero-stat"><span class="hero-val">${{c.overall_avg}}</span><span class="hero-unit">${{heroUnit}}</span></span>`
          : '';
        return `<div id="${{anchorId}}" class="${{cardClass}}" data-chart-idx="${{idx}}" data-chart-tab="${{key}}"><h3${{spanStyle}}>${{c.title}}</h3><div class="sub"${{spanStyle}}>${{c.subtitle || ''}}${{heroStat}}</div><div id="${{id}}" class="chart-container"></div>${{drillHint}}${{pickerHtml}}</div>`;
      }}

      const hasSubtabs = charts.some(c => c._subtab);

      // Add jump navigation for panels with many charts
      let jumpNavHtml = '';
      if (charts.length >= 6 && !hasSubtabs) {{
        jumpNavHtml = '<div class="jump-nav"><span class="jump-nav-label">Jump to:</span>';
        charts.forEach((c, idx) => {{
          const anchorId = 'anchor-' + key + '-' + idx;
          const shortTitle = c.title.length > 30 ? c.title.substring(0, 27) + '...' : c.title;
          jumpNavHtml += `<a href="#${{anchorId}}" class="jump-link">${{shortTitle}}</a>`;
        }});
        jumpNavHtml += '</div>';
      }}

      let html = summaryHtml + jumpNavHtml;
      if (hasSubtabs) {{
        const seen = new Set();
        const subtabOrder = [];
        charts.forEach(c => {{
          const st = c._subtab || 'Other';
          if (!seen.has(st)) {{ seen.add(st); subtabOrder.push(st); }}
        }});
        html += `<div class="subtabs" id="subtabs-${{key}}">`;
        subtabOrder.forEach((st, si) => {{
          html += `<button class="subtab${{si === 0 ? ' active' : ''}}" data-subtab="${{st}}" data-parenttab="${{key}}">${{st}}</button>`;
        }});
        html += '</div>';
        subtabOrder.forEach((st, si) => {{
          html += `<div class="subpanel${{si === 0 ? ' active' : ''}}" data-subtab-panel="${{st}}" data-parenttab="${{key}}"><div class="grid">`;
          charts.forEach((c, idx) => {{
            if ((c._subtab || 'Other') === st) html += buildCardHtml(c, idx, key);
          }});
          html += '</div></div>';
        }});
      }} else {{
        // Group charts by section if they have _section metadata
        const hasSections = charts.some(c => c._section);
        if (hasSections) {{
          const sections = [];
          const sectionMap = new Map();
          charts.forEach((c, idx) => {{
            const section = c._section || 'Other';
            if (!sectionMap.has(section)) {{
              sectionMap.set(section, []);
              sections.push(section);
            }}
            sectionMap.get(section).push({{ chart: c, idx }});
          }});

          html += '<div class="grid">';
          sections.forEach((section, sIdx) => {{
            if (sIdx > 0) {{
              html += `<div class="section-divider"><div class="section-title">${{section}}</div></div>`;
            }}
            sectionMap.get(section).forEach(item => {{
              html += buildCardHtml(item.chart, item.idx, key);
            }});
          }});
          html += '</div>';
        }} else {{
          html += '<div class="grid">';
          charts.forEach((c, idx) => {{ html += buildCardHtml(c, idx, key); }});
          html += '</div>';
        }}
      }}

      panel.innerHTML = html;
      panelsEl.appendChild(panel);

      panel.querySelectorAll('.hero-clickable').forEach(card => {{
        card.addEventListener('click', () => openHeroModal(card.dataset.hero));
      }});

      if (hasSubtabs) {{
        panel.querySelectorAll('.subtab').forEach(btn => {{
          btn.onclick = () => {{
            const parentKey = btn.dataset.parenttab;
            panel.querySelectorAll(`.subtab[data-parenttab="${{parentKey}}"]`).forEach(b => b.classList.remove('active'));
            panel.querySelectorAll(`.subpanel[data-parenttab="${{parentKey}}"]`).forEach(p => p.classList.remove('active'));
            btn.classList.add('active');
            const sp = panel.querySelector(`.subpanel[data-subtab-panel="${{btn.dataset.subtab}}"][data-parenttab="${{parentKey}}"]`);
            if (sp) sp.classList.add('active');
            (chartInstances[key] || []).forEach(ch => ch.resize());
            syncURL();
          }};
        }});
      }}

      chartInstances[key] = [];
      charts.forEach((c, idx) => {{
        const id = 'chart-' + key + '-' + idx;
        const el = document.getElementById(id);
        if (el) {{
          const ch = renderChart(el, c);
          if (ch) {{
            chartInstances[key].push(ch);
            if (c.drilldown) {{
              ch.on('click', function(params) {{
                const month = params.name || (params.data && params.data[0]);
                const seriesName = params.seriesName || '';
                openDrilldown(month, c, seriesName);
              }});
            }}
            if (c.type === 'devVelocityMultiLine') {{
              ch.on('click', function(params) {{
                const week = params.name;
                const developer = params.seriesName;
                const team = c._subtab;
                const prs = ((teamDevPrs[team] || {{}})[developer] || {{}})[week] || [];
                if (prs.length > 0) openDevPrModal(developer, week, prs);
              }});
            }}
            if (c._cycle_scope) {{
              ch.on('click', function(params) {{
                const week = params.name;
                const scope = c._cycle_scope;
                const prs = (cycleTimePrs[scope] || {{}})[week] || [];
                if (prs.length > 0) openCycleTimePrModal(scope, week, prs);
              }});
            }}
            if (c._velocity_scope) {{
              ch.on('click', function(params) {{
                const week = params.name;
                const scope = c._velocity_scope;
                const prs = (velocityPrs[scope] || {{}})[week] || [];
                if (prs.length > 0) openVelocityPrModal(scope, week, prs);
              }});
            }}
            if (c.type === 'scatter' && c._pr_examples) {{
              ch.on('click', function(params) {{
                const linesChanged = params.data[0];
                const complexity = params.data[1];
                const complexityBucket = Math.floor(complexity);
                const sizeBucket = Math.floor(linesChanged / 100) * 100;
                const key = `${{complexityBucket}}_${{sizeBucket}}`;
                const prs = c._pr_examples[key] || [];
                if (prs.length > 0) {{
                  openScatterPrModal(linesChanged, complexity, prs);
                }}
              }});
            }}
          }}
        }}
      }});
    }});

    requestAnimationFrame(() => {{
      (chartInstances['basic'] || []).forEach(ch => ch.resize());
    }});

    // Global chart search
    const searchEl = document.getElementById('chart-search');
    const searchWrap = document.getElementById('global-search');
    const clearBtn = document.getElementById('search-clear');
    const searchResultsEl = document.getElementById('search-results');
    const allChartEntries = [];

    tabOrder.forEach(key => {{
      const _tabVal = chartData[key];
      if (!Array.isArray(_tabVal)) return;
      _tabVal.forEach((c, idx) => {{
        allChartEntries.push({{ tab: key, idx, data: c, title: c.title || '', subtitle: c.subtitle || '' }});
      }});
    }});

    let searchChartInstances = [];

    function doSearch(query) {{
      const q = query.trim().toLowerCase();
      searchWrap.classList.toggle('has-value', q.length > 0);

      if (!q) {{
        tabsEl.style.display = '';
        panelsEl.style.display = '';
        searchResultsEl.classList.remove('active');
        searchChartInstances.forEach(ch => ch.dispose());
        searchChartInstances = [];
        searchResultsEl.innerHTML = '';
        const activeTab = document.querySelector('.tab.active');
        if (activeTab) {{
          const key = activeTab.dataset.tab;
          (chartInstances[key] || []).forEach(ch => ch.resize());
        }}
        return;
      }}

      tabsEl.style.display = 'none';
      panelsEl.style.display = 'none';
      searchResultsEl.classList.add('active');

      searchChartInstances.forEach(ch => ch.dispose());
      searchChartInstances = [];

      const matches = allChartEntries.filter(e =>
        e.title.toLowerCase().includes(q) || e.subtitle.toLowerCase().includes(q)
      );

      let html = `<div class="search-count"><span>${{matches.length}}</span> chart${{matches.length !== 1 ? 's' : ''}} matching "${{query.trim()}}"</div>`;
      html += '<div class="grid">';
      matches.forEach((m, i) => {{
        const id = 'search-chart-' + i;
        const hasPicker = m.data.hasPicker && m.data.series && m.data.series.length > 6;
        const cardClass = hasPicker ? 'chart-card has-picker' : 'chart-card';
        const pickerHtml = hasPicker ? `<div class="picker-panel" id="${{id}}-picker"></div>` : '';
        const spanStyle = hasPicker ? ' style="grid-column:1/-1"' : '';
        const tabBadge = `<span style="font-size:0.65rem;font-weight:500;color:var(--accent);background:var(--accent-dim);padding:0.15rem 0.45rem;border-radius:4px;margin-left:0.5rem;vertical-align:middle;text-transform:uppercase;letter-spacing:0.04em;">${{tabLabels[m.tab]}}</span>`;
        const searchHeroStat = m.data.overall_avg != null
          ? `<span class="hero-stat"><span class="hero-val">${{m.data.overall_avg}}</span><span class="hero-unit">hrs avg</span></span>`
          : '';
        html += `<div class="${{cardClass}}"><h3${{spanStyle}}>${{m.data.title}}${{tabBadge}}</h3><div class="sub"${{spanStyle}}>${{m.data.subtitle || ''}}${{searchHeroStat}}</div><div id="${{id}}" class="chart-container"></div>${{pickerHtml}}</div>`;
      }});
      html += '</div>';
      searchResultsEl.innerHTML = html;

      matches.forEach((m, i) => {{
        const id = 'search-chart-' + i;
        const el = document.getElementById(id);
        if (el) {{
          const ch = renderChart(el, m.data);
          if (ch) searchChartInstances.push(ch);
        }}
      }});
    }}

    searchEl.addEventListener('input', () => {{ doSearch(searchEl.value); syncURL(); }});
    clearBtn.addEventListener('click', () => {{
      searchEl.value = '';
      doSearch('');
      syncURL();
      searchEl.focus();
    }});

    // Drilldown modal logic
    const ddOverlay = document.getElementById('drilldown-overlay');
    const ddTitle = document.getElementById('dd-title');
    const ddBody = document.getElementById('dd-body');
    const ddClose = document.getElementById('dd-close');

    function escapeHtml(s) {{
      return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({{ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }})[c]);
    }}

    function openHeroModal(kind) {{
      const ddOverlay = document.getElementById('drilldown-overlay');
      const ddTitle = document.getElementById('dd-title');
      const ddBody = document.getElementById('dd-body');

      if (kind === 'active_devs') {{
        const list = (heroStats.active_devs_list || []);
        ddTitle.innerHTML = `Active Developers — last 30 days<span class="dd-count">${{list.length}} dev${{list.length !== 1 ? 's' : ''}}</span>`;
        if (!list.length) {{
          ddBody.innerHTML = '<p style="padding:1rem;color:var(--text-muted)">No PR activity in the last 30 days.</p>';
        }} else {{
          let html = '<table class="dd-table"><thead><tr><th>#</th><th>Developer</th><th>Team</th><th>PRs</th><th>Complexity</th></tr></thead><tbody>';
          list.forEach((d, i) => {{
            html += `<tr>
              <td style="font-family:'IBM Plex Mono',monospace;color:var(--text-muted)">${{i + 1}}</td>
              <td class="cell-name"><span class="name-text">${{escapeHtml(d.developer)}}</span></td>
              <td style="font-size:0.85rem">${{escapeHtml(d.team || '—')}}</td>
              <td><b>${{d.prs}}</b></td>
              <td>${{d.complexity}}</td>
            </tr>`;
          }});
          html += '</tbody></table>';
          ddBody.innerHTML = html;
        }}
        ddOverlay.classList.add('open');
        return;
      }}

      if (kind === 'total_prs') {{
        const list = (heroStats.recent_prs_list || []);
        const syncedSuffix = heroStats.last_synced ? ` &middot; last synced ${{escapeHtml(heroStats.last_synced)}}` : '';
        ddTitle.innerHTML = `Recent PRs<span class="dd-count">${{list.length}} most recent${{syncedSuffix}}</span>`;
        if (!list.length) {{
          ddBody.innerHTML = '<p style="padding:1rem;color:var(--text-muted)">No PRs available.</p>';
        }} else {{
          const cxColor = (v) => v >= 8 ? '#991b1b' : v >= 5 ? '#92400e' : '#065f46';
          const cxBg = (v) => v >= 8 ? '#fee2e2' : v >= 5 ? '#fef3c7' : '#d1fae5';
          const srcBadge = (s) => {{
            const v = String(s || '').toLowerCase();
            if (v === 'github') return '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#dbeafe;color:#1e40af">GitHub</span>';
            if (v === 'bitbucket') return '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#e0e7ff;color:#4338ca">Bitbucket</span>';
            return '—';
          }};
          let html = '<table class="dd-table"><thead><tr><th>PR</th><th>Developer</th><th>Team</th><th>Repo</th><th>Source</th><th>Complexity</th><th>Merged</th><th>Link</th></tr></thead><tbody>';
          list.forEach(pr => {{
            const title = pr.title || pr.url || '—';
            const display = title.length > 70 ? title.slice(0, 70) + '…' : title;
            const cx = pr.complexity || 0;
            const badge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{cxBg(cx)}};color:${{cxColor(cx)}}">${{cx}}</span>`;
            const link = pr.url
              ? `<a href="${{escapeHtml(pr.url)}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">→ Open</a>`
              : '—';
            html += `<tr>
              <td class="cell-name" title="${{escapeHtml(title)}}"><span class="name-text">${{escapeHtml(display)}}</span></td>
              <td style="font-size:0.85rem">${{escapeHtml(pr.developer || '—')}}</td>
              <td style="font-size:0.85rem">${{escapeHtml(pr.team || '—')}}</td>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem">${{escapeHtml(pr.repo || '—')}}</td>
              <td>${{srcBadge(pr.source)}}</td>
              <td>${{badge}}</td>
              <td style="font-family:'IBM Plex Mono',monospace;font-size:0.78rem">${{escapeHtml(pr.merged_at || '—')}}</td>
              <td>${{link}}</td>
            </tr>`;
          }});
          html += '</tbody></table>';
          ddBody.innerHTML = html;
        }}
        ddOverlay.classList.add('open');
        return;
      }}
    }}

    function openDevPrModal(developer, week, prs) {{
      const ddOverlay = document.getElementById('drilldown-overlay');
      const ddTitle = document.getElementById('dd-title');
      const ddBody = document.getElementById('dd-body');
      const weekDate = new Date(week + 'T00:00:00');
      const weekFmt = weekDate.toLocaleDateString('en-US', {{month: 'short', day: 'numeric', year: 'numeric'}});
      const totalComplexity = prs.reduce((sum, pr) => sum + (pr.complexity || 0), 0).toFixed(1);
      ddTitle.innerHTML = `PR List \u2014 ${{developer}} \u2014 week of ${{weekFmt}}<span class="dd-count">${{prs.length}} PR${{prs.length !== 1 ? 's' : ''}} \u00b7 complexity ${{totalComplexity}}</span>`;

      const complexityColor = (v) => {{
        if (v >= 8) return '#991b1b';
        if (v >= 5) return '#92400e';
        return '#065f46';
      }};
      const complexityBg = (v) => {{
        if (v >= 8) return '#fee2e2';
        if (v >= 5) return '#fef3c7';
        return '#d1fae5';
      }};

      let tableHtml = `<table class="dd-table">
        <thead><tr>
          <th>PR</th><th>Complexity</th><th>Repo</th><th>Source</th><th>Link</th>
        </tr></thead><tbody>`;

      prs.forEach(pr => {{
        const title = pr.title || pr.url || '\u2014';
        const displayTitle = title.length > 60 ? title.slice(0, 60) + '\u2026' : title;
        const cx = pr.complexity || 0;
        const badge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{complexityBg(cx)}};color:${{complexityColor(cx)}}">${{cx}}</span>`;
        const link = pr.url
          ? `<a href="${{pr.url}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">\u2192 Open PR</a>`
          : '\u2014';

        // Extract repo name and source from URL
        let repoName = '\u2014';
        let source = '\u2014';
        if (pr.url) {{
          try {{
            const url = new URL(pr.url);
            if (url.hostname.includes('github.com')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#dbeafe;color:#1e40af">GitHub</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) {{
                repoName = pathParts[1];
              }}
            }} else if (url.hostname.includes('bitbucket.org')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#e0e7ff;color:#4338ca">Bitbucket</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) {{
                repoName = pathParts[1];
              }}
            }}
          }} catch (e) {{
            // Invalid URL, leave as default
          }}
        }}

        tableHtml += `<tr>
          <td class="cell-name" title="${{title}}"><span class="name-text">${{displayTitle}}</span></td>
          <td>${{badge}}</td>
          <td style="font-size:0.85rem">${{repoName}}</td>
          <td>${{source}}</td>
          <td>${{link}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';
      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}

    function openCycleTimePrModal(scope, week, prs) {{
      const ddOverlay = document.getElementById('drilldown-overlay');
      const ddTitle = document.getElementById('dd-title');
      const ddBody = document.getElementById('dd-body');
      const weekDate = new Date(week + 'T00:00:00');
      const weekFmt = weekDate.toLocaleDateString('en-US', {{month: 'short', day: 'numeric', year: 'numeric'}});
      const avgCycle = (prs.reduce((s, p) => s + (p.cycle_hours || 0), 0) / prs.length).toFixed(1);
      const scopeLabel = scope === '_all' ? 'All Teams' : scope;
      ddTitle.innerHTML = `Merge Cycle Time — ${{scopeLabel}} — week of ${{weekFmt}}<span class="dd-count">${{prs.length}} PR${{prs.length !== 1 ? 's' : ''}} · avg ${{avgCycle}}h</span>`;

      const cxColor = (v) => v >= 8 ? '#991b1b' : v >= 5 ? '#92400e' : '#065f46';
      const cxBg = (v) => v >= 8 ? '#fee2e2' : v >= 5 ? '#fef3c7' : '#d1fae5';
      const cycleColor = (h) => h >= 168 ? '#991b1b' : h >= 48 ? '#92400e' : '#065f46';
      const cycleBg = (h) => h >= 168 ? '#fee2e2' : h >= 48 ? '#fef3c7' : '#d1fae5';

      const sorted = prs.slice().sort((a, b) => (b.cycle_hours || 0) - (a.cycle_hours || 0));

      let tableHtml = `<table class="dd-table">
        <thead><tr>
          <th>PR</th><th>Cycle Time</th><th>Complexity</th><th>Developer</th><th>Repo</th><th>Source</th><th>Link</th>
        </tr></thead><tbody>`;

      sorted.forEach(pr => {{
        const title = pr.title || pr.url || '—';
        const displayTitle = title.length > 60 ? title.slice(0, 60) + '…' : title;
        const cx = pr.complexity || 0;
        const hrs = pr.cycle_hours || 0;
        const hrsLabel = hrs >= 24 ? `${{(hrs / 24).toFixed(1)}}d` : `${{hrs.toFixed(1)}}h`;
        const cxBadge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{cxBg(cx)}};color:${{cxColor(cx)}}">${{cx}}</span>`;
        const cycleBadge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{cycleBg(hrs)}};color:${{cycleColor(hrs)}}">${{hrsLabel}}</span>`;
        const link = pr.url ? `<a href="${{pr.url}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">→ Open PR</a>` : '—';
        const dev = pr.developer || '—';

        let repoName = '—';
        let source = '—';
        if (pr.url) {{
          try {{
            const url = new URL(pr.url);
            if (url.hostname.includes('github.com')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#dbeafe;color:#1e40af">GitHub</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) repoName = pathParts[1];
            }} else if (url.hostname.includes('bitbucket.org')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#e0e7ff;color:#4338ca">Bitbucket</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) repoName = pathParts[1];
            }}
          }} catch (e) {{}}
        }}

        tableHtml += `<tr>
          <td class="cell-name" title="${{title}}"><span class="name-text">${{displayTitle}}</span></td>
          <td>${{cycleBadge}}</td>
          <td>${{cxBadge}}</td>
          <td style="font-size:0.85rem">${{dev}}</td>
          <td style="font-size:0.85rem">${{repoName}}</td>
          <td>${{source}}</td>
          <td>${{link}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';
      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}

    function openVelocityPrModal(scope, week, prs) {{
      const ddOverlay = document.getElementById('drilldown-overlay');
      const ddTitle = document.getElementById('dd-title');
      const ddBody = document.getElementById('dd-body');
      const weekDate = new Date(week + 'T00:00:00');
      const weekFmt = weekDate.toLocaleDateString('en-US', {{month: 'short', day: 'numeric', year: 'numeric'}});
      const totalCx = prs.reduce((s, p) => s + (p.complexity || 0), 0);
      const devSet = new Set(prs.map(p => p.developer).filter(Boolean));
      const perCapita = devSet.size > 0 ? (totalCx / devSet.size).toFixed(2) : '0';
      const scopeLabel = scope === '_all' ? 'All Teams' : scope;
      ddTitle.innerHTML = `Velocity Per Capita — ${{scopeLabel}} — week of ${{weekFmt}}<span class="dd-count">${{prs.length}} PR${{prs.length !== 1 ? 's' : ''}} · ${{devSet.size}} dev${{devSet.size !== 1 ? 's' : ''}} · total cx ${{totalCx}} · per-capita ${{perCapita}}</span>`;

      const cxColor = (v) => v >= 8 ? '#991b1b' : v >= 5 ? '#92400e' : '#065f46';
      const cxBg = (v) => v >= 8 ? '#fee2e2' : v >= 5 ? '#fef3c7' : '#d1fae5';

      const sorted = prs.slice().sort((a, b) => (b.complexity || 0) - (a.complexity || 0));

      let tableHtml = `<table class="dd-table">
        <thead><tr>
          <th>PR</th><th>Complexity</th><th>Developer</th><th>Team</th><th>Repo</th><th>Source</th><th>Link</th>
        </tr></thead><tbody>`;

      sorted.forEach(pr => {{
        const title = pr.title || pr.url || '—';
        const displayTitle = title.length > 60 ? title.slice(0, 60) + '…' : title;
        const cx = pr.complexity || 0;
        const cxBadge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{cxBg(cx)}};color:${{cxColor(cx)}}">${{cx}}</span>`;
        const link = pr.url ? `<a href="${{pr.url}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">→ Open PR</a>` : '—';
        const dev = pr.developer || '—';
        const team = pr.team || '—';

        let repoName = '—';
        let source = '—';
        if (pr.url) {{
          try {{
            const url = new URL(pr.url);
            if (url.hostname.includes('github.com')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#dbeafe;color:#1e40af">GitHub</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) repoName = pathParts[1];
            }} else if (url.hostname.includes('bitbucket.org')) {{
              source = '<span style="display:inline-block;font-size:0.7rem;font-family:\\'Syne\\',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:#e0e7ff;color:#4338ca">Bitbucket</span>';
              const pathParts = url.pathname.split('/').filter(p => p);
              if (pathParts.length >= 2) repoName = pathParts[1];
            }}
          }} catch (e) {{}}
        }}

        tableHtml += `<tr>
          <td class="cell-name" title="${{title}}"><span class="name-text">${{displayTitle}}</span></td>
          <td>${{cxBadge}}</td>
          <td style="font-size:0.85rem">${{dev}}</td>
          <td style="font-size:0.85rem">${{team}}</td>
          <td style="font-size:0.85rem">${{repoName}}</td>
          <td>${{source}}</td>
          <td>${{link}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';
      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}

    function openScatterPrModal(linesChanged, complexity, prs) {{
      const ddTitle = document.getElementById('dev-drill-title');
      const ddBody = document.getElementById('dev-drill-body');
      const ddOverlay = document.getElementById('dev-drill-overlay');

      const complexityColor = (v) => {{
        if (v >= 8) return '#991b1b';
        if (v >= 5) return '#92400e';
        return '#065f46';
      }};
      const complexityBg = (v) => {{
        if (v >= 8) return '#fee2e2';
        if (v >= 5) return '#fef3c7';
        return '#d1fae5';
      }};

      ddTitle.textContent = `PR Examples \u2014 Lines: ~${{Math.floor(linesChanged / 100) * 100}}, Complexity: ~${{Math.floor(complexity)}}`;

      let tableHtml = `<table class="dd-table">
        <thead>
          <tr>
            <th>PR</th>
            <th>Lines</th>
            <th>Complexity</th>
            <th>Link</th>
          </tr>
        </thead>
        <tbody>`;

      prs.forEach(pr => {{
        const title = pr.title || pr.url || '\u2014';
        const displayTitle = title.length > 60 ? title.slice(0, 60) + '\u2026' : title;
        const lines = pr.lines_changed || 0;
        const cx = pr.complexity || 0;
        const badge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{complexityBg(cx)}};color:${{complexityColor(cx)}}">${{cx}}</span>`;
        const link = pr.url
          ? `<a href="${{pr.url}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">\u2192 Open PR</a>`
          : '\u2014';
        tableHtml += `<tr>
          <td class="cell-name" title="${{title}}"><span class="name-text">${{displayTitle}}</span></td>
          <td style="text-align:center;font-size:0.85rem">${{lines.toLocaleString()}}</td>
          <td style="text-align:center">${{badge}}</td>
          <td>${{link}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';
      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}

    function openDrilldown(month, chartConfig, seriesName) {{
      let filtered = featuresRows.filter(r => r.month === month && r.category !== 'bug_fix');
      let title = `Features \u2014 ${{month}}`;

      if (chartConfig.filter) {{
        Object.entries(chartConfig.filter).forEach(([k, v]) => {{
          filtered = filtered.filter(r => r[k] === v);
        }});
        if (chartConfig.filter.team) title += ` \u2014 ${{chartConfig.filter.team}}`;
        if (chartConfig.filter.is_user_facing === 'true') title = `User-Facing ${{title}}`;
      }}

      if (seriesName && !chartConfig.filter) {{
        const teamMatch = filtered.filter(r => r.team === seriesName);
        const catMatch = filtered.filter(r => r.category === seriesName);
        if (teamMatch.length > 0 && teamMatch.length < filtered.length) {{
          filtered = teamMatch;
          title += ` \u2014 ${{seriesName}}`;
        }} else if (catMatch.length > 0 && catMatch.length < filtered.length) {{
          filtered = catMatch;
          title += ` \u2014 ${{seriesName}}`;
        }}
      }}

      filtered.sort((a, b) => b.released_date.localeCompare(a.released_date));

      ddTitle.innerHTML = `${{title}}<span class="dd-count">${{filtered.length}} item${{filtered.length !== 1 ? 's' : ''}}</span>`;

      const catBadge = (c) => `<span class="dd-badge cat-${{c}}">${{c.replace('_', ' ')}}</span>`;
      const ufBadge = (v) => v === 'true'
        ? '<span class="dd-badge uf-true">User-facing</span>'
        : '<span class="dd-badge uf-false">Internal</span>';

      const JIRA_BASE = 'https://boomii.atlassian.net/browse/';
      const isJiraKey = (k) => /^[A-Z]{{2,}}-\\d+$/.test(k);
      const jiraLink = (key) => isJiraKey(key)
        ? `<a href="${{JIRA_BASE}}${{key}}" target="_blank" rel="noopener">${{key}}</a>`
        : key;
      const ticketPills = (raw) => {{
        if (!raw) return '\u2014';
        const keys = raw.split('|').filter(Boolean);
        const MAX_SHOW = 3;
        const shown = keys.slice(0, MAX_SHOW);
        const rest = keys.length - MAX_SHOW;
        let html = shown.map(k =>
          `<a class="ticket-pill" href="${{JIRA_BASE}}${{k}}" target="_blank" rel="noopener">${{k}}</a>`
        ).join('');
        if (rest > 0) html += `<span class="ticket-overflow">+${{rest}}</span>`;
        return html;
      }};

      let tableHtml = `<table class="dd-table">
        <thead><tr>
          <th>Epic</th><th>Name</th><th>Tickets</th><th>Team</th><th>Category</th>
          <th>Visibility</th><th>Released</th><th>Lead Time</th>
        </tr></thead><tbody>`;

      filtered.forEach(r => {{
        const lt = r.lead_time_days ? `${{r.lead_time_days}}d` : '\u2014';
        tableHtml += `<tr>
          <td class="cell-id">${{jiraLink(r.feature_id)}}</td>
          <td class="cell-name"><span class="name-text">${{r.feature_name}}</span></td>
          <td class="cell-tickets">${{ticketPills(r.jira_keys)}}</td>
          <td>${{r.team}}</td>
          <td>${{catBadge(r.category)}}</td>
          <td>${{ufBadge(r.is_user_facing)}}</td>
          <td style="white-space:nowrap">${{r.released_date}}</td>
          <td style="text-align:right">${{lt}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';

      if (filtered.length === 0) {{
        tableHtml = '<div style="padding:3rem;text-align:center;color:var(--text-muted);font-size:0.9rem;">No features found for this selection.</div>';
      }}

      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}

    function closeDrilldown() {{
      ddOverlay.classList.remove('open');
    }}

    ddClose.addEventListener('click', closeDrilldown);
    ddOverlay.addEventListener('click', (e) => {{
      if (e.target === ddOverlay) closeDrilldown();
    }});
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') closeDrilldown();
    }});

    // Dev drill modal (for scatter charts)
    const devDrillOverlay = document.getElementById('dev-drill-overlay');
    const devDrillClose = document.getElementById('dev-drill-close');

    function closeDevDrill() {{
      devDrillOverlay.classList.remove('open');
    }}

    if (devDrillClose) {{
      devDrillClose.addEventListener('click', closeDevDrill);
    }}
    if (devDrillOverlay) {{
      devDrillOverlay.addEventListener('click', (e) => {{
        if (e.target === devDrillOverlay) closeDevDrill();
      }});
    }}
    document.addEventListener('keydown', (e) => {{
      if (e.key === 'Escape') closeDevDrill();
    }});

    // Restore state from URL on load
    (function restoreFromURL() {{
      const params = new URLSearchParams(window.location.search);
      const tab = params.get('tab');
      if (tab && tabOrder.includes(tab)) {{
        // Find which group contains this tab
        let targetGroup = null;
        for (const [gkey, gdata] of Object.entries(tabGroups)) {{
          if (gdata.tabs.includes(tab)) {{
            targetGroup = gkey;
            break;
          }}
        }}
        if (targetGroup) {{
          activeGroup = targetGroup;
          activeTab = tab;
          document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
          const groupBtn = document.querySelector(`.tab[data-group="${{targetGroup}}"]`);
          if (groupBtn) groupBtn.classList.add('active');
          renderSubtabs();
          showPanel(tab);
        }}
      }}
      const subtab = params.get('subtab');
      if (subtab) {{
        const activePanel = document.querySelector('.panel.active');
        if (activePanel) {{
          const btn = activePanel.querySelector(`.subtab[data-subtab="${{subtab}}"]`);
          if (btn) btn.click();
        }}
      }}
      const q = params.get('q');
      if (q) {{
        searchEl.value = q;
        doSearch(q);
      }}
    }})();
  </script>
</body>
</html>
"""
