#!/usr/bin/env python3
"""
Generate a diagram explaining the core principles of the complexity analyzer engine.
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.lines as mlines

# Colors - modern palette
COLORS = {
    "input": "#E3F2FD",      # Light blue
    "process": "#FFF3E0",    # Light orange
    "llm": "#E8F5E9",        # Light green
    "output": "#F3E5F5",     # Light purple
    "accent": "#1976D2",     # Blue
    "text": "#212121",
    "border": "#BDBDBD",
}


def add_box(ax, x, y, w, h, text, color, fontsize=9):
    """Add a rounded box with text."""
    box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", 
                         facecolor=color, edgecolor=COLORS["border"], linewidth=1)
    ax.add_patch(box)
    ax.text(x + w/2, y + h/2, text, ha="center", va="center", fontsize=fontsize, 
            wrap=True, color=COLORS["text"])


def add_arrow(ax, start, end, color="#757575"):
    """Add an arrow between two points."""
    ax.annotate("", xy=end, xytext=start,
                arrowprops=dict(arrowstyle="->", color=color, lw=2))


def main():
    fig, ax = plt.subplots(1, 1, figsize=(14, 12))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 12)
    ax.set_aspect("equal")
    ax.axis("off")

    # Title
    ax.text(7, 11.5, "Complexity Analyzer — Core Engine", fontsize=18, ha="center", 
            fontweight="bold", color=COLORS["text"])
    ax.text(7, 11, "Implementation effort (1–10), not line count or operational risk", 
            fontsize=10, ha="center", color="#616161")

    # === PIPELINE FLOW ===
    # Row 1: Input
    add_box(ax, 0.5, 9.2, 2.2, 1.2, "PR URL", COLORS["input"])
    add_box(ax, 3.2, 9.2, 2.2, 1.2, "GitHub API\nFetch", COLORS["process"])
    add_box(ax, 5.9, 9.2, 2.2, 1.2, "Raw Diff\n+ Metadata", COLORS["input"])
    
    add_arrow(ax, (2.7, 9.8), (3.2, 9.8))
    add_arrow(ax, (5.4, 9.8), (5.9, 9.8))

    # Row 2: Preprocess
    add_box(ax, 5.9, 7.2, 2.5, 1.5, "Preprocess\n(redact, filter,\nchunk, truncate)", COLORS["process"])
    add_arrow(ax, (6.05, 9.2), (6.05, 8.7))
    
    add_box(ax, 5.9, 5.4, 2.5, 1.5, "Build Prompt\n(URL, title, stats,\ndiff excerpt)", COLORS["process"])
    add_arrow(ax, (7.15, 7.2), (7.15, 6.9))

    # Row 3: LLM
    add_box(ax, 2.5, 3.2, 4.5, 2.0, "LLM Analysis\n(OpenAI / Anthropic / Bedrock)\n\nSystem prompt + diff → JSON", COLORS["llm"], fontsize=10)
    add_arrow(ax, (7.15, 6.1), (7, 5.2))
    add_arrow(ax, (7, 5.2), (5.25, 5.2))
    add_arrow(ax, (5.25, 5.2), (5.25, 5.2))

    # Row 4: Output
    add_box(ax, 2.5, 1.2, 2.0, 1.5, "Parse & Validate\n(clamp 1–10)", COLORS["output"])
    add_box(ax, 5.0, 1.2, 2.0, 1.5, "Score + Explanation", COLORS["output"])
    add_arrow(ax, (4.25, 4.2), (3.5, 2.7))
    add_arrow(ax, (3.5, 1.95), (5.0, 1.95))

    # === PRINCIPLES PANEL ===
    principles_y = 0.3
    ax.add_patch(Rectangle((8.5, 1.5), 5.2, 8.5, facecolor="#FAFAFA", 
                           edgecolor=COLORS["border"], linewidth=1, linestyle="-"))
    ax.text(11.1, 9.7, "Core Principles", fontsize=12, ha="center", fontweight="bold")
    
    principles = [
        ("What Complexity Means", [
            "Implementation effort",
            "Design + code + testing",
            "Developer velocity proxy",
        ]),
        ("LLM Factors", [
            "Scope (files/modules)",
            "Logic (control flow, abstractions)",
            "Testing effort implied",
            "Data (migrations, mappings)",
        ]),
        ("Score Bands", [
            "1–2: Almost trivial",
            "3–4: Small but non-trivial",
            "5–6: Medium (multi-module)",
            "7–8: Large/sophisticated",
            "9–10: Very complex",
        ]),
        ("Avoid Conflating", [
            "Line count ≠ complexity",
            "Lockfile churn ≠ high score",
            "Operational risk ≠ impl. difficulty",
        ]),
    ]
    
    y = 9.2
    for title, items in principles:
        ax.text(8.7, y, title, fontsize=9, fontweight="bold", color=COLORS["accent"])
        y -= 0.35
        for item in items:
            ax.text(8.9, y, f"• {item}", fontsize=8, color=COLORS["text"])
            y -= 0.3
        y -= 0.2

    # === PREPROCESS DETAILS ===
    ax.add_patch(Rectangle((0.5, 1.5), 4.5, 3.2, facecolor="#FFFDE7", 
                           edgecolor=COLORS["border"], linewidth=1))
    ax.text(2.75, 4.5, "Preprocess Steps", fontsize=10, ha="center", fontweight="bold")
    preprocess_steps = [
        "Redact: secrets, emails, keys",
        "Filter: lockfiles, binary, vendor/",
        "Chunk: max hunks per file (default 2)",
        "Truncate: tiktoken, max 50k tokens",
        "Stats: additions, deletions, byExt, byLang",
    ]
    for i, step in enumerate(preprocess_steps):
        ax.text(0.7, 4.2 - i * 0.5, step, fontsize=8)

    # File layout legend
    ax.text(7, 0.5, "Key files: cli/analyze.py (orchestration) • cli/preprocess.py • cli/prompt/default.txt • cli/scoring.py • cli/llm*.py", 
            fontsize=8, ha="center", style="italic", color="#757575")

    plt.tight_layout()
    out_path = "reports/complexity-engine-principles.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"Saved: {out_path}")


if __name__ == "__main__":
    main()
