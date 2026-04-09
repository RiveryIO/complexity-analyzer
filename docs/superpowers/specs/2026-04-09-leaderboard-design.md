# Leaderboard Feature — Design Spec

**Date:** 2026-04-09
**Status:** Approved

## Summary

Add a "Leaderboard" tab to the interactive dashboard showing which developers approved the most PRs. Data is stored as a new `approved_by` column in the existing `complexity-report.csv`.

---

## 1. Data Layer

### CSV Change
Add a single `approved_by` column to `complexity-report.csv`.
- Existing rows beyond the backfill window get an empty string.
- New rows from daily sync get it populated at insert time.

### Backfill Script (`scripts/backfill-approvals.py`)
One-shot script, run once after deploy:
1. Read `complexity-report.csv`
2. Filter to PRs merged in the last 30 days with empty `approved_by`
3. For each PR, call `GET /repos/{owner}/{repo}/pulls/{number}/reviews` via GitHub API
4. Take the first review where `state == "APPROVED"`, sorted by `submitted_at` ascending
5. Write reviewer's `login` into `approved_by` and save the CSV

### Daily Sync Update
After scoring each new PR, also fetch its first approver and populate `approved_by` at insert time. Update `scripts/sync-new-prs.sh` (or the Python equivalent) accordingly.

---

## 2. Leaderboard Tab (UI)

**Tab name:** "Leaderboard" — added to `tabOrder` in `interactive_report.py`.

**Time-period filter:** Three toggle buttons at the top of the tab:
- `Last Month` (default)
- `Last Quarter`
- `All Time`

Switching period swaps the displayed dataset client-side (no page reload).

**Table columns:**

| # | Reviewer | Team | Approvals | Avg Complexity Approved |
|---|----------|------|-----------|--------------------------|

- **#** — rank position; trophy icon for #1
- **Reviewer** — GitHub login from `approved_by`
- **Team** — resolved from existing team mapping config
- **Approvals** — count of PRs approved in selected period
- **Avg Complexity Approved** — avg complexity of PRs reviewed (signals review difficulty)

Sorted by Approvals descending. Top 3 rows get subtle gold / silver / bronze highlight. Uses existing `dd-table` CSS class — no new styles needed.

---

## 3. Report Generation Pipeline

### `reports/chart_data.py`
Add `_extract_leaderboard(df)`:
1. Filter rows where `approved_by` is non-empty
2. Group by `approved_by`, compute `approval_count` and `avg_complexity`
3. Join with team mapping to add `team`
4. Return three pre-computed datasets: last 30 days, last 90 days, all-time

### `reports/interactive_report.py`
- Add `leaderboard` to `tabOrder` and `tabLabels`
- Inject three JSON arrays as `leaderboard_json` into the HTML template
- Tab panel renders a static HTML table (no ECharts instance)
- JS period-toggle swaps which array is rendered

### Data Flow
```
complexity-report.csv
    └─► chart_data.py (_extract_leaderboard)
            └─► three JSON arrays (30d / 90d / all-time)
                    └─► injected into HTML as leaderboard_json
                            └─► JS renders table + period toggle
```

No new files needed in `reports/`. Fits cleanly into the existing pipeline.

---

## Out of Scope
- Multiple approvers per PR (only first approver by date is tracked)
- Backfill beyond last 30 days
- Live GitHub API calls at report-gen time
