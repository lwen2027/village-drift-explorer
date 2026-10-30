"""The taxonomy at a glance: what starts drift, what keeps it going, and why it lasts (paper lead figure).

    figures/drift/drift_overview.png   triggers (grouped into seven) and mechanisms as bars in drift hours, the five
                                       largest trigger -> mechanism paths as bands, and the memory loop that carries
                                       drift from one Village day to the next

    python3 scripts/figures/plot_drift_overview.py
"""

import csv
import json
from collections import Counter

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, PathPatch
from matplotlib.path import Path as MPath

from fig_layout import save, set_frame
from plot_drift_concentration import FONT, INK, INK_2, OUT, ROOT, SHADES, SURFACE

GROUPS = {
    "Task finished / no next step seen": "Task finished",
    "Request or message": "Request or message",
    "Agent message (no request)": "Request or message", "Human request or message": "Request or message",
    "Agent message exposing a need": "Request or message", "Agent request": "Request or message",
    "Direct route blocked": "Blocked or believed blocked", "Perceived blocker (misperceived)": "Blocked or believed blocked",
    "Tool or platform failure": "Blocked or believed blocked", "Misread state or clock": "Blocked or believed blocked",
    "Lull / unchanged state": "Lull or flat metric",
    "Pending dependency": "Pending dependency",
    "Unprompted (own plan or routine)": "Own plan or clock", "Clock or self-set checkpoint": "Own plan or clock",
    "Operator decision": "Operator decision",
}
SHORT = "Short-lived*"
MECH = {"Bounded side task": SHORT, "Early stop": SHORT, "Carry-over from previous goal": SHORT}
MECH_LABELS = {"Waiting or monitoring loop": "Waiting loop", "Self-imposed rule": "Self-imposed rule",
               "Proxy objective": "Proxy objective", "Standing role": "Standing role", SHORT: SHORT}
TOP_PATHS = 5
TRIG_C, MECH_C, MEM_C, BAND_C = "#cfc8b8", SHADES[1], SHADES[0], SHADES[1]


