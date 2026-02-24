#!/usr/bin/env python3
"""Standalone script to verify dashboard charts render (Playwright). Run after generate-reports."""

import sys
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent.parent / "reports"
INDEX_HTML = REPORTS_DIR / "index.html"


def main():
    if not INDEX_HTML.exists():
        print("ERROR: Run generate-reports first: complexity-cli generate-reports -i complexity-report.csv -o reports")
        sys.exit(1)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERROR: Install playwright: pip install playwright && playwright install chromium")
        sys.exit(1)

    errors = []

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()

        def on_console(msg):
            if msg.type == "error":
                errors.append(msg.text)

        page.on("console", on_console)
        try:
            url = INDEX_HTML.as_uri()
            page.goto(url, wait_until="networkidle", timeout=15000)
            page.wait_for_timeout(2000)

            # Click Team tab
            team_tab = page.get_by_role("button", name="Team")
            team_tab.click()
            page.wait_for_timeout(1200)

            # Take screenshot for visual inspection
            screenshot_path = REPORTS_DIR / "dashboard-team-tab.png"
            page.locator("#panel-team").screenshot(path=str(screenshot_path))
            print(f"Screenshot saved: {screenshot_path}")

            # Check chart canvases
            team_panel = page.locator("#panel-team")
            chart_containers = team_panel.locator(".chart-container")
            count = chart_containers.count()

            if count == 0:
                print("FAIL: No chart containers in Team tab")
                sys.exit(1)

            all_ok = True
            for i in range(count):
                container = chart_containers.nth(i)
                canvas = container.locator("canvas")
                try:
                    canvas.wait_for(state="visible", timeout=2000)
                except Exception as e:
                    print(f"FAIL: Chart {i} canvas not visible: {e}")
                    all_ok = False
                    continue

                box = canvas.bounding_box()
                if not box:
                    print(f"FAIL: Chart {i} has no bounding box")
                    all_ok = False
                elif box["width"] < 80 or box["height"] < 80:
                    print(f"FAIL: Chart {i} too small: {box['width']}x{box['height']}")
                    all_ok = False
                else:
                    print(f"OK: Chart {i} {box['width']:.0f}x{box['height']:.0f}")

            # Sample multiple points to verify chart has drawn content
            first_canvas = team_panel.locator("canvas").first
            has_content = page.evaluate(
                """(canvas) => {
                const ctx = canvas.getContext('2d');
                const w = canvas.width, h = canvas.height;
                if (w < 10 || h < 10) return false;
                const points = [[w/2, h/2], [w/4, h/4], [3*w/4, h/4]];
                for (const [x, y] of points) {
                    const imgData = ctx.getImageData(Math.floor(x), Math.floor(y), 1, 1);
                    if (imgData.data[3] > 0) return true;
                }
                return false;
            }""",
                first_canvas.element_handle(),
            )
            if not has_content:
                print("WARN: Chart canvas may be empty (no non-transparent pixels sampled)")

            js_errors = [e for e in errors if "favicon" not in e.lower()]
            if js_errors:
                print("WARN: Console errors:", js_errors)

            if all_ok:
                print("PASS: All Team tab charts render correctly")
            else:
                sys.exit(1)

        finally:
            browser.close()


if __name__ == "__main__":
    main()
