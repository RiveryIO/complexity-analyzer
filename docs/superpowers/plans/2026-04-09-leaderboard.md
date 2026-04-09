# Leaderboard Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Leaderboard" tab to the interactive dashboard showing PR approvers ranked by approval count, sourced from a new `approved_by` column in `complexity-report.csv`.

**Architecture:** Add `approved_by` to the CSV schema; call GitHub's reviews API during batch sync to populate it for new PRs; a one-shot backfill script handles the last 30 days; `chart_data.py` aggregates three time-window datasets; `interactive_report.py` renders a sortable HTML table with a period toggle.

**Tech Stack:** Python 3.12, pandas, httpx, ECharts dashboard (HTML/JS), existing `dd-table` CSS class.

---

## File Map

| Action | File | Responsibility |
|--------|------|---------------|
| Modify | `cli/csv_handler.py` | Add `approved_by` to `CSV_FIELDNAMES` and `add_row()` |
| Modify | `cli/github.py` | Add `fetch_first_approver()` function |
| Modify | `cli/batch.py` | Call `fetch_first_approver()` in `_write_row_from_result()` |
| Modify | `reports/chart_data.py` | Add `_extract_leaderboard()`, update `build_all_chart_data()` |
| Modify | `reports/interactive_report.py` | Add leaderboard tab: CSS, tab order, panel JS |
| Create | `scripts/backfill-approvals.py` | One-shot backfill for last 30 days |
| Modify | `tests/test_csv_handler.py` | Test `approved_by` in schema and `add_row()` |
| Modify | `tests/test_github.py` | Test `fetch_first_approver()` |
| Modify | `tests/test_reports.py` | Test `_extract_leaderboard()` |

---

## Task 1: Extend CSV schema with `approved_by`

**Files:**
- Modify: `cli/csv_handler.py:12-24` (CSV_FIELDNAMES) and `:78-134` (add_row)
- Test: `tests/test_csv_handler.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_csv_handler.py`:

```python
def test_approved_by_in_fieldnames():
    assert "approved_by" in CSV_FIELDNAMES


def test_add_row_writes_approved_by(tmp_path):
    output_file = tmp_path / "out.csv"
    writer = CSVBatchWriter(output_file)
    writer.add_row(
        "https://github.com/org/repo/pull/1",
        5,
        "explanation",
        "alice",
        developer="alice",
        date="2026-03-10",
        team="FullStack",
        merged_at="2026-03-10T10:00:00Z",
        created_at="2026-03-09T10:00:00Z",
        lines_added=10,
        lines_deleted=2,
        approved_by="bob",
    )
    writer.close()

    with output_file.open("r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert rows[0]["approved_by"] == "bob"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -m pytest tests/test_csv_handler.py::test_approved_by_in_fieldnames tests/test_csv_handler.py::test_add_row_writes_approved_by -v
```

Expected: FAIL — `approved_by` not in CSV_FIELDNAMES, `add_row` has no such param.

- [ ] **Step 3: Add `approved_by` to CSV_FIELDNAMES**

In `cli/csv_handler.py`, change the `CSV_FIELDNAMES` list (lines 12-24):

```python
CSV_FIELDNAMES = [
    "pr_url",
    "complexity",
    "developer",
    "date",
    "team",
    "merged_at",
    "created_at",
    "lines_added",
    "lines_deleted",
    "explanation",
    "source",
    "approved_by",
]
```

- [ ] **Step 4: Add `approved_by` parameter to `add_row()`**

In `cli/csv_handler.py`, update the `add_row` signature (after `lines_deleted`):

```python
def add_row(
    self,
    pr_url: str,
    complexity: int,
    explanation: str,
    author: str = "",
    *,
    developer: Optional[str] = None,
    date: Optional[str] = None,
    team: Optional[str] = None,
    merged_at: Optional[str] = None,
    created_at: Optional[str] = None,
    lines_added: Optional[int] = None,
    lines_deleted: Optional[int] = None,
    source: Optional[str] = None,
    approved_by: Optional[str] = None,
) -> None:
```

And in the `row` dict inside `add_row`, add `"approved_by"` after `"source"`:

