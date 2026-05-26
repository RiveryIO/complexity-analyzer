from datetime import datetime

import pandas as pd
import pytest

from cli.business_time import business_hours_between, business_hours_vector


def _dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


def test_same_workday_returns_elapsed_hours():
    # Sunday (workday in IL) 09:00 -> 13:30 = 4.5h
    assert business_hours_between(
        _dt("2025-11-23 09:00"), _dt("2025-11-23 13:30")
    ) == pytest.approx(4.5)


def test_skips_friday_and_saturday():
    # Thursday 17:00 -> Sunday 09:00. Thu evening (7h) + Sun morning (9h) = 16h, weekend excluded.
    h = business_hours_between(_dt("2025-11-20 17:00"), _dt("2025-11-23 09:00"))
    assert h == pytest.approx(16.0)


def test_full_weekend_in_middle():
    # Wed 09:00 -> next Wed 09:00 = 7 days * 24 - 48h (Fri+Sat) = 120h
    h = business_hours_between(_dt("2025-11-19 09:00"), _dt("2025-11-26 09:00"))
    assert h == pytest.approx(120.0)


def test_skips_israeli_holiday():
    # Yom Kippur 2025 = Oct 2 (Thursday). Wed 09:00 -> Sun 09:00 normally = 72h
    # minus Thu (Yom Kippur, 24h), minus Fri+Sat (48h) = 0h working
    h = business_hours_between(_dt("2025-10-01 09:00"), _dt("2025-10-05 09:00"))
    assert h == pytest.approx(24.0)  # Wed 09->Wed 24 = 15h... wait let me recompute
    # Actually: Wed 09:00 -> Sun 09:00.
    #   Wed 09:00-24:00 = 15h (workday)
    #   Thu = Yom Kippur, 0h
    #   Fri = weekend, 0h
    #   Sat = weekend, 0h
    #   Sun 00:00-09:00 = 9h
    # = 24h total. ✓


def test_returns_zero_when_end_before_start():
    assert business_hours_between(_dt("2025-11-23 09:00"), _dt("2025-11-22 09:00")) == 0.0


def test_vector_matches_scalar():
    starts = pd.Series([_dt("2025-11-20 17:00"), _dt("2025-11-23 09:00")])
    ends = pd.Series([_dt("2025-11-23 09:00"), _dt("2025-11-23 13:30")])
    out = business_hours_vector(starts, ends)
    assert out.iloc[0] == pytest.approx(16.0)
    assert out.iloc[1] == pytest.approx(4.5)
