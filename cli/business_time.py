"""Business-hours math for PR cycle time.

Excludes Israeli weekends (Fri+Sat) and Israeli national holidays.
Timestamps are treated as naive Asia/Jerusalem local time, matching the
tz-stripping that already happens in reports/chart_data.py.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import lru_cache

import holidays
import pandas as pd

WEEKEND_DAYS = {4, 5}  # Fri=4, Sat=5 (Mon=0)


@lru_cache(maxsize=1)
def _il_holidays() -> holidays.HolidayBase:
    # Years: cover the range that appears in the CSV plus a margin.
    return holidays.country_holidays("IL", years=range(2018, 2031))


def _is_off_day(d: date) -> bool:
    return d.weekday() in WEEKEND_DAYS or d in _il_holidays()


def business_hours_between(start: datetime, end: datetime) -> float:
    """Hours between start and end excluding Fri+Sat and Israeli holidays.

    Partial first/last days are counted by the in-day fraction. Returns 0 if
    end <= start.
    """
    if pd.isna(start) or pd.isna(end):
        return float("nan")
    if end <= start:
        return 0.0

    total = 0.0
    cur_day = start.date()
    end_day = end.date()

    while cur_day <= end_day:
        if not _is_off_day(cur_day):
            day_start = datetime.combine(cur_day, datetime.min.time())
            day_end = day_start + timedelta(days=1)
            seg_start = max(start, day_start)
            seg_end = min(end, day_end)
            if seg_end > seg_start:
                total += (seg_end - seg_start).total_seconds() / 3600.0
        cur_day += timedelta(days=1)

    return total


def business_hours_vector(starts: pd.Series, ends: pd.Series) -> pd.Series:
    """Vectorized-ish version. Returns a Series of float hours, same index as starts."""
    starts = pd.to_datetime(starts, errors="coerce")
    ends = pd.to_datetime(ends, errors="coerce")

    def _one(pair):
        s, e = pair
        if pd.isna(s) or pd.isna(e):
            return float("nan")
        return business_hours_between(s.to_pydatetime(), e.to_pydatetime())

    return pd.Series([_one((s, e)) for s, e in zip(starts, ends)], index=starts.index)