```python
row: Dict[str, Any] = {
    "pr_url": pr_url,
    "complexity": str(complexity),
    "developer": dev or "",
    "date": date or "",
    "team": team or "",
    "merged_at": merged_at or "",
    "created_at": created_at or "",
    "lines_added": str(lines_added) if lines_added is not None else "",
    "lines_deleted": str(lines_deleted) if lines_deleted is not None else "",
    "explanation": explanation,
    "source": source,
    "approved_by": approved_by or "",
}
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_csv_handler.py -v
```

Expected: all PASS, including the two new tests.

- [ ] **Step 6: Commit**

```bash
git add cli/csv_handler.py tests/test_csv_handler.py
git commit -m "feat: add approved_by column to CSV schema"
```

---

## Task 2: Add `fetch_first_approver()` to GitHub client

**Files:**
- Modify: `cli/github.py` (add function after `fetch_pr_metadata`)
- Test: `tests/test_github.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_github.py`:

```python
from cli.github import fetch_first_approver


@patch("cli.github.httpx.Client")
def test_fetch_first_approver_returns_first_approved(mock_client_class):
    """Returns login of the first APPROVED review sorted by submitted_at."""
    reviews = [
        {"state": "COMMENTED", "submitted_at": "2026-03-01T10:00:00Z", "user": {"login": "charlie"}},
        {"state": "APPROVED",  "submitted_at": "2026-03-02T10:00:00Z", "user": {"login": "alice"}},
        {"state": "APPROVED",  "submitted_at": "2026-03-03T10:00:00Z", "user": {"login": "bob"}},
    ]
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = reviews
    mock_response.raise_for_status = Mock()

    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    result = fetch_first_approver("owner", "repo", 123, token="tok")
    assert result == "alice"


@patch("cli.github.httpx.Client")
def test_fetch_first_approver_no_approvals_returns_empty(mock_client_class):
    """Returns '' when no APPROVED reviews exist."""
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"state": "COMMENTED", "submitted_at": "2026-03-01T10:00:00Z", "user": {"login": "charlie"}},
    ]
    mock_response.raise_for_status = Mock()

    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    result = fetch_first_approver("owner", "repo", 123, token="tok")
    assert result == ""


@patch("cli.github.httpx.Client")
def test_fetch_first_approver_404_returns_empty(mock_client_class):
    """Returns '' when GitHub returns 404 (e.g. private repo without access)."""
    mock_response = Mock()
    mock_response.status_code = 404

    mock_client = Mock()
    mock_client.__enter__ = Mock(return_value=mock_client)
    mock_client.__exit__ = Mock(return_value=False)
    mock_client.get.return_value = mock_response
    mock_client_class.return_value = mock_client

    result = fetch_first_approver("owner", "repo", 123, token="tok")
    assert result == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_github.py::test_fetch_first_approver_returns_first_approved tests/test_github.py::test_fetch_first_approver_no_approvals_returns_empty tests/test_github.py::test_fetch_first_approver_404_returns_empty -v
```

Expected: FAIL — `cannot import name 'fetch_first_approver'`.

- [ ] **Step 3: Implement `fetch_first_approver()` in `cli/github.py`**

Add this function after `fetch_pr_metadata` (after line ~513):

