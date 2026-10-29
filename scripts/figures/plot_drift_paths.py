"""The main drift paths: trigger -> mechanism, split by episode length (paper figure).

    figures/drift/drift_paths.png   one bar per trigger -> mechanism pair, sorted by drift hours, the top 15 shown
                                    the rest summarised in a footnote; each bar is split into episodes over 40 h, 5-40 h and under
                                    5 h, and labelled with its episode count and median episode length

A readable alternative to drift_flow.png: it shows which starts lead to which sustaining mechanism, and which of
those paths produce the long holds.

    python3 scripts/figures/plot_drift_paths.py
"""

import csv
from collections import defaultdict
from statistics import median

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from plot_drift_concentration import FONT, INK, INK_2, OUT, ROOT, SHADES, SURFACE, TITLE_FONT, style

TOP = 15
ARROW = r"$\rightarrow$"  # the body fonts have no arrow glyph
BANDS = ["Over 40 h", "5–40 h", "Under 5 h"]
SHORT_NAMES = {
    "Task finished / no next step seen": "Task finished",
    "Perceived blocker (misperceived)": "Misperceived blocker",
    "Agent message (no request)": "Agent message",
    "Agent message exposing a need": "Agent message exposing a need",
    "Unprompted (own plan or routine)": "Unprompted",
    "Waiting or monitoring loop": "waiting loop",
    "Self-imposed rule": "self-imposed rule",
    "Proxy objective": "proxy objective",
    "Standing role": "standing role",
}


def band(hours):
    return 0 if hours > 40 else 1 if hours > 5 else 2


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    paths = defaultdict(list)
    for r in rows:
        paths[r["trigger"], r["mechanism"]].append(float(r["hours"]))
    ranked = sorted(paths.items(), key=lambda kv: -sum(kv[1]))
    shown = ranked[:TOP]
    rest = [h for _, hs in ranked[TOP:] for h in hs]
    total = sum(float(r["hours"]) for r in rows)
    bars = [(f"{SHORT_NAMES.get(t, t)} {ARROW} {SHORT_NAMES.get(m, m)}", hs) for (t, m), hs in shown]
    xmax = max(sum(hs) for _, hs in bars)

    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for i, (label, hs) in enumerate(bars):
        y = len(bars) - 1 - i
        split = [0.0, 0.0, 0.0]
        for h in hs:
            split[band(h)] += h
        left = 0.0
        for h, shade in zip(split, SHADES):
            if h > 0:
                ax.barh(y, h, left=left, height=0.66, color=shade, edgecolor=SURFACE, linewidth=0.8)
            left += h
        n = len(hs)
        ax.text(left + xmax * 0.012, y,
                f"{left:,.0f} h  ·  {n} ep.  ·  median {median(hs):.1f} h  ·  {100 * left / total:.0f}%",
                va="center", fontsize=FONT - 0.5, color=INK_2)
    ax.set_yticks(range(len(bars)), [b[0] for b in reversed(bars)])
    ax.set_ylim(-0.6, len(bars) - 0.4)
    ax.set_xlim(0, xmax * 1.75)
    ax.set_title(f"The main drift paths: what started it {ARROW} what kept it going", loc="left", fontsize=FONT + 2,
                 color=INK, fontweight="semibold", pad=22, fontfamily=TITLE_FONT)
    style(ax)
    ax.legend(handles=[Patch(color=s, label=f"Episodes {b.lower() if b[0] == 'U' else b}") for s, b in
                       zip(SHADES, ["over 40 h", "5–40 h", "under 5 h"])],
              loc="lower left", bbox_to_anchor=(0, 1.0), ncol=3, fontsize=FONT - 0.5, frameon=False,
              handlelength=1.2, borderaxespad=0.2, columnspacing=1.2)
    # The remaining paths are many small ones; pooled into a bar they read as one big path, so they get a note.
    fig.text(0.01, 0.015, f"Not shown: the other {len(ranked) - TOP} paths, {sum(rest):,.0f} h "
             f"({100 * sum(rest) / total:.0f}%) across {len(rest)} episodes, median {median(rest):.1f} h.",
             fontsize=FONT - 1, color=INK_2)
    fig.subplots_adjust(left=0.36, right=0.99, top=0.89, bottom=0.08)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "drift_paths.png", dpi=300)
    print(f"wrote {OUT}/drift_paths.png")


if __name__ == "__main__":
    main()
