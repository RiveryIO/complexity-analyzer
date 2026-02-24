"""Playwright test to verify dashboard charts render correctly."""

import subprocess
import sys
from pathlib import Path

import pytest

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
INDEX_HTML = REPORTS_DIR / "index.html"
VERIFY_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_dashboard.py"


def test_dashboard_charts_render():
    """Verify Team tab charts render with correct dimensions (Playwright)."""
    if not INDEX_HTML.exists():
        pytest.skip("Run generate-reports first: complexity-cli generate-reports -i complexity-report.csv -o reports")

    pytest.importorskip("playwright")

    result = subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT)],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(REPORTS_DIR.parent),
    )

    if result.returncode != 0:
        pytest.fail(f"Dashboard verification failed:\n{result.stdout}\n{result.stderr}")

    assert "PASS:" in result.stdout, f"Expected PASS in output: {result.stdout}"
