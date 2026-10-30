"""What agents spent drift time doing (paper figure).

    figures/drift/drift_activity.png   drift hours by activity, split into the top agent, the 2nd-3rd agents and the
                                       rest, in the same style as drift_concentration.png

Activity comes from data/drift_activity_v1.csv: one primary activity per episode, taken from the researcher's
manual-review labels where they name an activity (pause and proxy categories) and coded from the episode
description otherwise.

    python3 scripts/figures/plot_drift_activity.py
"""

import csv
from collections import Counter, defaultdict

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from fig_layout import save, set_frame
from plot_drift_concentration import FONT, OUT, ROOT, SHADE_LABELS, SHADES, SURFACE, bar_row, style

ACTIVITIES = ["Waiting: pausing or re-checking", "Producing for a self-chosen count", "Helping other agents or humans",
              "Building internal tools, docs or records", "Village social and coordination", "Other off-goal project",
              "Games and play"]


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    with (ROOT / "data/drift_activity_v1.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if float(r["hours"] or 0) > 0]
    by = defaultdict(Counter)
    for r in rows:
        by[r["activity"]][r["agent"]] += float(r["hours"])
    assert set(by) == set(ACTIVITIES), set(by) ^ set(ACTIVITIES)
    data = sorted(ACTIVITIES, key=lambda a: -sum(by[a].values()))
    xmax = max(sum(c.values()) for c in by.values())

    fig, ax = plt.subplots(figsize=(7.0, 3.05))
    for i, a in enumerate(data):
        bar_row(ax, len(data) - 1 - i, by[a], xmax)  # first row at the top
    ax.set_yticks(range(len(data)), list(reversed(data)))
    ax.set_ylim(-0.6, len(data) - 0.4)
    ax.set_xlim(0, xmax * 2.0)
    total = sum(sum(c.values()) for c in by.values())
    set_frame(fig, "What agents did while off-goal: mostly waiting or chasing their own counts",
              f"Drift hours by activity ({total:,.0f} h in all), split by agent: a mostly dark bar is one agent's habit.",
              FONT)
    style(ax)
    ax.legend(handles=[Patch(color=s, label=l) for s, l in zip(SHADES, SHADE_LABELS)], loc="lower right",
              fontsize=FONT - 0.5, frameon=False, handlelength=1.2, borderaxespad=0.2)
    fig.subplots_adjust(left=0.3, right=0.99, top=0.89, bottom=0.1)
    OUT.mkdir(parents=True, exist_ok=True)
    save(fig, OUT / "drift_activity.png")
    print(f"wrote {OUT}/drift_activity.png")


if __name__ == "__main__":
    main()
