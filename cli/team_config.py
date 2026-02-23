"""Team mapping configuration for repo-to-team assignment."""

from pathlib import Path
from typing import Dict, Optional

import yaml


def _load_teams_yaml(path: Path) -> Optional[Dict[str, str]]:
    """Load teams from YAML file."""
    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return None


def _load_teams_json(path: Path) -> Optional[Dict[str, str]]:
    """Load teams from JSON file."""
    import json

    if not path.exists():
        return None
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except Exception:
        pass
    return None


def load_team_mapping(cwd: Optional[Path] = None) -> Dict[str, str]:
    """
    Load repo-to-team mapping from teams.yaml or teams.json.

    Looks for teams.yaml or teams.json in project root (cwd or current dir).

    Returns:
        Dict mapping "owner/repo" -> "Team Name"
    """
    base = cwd or Path.cwd()
    for name in ("teams.yaml", "teams.yml", "teams.json"):
        path = base / name
        if path.suffix in (".yaml", ".yml"):
            result = _load_teams_yaml(path)
        elif path.suffix == ".json":
            result = _load_teams_json(path)
        else:
            continue
        if result:
            return result
    return {}


def get_team_for_repo(owner: str, repo: str, mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Get team name for a repository.

    Args:
        owner: Repository owner
        repo: Repository name
        mapping: Optional pre-loaded mapping. If None, loads from teams.yaml/json.

    Returns:
        Team name or empty string if no mapping
    """
    if mapping is None:
        mapping = load_team_mapping()
    key = f"{owner}/{repo}"
    return mapping.get(key, "")
