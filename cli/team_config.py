"""Team mapping configuration for developer-to-team assignment."""

import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


def _parse_team_assignments_text(content: str) -> Dict[str, str]:
    """
    Parse format: [TeamName] followed by developers on same line or subsequent lines.

    Example:
        [Platform]
        alice
        bob charlie
        [Backend]
        dave eve
    """
    result: Dict[str, str] = {}
    current_team: Optional[str] = None
    team_header = re.compile(r"^\[([^\]]+)\]\s*(.*)$")
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = team_header.match(line)
        if m:
            current_team = m.group(1).strip()
            rest = m.group(2).strip()
            if rest and current_team:
                for dev in rest.split():
                    dev = dev.strip()
                    if dev:
                        result[dev] = current_team
            continue
        if current_team:
            for dev in line.split():
                dev = dev.strip()
                if dev:
                    result[dev] = current_team
    return result


def _load_teams_yaml(path: Path) -> Optional[Dict[str, str]]:
    """
    Load developer-to-team mapping from YAML file.

    Supports two formats:
    1. Raw text format: [TeamName] dev1 dev2 ...
    2. YAML structure: TeamName: [dev1, dev2, ...]
    """
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = f.read()

        # Try parsing as text format first ([team] dev1 dev2)
        if "[team" in raw.lower() or re.search(r"\[\w+\]\s+\w+", raw):
            return _parse_team_assignments_text(raw)

        # Try YAML: teamName: [dev1, dev2, ...]
        data = yaml.safe_load(raw)
        if not isinstance(data, dict):
            return None
        result: Dict[str, str] = {}
        for team, devs in data.items():
            if isinstance(devs, list):
                for d in devs:
                    if isinstance(d, str) and d.strip():
                        result[d.strip()] = str(team)
            elif isinstance(devs, str):
                for d in devs.split():
                    if d.strip():
                        result[d.strip()] = str(team)
        return result if result else None
    except Exception:
        pass
    return None


def _load_teams_txt(path: Path) -> Optional[Dict[str, str]]:
    """Load from .txt file with [team] dev1 dev2 format."""
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        result = _parse_team_assignments_text(content)
        return result if result else None
    except Exception:
        pass
    return None


def load_team_mapping(cwd: Optional[Path] = None) -> Dict[str, str]:
    """
    Load developer-to-team mapping from a config file.

    Searches (in order): github-teams.cfg, github-teams.yaml,
    teams.yaml, teams.yml, teams.cfg, teams.txt.

    Format: [TeamName] followed by developers (same line or subsequent lines until next [Team]):
        [Platform]
        alice
        bob
        charlie
        [Backend]
        dave eve
    Or YAML: TeamName: [dev1, dev2, ...]

    Returns:
        Dict mapping "developer" -> "Team Name"
    """
    base = cwd or Path.cwd()
    candidates = (
        "github-teams.cfg",
        "github-teams.yaml",
        "teams.yaml",
        "teams.yml",
        "teams.cfg",
        "teams.txt",
    )
    for name in candidates:
        path = base / name
        if path.suffix in (".yaml", ".yml"):
            result = _load_teams_yaml(path)
        elif path.suffix in (".txt", ".cfg"):
            result = _load_teams_txt(path)
        else:
            continue
        if result:
            return result
    return {}


