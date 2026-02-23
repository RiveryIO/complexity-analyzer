"""Tests for report validation helpers."""

import pytest
import pandas as pd
from pathlib import Path

from reports.validation import (
    MIN_PNG_SIZE_BYTES,
    has_plottable_agg,
    has_plottable_scatter,
    has_plottable_series,
    validate_png_has_content,
)


def test_has_plottable_series_empty():
    """Empty or null-only series is not plottable."""
    assert has_plottable_series(pd.Series(dtype=float)) is False
    assert has_plottable_series(pd.Series([], dtype=float)) is False
    assert has_plottable_series(pd.Series([None, None])) is False


def test_has_plottable_series_valid():
    """Series with data is plottable."""
    assert has_plottable_series(pd.Series([1, 2, 3])) is True
    assert has_plottable_series(pd.Series([0, 0, 1])) is True
    assert has_plottable_series(pd.Series([5.0]), min_points=1) is True


def test_has_plottable_series_min_points():
    """Respects min_points parameter."""
    assert has_plottable_series(pd.Series([1]), min_points=2) is False
    assert has_plottable_series(pd.Series([1, 2]), min_points=2) is True


def test_has_plottable_agg_empty():
    """Empty DataFrame or all zeros is not plottable."""
    assert has_plottable_agg(pd.DataFrame()) is False
    assert has_plottable_agg(pd.DataFrame({"a": [0, 0], "b": [0, 0]})) is False


def test_has_plottable_agg_valid():
    """DataFrame with non-zero values is plottable."""
    df = pd.DataFrame({"team": ["A", "B"], "complexity": [5, 3]})
    assert has_plottable_agg(df, value_col="complexity")
    assert has_plottable_agg(df)


def test_has_plottable_scatter():
    """Scatter needs enough valid (x,y) pairs."""
    assert has_plottable_scatter(pd.Series([1]), pd.Series([1]), min_points=2) is False
    assert has_plottable_scatter(pd.Series([1, 2]), pd.Series([1, 2]), min_points=2)
    assert has_plottable_scatter(pd.Series([1]), pd.Series([1]), min_points=1)


def test_validate_png_has_content_nonexistent(tmp_path):
    """Nonexistent file fails validation."""
    assert validate_png_has_content(tmp_path / "missing.png", remove_if_invalid=False) is False


def test_validate_png_has_content_small_file(tmp_path):
    """Small file (likely empty chart) fails validation and is removed when remove_if_invalid=True."""
    p = tmp_path / "tiny.png"
    p.write_bytes(b"x" * 500)  # Simulate small/empty PNG
    assert p.stat().st_size < MIN_PNG_SIZE_BYTES
    assert validate_png_has_content(p) is False
    assert not p.exists()  # Removed because default remove_if_invalid=True


def test_validate_png_has_content_large_file(tmp_path):
    """Larger file (chart with data) passes validation."""
    p = tmp_path / "real.png"
    p.write_bytes(b"x" * (MIN_PNG_SIZE_BYTES + 1000))
    assert validate_png_has_content(p, remove_if_invalid=False) is True
    assert p.exists()