```python
def fetch_first_approver(
    owner: str,
    repo: str,
    pr: int,
    token: Optional[str] = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> str:
    """
    Return the login of the first PR approver, or '' if none.

    Calls GET /repos/{owner}/{repo}/pulls/{pr}/reviews and returns the
    login of the earliest review with state == "APPROVED".

    Args:
        owner: Repository owner
        repo: Repository name
        pr: PR number
        token: GitHub token (optional for public repos)
        timeout: Request timeout in seconds

    Returns:
        GitHub login of first approver, or empty string if no approvals
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = build_github_headers(token)
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url, headers=headers)
            if response.status_code == 404:
                return ""
            response.raise_for_status()
            reviews = response.json()
        approved = [r for r in reviews if r.get("state") == "APPROVED"]
        approved.sort(key=lambda r: r.get("submitted_at", ""))
        return approved[0]["user"]["login"] if approved else ""
    except (httpx.HTTPStatusError, httpx.RequestError, KeyError, IndexError):
        return ""
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_github.py::test_fetch_first_approver_returns_first_approved tests/test_github.py::test_fetch_first_approver_no_approvals_returns_empty tests/test_github.py::test_fetch_first_approver_404_returns_empty -v
```

Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add cli/github.py tests/test_github.py
git commit -m "feat: add fetch_first_approver to GitHub client"
```

---

## Task 3: Populate `approved_by` during batch write

**Files:**
- Modify: `cli/batch.py:918-940` (`_write_row_from_result` nested function)

No new tests here — this is wiring. The CSV + github tests cover the components.

- [ ] **Step 1: Add imports to `cli/batch.py`**

At the top of `cli/batch.py`, ensure these imports are present. Add `import os` if not already there, and add `fetch_first_approver` to the github import:

```python
import os
```

Change the existing github import from:
```python
from .github import (
    GitHubAPIError,
    has_complexity_label,
    list_user_repos,
    search_closed_prs,
    search_closed_prs_by_repos,
    update_complexity_label,
)
```

To:
```python
from .github import (
    GitHubAPIError,
    fetch_first_approver,
    has_complexity_label,
    list_user_repos,
    search_closed_prs,
    search_closed_prs_by_repos,
    update_complexity_label,
)
```

- [ ] **Step 2: Update `_write_row_from_result` to fetch and write `approved_by`**

Replace the existing `_write_row_from_result` function (lines ~918-940) with:

```python
def _write_row_from_result(pr_url_result: str, result: Dict[str, Any]) -> None:
    """Extract fields from result and write to CSV."""
    complexity = result.get("score", result.get("complexity", 0))
    author = result.get("author", "") or ""
    team = get_team_for_developer(author)
    merged_at = result.get("merged_at") or ""
    created_at = result.get("created_at") or ""
    date = merged_at[:10] if merged_at else ""
    lines_added = result.get("lines_added")
    lines_deleted = result.get("lines_deleted")

    # Fetch first approver for GitHub PRs (non-critical — silent on failure)
    approved_by = ""
    if "github.com" in pr_url_result:
        try:
            _owner, _repo, _pr = parse_pr_url(pr_url_result)
            _token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
            approved_by = fetch_first_approver(_owner, _repo, int(_pr), token=_token)
        except Exception:
            pass

    csv_writer.add_row(
        pr_url_result,
        complexity,
        result.get("explanation", ""),
        author,
        developer=author,
        date=date,
        team=team,
        merged_at=merged_at,
        created_at=created_at,
        lines_added=lines_added,
        lines_deleted=lines_deleted,
        approved_by=approved_by,
    )
```

- [ ] **Step 3: Run existing batch tests to verify nothing broke**

```bash
python -m pytest tests/test_batch.py -v
```

Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add cli/batch.py
git commit -m "feat: fetch approved_by during batch PR sync"
```

---

## Task 4: Add leaderboard data extraction

**Files:**
- Modify: `reports/chart_data.py` (add `_extract_leaderboard`, update `build_all_chart_data`)
- Test: `tests/test_reports.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_reports.py`:

```python
from datetime import datetime, timezone, timedelta
import pandas as pd
from reports.chart_data import _extract_leaderboard


def test_extract_leaderboard_groups_by_approver():
    today = datetime.now(timezone.utc)
    recent = (today - timedelta(days=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    old = (today - timedelta(days=100)).strftime("%Y-%m-%dT%H:%M:%SZ")

    df = pd.DataFrame([
        {"pr_url": "https://github.com/o/r/pull/1", "complexity": 3, "approved_by": "alice", "date": recent, "merged_at": recent},
        {"pr_url": "https://github.com/o/r/pull/2", "complexity": 5, "approved_by": "alice", "date": recent, "merged_at": recent},
        {"pr_url": "https://github.com/o/r/pull/3", "complexity": 4, "approved_by": "bob",   "date": recent, "merged_at": recent},
        {"pr_url": "https://github.com/o/r/pull/4", "complexity": 2, "approved_by": "alice", "date": old,    "merged_at": old},
    ])

    result = _extract_leaderboard(df)

    # 30d: alice=2, bob=1
    assert result["30d"][0]["reviewer"] == "alice"
    assert result["30d"][0]["approvals"] == 2
    assert result["30d"][0]["rank"] == 1
    assert result["30d"][1]["reviewer"] == "bob"
    assert result["30d"][1]["approvals"] == 1

    # all-time: alice=3, bob=1
    assert result["all"][0]["reviewer"] == "alice"
    assert result["all"][0]["approvals"] == 3

    # avg_complexity for alice in 30d: (3+5)/2 = 4.0
    assert result["30d"][0]["avg_complexity"] == 4.0


def test_extract_leaderboard_no_approved_by_column():
    df = pd.DataFrame([
        {"pr_url": "https://github.com/o/r/pull/1", "complexity": 3, "date": "2026-03-10", "merged_at": "2026-03-10T10:00:00Z"},
    ])
    result = _extract_leaderboard(df)
    assert result == {"30d": [], "90d": [], "all": []}


def test_extract_leaderboard_empty_approved_by():
    df = pd.DataFrame([
        {"pr_url": "https://github.com/o/r/pull/1", "complexity": 3, "approved_by": "", "date": "2026-03-10", "merged_at": "2026-03-10T10:00:00Z"},
    ])
    result = _extract_leaderboard(df)
    assert result["30d"] == []
    assert result["all"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_reports.py::test_extract_leaderboard_groups_by_approver tests/test_reports.py::test_extract_leaderboard_no_approved_by_column tests/test_reports.py::test_extract_leaderboard_empty_approved_by -v
```

