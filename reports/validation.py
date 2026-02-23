"""Validation helpers to ensure reports contain plottable data before rendering."""

from pathlib import Path
from typing import Optional, Union

import pandas as pd

# Minimum PNG file size (bytes) - empty/blank matplotlib figures are typically 1-3KB
MIN_PNG_SIZE_BYTES = 2000


def has_plottable_series(series: pd.Series, min_points: int = 1) -> bool:
    """
    Check if a pandas Series has enough plottable data.

    Args:
        series: Data series to validate
        min_points: Minimum number of non-null, non-zero points (for line/bar charts)

    Returns:
        True if the series has plottable content
    """
    if series is None or (hasattr(series, "empty") and series.empty):
        return False
    valid = series.dropna()
    if len(valid) < min_points:
        return False
    return True


def has_plottable_agg(agg: pd.DataFrame, value_col: Optional[str] = None) -> bool:
    """
    Check if an aggregated DataFrame has plottable content.

    Args:
        agg: Aggregated data (e.g. from groupby)
        value_col: Optional column to check; if None, checks any numeric column

    Returns:
        True if there is at least one non-zero value
    """
    if agg is None or agg.empty:
        return False
    if value_col and value_col in agg.columns:
        return (agg[value_col].fillna(0) != 0).any()
    # Check any numeric column
    for col in agg.select_dtypes(include=["number"]).columns:
        if (agg[col].fillna(0) != 0).any():
            return True
    return False


def has_plottable_scatter(x: pd.Series, y: pd.Series, min_points: int = 2) -> bool:
    """Check if scatter plot has enough points."""
    if x is None or y is None or len(x) < min_points or len(y) < min_points:
        return False
    valid = x.notna() & y.notna()
    return valid.sum() >= min_points


def validate_png_has_content(path: Union[str, Path], remove_if_invalid: bool = True) -> bool:
    """
    Verify a saved PNG file contains meaningful content (not blank/empty).

    Uses file size as a heuristic: empty matplotlib figures are typically 1-3KB,
    while charts with data are usually larger.

    Args:
        path: Path to the PNG file
        remove_if_invalid: If True, delete the file when validation fails

    Returns:
        True if the PNG appears to have content (size >= MIN_PNG_SIZE_BYTES)
    """
    p = Path(path)
    if not p.exists():
        return False
    valid = p.stat().st_size >= MIN_PNG_SIZE_BYTES
    if not valid and remove_if_invalid:
        try:
            p.unlink()
        except OSError:
            pass
    return valid
