---
name: weekly-velocity-graph
description: Generates R&D velocity-by-week graph from complexity-report.csv. Use when the user asks for a weekly velocity chart, R&D velocity graph, or to visualize PR throughput by week.
---

# Weekly Velocity Graph

Generates a two-panel bar chart showing R&D velocity by week: PRs merged per week and complexity-weighted velocity (sum of scores).

## Prerequisites

- `complexity-report.csv` in project root (from `complexity-cli batch-analyze`)
- `matplotlib`: `pip install matplotlib`
- `GH_TOKEN` or `gh auth token` (for fetching merge dates)

## Workflow

1. **Ensure data exists**: If `complexity-report.csv` is missing or stale, run:
   ```bash
   complexity-cli batch-analyze --all-repos --days 14 -o complexity-report.csv --provider anthropic
   ```

2. **Generate the graph**:
   ```bash
   python scripts/velocity_by_week.py
   ```

3. **Output**: `velocity-by-week.png` in project root

## Optional: Custom CSV path

The script reads `complexity-report.csv` from the project root. To use a different file, pass it via env or modify the script's `csv_path` variable.
