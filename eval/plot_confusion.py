"""Draw the category confusion matrix as a PNG heatmap for the report.

Reads results/raw_function_summary.json (function labels) and writes
report/confusion_matrix_function.png.

Usage: python eval/plot_confusion.py
"""

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

EVAL = Path(__file__).resolve().parent
ROWS = ["wellness", "beauty", "gym", "course"]
COLUMNS = ["wellness", "beauty", "gym", "course", "none"]
COLUMN_NAMES = ["Wellness", "Beauty", "Gym", "Course", "No product"]
# One-hue sequential ramp (blue 100 -> 700); zero cells stay near the page colour.
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SURFACE, ZERO, INK, INK_2, MUTED, LINE = "#ffffff", "#f4f3ef", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"


def draw(summary, labels_name, out):
    """Render one matrix. Parameters: summary dict, label-set name, output path. Return: None."""
    cmap = LinearSegmentedColormap.from_list("blue", RAMP)
    counts = [[summary["confusion"][row].get(col, 0) for col in COLUMNS] for row in ROWS]
    totals = [sum(row) for row in counts]
    correct = sum(counts[i][i] for i in range(len(ROWS)))

    fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=300)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    gap = 0.04  # surface gap between cells
    for i, row in enumerate(counts):
        for j, value in enumerate(row):
            share = value / totals[i]
            fill = ZERO if value == 0 else cmap(min(1.0, share / 0.95))
            ax.add_patch(FancyBboxPatch((j + gap / 2, i + gap / 2), 1 - gap, 1 - gap,
                                        boxstyle="round,pad=0,rounding_size=0.05",
                                        facecolor=fill, edgecolor=LINE if value == 0 else fill, linewidth=0.6))
            dark = value and share >= 0.45
            colour = "#ffffff" if dark else (MUTED if value == 0 else INK)
            ax.text(j + 0.5, i + 0.43, str(value), ha="center", va="center", fontsize=13,
                    fontweight="bold" if i == j else "normal", color=colour)
            if value:
                ax.text(j + 0.5, i + 0.72, f"{100 * share:.0f}%", ha="center", va="center",
                        fontsize=7.5, color="#dfe9f7" if dark else INK_2)

    ax.set_xlim(0, len(COLUMNS))
    ax.set_ylim(len(ROWS), 0)
    ax.set_aspect("auto")
    ax.set_xticks([j + 0.5 for j in range(len(COLUMNS))], COLUMN_NAMES, fontsize=9.5, color=INK)
    ax.set_yticks([i + 0.5 for i in range(len(ROWS))], [r.capitalize() for r in ROWS], fontsize=9.5, color=INK)
    ax.xaxis.tick_top()
    ax.xaxis.set_label_position("top")
    ax.tick_params(length=0, pad=6)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xlabel("Category of the product SellGPT recommended", fontsize=9, color=INK_2, labelpad=10)
    ax.set_ylabel("Category the prompt called for", fontsize=9, color=INK_2, labelpad=10)

    n = sum(totals)
    fig.text(0.02, 0.025, f"{labels_name.capitalize()} labels · {totals[0]} conversations per row "
             f"(30 prompts × 3 runs) · percentages are of the row.\n"
             f"Diagonal = correct: {correct} of {n} ({100 * correct / n:.1f}%).",
             fontsize=7.5, color=MUTED, linespacing=1.5)
    fig.subplots_adjust(left=0.13, right=0.98, top=0.83, bottom=0.13)
    fig.savefig(out, facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote {out}")


def main():
    """Draw both label sets. Parameters: none. Return: None."""
    out_dir = EVAL / "report"
    out_dir.mkdir(exist_ok=True)
    for name, file in (("function", "raw_function_summary.json"),):
        summary = json.loads((EVAL / "results" / file).read_text(encoding="utf-8"))
        draw(summary, name, out_dir / f"confusion_matrix_{name}.png")


if __name__ == "__main__":
    main()
