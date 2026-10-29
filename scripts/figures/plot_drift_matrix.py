"""Trigger x mechanism heatmap (paper figure).

    figures/drift/drift_matrix.png   rows are triggers, columns mechanisms, both sorted by drift hours; each cell is
                                     shaded by its hours and labelled with hours and episode count; the margins give
                                     each row's and column's total and the median length of its episodes

The three short-lived mechanisms (bounded side task, early stop, carry-over) are pooled into one column.

    python3 scripts/figures/plot_drift_matrix.py
"""

import csv
from collections import defaultdict
from statistics import median

import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, LogNorm

from plot_drift_concentration import FONT, INK, INK_2, OUT, ROOT, SHADES, SURFACE, TITLE_FONT

SHORT = "Short-lived*"
MECHANISM_GROUPS = {"Bounded side task": SHORT, "Early stop": SHORT, "Carry-over from previous goal": SHORT}
MECHANISMS = ["Waiting or monitoring loop", "Self-imposed rule", "Proxy objective", "Standing role", SHORT]
COLUMN_LABELS = ["Waiting or\nmonitoring loop", "Self-imposed\nrule", "Proxy\nobjective", "Standing\nrole", SHORT]
CMAP = LinearSegmentedColormap.from_list("rust", ["#f8ebe5", SHADES[2], SHADES[1], SHADES[0]])


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    cell, by_t, by_m = defaultdict(list), defaultdict(list), defaultdict(list)
    for r in rows:
        t, m, h = r["trigger"], MECHANISM_GROUPS.get(r["mechanism"], r["mechanism"]), float(r["hours"])
        cell[t, m].append(h); by_t[t].append(h); by_m[m].append(h)
    triggers = sorted(by_t, key=lambda t: -sum(by_t[t]))
    vmax = max(sum(v) for v in cell.values())

    fig, ax = plt.subplots(figsize=(7.0, 5.6))
    for i, t in enumerate(triggers):
        for j, m in enumerate(MECHANISMS):
            hs = cell.get((t, m))
            if not hs or sum(hs) < 0.5:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor="#f6f5f2", edgecolor=SURFACE, linewidth=1.5))
                continue
            v = sum(hs)
            color = CMAP(LogNorm(1, vmax)(max(v, 1)))
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=color, edgecolor=SURFACE, linewidth=1.5))
            dark = v > 150
            ax.text(j + 0.5, i + 0.42, f"{v:,.0f} h", ha="center", va="center", fontsize=FONT,
                    color=SURFACE if dark else INK, fontweight="bold" if v >= 200 else "normal")
            ax.text(j + 0.5, i + 0.72, f"{len(hs)} ep.", ha="center", va="center", fontsize=FONT - 1.5,
                    color=SURFACE if dark else INK_2)
    # Margins: row and column totals with the median episode length.
    for i, t in enumerate(triggers):
        ax.text(len(MECHANISMS) + 0.12, i + 0.5, f"{sum(by_t[t]):,.0f} h · median {median(by_t[t]):.1f} h",
                va="center", fontsize=FONT - 1, color=INK_2)
    for j, m in enumerate(MECHANISMS):
        ax.text(j + 0.5, len(triggers) + 0.35, f"{sum(by_m[m]):,.0f} h\nmedian {median(by_m[m]):.1f} h",
                ha="center", va="top", fontsize=FONT - 1, color=INK_2, linespacing=1.3)
    ax.set_xlim(0, len(MECHANISMS) + 1.6)
    ax.set_ylim(len(triggers) + 1.2, 0)
    ax.set_xticks([j + 0.5 for j in range(len(MECHANISMS))], COLUMN_LABELS)
    ax.xaxis.tick_top()
    ax.set_yticks([i + 0.5 for i in range(len(triggers))], triggers)
    ax.tick_params(length=0, labelsize=FONT, colors=INK)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_title("What started each drift (rows) and what kept it going (columns), in drift hours", loc="left",
                 fontsize=FONT + 2, color=INK, fontweight="bold", pad=34, fontfamily=TITLE_FONT)
    fig.text(0.01, 0.012, "* Short-lived = bounded side task, early stop and carry-over from a previous goal.  "
             "Shading is on a log scale.", fontsize=FONT - 1, color=INK_2)
    fig.subplots_adjust(left=0.29, right=0.99, top=0.86, bottom=0.04)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "drift_matrix.png", dpi=300)
    print(f"wrote {OUT}/drift_matrix.png")


if __name__ == "__main__":
    main()
