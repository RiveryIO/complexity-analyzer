# Engineering Intelligence Reports

All reports are generated from the CSV only (no GitHub API calls). Target: <10 seconds total.

## Core Operational (1–3, 7)

| # | Report | File | Description |
|---|--------|------|-------------|
| 1 | Complexity Volume Over Time | 01-complexity-volume-over-time.png | Stacked bar by week, by team |
| 2 | PR Count vs Complexity Over Time | 02-pr-count-vs-complexity.png | Dual line: PR count and total complexity |
| 3 | Avg Complexity per PR (Rolling 4w) | 03-avg-complexity-rolling.png | Line chart, 4-week rolling mean |
| 7 | High Complexity PR Frequency | 07-high-complexity-frequency.png | % of PRs >= 8 per team |

## Team-Level Leadership (4–6, 12, 14, 17)

| # | Report | File | Description |
|---|--------|------|-------------|
| 4 | Complexity Distribution by Team | 04-complexity-distribution-by-team.png | Boxplot per team |
| 5 | Developer Complexity Contribution | 05-developer-contribution.png | Stacked bar per sprint |
| 6 | Complexity per Dev vs PR Count | 06-complexity-per-dev-vs-pr-count.png | Scatter per developer |
| 12 | Team Complexity Gini | 12-team-gini.png | Concentration per team |
| 14 | Complexity vs Cycle Time | 14-complexity-vs-cycle-time.png | Scatter (created_at → merged_at) |
| 17 | Complexity per Team per Developer | 17-complexity-per-team-per-dev.png | Normalized bar chart |

## Risk & Quality (8–9)

| # | Report | File | Description |
|---|--------|------|-------------|
| 8 | Complexity vs Merge Day of Week | 08-complexity-vs-merge-weekday.png | Bar by weekday |
| 9 | Complexity Histogram | 09-complexity-histogram.png | Org-wide distribution |

## Fairness / Anti-Gaming (10–11)

| # | Report | File | Description |
|---|--------|------|-------------|
| 10 | PR Size vs Complexity | 10-pr-size-vs-complexity.png | Scatter (lines changed vs complexity) |
| 11 | PR Count vs Avg Complexity | 11-pr-count-vs-avg-complexity.png | Scatter per dev (anti-splitting) |

## Advanced (13, 15, 16)

| # | Report | File | Description |
|---|--------|------|-------------|
| 13 | Complexity Weighted Velocity | 13-complexity-weighted-velocity.png | Per sprint: total_complexity / #devs |
| 15 | Complexity Trend by Team | 15-complexity-trend-by-team.png | Rolling median per team |
| 16 | Cumulative Complexity | 16-cumulative-complexity.png | Cumulative sum over time |

## Report 18 (Incidents)

Complexity vs Deployment Incidents requires external incident data. Not implemented in v1. To add: provide a CSV with `pr_url,incidents` and merge with the main CSV.
