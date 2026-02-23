"""Team mapping configuration for developer-to-team assignment."""

import re
from pathlib import Path
from typing import Dict, Optional

import yaml


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
    # Match [TeamName] and capture team name; everything until next [ or EOL is developers
    pattern = re.compile(r"\[([^\]]+)\]\s*([^[]*)")
    for match in pattern.finditer(content):
        team = match.group(1).strip()
        developers = match.group(2).split()
        for dev in developers:
            dev = dev.strip()
            if dev and not dev.startswith("#"):
                result[dev] = team
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
    Load developer-to-team mapping from teams.yaml, teams.cfg, or teams.txt.

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
    for name in ("teams.yaml", "teams.yml", "teams.cfg", "teams.txt"):
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
