#!/usr/bin/env python3
"""Upsert classified Jira features into features-released.csv.

Usage::

    python scripts/jira_features_to_csv.py -i features.json
    cat features.json | python scripts/jira_features_to_csv.py -i -
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime
from math import isnan
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CSV = REPO_ROOT / "features-released.csv"

FIELDNAMES = [
    "feature_id",
    "feature_name",
    "jira_keys",
    "ticket_count",
    "category",
    "is_user_facing",
    "llm_reasoning",
    "team",
    "released_date",
    "first_created",
    "lead_time_days",
    "quarter",
    "iso_week",
    "story_points",
    "description",
    "fix_versions",
]


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(value[:26], fmt[:len(fmt)]).date()
        except (ValueError, TypeError):
            continue
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, TypeError):
        return None


def _quarter(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


def _iso_week(d: date) -> str:
    cal = d.isocalendar()
    return f"{cal[0]}-W{cal[1]:02d}"


def _safe_float(v: Any) -> str:
    if v is None:
        return ""
    try:
        f = float(v)
        return "" if isnan(f) else str(f)
    except (ValueError, TypeError):
        return ""


def normalize_row(raw: dict[str, Any]) -> dict[str, str]:
    """Convert a raw JSON object into a flat CSV row with derived columns."""
    jira_keys = raw.get("jira_keys", [])
    if isinstance(jira_keys, list):
        jira_keys_str = "|".join(jira_keys)
        ticket_count = len(jira_keys)
    else:
        jira_keys_str = str(jira_keys)
        ticket_count = len(str(jira_keys).split("|")) if jira_keys else 0

    released = _parse_date(raw.get("released_date"))
    created = _parse_date(raw.get("first_created"))
    lead_time = ""
    if released and created:
        lead_time = str((released - created).days)

    fix_versions = raw.get("fix_versions", [])
    if isinstance(fix_versions, list):
        fix_versions = "|".join(str(v) for v in fix_versions)

    is_uf = raw.get("is_user_facing")
    if isinstance(is_uf, bool):
        is_uf_str = str(is_uf).lower()
    else:
        is_uf_str = str(is_uf).lower() if is_uf is not None else ""

    return {
        "feature_id": str(raw.get("feature_id", "")),
        "feature_name": str(raw.get("feature_name", "")),
        "jira_keys": jira_keys_str,
        "ticket_count": str(ticket_count),
        "category": str(raw.get("category", "")),
        "is_user_facing": is_uf_str,
        "llm_reasoning": str(raw.get("llm_reasoning", "")),
        "team": str(raw.get("team", "")),
        "released_date": released.isoformat() if released else "",
        "first_created": created.isoformat() if created else "",
        "lead_time_days": lead_time,
        "quarter": _quarter(released) if released else "",
        "iso_week": _iso_week(released) if released else "",
        "story_points": _safe_float(raw.get("story_points")),
        "description": str(raw.get("description", "")),
        "fix_versions": str(fix_versions),
    }


def load_existing(csv_path: Path) -> dict[str, dict[str, str]]:
    """Load existing CSV into a dict keyed by feature_id."""
    rows: dict[str, dict[str, str]] = {}
    if not csv_path.exists():
        return rows
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            fid = row.get("feature_id", "").strip()
            if fid:
                rows[fid] = row
    return rows


def upsert(
    existing: dict[str, dict[str, str]],
    new_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Merge new rows into existing, updating by feature_id."""
    for row in new_rows:
        fid = row.get("feature_id", "").strip()
        if not fid:
            continue
        existing[fid] = row
    merged = list(existing.values())
    merged.sort(key=lambda r: r.get("released_date", ""), reverse=True)
    return merged


def write_csv(
    rows: list[dict[str, str]], csv_path: Path,
) -> None:
    """Write rows to CSV, overwriting the file."""
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=FIELDNAMES, extrasaction="ignore",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> None:
    """CLI entry point."""
    ap = argparse.ArgumentParser(
        description="Upsert Jira features into CSV",
    )
    ap.add_argument(
        "--input", "-i", default="-",
        help="JSON file path, or '-' for stdin",
    )
    ap.add_argument(
        "--output", "-o", default=str(DEFAULT_CSV),
        help="Output CSV path",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Preview without writing",
    )
    args = ap.parse_args()

    if args.input == "-":
        raw_json = sys.stdin.read()
    else:
        raw_json = Path(args.input).read_text(encoding="utf-8")

    try:
        data = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, list):
        data = [data]

    new_rows = [normalize_row(item) for item in data]

    csv_path = Path(args.output)
    existing = load_existing(csv_path)
    seen = set(existing.keys())

    before_count = len(existing)
    merged = upsert(existing, new_rows)
    after_count = len(merged)
    new_count = after_count - before_count
    updated_count = len(new_rows) - new_count

    if args.dry_run:
        msg = (
            f"DRY RUN: {after_count} rows "
            f"({new_count} new, {updated_count} updated)"
        )
        print(msg)
        for row in new_rows:
            tag = "NEW" if row["feature_id"] not in seen else "UPD"
            fid = row["feature_id"]
            name = row["feature_name"]
            team = row["team"]
            rd = row["released_date"]
            print(f"  [{tag}] {fid}: {name} ({team}, {rd})")
        return

    write_csv(merged, csv_path)
    print(
        f"Wrote {after_count} rows to {csv_path} "
        f"({new_count} new, {updated_count} updated)"
    )


if __name__ == "__main__":
    main()