def get_team_for_developer(developer: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Get team name for a developer (GitHub username).

    Args:
        developer: GitHub username
        mapping: Optional pre-loaded mapping. If None, loads from teams.yaml/txt.

    Returns:
        Team name or empty string if no mapping
    """
    if not developer or not developer.strip():
        return ""
    if mapping is None:
        mapping = load_team_mapping()
    return mapping.get(developer.strip(), "")


def get_team_for_repo(owner: str, repo: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Deprecated: Use get_team_for_developer(author) instead.
    Kept for backward compatibility; returns empty string.
    """
    return ""


# ---------------------------------------------------------------------------
# Developer tenure (start/end dates) for headcount calculations
# ---------------------------------------------------------------------------

_TENURE_FILENAME = "developer-tenure.yaml"


def _parse_date_field(val: object) -> Optional[date]:
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _parse_leaves(raw_leaves: object) -> List[Dict[str, date]]:
    """Parse a list of ``{from: ..., to: ...}`` leave ranges."""
    if not isinstance(raw_leaves, list):
        return []
    result: List[Dict[str, date]] = []
    for entry in raw_leaves:
        if not isinstance(entry, dict):
            continue
        leave_from = _parse_date_field(entry.get("from"))
        leave_to = _parse_date_field(entry.get("to"))
        if leave_from and leave_to:
            result.append({"from": leave_from, "to": leave_to})
    return result


def load_developer_tenure(
    cwd: Optional[Path] = None,
) -> Dict[str, dict]:
    """Load developer start/end dates and leave ranges from developer-tenure.yaml.

    Returns dict keyed by GitHub username::

        {"alice": {"start": date(2024,1,1), "end": None, "leaves": [...]}, ...}

    Each leave entry is ``{"from": date, "to": date}``.
    """
    base = cwd or Path.cwd()
    path = base / _TENURE_FILENAME
    if not path.exists():
        logger.warning(
            "%s not found – headcount will fall back to CSV-derived counts", _TENURE_FILENAME
        )
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning("Failed to parse %s: %s", _TENURE_FILENAME, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    devs_raw = data.get("developers", data)
    if not isinstance(devs_raw, dict):
        return {}

    result: Dict[str, dict] = {}
    for username, info in devs_raw.items():
        if not isinstance(info, dict):
            continue
        start_date = _parse_date_field(info.get("start"))
        if start_date is None:
            continue
        result[str(username).strip()] = {
            "start": start_date,
            "end": _parse_date_field(info.get("end")),
            "leaves": _parse_leaves(info.get("leaves")),
        }
    return result


def _is_on_leave(week_start: date, week_end: date, leaves: List[Dict[str, date]]) -> bool:
    """True if any leave range fully covers the week (from <= week_start and to >= week_end)."""
    for lv in leaves:
        if lv["from"] <= week_start and lv["to"] >= week_end:
            return True
    return False


def get_active_headcount(
    week_start: date,
    team: Optional[str] = None,
    tenure: Optional[Dict[str, dict]] = None,
    team_mapping: Optional[Dict[str, str]] = None,
) -> int:
    """Return the number of developers active during the week starting at *week_start*.

    A developer is active if ``start <= week_end`` and (``end`` is None or
    ``end >= week_start``) and they are not on leave for the entire week.

    Args:
        week_start: Monday of the ISO week.
        team: If given, only count developers belonging to this team.
        tenure: Pre-loaded tenure dict (from :func:`load_developer_tenure`).
        team_mapping: Pre-loaded team mapping (from :func:`load_team_mapping`).
    """
    if tenure is None:
        tenure = load_developer_tenure()
    if team_mapping is None:
        team_mapping = load_team_mapping()

    week_end = week_start + timedelta(days=6)
    count = 0
    for dev, info in tenure.items():
        start = info["start"]
        end = info.get("end")
        if start is None or start > week_end:
            continue
        if end is not None and end < week_start:
            continue
        if team is not None and team_mapping.get(dev, "") != team:
            continue
        if _is_on_leave(week_start, week_end, info.get("leaves", [])):
            continue
        count += 1
    return count


def get_weekly_headcounts(
    weeks: List[date],
    teams: Optional[List[str]] = None,
    cwd: Optional[Path] = None,
) -> Dict[str, List[int]]:
    """Compute headcount for each week, for 'All Teams' and each team.

    Returns::

        {"All Teams": [12, 13, ...], "Core": [5, 5, ...], ...}
    """
    tenure = load_developer_tenure(cwd)
    team_mapping = load_team_mapping(cwd)

    if teams is None:
        teams = sorted({t for t in team_mapping.values() if t and t != "Bots"})

    result: Dict[str, List[int]] = {"All Teams": []}
    for t in teams:
        result[t] = []

    for w in weeks:
        result["All Teams"].append(
            get_active_headcount(w, team=None, tenure=tenure, team_mapping=team_mapping)
        )
        for t in teams:
            result[t].append(
                get_active_headcount(w, team=t, tenure=tenure, team_mapping=team_mapping)
            )

    return result
