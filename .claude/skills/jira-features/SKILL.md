---
name: jira-features
description: Pulls resolved Jira tickets via Atlassian MCP, groups them into features by Epic, uses LLM classification to determine user-facing vs internal, and writes features-released.csv. Use when the user asks to fetch Jira features, update the feature velocity CSV, track released features, measure feature velocity, or sync Jira data.
---

# Jira Feature Velocity Tracker

Fetches Done tickets from Jira boards (one per team), groups them into features by Epic, classifies each as user-facing via LLM reasoning, and writes `features-released.csv`.

## Prerequisites

- Atlassian MCP server connected (`user-mcp-atlassian`)
- `jira-teams.yaml` in project root (template ships with the repo; board IDs populated via Step 1 below)

## Workflow

Follow **all five steps** in order. Step 1 is one-time setup; Steps 2-5 run each time.

---

### Step 1 -- Board Discovery (one-time)

Populate `jira-teams.yaml` with real board IDs.

1. Call `jira_search_fields` via MCP with keyword `"story point"` to find the custom field ID for story points. Save it in `jira-teams.yaml` under `settings.story_points_field`.

2. Call `jira_get_agile_boards` via MCP (limit 50, paginate if needed) to list all boards.

3. For each team in `jira-teams.yaml` (Core, FullStack, Integration, CDC, Ninja, Devops), find the board whose name best matches the team name. Present the mapping to the user for confirmation:

```
Proposed board mapping:
  Core        -> board 42 "Core Team Board"
  FullStack   -> board 43 "FullStack Board"
  ...
```

4. After confirmation, update `jira-teams.yaml` with the real `board_id` and `board_name` values.

---

### Step 2 -- Fetch Done Tickets

For each team/board in `jira-teams.yaml`:

1. Build the JQL query, **excluding QA assignees** listed in `settings.excluded_assignees`:

```
project = <board_project> AND status in ("Done", "Closed", "Released") AND resolved >= "-{days}d" AND assignee NOT IN ("Nastia Feigin")
```

Default `{days}` is from `settings.default_lookback_days` (90). Override with user-supplied value.
Build the `NOT IN` clause dynamically from `settings.excluded_assignees` in `jira-teams.yaml`.

2. Call `jira_search` via MCP with:
   - `jql`: the query above
   - `fields`: `summary,description,issuetype,status,resolutiondate,created,parent,labels,components,fixVersions,{story_points_field},assignee`
   - `limit`: 50
   - `start_at`: 0 (paginate until all results fetched)

3. Collect all tickets across all teams. Tag each ticket with its `team` name from the board mapping.

4. Optionally save raw results to `cache/jira-raw-{date}.json` for debugging.

---

### Step 3 -- Epic Grouping & Dedup

Group the fetched tickets into "features":

1. **Epic-parented tickets**: Group all tickets that share the same `parent` (Epic key) into one feature.
   - `feature_id` = the Epic key (e.g., `PROJ-100`)
   - `feature_name` = the Epic's summary (fetch via `jira_get_issue` if not already available)
   - `jira_keys` = list of all child ticket keys in this group
   - `released_date` = the latest `resolutiondate` among the group
   - `first_created` = the earliest `created` date among the group
   - `story_points` = sum of story points across all tickets in the group
   - `fix_versions` = union of all fix versions

2. **Orphan tickets** (no Epic parent): Each is its own feature.
   - `feature_id` = the ticket key
   - `feature_name` = the ticket summary
   - `jira_keys` = just this one key

3. **Bug/Defect handling**: If `issuetype` is `Bug` or `Defect`, set `category = bug_fix` regardless of Epic grouping. Bugs under an Epic are still grouped with that Epic but the category reflects the bug nature. If an Epic contains ONLY bugs/defects, the whole feature is `category = bug_fix`. Mixed Epics (bugs + stories) keep `category = feature`.

4. **QA ticket exclusion**: Tickets assigned to QA personnel (listed in `settings.excluded_assignees`) are already filtered out at the JQL level (Step 2). If any slip through, drop them before grouping. A feature split into N sub-tickets should count as **1 feature**, not N. QA validation tickets are part of the feature delivery process, not standalone features.

