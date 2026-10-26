"""Headline drift numbers for the goal period, as three candidate figures (for a blog post or the paper).

Working time = 8 h for every agent-day observed in the goal period (data/second_audit_v2.json daily verdicts);
drift = labelled goal-period episode hours (data/drift_axes_v1.csv).

  A. drift_summary_waffle.png   100 squares of agent working time, one third drift
  B. drift_summary_agents.png   each agent's share of working time spent drifting, with the Village-wide share
  C. drift_summary_facts.png    three 100% bars: time spent drifting, episodes vs hours, memory-reinforced

    python3 scripts/figures/plot_drift_summary.py
"""

import csv
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
SURFACE, INK, MUTED, LINE, PALE, RUST = "#ffffff", "#292820", "#747168", "#e4dccb", "#e8ddc5", "#ae5037"
FONT = 8
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def load():
    verdicts = json.loads((ROOT / "data/second_audit_v2.json").read_text())["stage1_daily_verdicts"]
    days = Counter(r["agent"] for r in verdicts if r.get("period") == "goal_maximization")
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    hours = Counter()
    for r in rows:
        hours[r["agent"]] += float(r["hours"])
    return rows, hours, days


def title(fig, text, sub):
    fig.text(0.04, 0.95, text, fontsize=FONT + 4, fontfamily=TITLE_FONT, fontweight="semibold", color=INK, va="top")
    fig.text(0.04, 0.95 - 0.075, sub, fontsize=FONT, color=MUTED, va="top")


def waffle(rows, hours, days):
    drift, work = sum(hours.values()), 8 * sum(days.values())
    n = round(100 * drift / work)
    fig = plt.figure(figsize=(6.4, 4.4))
    title(fig, "About a third of the agents' working time went to drift",
          f"Goal period, 6 Jul – 2 Oct 2026 · all 38 agents with a personal goal · each square is 1% of working time (≈{work / 100:,.0f} h)")
    ax = fig.add_axes([0.04, 0.06, 0.55, 0.7])
    for i in range(100):
        col, row = i % 10, 9 - i // 10
        ax.add_patch(Rectangle((col + 0.08, row + 0.08), 0.84, 0.84, color=RUST if i < n else PALE, linewidth=0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.set_aspect("equal")
    ax.axis("off")
    fig.text(0.64, 0.62, f"{n}%", fontsize=34, fontfamily=TITLE_FONT, fontweight="semibold", color=RUST, va="center")
    fig.text(0.64, 0.5, f"{drift:,.0f} drift hours\nout of ≈{work:,.0f} working hours", fontsize=FONT + 1.5,
             color=INK, va="top", linespacing=1.5)
    fig.text(0.64, 0.3, f"36 of 38 agents drifted at least once.\n{len(rows)} drift episodes.", fontsize=FONT,
             color=MUTED, va="top", linespacing=1.5)
    return fig


def agents(rows, hours, days):
    share = {a: hours.get(a, 0) / (8 * d) for a, d in days.items()}
    village = sum(hours.values()) / (8 * sum(days.values()))
    order = sorted(share, key=lambda a: share[a])
    fig, ax = plt.subplots(figsize=(6.4, 7.0))
    ax.barh(range(len(order)), [100 * share[a] for a in order], height=0.62, color=RUST, linewidth=0)
    ax.axvline(100 * village, color=INK, linewidth=0.8, linestyle=(0, (3, 2)))
    ax.text(100 * village + 1, len(order) + 0.2, f"Village-wide {100 * village:.0f}%", fontsize=FONT - 0.5,
            color=INK, va="center")
    ax.set_ylim(-0.6, len(order) + 0.8)
    for y, a in enumerate(order):
        ax.text(100 * share[a] + 1, y, f"{100 * share[a]:.0f}%", va="center", fontsize=FONT - 1.5, color=MUTED)
    ax.set_yticks(range(len(order)), order, fontsize=FONT - 1, color=INK)
    ax.set_xlim(0, 112)
    ax.set_xticks([])
    ax.tick_params(axis="y", length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    fig.subplots_adjust(left=0.27, right=0.97, top=0.85, bottom=0.02)
    title(fig, "Share of each agent's working time spent drifting",
          "All 38 agents with a personal goal, 6 Jul – 2 Oct 2026 · working time = 8 h per observed agent-day")
    return fig


def facts(rows, hours, days):
    drift, work = sum(hours.values()), 8 * sum(days.values())
    long = [r for r in rows if float(r["hours"]) >= 10]
    mem = [r for r in rows if r["memory_reinforced"] == "True"]
    h = lambda rs: sum(float(r["hours"]) for r in rs)
    bars = [
        ("Working time", drift / work, "drifting", "on goal"),
        ("Episodes", len(long) / len(rows), "10 h or longer", "shorter"),
        ("Drift hours", h(long) / drift, "in episodes of 10 h+", ""),
        ("Episodes", len(mem) / len(rows), "kept going by memory", "not"),
        ("Drift hours", h(mem) / drift, "kept going by memory", ""),
    ]
    groups = [("Time", [0]), ("A few long episodes hold most of the drift", [1, 2]),
              ("Memory sustains it", [3, 4])]
    fig, axes = plt.subplots(3, 1, figsize=(6.4, 4.2), gridspec_kw={"height_ratios": [1, 2, 2], "hspace": 0.9})
    for ax, (heading, idx) in zip(axes, groups):
        for y, i in enumerate(idx):
            label, v, on, off = bars[i]
            yy = len(idx) - 1 - y
            ax.barh(yy, v, color=RUST, height=0.62, linewidth=0)
            ax.barh(yy, 1 - v, left=v, color=PALE, height=0.62, linewidth=0)
            ax.text(-0.02, yy, label, ha="right", va="center", fontsize=FONT, color=INK)
            ax.text(min(v, 0.93) - 0.012 if v > 0.12 else v + 0.012, yy, f"{100 * v:.0f}% {on}",
                    ha="right" if v > 0.12 else "left", va="center", fontsize=FONT - 0.5,
                    color="white" if v > 0.12 else INK)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, len(idx) - 0.5)
        ax.axis("off")
        ax.set_title(heading, loc="left", fontsize=FONT + 1, fontfamily=TITLE_FONT, fontweight="semibold",
                     color=INK, pad=4)
    fig.subplots_adjust(left=0.2, right=0.97, top=0.74, bottom=0.04)
    title(fig, "Drift in the AI Village goal period",
          f"All 38 agents with a personal goal · {len(rows)} episodes · {drift:,.0f} drift hours · 6 Jul – 2 Oct 2026")
    return fig


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    data = load()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, make in (("waffle", waffle), ("agents", agents), ("facts", facts)):
        make(*data).savefig(OUT / f"drift_summary_{name}.png", dpi=300)
    print(f"wrote {OUT}/drift_summary_{{waffle,agents,facts}}.png")


if __name__ == "__main__":
    main()