Expected: FAIL — `cannot import name '_extract_leaderboard'`.

- [ ] **Step 3: Implement `_extract_leaderboard()` in `reports/chart_data.py`**

Add this function before `build_all_chart_data` at the end of `reports/chart_data.py`:

```python
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
```

- [ ] **Step 4: Update `build_all_chart_data()` to include leaderboard**

Change `build_all_chart_data` (last function in `reports/chart_data.py`) — update the return type and add the leaderboard key:

```python
def build_all_chart_data(df: pd.DataFrame) -> Dict[str, Any]:
    """Build chart data for all tabs. Returns {tab: [chart_data, ...]}."""
    features_data = _extract_features()
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

- [ ] **Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_reports.py::test_extract_leaderboard_groups_by_approver tests/test_reports.py::test_extract_leaderboard_no_approved_by_column tests/test_reports.py::test_extract_leaderboard_empty_approved_by -v
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add reports/chart_data.py tests/test_reports.py
git commit -m "feat: add leaderboard data extraction to chart_data"
```

---

## Task 5: Add Leaderboard tab to interactive dashboard

**Files:**
- Modify: `reports/interactive_report.py`
  - Add CSS (in `<style>` block)
  - Update `tabOrder` and `tabLabels` (line ~943-944)
  - Add leaderboard panel rendering in `tabOrder.forEach` loop (line ~1355)

This task has no unit test — the report generates HTML. Verify by running the report generator and opening the output.

- [ ] **Step 1: Add leaderboard CSS to the `<style>` block**

Find the CSS section in `_HTML_TEMPLATE` (look for existing CSS like `.dd-table`). Add the leaderboard styles right before the closing `</style>` tag:

```css
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
```

- [ ] **Step 2: Add `leaderboard` to `tabOrder` and `tabLabels`**

Find line ~943 in `_HTML_TEMPLATE`:

```javascript
    const tabOrder = ['basic', 'team', 'risk', 'fairness', 'advanced', 'features', 'todo', 'engineers', 'changelog'];
    const tabLabels = {{ basic: 'Basic', team: 'Team', risk: 'Risk', fairness: 'Fairness', advanced: 'Advanced', features: 'Features', todo: 'Roadmap', engineers: 'Engineers', changelog: 'Changelog' }};
```

Change to:

```javascript
    const tabOrder = ['basic', 'team', 'risk', 'fairness', 'advanced', 'features', 'leaderboard', 'todo', 'engineers', 'changelog'];
    const tabLabels = {{ basic: 'Basic', team: 'Team', risk: 'Risk', fairness: 'Fairness', advanced: 'Advanced', features: 'Features', leaderboard: 'Leaderboard', todo: 'Roadmap', engineers: 'Engineers', changelog: 'Changelog' }};
```

- [ ] **Step 3: Add leaderboard panel rendering in the `tabOrder.forEach` loop**

Find the `tabOrder.forEach((key, i) => {{` loop that builds panels (around line ~1355). Inside this loop, before the final `else` block that renders chart panels, add a leaderboard branch. Insert it right after the `if (key === 'todo')` block (around line ~1380):

