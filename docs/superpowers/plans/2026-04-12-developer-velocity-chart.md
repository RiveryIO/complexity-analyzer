# Developer Velocity Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-developer weekly complexity line chart to each team subtab, where clicking a dot opens a modal listing the PRs behind that data point.

**Architecture:** Two Python changes (data layer in `chart_data.py`) plus one large JavaScript addition in `interactive_report.py`. The data layer builds: (1) a `devVelocityMultiLine` chart config per team, and (2) a `_team_dev_prs` nested dict keyed `team → developer → week → [prs]`. The JS layer adds a new ECharts renderer for that chart type and a modal handler that reads from `_team_dev_prs` on dot click. All data is embedded in the static HTML at generation time.

**Tech Stack:** Python 3.12, pandas, ECharts 5 (already loaded in the dashboard), pytest

---

## File Map

| File | Change |
|---|---|
| `reports/chart_data.py` | Add `_build_team_dev_prs()` helper; extend `_extract_team()` with `devVelocityMultiLine` chart; extend `build_all_chart_data()` return dict |
| `reports/interactive_report.py` | Add `renderDevVelocityMultiLine` JS function; add `openDevPrModal` JS function; wire click handler in chart loop |
| `tests/test_chart_data.py` | New file — unit tests for the two new data functions |

---

## Task 1: Tests + `_build_team_dev_prs()` helper

**Files:**
- Create: `tests/test_chart_data.py`
- Modify: `reports/chart_data.py`

- [ ] **Step 1.1: Write the failing tests**

Create `tests/test_chart_data.py`:

```python
"""Unit tests for chart_data module."""

import pandas as pd
import pytest
from unittest.mock import patch

from reports.chart_data import _build_team_dev_prs, build_all_chart_data


TEAM_MAPPING = {"alice": "Alpha", "bob": "Alpha", "carol": "Beta"}


def _make_df():
    return pd.DataFrame([
        {
            "pr_url": "https://github.com/org/repo/pull/1",
            "complexity": 3.0,
            "developer": "alice",
            "merged_at": "2026-01-06",
            "date": "2026-01-06",
            "team": "",
            "created_at": "2026-01-05",
            "lines_added": 10,
            "lines_deleted": 5,
        },
        {
            "pr_url": "https://github.com/org/repo/pull/2",
            "complexity": 5.0,
            "developer": "alice",
            "merged_at": "2026-01-07",
            "date": "2026-01-07",
            "team": "",
            "created_at": "2026-01-06",
            "lines_added": 20,
            "lines_deleted": 0,
        },
        {
            "pr_url": "https://github.com/org/repo/pull/3",
            "complexity": 8.0,
            "developer": "bob",
            "merged_at": "2026-01-13",
            "date": "2026-01-13",
            "team": "",
            "created_at": "2026-01-12",
            "lines_added": 30,
            "lines_deleted": 10,
        },
    ])


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_structure(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Top-level keys are teams
    assert "Alpha" in result
    assert "Beta" not in result  # carol has no PRs
    # Second level: developers
    assert "alice" in result["Alpha"]
    assert "bob" in result["Alpha"]
    # Third level: week start date strings
    alpha_alice = result["Alpha"]["alice"]
    assert len(alpha_alice) >= 1
    # Each week maps to a list of PR dicts
    for week_key, prs in alpha_alice.items():
        assert isinstance(prs, list)
        for pr in prs:
            assert "title" in pr
            assert "url" in pr
            assert "complexity" in pr
            assert "merged_at" in pr


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_pr_fields(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Alice has 2 PRs in the same week (Jan 5–11)
    alice_weeks = result["Alpha"]["alice"]
    all_prs = [pr for prs in alice_weeks.values() for pr in prs]
    assert len(all_prs) == 2
    pr1 = all_prs[0]
    assert pr1["url"] == "https://github.com/org/repo/pull/1" or pr1["url"] == "https://github.com/org/repo/pull/2"
    assert isinstance(pr1["complexity"], float)
    assert isinstance(pr1["merged_at"], str)
    # Title is derived as "repo #N"
    assert "repo" in pr1["title"]
    assert "#1" in pr1["title"] or "#2" in pr1["title"]


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
def test_build_team_dev_prs_week_key_matches_monday(mock_mapping):
    df = _make_df()
    result = _build_team_dev_prs(df)
    # Week keys must be ISO date strings in YYYY-MM-DD format for week starts
    for team, devs in result.items():
        for dev, weeks in devs.items():
            for week_key in weeks:
                # Must parse as a date
                import datetime
                d = datetime.date.fromisoformat(week_key)
                # Must be a Monday (weekday() == 0)
                assert d.weekday() == 0, f"{week_key} is not a Monday"


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
@patch("reports.chart_data.get_weekly_headcounts", return_value={})
def test_build_all_chart_data_includes_team_dev_prs(mock_hc, mock_mapping):
    df = _make_df()
    result = build_all_chart_data(df)
    assert "_team_dev_prs" in result
    assert isinstance(result["_team_dev_prs"], dict)


@patch("reports.chart_data.load_team_mapping", return_value=TEAM_MAPPING)
@patch("reports.chart_data.get_weekly_headcounts", return_value={})
def test_extract_team_includes_dev_velocity_chart(mock_hc, mock_mapping):
    df = _make_df()
    result = build_all_chart_data(df)
    team_charts = result["team"]
    dev_vel_charts = [c for c in team_charts if c.get("type") == "devVelocityMultiLine"]
    assert len(dev_vel_charts) >= 1
    chart = dev_vel_charts[0]
    assert chart["_subtab"] == "Alpha"
    assert "series" in chart
    assert "x" in chart
    # Each series has name, data, prCounts of equal length
    for s in chart["series"]:
        assert "name" in s
        assert "data" in s
        assert "prCounts" in s
        assert len(s["data"]) == len(chart["x"])
        assert len(s["prCounts"]) == len(chart["x"])
```

