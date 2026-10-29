"""Figures for the drift paper: how concentrated each mechanism and trigger is in a few agents.

Main figure, figures/drift/drift_concentration.png: (a) triggers, (b) mechanisms, each sorted by hours.
Each bar is drift hours split into the largest contributing agent, the 2nd-3rd agents and all others; the label
gives total hours, the number of agents and the top agent's share.

Supplementary figure, figures/drift/drift_agent_profile.png: one row per agent, each cell the share of
that agent's own drift hours in a mechanism or trigger (rows sum to 100% within each panel), with the agent's total
hours on the right.

    python3 scripts/figures/plot_drift_concentration.py
"""

import argparse
import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
import matplotlib.font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
SURFACE, INK, INK_2, GRID = "#ffffff", "#0b0b0b", "#52514e", "#e3e2de"
# One hue, three steps (largest agent, 2nd-3rd, all others); the lightest still holds up in print.
SHADES = ["#8d3b26", "#c97559", "#ebc5b6"]  # rust ramp: drift is always rust; blue is reserved for the control group
SHADE_LABELS = ["Top agent", "2nd–3rd agents", "All other agents"]
MECHANISMS = ["Waiting or monitoring loop", "Self-imposed rule", "Proxy objective", "Standing role",
              "Bounded side task", "Early stop", "Carry-over from previous goal"]
TRIGGERS = ["Unprompted (own plan or routine)", "Direct route blocked", "Task finished / no next step seen", "Pending dependency",
            "Lull / unchanged state", "Clock or self-set checkpoint", "Agent message (no request)", "Human request or message",
            "Agent message exposing a need", "Agent request",
            "Perceived blocker (misperceived)", "Tool or platform failure", "Misread state or clock",
            "Operator decision"]
FONT = 7.5
TITLE_FONT = "Lora"  # matches the AI Village site; bundled in scripts/figures/fonts (SIL OFL)
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if float(r["hours"] or 0) > 0]


def hours_by(rows, key):
    by = defaultdict(Counter)
    for r in rows:
        by[r[key]][r["agent"]] += float(r["hours"])
    return by


def style(ax):
    # No gridlines or x-axis: every bar is labelled with its hours, and gridlines would run through the labels.
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.axvline(0, color=INK_2, linewidth=0.6)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)


def bar_row(ax, y, c, xmax):
    top = c.most_common()
    parts = [top[0][1], sum(h for _, h in top[1:3]), sum(h for _, h in top[3:])]
    total, left = sum(parts), 0.0
    for h, shade in zip(parts, SHADES):
        if h > 0:
            ax.barh(y, h, left=left, height=0.64, color=shade, edgecolor=SURFACE, linewidth=0.8)
        left += h
    n = len(c)
    ax.text(total + xmax * 0.012, y,
            f"{total:,.0f} h · {n} agent{'s' if n != 1 else ''} · top: {top[0][0]} {100 * top[0][1] / total:.0f}%",
            va="center", fontsize=FONT - 0.5, color=INK_2)


def concentration(rows):
    mech, trig = hours_by(rows, "mechanism"), hours_by(rows, "trigger")
    assert set(mech) == set(MECHANISMS), set(mech) ^ set(MECHANISMS)
    assert set(trig) == set(TRIGGERS), set(trig) ^ set(TRIGGERS)
    xmax = max(sum(c.values()) for c in list(mech.values()) + list(trig.values()))

    trig_rows = [(t, trig[t]) for t in sorted(TRIGGERS, key=lambda t: -sum(trig[t].values()))]
    mech_rows = [(m, mech[m]) for m in sorted(MECHANISMS, key=lambda m: -sum(mech[m].values()))]

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.0, 6.4), sharex=True,
                                   gridspec_kw={"height_ratios": [len(trig_rows), len(mech_rows)], "hspace": 0.12})
    for ax, data, letter, name in ((ax1, trig_rows, "a", "Trigger (what started it)"),
                                   (ax2, mech_rows, "b", "Mechanism (what kept the drift going)")):
        for i, (label, c) in enumerate(data):
            bar_row(ax, len(data) - 1 - i, c, xmax)  # first row at the top
        ax.set_yticks(range(len(data)), [label for label, _ in reversed(data)])
        ax.set_ylim(-0.6, len(data) - 0.4)
        ax.set_title(f"({letter}) {name}", loc="left", fontsize=FONT + 2, color=INK, fontweight="semibold", pad=6, fontfamily=TITLE_FONT)
        style(ax)
    ax2.set_xlim(0, xmax * 2.0)
    ax1.legend(handles=[Patch(color=s, label=l) for s, l in zip(SHADES, SHADE_LABELS)], loc="lower right",
               fontsize=FONT - 0.5, frameon=False, handlelength=1.2, borderaxespad=0.2)
    fig.subplots_adjust(left=0.3, right=0.99, top=0.96, bottom=0.03)
    return fig