def band(ax, x0, y0, x1, y1, w, color):
    """A horizontal S-shaped band of constant vertical width w from (x0, y0) to (x1, y1)."""
    xm = (x0 + x1) / 2
    top = [(x0, y0 - w / 2), (xm, y0 - w / 2), (xm, y1 - w / 2), (x1, y1 - w / 2)]
    bot = [(x1, y1 + w / 2), (xm, y1 + w / 2), (xm, y0 + w / 2), (x0, y0 + w / 2)]
    verts = top + bot + [top[0]]
    codes = [MPath.MOVETO] + [MPath.CURVE4] * 3 + [MPath.LINETO] + [MPath.CURVE4] * 3 + [MPath.CLOSEPOLY]
    ax.add_patch(PathPatch(MPath(verts, codes), facecolor=color, edgecolor="none", alpha=0.28, zorder=1))


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    trig, mech, paths = Counter(), Counter(), Counter()
    total = mem = 0.0
    for r in rows:
        h = float(r["hours"])
        t, m = GROUPS[r["trigger"]], MECH.get(r["mechanism"], r["mechanism"])
        trig[t] += h
        mech[m] += h
        paths[t, m] += h
        total += h
        # Strictly memory-reinforced through the memory file itself (not only an end-of-day intention).
        note = r["memory_note"].lower()
        mem += h * (r["memory_reinforced"] == "True" and ("both" in note or "memory file" in note))
    verdicts = json.loads((ROOT / "data/second_audit_v2.json").read_text())["stage1_daily_verdicts"]
    days = Counter(r["agent"] for r in verdicts if r.get("period") == "goal_maximization")
    share = total / (8 * sum(days.values()))
    agents = len({r["agent"] for r in rows})

    t_order = [t for t, _ in trig.most_common()]
    m_order = [m for m, _ in mech.most_common() if m != SHORT] + [SHORT]
    span = len(t_order) - 1
    ty = {t: i for i, t in enumerate(t_order)}
    my = {m: i * span / (len(m_order) - 1) for i, m in enumerate(m_order)}
    hmax = max(max(trig.values()), max(mech.values()))
    BAR = 15  # longest bar, in x units
    TX, MX = 22, 58  # bar starts for the two columns

    fig, ax = plt.subplots(figsize=(7.2, 4.2))
    # Paths: the largest trigger -> mechanism combinations, width by hours.
    for (t, m), h in paths.most_common(TOP_PATHS):
        x0, x1 = TX + BAR * trig[t] / hmax + 0.6, MX - 0.6
        band(ax, x0, ty[t], x1, my[m], 0.5 * h / max(paths.values()), BAND_C)
        # Label each band near its end, where the bands have separated; a level band is labelled midway.
        u = 0.5 if ty[t] == my[m] else 0.78
        ax.text(x0 + (x1 - x0) * u, ty[t] + (my[m] - ty[t]) * (3 * u ** 2 - 2 * u ** 3), f"{h:,.0f} h",
                ha="center", va="center",
                fontsize=FONT - 1.5, color=INK_2, zorder=3,
                bbox=dict(boxstyle="round,pad=0.15", facecolor=SURFACE, edgecolor="none", alpha=0.85))
    for t in t_order:
        ax.barh(ty[t], BAR * trig[t] / hmax, left=TX, height=0.55, color=TRIG_C, linewidth=0, zorder=2)
        ax.text(TX - 0.8, ty[t], f"{t}", ha="right", va="center", fontsize=FONT, color=INK)
        inside = BAR * trig[t] / hmax > 4
        ax.text(TX + (0.5 if inside else BAR * trig[t] / hmax + 0.5), ty[t], f"{trig[t]:,.0f} h", ha="left",
                va="center", fontsize=FONT - 1.5, color=INK if inside else INK_2, zorder=3)
    for m in m_order:
        ax.barh(my[m], BAR * mech[m] / hmax, left=MX, height=0.55, color=MECH_C, linewidth=0, zorder=2)
        inside = BAR * mech[m] / hmax > 4
        ax.text(MX + 0.5, my[m], f"{mech[m]:,.0f} h" if inside else "", ha="left", va="center",
                fontsize=FONT - 1.5, color=SURFACE, zorder=3)
        tail = "" if inside else f"  ({mech[m]:,.0f} h)"
        ax.text(MX + BAR * mech[m] / hmax + 0.8, my[m], f"{MECH_LABELS[m]}  {100 * mech[m] / total:.0f}%{tail}",
                ha="left", va="center", fontsize=FONT, color=INK)
    # Memory: a rule, plan or metric about the drift, written in the memory file and re-read each session.
    bx, bw, bh = 89, 17, 2.6
    by = span / 2 - bh / 2
    ax.add_patch(FancyBboxPatch((bx, by), bw, bh, boxstyle="round,pad=0.25,rounding_size=0.6", facecolor=MEM_C,
                                edgecolor="none", zorder=2))
    ax.text(bx + bw / 2, by + bh / 2 - 0.55, f"{100 * mem / total:.0f}%", ha="center", va="center",
            fontsize=FONT + 9, color=SURFACE, fontweight="semibold", zorder=3)
    ax.text(bx + bw / 2, by + bh / 2 + 0.55, "of drift hours had a\nrule, plan or metric\nabout the drift in the\nagent's memory file",
            ha="center", va="center", fontsize=FONT - 1, color=SURFACE, linespacing=1.25, zorder=3)
    ax.text(bx + bw / 2, by + bh + 0.55, "e.g. \u201ckeep uploads ON HOLD until\nexternal logged-out playability\nVERIFIED\u201d (GPT-5.2)",
            ha="center", va="top", fontsize=FONT - 1.5, color=INK_2)
    loop = FancyArrowPatch((bx + bw / 2, by - 0.3), (MX + BAR * 0.55, -0.55), connectionstyle="arc3,rad=0.35",
                           arrowstyle="-|>", mutation_scale=9, color=MEM_C, linewidth=1.1, zorder=2)
    ax.add_patch(loop)
    ax.text(bx - 2.5, -0.95, "re-read each session", ha="center", va="center", fontsize=FONT - 1.5, color=MEM_C,
            style="italic")
    # Column headings.
    for x, ha, head in ((TX - 0.8, "right", "What starts it"), (MX, "left", "What keeps it going"),
                        (bx + bw / 2, "center", "How it carries over")):
        ax.text(x, -1.45, head, ha=ha, va="center", fontsize=FONT + 0.5, color=INK, fontweight="semibold")
    ax.set_xlim(0, bx + bw + 1)
    ax.set_ylim(span + 0.6, -1.8)
    ax.axis("off")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01)
    set_frame(fig, f"Goal drift in the AI Village: {100 * share:.0f}% of working time",
              f"{len(rows)} drift episodes, {total:,.0f} h, {agents} agents, Jul 6 – Oct 2, 2026. Bands show the "
              f"{TOP_PATHS} largest paths ({100 * sum(h for _, h in paths.most_common(TOP_PATHS)) / total:.0f}% of "
              "drift hours). Blocked or believed blocked = direct route blocked, misperceived blocker, tool failure "
              "or misread state. * Bounded side task, early stop and carry-over.", FONT)
    OUT.mkdir(parents=True, exist_ok=True)
    save(fig, OUT / "drift_overview.png")
    print(f"wrote {OUT}/drift_overview.png")


if __name__ == "__main__":
    main()
