"""Settings verification for complexity-cli."""

from pathlib import Path
from typing import List, Optional, Tuple

from .config import get_anthropic_api_key, get_github_token, get_openai_api_key
from .csv_handler import CSV_FIELDNAMES
from .github import check_rate_limit
from .team_config import load_team_mapping


def _check(
    name: str,
    ok: bool,
    hint: str = "",
) -> Tuple[str, bool, str]:
    """Return (name, ok, hint)."""
    return (name, ok, hint)


def run_verify_settings(
    csv_path: Optional[Path] = None,
    csv_required: bool = False,
) -> List[Tuple[str, bool, str]]:
    """
    Verify all settings required to pull data and generate reports.

    Args:
        csv_path: Path to complexity CSV (default: complexity-report.csv in cwd)
        csv_required: If True, fail when CSV is missing

    Returns:
        List of (check_name, passed, hint) tuples
    """
    results: List[Tuple[str, bool, str]] = []
    cwd = Path.cwd()
    csv_file = csv_path or (cwd / "complexity-report.csv")

    # Check GitHub token
    gh_token = get_github_token()
    if gh_token:
        results.append(_check("GH_TOKEN / GITHUB_TOKEN", True))
    else:
        results.append(
            _check("GH_TOKEN / GITHUB_TOKEN", False, "Set GH_TOKEN or run `gh auth login`")
        )

    # Check OpenAI API key
    openai_key = get_openai_api_key()
    if openai_key:
        results.append(_check("OPENAI_API_KEY", True))
    else:
        results.append(
            _check("OPENAI_API_KEY", False, "Set OPENAI_API_KEY for --provider openai")
        )

    # Check Anthropic API key
    anthropic_key = get_anthropic_api_key()
    if anthropic_key:
        results.append(_check("ANTHROPIC_API_KEY", True))
    else:
        results.append(
            _check("ANTHROPIC_API_KEY", False, "Set ANTHROPIC_API_KEY for --provider anthropic")
        )

    # Check GitHub rate limit (only if token present)
    if gh_token:
        try:
            info = check_rate_limit(token=gh_token)
            core = info.get("core", {})
            remaining = core.get("remaining", 0)
            reset = core.get("reset", 0)
            if remaining > 0:
                results.append(_check("GitHub rate limit", True, f"{remaining} remaining"))
            else:
                results.append(
                    _check(
                        "GitHub rate limit",
                        False,
                        f"Exhausted; resets at {reset}" if reset else "Exhausted",
                    )
                )
        except Exception as e:
            results.append(_check("GitHub rate limit", False, str(e)))
    else:
        results.append(_check("GitHub rate limit", False, "Set GH_TOKEN first"))

    # Check CSV path
    if csv_file.exists():
        results.append(_check("CSV path", True, str(csv_file)))
    else:
        ok = not csv_required
        results.append(
            _check("CSV path", ok, f"Not found: {csv_file}" if csv_required else f"Optional: {csv_file}")
        )

    # Check team config
    mapping = load_team_mapping(cwd)
    if mapping:
        results.append(_check("Team config (teams.yaml)", True, f"{len(mapping)} mappings"))
    else:
        results.append(
            _check("Team config (teams.yaml)", True, "Optional: copy teams.yaml.example to teams.yaml")
        )

    # Check required columns in CSV (if exists)
    if csv_file.exists():
        try:
            with csv_file.open("r", encoding="utf-8") as f:
                import csv as csv_module

                reader = csv_module.DictReader(f)
                fieldnames = reader.fieldnames or []
            missing = [c for c in CSV_FIELDNAMES if c not in fieldnames]
            if not missing:
                results.append(_check("CSV columns", True, "All required columns present"))
            else:
                results.append(
                    _check(
                        "CSV columns",
                        False,
                        f"Missing: {', '.join(missing)}. Run migrate-csv to enrich.",
                    )
                )
        except Exception as e:
            results.append(_check("CSV columns", False, str(e)))
    else:
        results.append(_check("CSV columns", True, "N/A (no CSV)"))

    return results
