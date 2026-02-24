"""Composite master report - combines all generated report PNGs into one image."""

from pathlib import Path
from typing import List

import matplotlib.image as mpimg
import matplotlib.pyplot as plt


def _sort_paths(paths: List[str]) -> List[Path]:
    """Sort paths: basic first, then team (overview then by team), risk, fairness, advanced."""
    def key(p: Path) -> tuple:
        parts = p.parts
        if "basic" in parts:
            return (0, str(p))
        if "team" in parts:
            if "overview" in parts:
                return (1, str(p))
            return (2, str(p))
        if "risk" in parts:
            return (3, str(p))
        if "fairness" in parts:
            return (4, str(p))
        if "advanced" in parts:
            return (5, str(p))
        return (6, str(p))

    return sorted((Path(p) for p in paths if p.endswith(".png")), key=key)


def build_master_report(generated_paths: List[str], output_dir: Path) -> str:
    """
    Composite all generated report PNGs into a single master image.

    Reuses existing report outputs - no code duplication. Loads each PNG
    and arranges in a grid.

    Args:
        generated_paths: List of paths to generated PNG files
        output_dir: Directory to save master PNG (e.g. reports/)

    Returns:
        Path to master PNG file
    """
    paths = [Path(p) for p in generated_paths if Path(p).exists()]
    if not paths:
        return ""

    paths = _sort_paths([str(p) for p in paths])
    n = len(paths)

    # Grid: 5 columns, rows as needed
    ncols = 5
    nrows = (n + ncols - 1) // ncols

    # Each cell ~4x2.5 inches, total figure size
    fig_w = ncols * 4
    fig_h = nrows * 2.5
    fig, axes = plt.subplots(nrows, ncols, figsize=(fig_w, fig_h))
    flat_axes = (
        axes.flatten()
        if hasattr(axes, "flatten")
        else ([axes] if not hasattr(axes, "__len__") else list(axes))
    )

    for idx, ax in enumerate(flat_axes):
        ax.set_axis_off()
        if idx < n:
            try:
                img = mpimg.imread(paths[idx])
                ax.imshow(img, aspect="auto")
            except Exception:
                pass

    fig.suptitle("Engineering Intelligence Reports — Master Summary", fontsize=14, y=1.002)
    fig.tight_layout()
    out = Path(output_dir) / "master-all-reports.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out)
