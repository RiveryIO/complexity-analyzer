# Developer Velocity Chart — Design Spec

**Date:** 2026-04-12
**Status:** Approved

---

## Summary

Add a per-developer velocity line chart to each team subtab in the interactive dashboard. Each developer appears as a separate line showing weekly complexity score. Clicking any dot opens a modal listing the PRs behind that data point. The modal is only reachable from the chart — it has no nav link or URL route.

---

## 1. Data Layer (`reports/chart_data.py`)

### 1.1 New chart object — one per team

Added inside `_extract_team()`, after the existing `22-{team}` velocity-per-capita chart:

```json
{
  "id": "30-TeamName",
  "type": "devVelocityMultiLine",
  "title": "Developer Velocity — TeamName",
  "subtitle": "Weekly complexity per developer (click a dot to see PRs)",
  "_subtab": "TeamName",
  "x": ["2026-01-05", "2026-01-12", "..."],
  "series": [
    { "name": "Alice", "data": [5.0, 3.0, 0.0, "..."], "prCounts": [2, 1, 0, "..."] },
    { "name": "Bob",   "data": [8.0, 0.0, 6.0, "..."], "prCounts": [4, 0, 3, "..."] }
  ]
}
```

- `x` — shared weekly labels (ISO date strings, Monday of each week), covering all weeks where the team had any activity
- `series[i].data[j]` — total complexity merged by developer `i` in week `j` (0.0 if no PRs)
- `series[i].prCounts[j]` — number of PRs merged by developer `i` in week `j`

### 1.2 New drilldown lookup — added to `build_all_chart_data()` return value

```python
"_team_dev_prs": {
  "TeamName": {
    "Alice": {
      "2026-01-05": [
        {
          "title": "Fix login timeout",
          "url": "https://github.com/org/repo/pull/123",
          "complexity": 3.0,
          "merged_at": "2026-01-06"
        }
      ]
    }
  }
}
```

Keyed `team → developer → week_start_date_str → list[pr]`. Week start dates are ISO strings matching the `x` labels in the chart. Each PR object has: `title`, `url`, `complexity` (number), `merged_at` (ISO date string).

Bots and developers with no team assignment are excluded.

---

## 2. Chart Rendering (`reports/interactive_report.py`)

### 2.1 New chart type: `devVelocityMultiLine`

Added as a branch in the `renderChart()` function.

ECharts configuration:
- Type: `line`, one series per developer
- All series enabled by default (legend shows all names, none hidden)
- Legend position: bottom, scrollable if > 8 developers
- Y-axis label: "Complexity"
- X-axis: week date strings, rotated 45°
- Tooltip: custom formatter, triggered on axis, showing for each visible series: `"Alice: 8.0 (4 PRs)"`; developers with 0 PRs for that week are omitted from the tooltip
- Symbols: circles, size 8, hover size 12
- Smooth: false (straight lines — easier to read per-week deltas)

### 2.2 Click handler

On `chart.on('click', params)`:
1. Extract `developer = params.seriesName`, `week = params.name`, `team` from the chart's `_subtab` field (stored on the chart config object)
2. Look up `chartData._team_dev_prs[team][developer][week]`
3. If the list is non-empty, call `openDevPrModal(developer, week, prs)`
4. If empty or missing (dot was a 0-value point), do nothing

### 2.3 Card hint

Each `devVelocityMultiLine` card gets the existing `drill-hint` class text: `"▶ Click a dot to see the PRs behind it"`.

---

## 3. Drilldown Modal

### 3.1 Structure

Reuses the existing `drilldown-overlay` / `drilldown-panel` DOM elements already present in the page. A new JS function `openDevPrModal(developer, week, prs)` populates and opens it.

Header: `"{Developer} — week of {formatted week date}"` + `×` close button.

Table columns:
| Column | Notes |
|---|---|
| Title | Truncated to 60 chars; full title in `title` attribute for hover |
| Complexity | Colored badge (reuses existing badge CSS) |
| Merged | Formatted as `MMM D, YYYY` |
| Link | `"→ Open PR"` anchor, `target="_blank"`, `rel="noopener"` |

Footer line: `"N PRs · total complexity X"` where X is the sum of complexity in the list.

### 3.2 Access

- Only reachable by clicking a non-zero dot on the developer velocity chart
- No tab entry, no URL route, no back-link from any other part of the dashboard
- ESC key closes; click on the overlay backdrop closes; `×` button closes

---

## 4. Positioning Within Team Subtabs

Final order of charts within each team subtab:

1. Velocity Per Capita — `22-{team}` (existing, unchanged)
2. **Developer Velocity — `30-{team}` (new)**
3. Developer Contribution stacked bar — `05-{team}` (existing, unchanged)
4. Complexity vs PR Count scatter — `06-{team}` (existing, unchanged)

The new chart is placed between the two "velocity over time" charts to group temporal views together before the aggregate/scatter views.

---

## 5. Scope

**In scope:**
- `_extract_team()` extended with `devVelocityMultiLine` chart data and `_team_dev_prs` lookup
- `build_all_chart_data()` return dict extended with `_team_dev_prs`
- `renderChart()` extended with `devVelocityMultiLine` branch
- Click handler + `openDevPrModal()` JS function
- Modal populated from existing overlay DOM elements

**Out of scope:**
- URL routing to modal state
- Any new tab or page
- Filters beyond ECharts built-in legend toggle
- Mobile-specific layout
- Export or copy functionality for the PR list