```javascript
      if (key === 'leaderboard') {{
        const lbData = (chartData['leaderboard'] || {{}});
        let activePeriod = '30d';

        function renderLbTable(period) {{
          const rows = lbData[period] || [];
          const medals = ['\ud83e\udd47', '\ud83e\udd48', '\ud83e\udd49'];
          const rowClasses = ['gold-row', 'silver-row', 'bronze-row'];
          if (!rows.length) {{
            document.getElementById('lb-tbody').innerHTML =
              '<tr><td colspan="5" style="text-align:center;padding:2rem;color:var(--text-muted)">No approval data for this period</td></tr>';
            return;
          }}
          document.getElementById('lb-tbody').innerHTML = rows.map((r, i) => {{
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
```

- [ ] **Step 4: Verify the report generates without errors**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -c "
import pandas as pd
from reports.interactive_report import build_interactive_report
from pathlib import Path
df = pd.read_csv('complexity-report.csv', dtype=str)
build_interactive_report(df, Path('output'))
print('OK — output/index.html generated')
"
```

Expected: prints `OK — output/index.html generated` with no exceptions.

- [ ] **Step 5: Open the report and visually confirm the Leaderboard tab appears**

```bash
open output/index.html
```

Check: tab bar shows "Leaderboard", clicking it shows the period buttons and table (empty for now since no `approved_by` data yet — that's expected).

- [ ] **Step 6: Commit**

```bash
git add reports/interactive_report.py
git commit -m "feat: add Leaderboard tab to interactive dashboard"
```

---

## Task 6: Backfill script for last 30 days

**Files:**
- Create: `scripts/backfill-approvals.py`

This script is run once after deploy. It reads `complexity-report.csv`, finds GitHub PRs merged in the last 30 days with an empty `approved_by`, fetches the first approver from GitHub, and writes the CSV back.

- [ ] **Step 1: Create `scripts/backfill-approvals.py`**

```python
#!/usr/bin/env python3
"""
One-shot backfill: sets approved_by for GitHub PRs merged in the last 30 days.

Usage:
    python scripts/backfill-approvals.py

Requires:
    GH_TOKEN or GITHUB_TOKEN env var with repo read access.

Run ONCE after deploying the approved_by column. Safe to re-run — skips rows
that already have approved_by set.
"""

import csv
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import httpx

PROJECT_DIR = Path(__file__).resolve().parent.parent
CSV_FILE = PROJECT_DIR / "complexity-report.csv"
CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)
SLEEP_BETWEEN_REQUESTS = 0.3  # seconds — stays well within GitHub rate limits


def _get_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Error: set GH_TOKEN or GITHUB_TOKEN", file=sys.stderr)
        sys.exit(1)
    return token


def _parse_github_url(url: str):
    """Parse 'https://github.com/owner/repo/pull/123' → (owner, repo, pr_number)."""
    parts = url.rstrip("/").split("/")
    return parts[-4], parts[-3], int(parts[-1])


def _fetch_first_approver(owner: str, repo: str, pr: int, token: str) -> str:
    """Return login of first APPROVED reviewer, or '' if none."""
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr}/reviews"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    try:
        resp = httpx.get(url, headers=headers, timeout=30)
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        reviews = resp.json()
        approved = [r for r in reviews if r.get("state") == "APPROVED"]
        approved.sort(key=lambda r: r.get("submitted_at", ""))
        return approved[0]["user"]["login"] if approved else ""
    except Exception as e:
        print(f"  Warning: {e}", file=sys.stderr)
        return ""


def main() -> None:
    if not CSV_FILE.exists():
        print(f"Error: {CSV_FILE} not found", file=sys.stderr)
        sys.exit(1)

    token = _get_token()

    with CSV_FILE.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    if "approved_by" not in fieldnames:
        print(
            "Error: 'approved_by' column not found. Deploy the schema change (Task 1) first.",
            file=sys.stderr,
        )
        sys.exit(1)

    to_backfill = []
    for row in rows:
        if row.get("approved_by", "").strip():
            continue  # Already populated — skip
        if "github.com" not in row.get("pr_url", ""):
            continue  # Bitbucket PRs have no GitHub reviews API
        merged_at = row.get("merged_at", "")
        if not merged_at:
            continue
        try:
            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if merged_dt >= CUTOFF:
            to_backfill.append(row)

    print(f"Found {len(to_backfill)} GitHub PRs in last 30 days without approved_by")
    if not to_backfill:
        print("Nothing to do.")
        return

    filled = 0
    for i, row in enumerate(to_backfill, 1):
        pr_url = row["pr_url"]
        try:
            owner, repo, pr_num = _parse_github_url(pr_url)
        except (IndexError, ValueError):
            print(f"  [{i}/{len(to_backfill)}] Skipping malformed URL: {pr_url}")
            continue

        print(f"  [{i}/{len(to_backfill)}] {owner}/{repo}#{pr_num} ... ", end="", flush=True)
        approver = _fetch_first_approver(owner, repo, pr_num, token)
        row["approved_by"] = approver
        if approver:
            filled += 1
        print(approver or "(no approver)")
        time.sleep(SLEEP_BETWEEN_REQUESTS)

    with CSV_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone. Filled {filled}/{len(to_backfill)} approver fields.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x scripts/backfill-approvals.py