- [ ] **Step 1.2: Run tests to verify they fail**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -m pytest tests/test_chart_data.py -v 2>&1 | head -40
```

Expected: ImportError or AttributeError — `_build_team_dev_prs` does not exist yet.

- [ ] **Step 1.3: Add `_build_team_dev_prs()` to `reports/chart_data.py`**

Add this helper function after the existing `_gini()` function (around line 28), before `_extract_basic()`:

```python
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
    """Build lookup: team → developer → week_start_str → list[pr_dict].

    Used by the JS drilldown modal when a user clicks a dot on the
    devVelocityMultiLine chart. Only includes developers with known team
    assignments; Bots excluded.
    """
    # load_team_mapping is already imported at module level in chart_data.py
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

        pr_dict = {
            "title": _pr_title_from_url(pr_url),
            "url": pr_url,
            "complexity": float(row.get("complexity", 0) or 0),
            "merged_at": merged_at,
        }

        result.setdefault(team, {}).setdefault(dev, {}).setdefault(week_key, []).append(pr_dict)

    return result
```

- [ ] **Step 1.4: Run tests to verify they pass**

```bash
python -m pytest tests/test_chart_data.py::test_build_team_dev_prs_structure \
  tests/test_chart_data.py::test_build_team_dev_prs_pr_fields \
  tests/test_chart_data.py::test_build_team_dev_prs_week_key_matches_monday -v
```

Expected: all 3 PASS.

- [ ] **Step 1.5: Commit**

```bash
git add tests/test_chart_data.py reports/chart_data.py
git commit -m "feat: add _build_team_dev_prs() helper for dev velocity drilldown"
```

---

## Task 2: Add `devVelocityMultiLine` chart to `_extract_team()`

**Files:**
- Modify: `reports/chart_data.py` (lines ~288–343, the `for team in all_teams:` loop)

- [ ] **Step 2.1: Add chart generation inside the `for team in all_teams:` loop**

In `_extract_team()`, inside the `for team in all_teams:` loop, after the block that appends the `22-{team}` velocity-per-capita chart (after line ~313) and before the `# 05: Stacked bar` comment, add:

