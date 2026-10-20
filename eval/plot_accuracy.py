"""Draw Figure 1 of the report: accuracy per target category, as a PNG.

Bars per category: SellGPT and the retrieval top-1 baseline, both with function
labels. Reads results/raw_function_summary.json and report_stats.json; writes
report/accuracy_by_category.png.

Usage: python eval/plot_accuracy.py   (after score_eval.py and report_stats.py)
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

EVAL = Path(__file__).resolve().parent
RESULTS = EVAL / "results"
CATEGORIES = ["wellness", "beauty", "gym", "course"]
# First three categorical slots of the validated palette (blue, orange, aqua).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, INK_2, MUTED, GRID, BASE = "#ffffff", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def load(name):
    """Read a results JSON file. Parameter: file name. Return: dict."""
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def main():
    """Render the grouped bar chart. Parameters: none. Return: None."""
    function, stats = load("raw_function_summary.json"), load("report_stats.json")
    series = [
        ("SellGPT", [100 * function["by_category"][c]["correct"] for c in CATEGORIES]),
        ("Retrieval top-1, no LLM",
         [100 * stats["function"]["retrieval_baseline"]["by_category"][c] for c in CATEGORIES]),
    ]

    fig, ax = plt.subplots(figsize=(7.2, 3.9), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    width, gap = 0.3, 0.02  # bar width and surface gap between neighbouring bars
    for s, (name, values) in enumerate(series):
        for i, value in enumerate(values):
            x = i + (s - (len(series) - 1) / 2) * (width + gap) - width / 2
            # Rounded top only: a rounded box plus a square block covering its bottom corners.
            ax.add_patch(FancyBboxPatch((x, 0), width, value, boxstyle="round,pad=0,rounding_size=0.035",
                                        mutation_aspect=40, facecolor=SERIES[s], edgecolor="none"))
            ax.add_patch(plt.Rectangle((x, 0), width, min(value, 3), facecolor=SERIES[s], edgecolor="none"))
            ax.text(x + width / 2, value + 1.5, f"{value:.0f}", ha="center", va="bottom", fontsize=7.5, color=INK_2)
        ax.bar([0], [0], color=SERIES[s], label=name)  # legend handle only

    ax.set_xlim(-0.55, len(CATEGORIES) - 0.45)
    ax.set_ylim(0, 108)
    ax.set_xticks(range(len(CATEGORIES)), [c.capitalize() for c in CATEGORIES], fontsize=9.5, color=INK)
    ax.set_yticks(range(0, 101, 25), [f"{v}%" for v in range(0, 101, 25)], fontsize=8, color=MUTED)
    ax.tick_params(length=0, pad=5)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(BASE)
    ax.set_ylabel("Correct category", fontsize=9, color=INK_2, labelpad=8)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncol=len(series), frameon=False, fontsize=8,
              handlelength=1.1, handleheight=1.1, columnspacing=1.6, labelcolor=INK)
    fig.text(0.02, 0.03, "90 conversations per category (30 prompts × 3 runs).", fontsize=7.5, color=MUTED)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.86, bottom=0.14)
    out = EVAL / "report" / "accuracy_by_category.png"
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
