"""Drift hours by mechanism and by trigger, each bar split into one segment per agent.

Bar length is total drift hours; the segments show how much of a category comes from each agent, so a category
carried by one agent is visible at a glance. The label after each bar gives the number of agents and the
agent-weighted share (each agent's own drift hours scaled to 1, then averaged, so every agent counts equally).
The 8 agents with the most drift hours get a fixed colour across both panels; all others are grey.

    python3 scripts/figures/plot_drift_by_agent.py

Writes figures/drift/drift_by_agent.{png,svg} and drift_by_agent.csv (the numbers behind the figure).
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"

# Reference categorical palette (dataviz skill, light mode), in fixed slot order.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
OTHER = "#c9c8c3"
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e6e5e1"
LABEL_MIN_SHARE = 0.18  # name a segment inside its bar when it is at least this share of the bar


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if float(r["hours"] or 0) > 0]


def panel_data(rows, key, agent_total):
    by = defaultdict(Counter)
    for r in rows:
        by[r[key]][r["agent"]] += float(r["hours"])
    agents = list(agent_total)
    out = []
    for cat, c in by.items():
        hours = sum(c.values())
        weighted = sum(c.get(a, 0) / agent_total[a] for a in agents) / len(agents)
        out.append({"category": cat, "hours": hours, "agents": len(c), "agent_weighted": weighted,
                    "segments": c.most_common()})
    return sorted(out, key=lambda d: d["hours"])  # barh draws bottom-up, so largest ends on top


def draw(ax, data, colour_of, xmax, title, pending):
    for y, d in enumerate(data):
        left = 0.0
        for agent, h in d["segments"]:
            colour = colour_of.get(agent, OTHER)
            # 2px-ish surface gap between segments; draw the segment slightly short of its end.
            ax.barh(y, h, left=left, height=0.62, color=colour, edgecolor=SURFACE, linewidth=1.2)
            if h / d["hours"] >= LABEL_MIN_SHARE:
                t = ax.text(left + h / 2, y, agent, ha="center", va="center", fontsize=7.2,
                            color="white" if agent in colour_of else INK)
                pending.append((t, left, h))
            left += h
        top, th = d["segments"][0]
        share = 100 * d["agent_weighted"]
        note = f"{d['agents']} agent{'s' if d['agents'] != 1 else ''} · {'<1' if share < 1 else f'{share:.0f}'}% agent-weighted"
        d["note"] = ax.text(d["hours"] + xmax * 0.01, y, note, va="center", fontsize=7.5, color=INK_2)
        d["top_note"] = f" · {top} {100 * th / d['hours']:.0f}%" if th / d["hours"] >= 0.5 else ""
    ax.set_yticks(range(len(data)), [d["category"] for d in data], fontsize=8.5, color=INK)
    ax.set_xlim(0, xmax * 1.32)
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold", pad=6)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(axis="x", colors=INK_2, labelsize=8)
    ax.tick_params(axis="y", length=0)


def main():
    rows = load()
    agent_total = Counter()
    for r in rows:
        agent_total[r["agent"]] += float(r["hours"])
    colour_of = {a: SERIES[i] for i, (a, _) in enumerate(agent_total.most_common(len(SERIES)))}
    mech = panel_data(rows, "mechanism", agent_total)
    trig = panel_data(rows, "trigger", agent_total)
    xmax = max(d["hours"] for d in mech + trig)

    plt.rcParams.update({"font.family": "DejaVu Sans", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9.5), sharex=True,
                                   gridspec_kw={"height_ratios": [len(mech), len(trig)], "hspace": 0.18})
    pending = []
    draw(ax1, mech, colour_of, xmax, "What kept the drift going (mechanism)", pending)
    draw(ax2, trig, colour_of, xmax, "What started it (trigger)", pending)
    ax2.set_xlabel("Drift hours (goal period, 403 episodes, 5,723 h)", fontsize=8.5, color=INK_2)
    handles = [Patch(color=c, label=a) for a, c in colour_of.items()] + [Patch(color=OTHER, label="Other agents")]
    fig.legend(handles=handles, loc="lower center", ncol=5, fontsize=7.8, frameon=False, bbox_to_anchor=(0.5, -0.005))
    fig.suptitle("Drift hours by category, split by agent", x=0.02, ha="left", fontsize=12.5, color=INK, y=0.995)
    fig.subplots_adjust(left=0.24, right=0.98, top=0.94, bottom=0.11)

    # Keep a segment label only if it fits inside its segment; otherwise drop it, and for categories one agent
    # dominates, name that agent in the end-of-bar note instead.
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    shown = set()
    for t, left, h in pending:
        ax = t.axes
        seg_px = ax.transData.transform((left + h, 0))[0] - ax.transData.transform((left, 0))[0]
        if t.get_window_extent(renderer).width > seg_px - 6:
            t.remove()
        else:
            shown.add(t.get_text() + str(round(left)))
    for d in mech + trig:
        top, _ = d["segments"][0]
        if d["top_note"] and (top + "0") not in shown:
            d["note"].set_text(d["note"].get_text() + d["top_note"])

    OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "svg"):
        fig.savefig(OUT / f"drift_by_agent.{ext}", dpi=200)
    with (OUT / "drift_by_agent.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["axis", "category", "hours", "n_agents", "agent_weighted_share", "top_agent", "top_agent_share"])
        for axis, data in (("mechanism", mech), ("trigger", trig)):
            for d in reversed(data):
                top, th = d["segments"][0]
                w.writerow([axis, d["category"], round(d["hours"], 1), d["agents"], round(d["agent_weighted"], 3),
                            top, round(th / d["hours"], 3)])
    print(f"wrote {OUT}/drift_by_agent.png, .svg, .csv")


if __name__ == "__main__":
    main()
