"""Test that March 2026 PRs appear correctly in Developer Velocity charts."""

import sys
from pathlib import Path
from io import StringIO
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from reports.chart_data import _extract_team


def test_orhss_march_2026_in_developer_velocity():
    """Test that orhss's March 2026 PRs show up in Developer Velocity chart."""

    # Create minimal CSV data with orhss PRs in Feb and March 2026
    csv_data = """pr_url,complexity,developer,date,team,merged_at,created_at,lines_added,lines_deleted,explanation,source,approved_by,pr_title
https://github.com/test/pr1,5,orhss,2026-02-20,Core,2026-02-20T10:00:00,2026-02-19T10:00:00,50,10,Test PR,github,,Test PR 1
https://github.com/test/pr2,7,orhss,2026-03-05,Core,2026-03-05T10:00:00,2026-03-04T10:00:00,100,20,Test PR,github,,Test PR 2
https://github.com/test/pr3,4,orhss,2026-03-15,Core,2026-03-15T10:00:00,2026-03-14T10:00:00,80,15,Test PR,github,,Test PR 3
https://github.com/test/pr4,3,nvgoldin,2026-03-10,Core,2026-03-10T10:00:00,2026-03-09T10:00:00,60,12,Test PR,github,,Test PR 4
"""

    # Load into DataFrame
    df = pd.read_csv(StringIO(csv_data))

    # Generate team charts
    charts = _extract_team(df)

    # Find the Developer Velocity chart for Core team
    dev_velocity_chart = None
    for chart in charts:
        if chart["id"] == "30-Core" and "Developer Velocity" in chart["title"]:
            dev_velocity_chart = chart
            break

    assert dev_velocity_chart is not None, "Developer Velocity — Core chart not found"

    # Find orhss's series
    orhss_series = None
    for series in dev_velocity_chart["series"]:
        if series["name"] == "orhss":
            orhss_series = series
            break

    assert orhss_series is not None, "orhss series not found in chart"

    # Check the x-axis dates and orhss's data
    x_dates = dev_velocity_chart["x"]
    orhss_data = orhss_series["data"]
    orhss_pr_counts = orhss_series["prCounts"]

    print("\n" + "="*80)
    print("orhss Developer Velocity data:")
    print("="*80)

    march_data_found = False
    feb_data_found = False

    for i, date in enumerate(x_dates):
        if orhss_data[i] > 0:
            print(f"  Week {date}: {orhss_data[i]} complexity ({orhss_pr_counts[i]} PRs)")

            if date.startswith("2026-02"):
                feb_data_found = True
            elif date.startswith("2026-03"):
                march_data_found = True

    print()
    print(f"February data found: {feb_data_found}")
    print(f"March data found: {march_data_found}")
    print("="*80)

    # Assertions
    assert feb_data_found, "orhss should have PRs in February 2026"
    assert march_data_found, "orhss should have PRs in March 2026 but chart shows zeros"

    # Verify the specific March weeks
    march_weeks = [date for date in x_dates if date.startswith("2026-03")]
    assert len(march_weeks) > 0, "No March 2026 weeks in x-axis"

    march_complexity = sum(
        orhss_data[i]
        for i, date in enumerate(x_dates)
        if date.startswith("2026-03")
    )

    assert march_complexity > 0, f"orhss March 2026 total complexity should be > 0, got {march_complexity}"
    print(f"\n✓ orhss March 2026 total complexity: {march_complexity}")


if __name__ == "__main__":
    test_orhss_march_2026_in_developer_velocity()
    print("\n✅ Test passed!")