---

### Step 4 -- LLM Classification

For each feature group, classify using your own reasoning (you ARE the LLM):

1. **`is_user_facing`** (true/false): Does this feature directly impact what end users see or experience? Consider:
   - Changes to UI, API responses, user flows, notifications = user-facing
   - Internal tooling, CI/CD, refactors, monitoring, infra = NOT user-facing
   - Bug fixes that affect user experience = user-facing
   - Performance improvements users would notice = user-facing

2. **`category`**: One of:
   - `feature` -- new capability or significant enhancement
   - `bug_fix` -- fixes broken behavior
   - `improvement` -- incremental enhancement to existing capability
   - `tech_debt` -- refactoring, cleanup, dependency updates, infra

3. **`description`**: One-line summary of what was shipped, written for a non-technical audience.

4. **`llm_reasoning`**: One sentence explaining the classification decision (audit trail).

Present the classification results to the user in a summary table before writing. Example:

```
| feature_id | feature_name           | team      | category | user_facing | released   |
|------------|------------------------|-----------|----------|-------------|------------|
| PROJ-100   | New onboarding flow    | FullStack | feature  | yes         | 2026-03-01 |
| PROJ-205   | Fix login timeout      | Core      | bug_fix  | yes         | 2026-02-28 |
| PROJ-310   | Upgrade Redis driver   | Devops    | tech_debt| no          | 2026-02-25 |
```

Ask user to confirm or adjust any classifications before proceeding.

---

### Step 5 -- Write CSV

1. Build the JSON array of classified features matching the schema expected by `scripts/jira_features_to_csv.py`.

2. Write the JSON to a temp file or pipe to stdin:

```bash
python scripts/jira_features_to_csv.py --input features.json
```

Or for a preview first:

```bash
python scripts/jira_features_to_csv.py --input features.json --dry-run
```

3. Report the result: how many features were written (new vs updated).

---

## CSV Schema: `features-released.csv`

| Column | Type | Description |
|--------|------|-------------|
| `feature_id` | string | Epic key or standalone issue key (primary key) |
| `feature_name` | string | Epic summary or LLM-generated name |
| `jira_keys` | string | Pipe-separated constituent ticket keys |
| `ticket_count` | int | Number of tickets in this feature |
| `category` | enum | `feature` / `bug_fix` / `improvement` / `tech_debt` |
| `is_user_facing` | bool | LLM-classified: impacts end users? |
| `llm_reasoning` | string | Classification rationale |
| `team` | string | Team name from jira-teams.yaml |
| `released_date` | date | Latest resolution date in the group |
| `first_created` | date | Earliest creation date in the group |
| `lead_time_days` | int | `released_date - first_created` (computed) |
| `quarter` | string | e.g., `2026-Q1` (computed) |
| `iso_week` | string | e.g., `2026-W10` (computed) |
| `story_points` | float | Sum of story points |
| `description` | string | LLM-generated one-liner |
| `fix_versions` | string | Jira fix versions (pipe-separated) |
| `ticket_links` | string | Pipe-separated Jira browse URLs for each key in `jira_keys` |
| `parent_epic_link` | string | Jira browse URL for the parent epic (empty for orphan tickets or synthetic IDs) |

## Velocity Queries This Enables

- **Features shipped per week by team**: group `iso_week` + `team` where `is_user_facing = true`
- **Throughput by quarter**: count by `quarter` + `team`
- **Feature vs bug ratio**: `category` breakdown per team
- **Average lead time**: mean `lead_time_days` per `quarter` + `team`
- **Story points velocity**: sum `story_points` per `iso_week` + `team`

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | 90 | Lookback window for resolved tickets |
| `--team` | all | Restrict to a single team |
| `--dry-run` | false | Preview CSV changes without writing |

## Notes

- The Bots team from `teams.cfg` is excluded (no Jira board for bots).
- Derived columns (`lead_time_days`, `quarter`, `iso_week`) are computed by `jira_features_to_csv.py`, not by the agent.
- Re-running is safe: features are upserted by `feature_id`, so re-classification updates existing rows.
