"""Bitbucket identity mapping - converts display names to usernames."""

from pathlib import Path
from typing import Dict, Optional

import yaml

# Cache the mapping
_DISPLAY_NAME_TO_USERNAME: Optional[Dict[str, str]] = None


def load_bitbucket_identity_mapping() -> Dict[str, str]:
    """
    Load display name to username mapping for Bitbucket.

    Uses identity_mapping.yaml from team_lead if available, otherwise
    returns empty dict.

    Returns:
        Dict mapping Bitbucket display names to usernames
    """
    global _DISPLAY_NAME_TO_USERNAME

    if _DISPLAY_NAME_TO_USERNAME is not None:
        return _DISPLAY_NAME_TO_USERNAME

    mapping: Dict[str, str] = {}

    # Try to load from team_lead identity mapping
    team_lead_path = Path.home() / "Documents/Dev/team_lead/config/identity_mapping.yaml"
    if team_lead_path.exists():
        try:
            with open(team_lead_path, "r") as f:
                data = yaml.safe_load(f)

            # Build reverse mapping from display_name -> bitbucket username
            identities = data.get("identities", {})
            for person_id, person_data in identities.items():
                display_name = person_data.get("display_name", "")
                bb_username = person_data.get("platforms", {}).get("bitbucket", "")
                if display_name and bb_username:
                    mapping[display_name] = bb_username
        except Exception:
            pass  # Fail silently, return empty mapping

    _DISPLAY_NAME_TO_USERNAME = mapping
    return mapping


def resolve_bitbucket_username(author_data: Dict) -> str:
    """
    Resolve Bitbucket username from author data.

    Tries in order:
    1. username field (if present)
    2. nickname field (if present)
    3. display_name mapped through identity_mapping.yaml
    4. display_name as fallback

    Args:
        author_data: Bitbucket author dict from API response

    Returns:
        Best available username/identifier
    """
    if not author_data:
        return ""

    # Try username first (though Bitbucket v2 API often doesn't include this)
    username = author_data.get("username", "")
    if username:
        return username

    # Try nickname
    nickname = author_data.get("nickname", "")
    if nickname:
        # Check if nickname looks like a username (no spaces)
        if nickname and " " not in nickname:
            return nickname

    # Try mapping display_name to username via identity mapping
    display_name = author_data.get("display_name", "")
    if display_name:
        mapping = load_bitbucket_identity_mapping()
        mapped_username = mapping.get(display_name)
        if mapped_username:
            return mapped_username

        # Fallback to display_name if no mapping found
        return display_name

    return ""