```python
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
            # Reindex both to full week range so all weeks are represented
            dev_week_cx = dev_week_cx.reindex(all_week_dates, fill_value=0)
            dev_week_cnt = dev_week_cnt.reindex(all_week_dates, fill_value=0)
            week_labels_30 = [w.strftime("%Y-%m-%d") for w in all_week_dates]
            series_30 = []
            for dev in dev_week_cx.columns:
                cx_vals = [round(float(v), 2) for v in dev_week_cx[dev].tolist()]
                cnt_vals = [int(v) for v in dev_week_cnt[dev].tolist()] if dev in dev_week_cnt.columns else [0] * len(all_week_dates)
                series_30.append({
                    "name": dev,
                    "data": cx_vals,
                    "prCounts": cnt_vals,
                })
            if series_30:
                charts.append({
                    "id": f"30-{team}",
                    "type": "devVelocityMultiLine",
                    "title": f"Developer Velocity — {team}",
                    "subtitle": "Weekly complexity per developer · click a dot to see PRs",
                    "_subtab": team,
                    "x": week_labels_30,
                    "series": series_30,
                })
```

- [ ] **Step 2.2: Run the relevant tests**

```bash
python -m pytest tests/test_chart_data.py::test_extract_team_includes_dev_velocity_chart -v
```

Expected: PASS.

- [ ] **Step 2.3: Commit**

```bash
git add reports/chart_data.py
git commit -m "feat: add devVelocityMultiLine chart data to _extract_team()"
```

---

## Task 3: Expose `_team_dev_prs` in `build_all_chart_data()`

**Files:**
- Modify: `reports/chart_data.py` (the `build_all_chart_data()` function, lines ~673–693)

- [ ] **Step 3.1: Update `build_all_chart_data()` return dict**

In `build_all_chart_data()`, find the `return {` block and add `_team_dev_prs`:

Before:
```python
    return {
        "basic": _extract_basic(df),
        "team": _extract_team(df),
        "risk": _extract_risk(df),
        "fairness": _extract_fairness(df),
        "advanced": _extract_advanced(df),
        "features": features_data.get("charts", []),
        "_features_rows": features_data.get("rows", []),
        "leaderboard": _extract_leaderboard(df),
    }
```

After:
```python
    return {
        "basic": _extract_basic(df),
        "team": _extract_team(df),
        "risk": _extract_risk(df),
        "fairness": _extract_fairness(df),
        "advanced": _extract_advanced(df),
        "features": features_data.get("charts", []),
        "_features_rows": features_data.get("rows", []),
        "leaderboard": _extract_leaderboard(df),
        "_team_dev_prs": _build_team_dev_prs(df),
    }
```

- [ ] **Step 3.2: Run the test**

```bash
python -m pytest tests/test_chart_data.py::test_build_all_chart_data_includes_team_dev_prs -v
```

Expected: PASS.

- [ ] **Step 3.3: Run the full test suite to check for regressions**

```bash
python -m pytest tests/ -v --ignore=tests/test_dashboard_charts.py -x 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 3.4: Commit**

```bash
git add reports/chart_data.py
git commit -m "feat: expose _team_dev_prs in build_all_chart_data() for JS drilldown"
```

---

## Task 4: Add `renderDevVelocityMultiLine` JS renderer

**Files:**
- Modify: `reports/interactive_report.py`

The JS in this file is an f-string template. All `{` and `}` in JS must be doubled (`{{` / `}}`). Single `{name}` are Python interpolation points. Add the new renderer function alongside the existing ones.

- [ ] **Step 4.1: Find the insertion point**

In `reports/interactive_report.py`, find the `renderChart` dispatch function. It currently looks like this (around line 1319):

```python
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
      return renderBar(container, c);
    }}
