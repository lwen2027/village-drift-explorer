"""Figure for the drift paper: how often memory carried a drift episode, by episode length.

figures/drift/drift_memory_by_length.png: one bar per length band, the share of episodes whose drift was
reinforced by the agent's own memory (a rule, plan or metric in the memory file, or an overnight intention),
labelled with the count. Data: data/drift_axes_v1.csv (memory_reinforced, hours).

    python3 scripts/figures/plot_drift_memory_length.py
"""

import csv
from pathlib import Path

import matplotlib
import matplotlib.font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from fig_layout import save, set_frame

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
INK, INK_2, GRID = "#0b0b0b", "#52514e", "#e3e2de"
RUST = "#8d3b26"
FONT = 7.5
BANDS = [(0, 1, "Under 1 h"), (1, 8, "1–8 h"), (8, 24, "8–24 h"), (24, 40, "24–40 h"), (40, float("inf"), "Over 40 h")]
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))  # all 403 episodes; the 42 under a minute count as "under 1 h"


def main():
    rows = load()
    labels, shares, counts = [], [], []
    for lo, hi, label in BANDS:
        band = [r for r in rows if lo <= float(r["hours"] or 0) < hi]
        held = sum(r["memory_reinforced"] == "True" for r in band)
        labels.append(label)
        shares.append(100 * held / len(band))
        counts.append((held, len(band)))

    plt.rcParams.update({"font.family": "Helvetica Neue"})
    fig, ax = plt.subplots(figsize=(4.6, 2.4))
    ticks = [f"{label}\n{held} of {n}" for label, (held, n) in zip(labels, counts)]
    bars = ax.bar(ticks, shares, width=0.6, color=RUST, edgecolor="white", linewidth=1)
    for b, s in zip(bars, shares):
        ax.text(b.get_x() + b.get_width() / 2, s + 2, f"{s:.0f}%", ha="center", va="bottom", fontsize=FONT, color=INK,
                fontweight="semibold")
    ax.set_ylim(0, 112)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels([f"{t}%" for t in (0, 25, 50, 75, 100)], fontsize=FONT - 0.5, color=INK_2)
    ax.set_ylabel("Episodes carried by memory", fontsize=FONT, color=INK_2)
    ax.set_xlabel("Episode length (drift hours)", fontsize=FONT, color=INK_2)
    ax.tick_params(axis="x", labelsize=FONT, colors=INK, length=0)
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    set_frame(fig, "The longer a drift lasts, the more likely memory is carrying it",
              "Share of drift episodes reinforced by the agent's own memory (a rule, plan or metric in the memory file, "
              "or an overnight intention), by episode length. 403 episodes.", font=FONT)
    save(fig, OUT / "drift_memory_by_length.png")


if __name__ == "__main__":
    main()