```

- [ ] **Step 3: Dry-run smoke test (reads only, no writes)**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -c "
import csv
from pathlib import Path
from datetime import datetime, timezone, timedelta

CSV_FILE = Path('complexity-report.csv')
CUTOFF = datetime.now(timezone.utc) - timedelta(days=30)

with CSV_FILE.open() as f:
    rows = list(csv.DictReader(f))

to_backfill = [
    r for r in rows
    if not r.get('approved_by', '').strip()
    and 'github.com' in r.get('pr_url', '')
    and r.get('merged_at', '')
    and datetime.fromisoformat(r['merged_at'].replace('Z', '+00:00')) >= CUTOFF
]
print(f'Would backfill {len(to_backfill)} PRs')
"
```

Expected: prints a count like `Would backfill 247 PRs`. If count is 0, check that `approved_by` column exists in the CSV.

- [ ] **Step 4: Run the actual backfill**

```bash
GH_TOKEN="$(gh auth token)" python scripts/backfill-approvals.py
```

Expected: progress lines like `  [1/247] RiveryIO/rivery_back#12751 ... alice` followed by `Done. Filled X/247 approver fields.`

- [ ] **Step 5: Verify the CSV was updated correctly**

```bash
python -c "
import csv
from pathlib import Path
rows = list(csv.DictReader(Path('complexity-report.csv').open()))
filled = sum(1 for r in rows if r.get('approved_by', '').strip())
print(f'Rows with approved_by: {filled}/{len(rows)}')
"
```

Expected: shows a non-zero count of rows with `approved_by` populated.

- [ ] **Step 6: Regenerate the dashboard and check the Leaderboard tab**

```bash
python -c "
import pandas as pd
from reports.interactive_report import build_interactive_report
from pathlib import Path
df = pd.read_csv('complexity-report.csv', dtype=str)
build_interactive_report(df, Path('output'))
print('Done')
"
open output/index.html
```

Expected: Leaderboard tab now shows actual reviewers ranked by approval count.

- [ ] **Step 7: Commit everything**

```bash
git add scripts/backfill-approvals.py complexity-report.csv
git commit -m "feat: add backfill script and run initial approved_by backfill"
```

---

## Task 7: Full test suite pass

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/ohadperry/Documents/Dev/complexity-analyzer
python -m pytest tests/ -v
```

Expected: all tests PASS. If any fail, fix them before continuing.

- [ ] **Step 2: Run flake8**

```bash
flake8 cli/csv_handler.py cli/github.py cli/batch.py reports/chart_data.py scripts/backfill-approvals.py --max-line-length=120
```

Expected: no output (no errors).

- [ ] **Step 3: Commit if any fixes were needed**

```bash
git add -p
git commit -m "fix: lint and test suite cleanup for leaderboard feature"
```

---

## Spec Coverage Check

| Spec requirement | Task |
|-----------------|------|
| `approved_by` column added to CSV | Task 1 |
| Existing rows don't break (empty string default) | Task 1 (fieldname + add_row default) |
| Backfill script for last 30 days | Task 6 |
| First approver by date | Task 2 (`fetch_first_approver` sorts by `submitted_at`) |
| Daily sync populates `approved_by` for new PRs | Task 3 |
| Leaderboard data: 30d / 90d / all-time | Task 4 |
| Team resolved from team mapping | Task 4 (`mapping.get(reviewer, "")`) |
| Avg complexity approved shown | Task 4 + Task 5 |
| New "Leaderboard" tab | Task 5 |
| Period toggle buttons | Task 5 |
| Top 3 gold/silver/bronze highlight | Task 5 |
| Uses existing `dd-table` CSS | Task 5 |