```

- [ ] **Step 4.2: Add the new renderer function before `renderChart` and register it**

Find the line `    function renderChart(container, c) {{` and insert the new `renderDevVelocityMultiLine` function immediately before it:

```python
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
      chart.setOption({{
        ...CHART_THEME,
        legend: {{
          type: 'scroll',
          bottom: 0,
          textStyle: {{fontSize: 11}},
        }},
        grid: {{top: 28, right: 16, bottom: 60, left: 48, containLabel: false}},
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
```

Then update the `renderChart` dispatch to include the new type. Find the line:

```python
      if (type === 'area') return renderArea(container, c);
```

And add immediately after it (before `return renderBar(container, c);`):

```python
      if (type === 'devVelocityMultiLine') return renderDevVelocityMultiLine(container, c);
```

- [ ] **Step 4.3: Regenerate the dashboard and check JS renders without errors**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -c "
import pandas as pd
from reports.chart_data import build_all_chart_data
from reports.interactive_report import build_interactive_report
df = pd.read_csv('complexity-report.csv')
build_interactive_report(df, output_path='output/index.html')
print('Generated OK')
"
```

Expected: `Generated OK` with no Python exceptions.

- [ ] **Step 4.4: Open the dashboard and verify the new chart appears in team subtabs**

Open `output/index.html` in a browser (or use `open output/index.html` on macOS). Navigate to the Team tab, click a team subtab (e.g., the first team shown). The "Developer Velocity — TeamName" line chart should appear with one colored line per developer and a scrollable legend at the bottom. Hovering a data point should show a tooltip like `"Alice: 5.0 (2 PRs)"`.

- [ ] **Step 4.5: Commit**

```bash
git add reports/interactive_report.py
git commit -m "feat: add renderDevVelocityMultiLine ECharts renderer"
```

---

## Task 5: Add `openDevPrModal` and wire click handler

**Files:**
- Modify: `reports/interactive_report.py`

- [ ] **Step 5.1: Add `teamDevPrs` const and `openDevPrModal` JS function**

In `reports/interactive_report.py`, find the line (around line 1366):

```python
    const featuresRows = chartData['_features_rows'] || [];
```

Add immediately after it:

```python
    const teamDevPrs = chartData['_team_dev_prs'] || {{}};
```

Then find the existing `openDrilldown` function definition (around line 1824) and insert `openDevPrModal` immediately before it:

```python
    function openDevPrModal(developer, week, prs) {{
      // Format week as "Jan 5, 2026"
      const weekDate = new Date(week + 'T00:00:00');
      const weekFmt = weekDate.toLocaleDateString('en-US', {{month: 'short', day: 'numeric', year: 'numeric'}});

      const totalComplexity = prs.reduce((sum, pr) => sum + (pr.complexity || 0), 0).toFixed(1);

      ddTitle.innerHTML = `${{developer}} \u2014 week of ${{weekFmt}}<span class="dd-count">${{prs.length}} PR${{prs.length !== 1 ? 's' : ''}} \u00b7 complexity ${{totalComplexity}}</span>`;

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
          <th>PR</th><th>Complexity</th><th>Merged</th><th>Link</th>
        </tr></thead><tbody>`;

      prs.forEach(pr => {{
        const title = pr.title || pr.url || '\u2014';
        const displayTitle = title.length > 60 ? title.slice(0, 60) + '\u2026' : title;
        const mergedDate = pr.merged_at ? new Date(pr.merged_at + 'T00:00:00').toLocaleDateString('en-US', {{month: 'short', day: 'numeric', year: 'numeric'}}) : '\u2014';
        const cx = pr.complexity || 0;
        const badge = `<span style="display:inline-block;font-size:0.7rem;font-family:'Syne',sans-serif;font-weight:600;padding:0.12rem 0.45rem;border-radius:4px;background:${{complexityBg(cx)}};color:${{complexityColor(cx)}}">${{cx}}</span>`;
        const link = pr.url
          ? `<a href="${{pr.url}}" target="_blank" rel="noopener" style="color:var(--accent);font-size:0.85rem">\u2192 Open PR</a>`
          : '\u2014';
        tableHtml += `<tr>
          <td class="cell-name"><span class="name-text" title="${{title}}">${{displayTitle}}</span></td>
          <td>${{badge}}</td>
          <td style="white-space:nowrap;font-size:0.85rem">${{mergedDate}}</td>
          <td>${{link}}</td>
        </tr>`;
      }});

      tableHtml += '</tbody></table>';
      ddBody.innerHTML = tableHtml;
      ddOverlay.classList.add('open');
    }}
```

- [ ] **Step 5.2: Wire the click handler in the chart rendering loop**

In `reports/interactive_report.py`, find the chart rendering loop (around line 1715–1730):

```python
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
          }}
```

Replace that block with:

```python
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
          }}
