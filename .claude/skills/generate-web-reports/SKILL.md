---
name: generate-web-reports
description: "Generates an interactive HTML dashboard from complexity-report.csv, serves it locally, and opens the browser. Produces tabbed ECharts with search, developer filtering, and 20+ chart types across basic, team, risk, fairness, and advanced categories. Use when the user asks to generate reports, view the dashboard, open the web report, visualize complexity data, or see engineering intelligence charts."
---

# Generate Web Reports

Produces an interactive HTML dashboard (`reports/index.html`) with 20+ dynamic ECharts organized in tabs: Basic, Team, Risk, Fairness, Advanced. Includes global chart search and per-developer filtering.

## Prerequisites

- `complexity-report.csv` in project root (from `complexity-cli batch-analyze`)
- Python packages: `pandas`, `numpy`, `matplotlib`
- `teams.cfg` must exist for team-level charts

## Workflow

### Step 1: Ensure Data Exists

If `complexity-report.csv` is missing or stale, generate it first:

```bash
complexity-cli batch-analyze --all-repos --days 30 -o complexity-report.csv --provider anthropic
```

### Step 2: Generate Reports

```bash
complexity-cli generate-reports -i complexity-report.csv -o reports
```

This runs all report functions in parallel (~10 seconds), produces PNG charts, a master composite, and the interactive `reports/index.html` dashboard.

### Step 3: Serve & Open Browser

```bash
python -m http.server 8080 -d reports &
open http://localhost:8080
```

On Linux use `xdg-open` instead of `open`.

### Step 4: Stop Server When Done

```bash
# Find and kill the server
lsof -ti:8080 | xargs kill 2>/dev/null
```

## What the Dashboard Shows

| Tab | Charts |
|-----|--------|
| **Basic** | Velocity over time, velocity by month, PR count vs complexity, rolling avg complexity, merge cycle time, high-risk PR % |
| **Team** | Complexity distribution (boxplot), Gini coefficient, velocity per team per dev, merge cycle by team, complexity vs cycle time, developer velocity (stacked bar), complexity vs PR count (scatter) |
| **Risk** | Complexity by merge weekday, complexity distribution histogram |
| **Fairness** | PR size vs complexity (correlation check), PR count vs avg complexity (anti-splitting) |
| **Advanced** | Developer velocity by week (multi-line with picker), team velocity trend (rolling 4w), cumulative velocity |

## Quick One-Liner

```bash
complexity-cli generate-reports && python -m http.server 8080 -d reports & sleep 1 && open http://localhost:8080
```

## Public Dashboard (Auto-Deploy)

The dashboard is also deployed automatically to GitHub Pages on every push of `complexity-report.csv` to `main`.

**URL:** `https://riveryio.github.io/complexity-analyzer/` (password-protected via StatiCrypt)

To update the public dashboard:

```bash
git add complexity-report.csv
git commit -m "data: update complexity report"
git push
```

GitHub Actions generates reports and deploys a password-protected version. The workflow lives in `.github/workflows/deploy-reports.yml`.
