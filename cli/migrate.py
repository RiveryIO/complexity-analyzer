"""CSV schema migration: enrich existing rows with missing columns."""

import csv
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .constants import DEFAULT_SLEEP_SECONDS, DEFAULT_TIMEOUT
from .csv_handler import CSV_FIELDNAMES
from .github import GitHubAPIError, fetch_pr_metadata, wait_for_rate_limit
from .io_safety import normalize_path
from .team_config import get_team_for_developer
from .utils import parse_pr_url

logger = logging.getLogger("complexity-cli")


def _load_csv_rows(path: Path) -> List[Dict[str, str]]:
    """Load all rows from CSV, normalizing column names."""
    rows: List[Dict[str, str]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        for row in reader:
            normalized: Dict[str, str] = {}
            pr_url = (
                row.get("pr_url")
                or row.get("PR link")
                or row.get("pr link")
                or (list(row.values())[0] if row else "")
            )
            normalized["pr_url"] = str(pr_url or "").strip()
            normalized["complexity"] = str(row.get("complexity") or "").strip()
            normalized["developer"] = str(
                row.get("developer") or row.get("author") or ""
            ).strip()
            normalized["date"] = str(row.get("date") or "").strip()
            normalized["team"] = str(row.get("team") or "").strip()
            normalized["merged_at"] = str(row.get("merged_at") or "").strip()
            normalized["created_at"] = str(row.get("created_at") or "").strip()
            normalized["lines_added"] = str(row.get("lines_added") or "").strip()
            normalized["lines_deleted"] = str(row.get("lines_deleted") or "").strip()
            normalized["explanation"] = str(row.get("explanation") or "").strip()
            rows.append(normalized)
    return rows


def _needs_enrichment(row: Dict[str, str]) -> bool:
    """True if row needs merged_at, created_at, lines_added, or lines_deleted."""
    return (
        not row.get("merged_at")
        or not row.get("created_at")
        or not row.get("lines_added")
        or not row.get("lines_deleted")
    )


def run_migration(
    input_path: Path,
    output_path: Path,
    token: Optional[str] = None,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """
    Enrich CSV rows with missing columns (merged_at, created_at, lines_added, lines_deleted, team).

    Fetches metadata from GitHub for rows that need it. Uses team config for team column.

    Args:
        input_path: Input CSV path
        output_path: Output CSV path (can be same as input)
        token: GitHub token
        sleep_seconds: Sleep between API calls
        progress_callback: Optional callback for progress messages

    Returns:
        Number of rows enriched
    """
    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)
        else:
            logger.info(msg)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    rows = _load_csv_rows(input_path)
    if not rows:
        log("No rows to migrate")
        return 0

    enriched = 0
    for i, row in enumerate(rows):
        pr_url = row.get("pr_url", "").strip()
        if not pr_url:
            continue

        needs = _needs_enrichment(row)
        if not needs:
            continue

        try:
            owner, repo, pr = parse_pr_url(pr_url)
        except ValueError:
            log(f"Skipping invalid PR URL: {pr_url}")
            continue

        # Fetch metadata from GitHub
        try:
            wait_for_rate_limit(
                token=token,
                api_type="core",
                min_remaining=1,
                progress_callback=progress_callback,
                timeout=DEFAULT_TIMEOUT,
            )
            meta = fetch_pr_metadata(
                owner, repo, int(pr),
                token=token,
                timeout=DEFAULT_TIMEOUT,
                check_rate_limit_first=False,
                progress_callback=progress_callback,
            )
        except GitHubAPIError as e:
            log(f"Warning: Could not fetch {pr_url}: {e}")
            continue
        except Exception as e:
            log(f"Warning: Could not fetch {pr_url}: {e}")
            continue

        # Enrich row
        merged_at = meta.get("merged_at") or ""
        created_at = meta.get("created_at") or ""
        additions = meta.get("additions")
        deletions = meta.get("deletions")

        row["merged_at"] = merged_at
        row["created_at"] = created_at
        row["date"] = merged_at[:10] if merged_at else row.get("date", "")
        row["lines_added"] = str(additions) if additions is not None else ""
        row["lines_deleted"] = str(deletions) if deletions is not None else ""

        # Team from config (developer-based mapping)
        developer = row.get("developer") or row.get("author") or ""
        if not row.get("team") and developer:
            row["team"] = get_team_for_developer(developer)

        enriched += 1
        if (i + 1) % 10 == 0:
            log(f"  Enriched {i + 1}/{len(rows)} rows...")

        time.sleep(sleep_seconds)

    # Write output
    out = output_path if output_path.is_absolute() else normalize_path(Path.cwd(), str(output_path))
    out.parent.mkdir(parents=True, exist_ok=True)

    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for row in rows:
            # Ensure all columns present
            out_row: Dict[str, Any] = {k: row.get(k, "") for k in CSV_FIELDNAMES}
            writer.writerow(out_row)

    return enriched


def run_migration_background(
    input_path: Path,
    output_path: Path,
    token: Optional[str] = None,
    log_path: Optional[Path] = None,
) -> int:
    """
    Run migration in background process. Returns PID of child process.

    Logs to log_path (default: reports/migration.log).
    """
    log_file = log_path or (Path.cwd() / "reports" / "migration.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    if token:
        env["GH_TOKEN"] = token

    cmd = [
        sys.executable, "-m", "cli.main", "migrate-csv",
        "--input", str(input_path),
        "--output", str(output_path),
    ]

    with log_file.open("a", encoding="utf-8") as log_handle:
        proc = subprocess.Popen(
            cmd,
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            env=env,
            cwd=Path.cwd(),
            start_new_session=True,
        )
    return proc.pid