```

- [ ] **Step 5.3: Regenerate the dashboard**

```bash
python -c "
import pandas as pd
from reports.chart_data import build_all_chart_data
from reports.interactive_report import build_interactive_report
df = pd.read_csv('complexity-report.csv')
build_interactive_report(df, output_path='output/index.html')
print('Generated OK')
"
```

Expected: `Generated OK` with no exceptions.

- [ ] **Step 5.4: Test the click interaction**

Open `output/index.html` in a browser. Go to the Team tab → click a team subtab → find the "Developer Velocity" line chart → click a dot that is not at zero on the Y-axis. A modal should appear with:
- Header: `"{Developer} — week of {date}"` and a count like `"2 PRs · complexity 8.0"`
- A table with columns: PR, Complexity, Merged, Link
- Each row has a repo#number title, a colored complexity badge, a formatted date, and a `→ Open PR` link
- Pressing ESC or clicking outside the modal closes it
- Clicking a zero-value dot does nothing (no modal)

- [ ] **Step 5.5: Run the full test suite**

```bash
python -m pytest tests/ -v --ignore=tests/test_dashboard_charts.py -x 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 5.6: Run flake8**

```bash
python -m flake8 reports/chart_data.py reports/interactive_report.py --max-line-length=120
```

Expected: no errors. Fix any E501 (line too long) or E302 (blank lines) issues before committing.

- [ ] **Step 5.7: Commit**

```bash
git add reports/interactive_report.py
git commit -m "feat: add developer velocity drilldown modal with PR list"
```

---

## Task 6: Final verification

- [ ] **Step 6.1: Run the full test suite one more time**

```bash
python -m pytest tests/ -v --ignore=tests/test_dashboard_charts.py 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 6.2: Regenerate dashboard from real data and spot-check**

```bash
python -c "
import pandas as pd
from reports.chart_data import build_all_chart_data
from reports.interactive_report import build_interactive_report
df = pd.read_csv('complexity-report.csv')
result = build_all_chart_data(df)
# Sanity checks
team_charts = result['team']
dev_vel = [c for c in team_charts if c.get('type') == 'devVelocityMultiLine']
print(f'devVelocityMultiLine charts: {len(dev_vel)}')
for c in dev_vel:
    print(f'  {c[\"id\"]}: {len(c[\"series\"])} developers, {len(c[\"x\"])} weeks')
prs_lookup = result['_team_dev_prs']
print(f'Teams in drilldown lookup: {list(prs_lookup.keys())}')
build_interactive_report(df, output_path='output/index.html')
print('Dashboard regenerated OK')
"
```

Expected: Shows chart counts and team names, ends with `Dashboard regenerated OK`.

- [ ] **Step 6.3: Final commit if anything changed**

```bash
git status
# Only commit if there are actual changes
git add -p
git commit -m "chore: final cleanup after developer velocity chart feature"
```