def profile(rows):
    agent_total = Counter()
    for r in rows:
        agent_total[r["agent"]] += float(r["hours"])
    agents = [a for a, _ in agent_total.most_common()]
    mech, trig = hours_by(rows, "mechanism"), hours_by(rows, "trigger")
    mech_cols = sorted(MECHANISMS, key=lambda m: -sum(mech[m].values()))
    trig_cols = sorted(TRIGGERS, key=lambda t: -sum(trig[t].values()))
    cmap = LinearSegmentedColormap.from_list("seq", ["#ffffff", "#f2d9cf", "#d99a83", "#ae5037", "#6e2a19"])
    norm = Normalize(0, 100)

    fig, axes = plt.subplots(1, 2, figsize=(7.2, 7.8),
                             gridspec_kw={"width_ratios": [len(trig_cols), len(mech_cols)], "wspace": 0.05})
    for i, (ax, by, cols, title) in enumerate(((axes[0], trig, trig_cols, "(a) Trigger"),
                                               (axes[1], mech, mech_cols, "(b) Mechanism"))):
        grid = [[100 * by[c].get(a, 0) / agent_total[a] for c in cols] for a in agents]
        ax.imshow(grid, aspect="auto", cmap=cmap, norm=norm)
        for yi, row in enumerate(grid):
            for xi, v in enumerate(row):
                if v >= 5:
                    ax.text(xi, yi, f"{v:.0f}", ha="center", va="center", fontsize=FONT - 1.8,
                            color="white" if v >= 55 else INK)
        ax.set_xticks(range(len(cols)), cols, rotation=60, ha="right", rotation_mode="anchor",
                      fontsize=FONT - 1, color=INK)
        ax.set_yticks(range(len(agents)), agents if i == 0 else [], fontsize=FONT - 1, color=INK)
        ax.set_title(title, loc="left", fontsize=FONT + 2, color=INK, fontweight="semibold", pad=4, fontfamily=TITLE_FONT)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_xticks([x - 0.5 for x in range(1, len(cols))], minor=True)
        ax.set_yticks([y - 0.5 for y in range(1, len(agents))], minor=True)
        ax.grid(which="minor", color=SURFACE, linewidth=0.8)
        ax.tick_params(which="minor", length=0)
        if i == 1:
            ax.set_yticks(range(len(agents)), [f"{agent_total[a]:,.0f} h" if agent_total[a] >= 1 else "<1 h" for a in agents], minor=False,
                          fontsize=FONT - 1.5, color=INK_2)
            ax.yaxis.tick_right()
    fig.subplots_adjust(left=0.2, right=0.92, top=0.96, bottom=0.25)
    return fig


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--font", default="Helvetica Neue")
    ap.add_argument("--out", type=Path, default=OUT)
    args = ap.parse_args()
    plt.rcParams.update({"font.family": args.font, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    rows = load()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, fig in (("drift_concentration", concentration(rows)), ("drift_agent_profile", profile(rows))):
        fig.savefig(args.out / f"{name}.png", dpi=300)
    print(f"wrote {args.out}/drift_concentration.png and drift_agent_profile.png")


if __name__ == "__main__":
    main()
