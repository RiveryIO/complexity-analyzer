#!/usr/bin/env python3
"""Headless Jira feature sync — fetches resolved tickets and upserts features-released.csv.

Reads credentials from .env (JIRA_URL, JIRA_EMAIL, JIRA_API_KEY).
Reads team/project config from jira-teams.yaml.
Groups tickets by parent Epic, then calls jira_features_to_csv.py to upsert.

Usage:
    python scripts/sync-jira-features.py [--days 90] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from base64 import b64encode
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = REPO_ROOT / ".env"
TEAMS_FILE = REPO_ROOT / "jira-teams.yaml"


# ---------------------------------------------------------------------------
# .env loader
# ---------------------------------------------------------------------------

def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE pairs from a .env file into os.environ."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# ---------------------------------------------------------------------------
# Jira REST API helpers
# ---------------------------------------------------------------------------

def _auth_header(email: str, token: str) -> str:
    creds = f"{email}:{token}"
    return "Basic " + b64encode(creds.encode()).decode()


def jira_get(base_url: str, path: str, params: dict, auth: str, ca_bundle: str | None) -> dict:
    """Make a GET request to Jira REST API v3 and return parsed JSON."""
    qs = urlencode(params)
    url = f"{base_url.rstrip('/')}{path}?{qs}"
    req = Request(url, headers={"Authorization": auth, "Accept": "application/json"})

    ssl_context = None
    if ca_bundle:
        import ssl
        ssl_context = ssl.create_default_context(cafile=ca_bundle)

    try:
        with urlopen(req, context=ssl_context, timeout=30) as resp:
            return json.loads(resp.read())
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")
        print(f"HTTP {exc.code} for {url}: {body[:300]}", file=sys.stderr)
        raise


def fetch_issues(
    base_url: str,
    auth: str,
    jql: str,
    fields: list[str],
    ca_bundle: str | None,
) -> list[dict]:
    """Paginate through Jira search results and return all issues."""
    all_issues: list[dict] = []
    start_at = 0
    page_size = 50
    while True:
        data = jira_get(
            base_url,
            "/rest/api/3/search/jql",
            {"jql": jql, "fields": ",".join(fields), "maxResults": page_size, "startAt": start_at},
            auth,
            ca_bundle,
        )
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("total", 0)
        start_at += len(issues)
        if start_at >= total or not issues:
            break
    return all_issues


def fetch_epic_summary(base_url: str, auth: str, key: str, ca_bundle: str | None) -> str:
    """Fetch the summary of an Epic by key."""
    try:
        data = jira_get(base_url, f"/rest/api/3/issue/{key}", {"fields": "summary"}, auth, ca_bundle)
        return data.get("fields", {}).get("summary", key)
    except Exception:
        return key


# ---------------------------------------------------------------------------
# Grouping
# ---------------------------------------------------------------------------

def _issue_type(issue: dict) -> str:
    return (issue.get("fields", {}).get("issuetype", {}).get("name", "") or "").lower()


def _category(issue_type: str) -> str:
    if issue_type in ("bug", "defect"):
        return "bug_fix"
    return "feature"


def group_into_features(issues: list[dict], team: str, base_url: str, auth: str, ca_bundle: str | None) -> list[dict]:
    """Group issues by parent Epic key into feature dicts."""
    epics: dict[str, dict] = {}   # epic_key -> aggregated feature
    orphans: list[dict] = []

    for issue in issues:
        fields = issue.get("fields", {})
        key = issue["key"]
        summary = fields.get("summary", "")
        resolution_date = fields.get("resolutiondate", "") or ""
        created_date = fields.get("created", "") or ""
        sp = fields.get("customfield_11703") or fields.get("story_points")
        fix_versions = [v.get("name", "") for v in (fields.get("fixVersions") or [])]
        itype = _issue_type(issue)

        parent = fields.get("parent") or {}
        parent_key = parent.get("key", "")
        parent_type = (parent.get("fields", {}).get("issuetype", {}).get("name", "") or "").lower()
        is_epic_parent = parent_type == "epic" or (parent_key and parent_key != key)

        if is_epic_parent and parent_key:
            if parent_key not in epics:
                epics[parent_key] = {
                    "feature_id": parent_key,
                    "feature_name": "",
                    "jira_keys": [],
                    "released_dates": [],
                    "created_dates": [],
                    "story_points": 0.0,
                    "fix_versions": set(),
                    "team": team,
                    "issue_types": [],
                    "is_user_facing": "",
                    "llm_reasoning": "auto-synced",
                    "description": "",
                    "category": "",
                }
            epic = epics[parent_key]
            epic["jira_keys"].append(key)
            if resolution_date:
                epic["released_dates"].append(resolution_date[:10])
            if created_date:
                epic["created_dates"].append(created_date[:10])
            if sp is not None:
                try:
                    epic["story_points"] += float(sp)
                except (ValueError, TypeError):
                    pass
            epic["fix_versions"].update(fix_versions)
            epic["issue_types"].append(itype)
        else:
            orphans.append({
                "feature_id": key,
                "feature_name": summary,
                "jira_keys": [key],
                "released_dates": [resolution_date[:10]] if resolution_date else [],
                "created_dates": [created_date[:10]] if created_date else [],
                "story_points": float(sp) if sp is not None else 0.0,
                "fix_versions": set(fix_versions),
                "team": team,
                "issue_types": [itype],
                "is_user_facing": "",
                "llm_reasoning": "auto-synced",
                "description": "",
                "category": _category(itype),
            })

    # Resolve epic summaries (batch-fetch)
    for epic_key, epic in epics.items():
        epic["feature_name"] = fetch_epic_summary(base_url, auth, epic_key, ca_bundle)
        all_bug = all(t in ("bug", "defect") for t in epic["issue_types"])
        epic["category"] = "bug_fix" if all_bug else "feature"

    results = []
    for feature in list(epics.values()) + orphans:
        released_date = max(feature["released_dates"]) if feature["released_dates"] else ""
        first_created = min(feature["created_dates"]) if feature["created_dates"] else ""
        results.append({
            "feature_id": feature["feature_id"],
            "feature_name": feature["feature_name"],
            "jira_keys": feature["jira_keys"],
            "released_date": released_date,
            "first_created": first_created,
            "story_points": feature["story_points"] or None,
            "fix_versions": sorted(feature["fix_versions"]),
            "team": feature["team"],
            "category": feature["category"],
            "is_user_facing": feature["is_user_facing"],
            "llm_reasoning": feature["llm_reasoning"],
            "description": feature["description"],
        })

    return results


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Headless Jira feature sync")
    ap.add_argument("--days", type=int, default=None, help="Lookback window in days")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    load_dotenv(ENV_FILE)

    jira_url = os.environ.get("JIRA_URL", "https://boomii.atlassian.net")
    email = os.environ.get("JIRA_EMAIL", "")
    token = os.environ.get("JIRA_API_KEY", "")
    ca_bundle = os.environ.get("REQUESTS_CA_BUNDLE") or os.environ.get("SSL_CERT_FILE")

    if not email or not token:
        print("ERROR: JIRA_EMAIL and JIRA_API_KEY must be set in .env", file=sys.stderr)
        sys.exit(1)

    auth = _auth_header(email, token)

    with open(TEAMS_FILE) as f:
        config = yaml.safe_load(f)

    teams: dict = config.get("teams", {})
    settings: dict = config.get("settings", {})
    days = args.days or settings.get("default_lookback_days", 90)
    done_statuses = settings.get("jira_done_statuses", ["Done", "Closed", "Released"])
    sp_field = settings.get("story_points_field", "customfield_11703")
    excluded = settings.get("excluded_assignees", [])

    fields = [
        "summary", "description", "issuetype", "status",
        "resolutiondate", "created", "parent", "labels",
        "components", "fixVersions", sp_field, "assignee",
    ]

    excluded_jql = ""
    if excluded:
        quoted = ", ".join(f'"{a}"' for a in excluded)
        excluded_jql = f" AND assignee NOT IN ({quoted})"

    status_jql = ", ".join(f'"{s}"' for s in done_statuses)

    all_features: list[dict] = []
    total_tickets = 0

    for team_name, team_cfg in teams.items():
        projects = team_cfg.get("jira_projects", [])
        if not projects:
            print(f"  Skipping {team_name} — no jira_projects configured", file=sys.stderr)
            continue

        proj_list = ", ".join(projects)
        jql = (
            f"project IN ({proj_list})"
            f" AND status IN ({status_jql})"
            f" AND resolved >= \"-{days}d\""
            f"{excluded_jql}"
            f" ORDER BY resolved DESC"
        )

        print(f"  Fetching {team_name} ({proj_list})...", file=sys.stderr)
        try:
            issues = fetch_issues(jira_url, auth, jql, fields, ca_bundle)
        except Exception as exc:
            print(f"  ERROR fetching {team_name}: {exc}", file=sys.stderr)
            continue

        print(f"    {len(issues)} tickets", file=sys.stderr)
        total_tickets += len(issues)

        features = group_into_features(issues, team_name, jira_url, auth, ca_bundle)
        all_features.extend(features)

    print(f"  Total: {total_tickets} tickets → {len(all_features)} features", file=sys.stderr)

    if not all_features:
        print("No features found.", file=sys.stderr)
        sys.exit(0)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
        json.dump(all_features, tmp, indent=2)
        tmp_path = tmp.name

    csv_script = REPO_ROOT / "scripts" / "jira_features_to_csv.py"
    cmd = [sys.executable, str(csv_script), "--input", tmp_path]
    if args.dry_run:
        cmd.append("--dry-run")

    result = subprocess.run(cmd, capture_output=True, text=True)
    Path(tmp_path).unlink(missing_ok=True)

    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
