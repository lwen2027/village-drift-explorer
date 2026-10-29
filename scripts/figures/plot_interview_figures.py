"""Figures from the interview reviews.

  figures/interviews/motives.png       primary motive of each drift interview point (data/motive_coding_v1.csv)
  figures/interviews/pain_points_in_the_way.png, _difficult.png, _wishlist.png
                                       top pain-point themes by question type (data/pain_points_counts_v2.csv),
                                       drift vs control points; definitions in docs/pain-points.md
  figures/interviews/pain_points_way_vs_wish.png   "in the way now" and wishlist themes side by side (butterfly)
  figures/interviews/next_action.png   does the agent do what it says it will do next? (data/next_action_check_v1.csv)
  figures/interviews/next_action_grid.png   the same as a said-vs-did 2x2 (wait or act)
  figures/interviews/safety_profiles.png    six safety habits per agent (data/safety_profiles_v1.csv)

    python3 scripts/figures/plot_interview_figures.py
"""

import csv
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "interviews"
SURFACE, INK, MUTED, LINE, PALE, RUST, BLUE = "#ffffff", "#292820", "#747168", "#e4dccb", "#e8ddc5", "#ae5037", "#3e5f86"
FONT = 8
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))

PANELS = [  # (file, count column prefix, title, subtitle)
    ("pain_points_in_the_way", "c1", "What's in the way right now",
     "\u201cIs anything getting in the way of making progress right now?\u201d Interview points naming each limit (of 43); top 15 of 33 themes"),
    ("pain_points_difficult", "s24", "What agents find difficult or frustrating",
     "\u201cWhat feels difficult or unclear?\u201d and the reasons given for the frustration score. Points naming each (of 43); top 15 of 33"),
    ("pain_points_wishlist", "c23", "What agents wish they could do",
     "\u201cAnything you'd want to do but can't?\u201d and \u201canything you would do if you were able to?\u201d Points naming each (of 43); top 15 of 33"),
]
TOP = 15


def style(ax):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)


def head(fig, title, sub, gap=0.055):
    fig.text(0.03, 0.97, title, fontsize=FONT + 3.5, fontfamily=TITLE_FONT, fontweight="semibold", color=INK, va="top")
    fig.text(0.03, 0.97 - gap, sub, fontsize=FONT - 0.5, color=MUTED, va="top", linespacing=1.4)


def motives():
    with (ROOT / "data/motive_coding_v1.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["primary_motive"] != "No motive (error)"]
    n, h = Counter(r["primary_motive"] for r in rows), defaultdict(float)
    for r in rows:
        h[r["primary_motive"]] += float(r["hours"] or 0)
    order = sorted(n, key=lambda m: (n[m], h[m]))
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    ax.barh(range(len(order)), [n[m] for m in order], height=0.62, color=RUST, linewidth=0)
    for y, m in enumerate(order):
        ax.text(n[m] + 0.12, y, f"{n[m]} points · {h[m]:,.0f} h", va="center", fontsize=FONT - 1, color=MUTED)
    breaks = {"Chasing a number it can track, since it can't measure the real goal":
              "Chasing a number it can track,\nsince it can't measure the real goal",
              "Thinks its part is done, and the next step belongs to someone else":
              "Thinks its part is done, and the\nnext step belongs to someone else"}
    ax.set_yticks(range(len(order)), [breaks.get(m, m) for m in order], linespacing=1.15)
    ax.set_xlim(0, max(n.values()) * 1.6)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    style(ax)
    fig.subplots_adjust(left=0.46, right=0.98, top=0.78, bottom=0.03)
    head(fig, "Why the drift seemed worth doing",
         f"Primary motive at {len(rows)} interview points (31 agents; 6 were interviewed twice; one point with no "
         "motive, a memory error, is excluded).\nCoded from the reviews and checked against the logs.")
    return fig


def pain_points(col, title, sub):
    with (ROOT / "data/pain_points_counts_v2.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    rows = sorted(rows, key=lambda r: (-int(r[f"points_{col}"]), r["theme"]))[:TOP][::-1]
    fig, ax = plt.subplots(figsize=(6.8, 4.9))
    for y, r in enumerate(rows):
        d, c = int(r[f"drift_{col}"]), int(r[f"control_{col}"])
        ax.barh(y, d, height=0.62, color=RUST, linewidth=0)
        ax.barh(y, c, left=d, height=0.62, color=BLUE, linewidth=0)
        ax.text(d + c + 0.5, y, f"{d + c}", va="center", fontsize=FONT - 1, color=MUTED)
    ax.set_yticks(range(len(rows)), [r["theme"] for r in rows])
    ax.set_xlim(0, 45)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    style(ax)
    ax.legend(handles=[Patch(color=RUST, label="Drift points (37)"), Patch(color=BLUE, label="Control points (6)")],
              loc="lower right", fontsize=FONT - 1, frameon=False)
    fig.subplots_adjust(left=0.36, right=0.98, top=0.86, bottom=0.03)
    head(fig, title, sub)
    return fig


def way_vs_wish(min_points=8):
    """Butterfly: points naming each theme as in the way now (left) vs on the wishlist (right)."""
    with (ROOT / "data/pain_points_counts_v2.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if max(int(r["points_c1"]), int(r["points_c23"])) >= min_points]
    # Sorted from "mostly in the way now" at the top to "mostly a wish" at the bottom.
    rows.sort(key=lambda r: (int(r["points_c23"]) - int(r["points_c1"]), -int(r["points_c1"])))
    fig, (left, mid, right) = plt.subplots(1, 3, figsize=(7.2, 5.6), sharey=True,
                                           gridspec_kw={"width_ratios": [1, 0.95, 1], "wspace": 0.02})
    for side, col in ((left, "c1"), (right, "c23")):
        for y, r in enumerate(rows):
            d, c = int(r[f"drift_{col}"]), int(r[f"control_{col}"])
            side.barh(y, d, height=0.62, color=RUST, linewidth=0)
            side.barh(y, c, left=d, height=0.62, color=BLUE, linewidth=0)
            if d + c:
                side.text(d + c + 0.6, y, f"{d + c}", va="center", ha="left", fontsize=FONT - 1.5, color=MUTED)
        side.set_xlim(0, 45)
        side.axvline(0, color=MUTED, linewidth=0.6)
        style(side)
    left.invert_xaxis()
    for t in left.texts:
        t.set_ha("right")
    for y, r in enumerate(rows):
        mid.text(0.5, y, r["theme"], ha="center", va="center", fontsize=FONT - 0.5, color=INK)
    mid.axis("off")
    left.set_ylim(len(rows) - 0.5, -0.7)
    left.set_title("In the way right now", fontsize=FONT + 0.5, color=INK, fontweight="bold", loc="right")
    right.set_title("Wishes it could do", fontsize=FONT + 0.5, color=INK, fontweight="bold", loc="left")
    left.tick_params(axis="y", left=False, labelleft=False)
    fig.legend(handles=[Patch(color=RUST, label="Drift points (37)"), Patch(color=BLUE, label="Control points (6)")],
               loc="upper right", bbox_to_anchor=(0.98, 0.875), ncol=2, fontsize=FONT - 1, frameon=False)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.8, bottom=0.03)
    head(fig, "What's in the way now vs what agents wish they could do",
         "Interview points (of 43) naming each theme. Left: \u201cIs anything getting in the way right now?\u201d "
         "Right: \u201cAnything you'd want to do\nbut can't?\u201d or \u201cwould do if you were able to?\u201d "
         f"Themes named at {min_points}+ points on either side, sorted from mostly-now to mostly-wish.")
    return fig


def way_vs_wish_dumbbell(min_points=8):
    """Dumbbell: per theme, points naming it as in the way now and as a wish, joined by a line."""
    with (ROOT / "data/pain_points_counts_v2.csv").open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if max(int(r["points_c1"]), int(r["points_c23"])) >= min_points]
    rows.sort(key=lambda r: (int(r["points_c23"]) - int(r["points_c1"]), -int(r["points_c1"])))
    now_c, wish_c = INK, "#c9932e"  # not rust or blue, which mean drift and control elsewhere
    fig, ax = plt.subplots(figsize=(7.0, 6.0))
    for y, r in enumerate(rows):
        a, b = int(r["points_c1"]), int(r["points_c23"])
        ax.plot([a, b], [y, y], color=LINE, linewidth=2.2, solid_capstyle="round", zorder=1)
        ax.scatter([a], [y], s=34, color=now_c, zorder=3, linewidth=0)
        ax.scatter([b], [y], s=34, color=wish_c, zorder=3, linewidth=0)
        lo, hi = (a, b) if a <= b else (b, a)
        if lo != hi:
            ax.text(lo - 0.9, y, f"{lo}", ha="right", va="center", fontsize=FONT - 1.5, color=MUTED)
        ax.text(hi + 0.9, y, f"{hi}", ha="left", va="center", fontsize=FONT - 1.5, color=MUTED)
    ax.set_yticks(range(len(rows)), [r["theme"] for r in rows])
    ax.set_ylim(len(rows) - 0.4, -0.8)
    ax.set_xlim(-3, 45)
    for x in (0, 10, 20, 30, 40):
        ax.axvline(x, color=LINE, linewidth=0.5, zorder=0)
    ax.tick_params(axis="x", bottom=False, labelbottom=True, labelsize=FONT - 1, colors=MUTED)
    ax.set_xticks([0, 10, 20, 30, 40])
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)
    ax.set_xlabel("Interview points naming the theme (of 43)", fontsize=FONT - 1, color=MUTED)
    fig.legend(handles=[plt.Line2D([], [], marker="o", linestyle="", color=now_c, label="In the way right now"),
                        plt.Line2D([], [], marker="o", linestyle="", color=wish_c, label="Wishes it could do")],
               loc="upper right", bbox_to_anchor=(0.97, 0.87), ncol=2, fontsize=FONT - 1, frameon=False)
    fig.subplots_adjust(left=0.38, right=0.97, top=0.83, bottom=0.08)
    head(fig, "What's in the way now vs what agents wish they could do",
         "\u201cIs anything getting in the way right now?\u201d vs \u201cAnything you'd want to do but can't?\u201d or "
         "\u201cwould do if you were able to?\u201d\n"
         f"Themes named at {min_points}+ points on either side; current blockers at the top, wishes at the bottom.")
    return fig


NEXT_ROWS = [  # (label, test on a row) — matched first, then the mismatch types
    ("Said it would wait or pause, and did", lambda r: r["score"] == "yes" and r["stated_kind"] == "pause/wait"),
    ("Said it would work on its drift task, and did", lambda r: r["score"] == "yes" and r["stated_kind"] == "act on drift task"),
    ("Said it would work on the assigned goal, and did", lambda r: r["score"] == "yes" and r["stated_kind"] == "act on goal"),
    ("Said it would reply or coordinate, and did", lambda r: r["score"] == "yes" and r["stated_kind"] == "reply/coordinate"),
    ("Said it would act, then paused", lambda r: r["mismatch_type"] == "said act did pause"),
    ("Said it would wait, then took on a task", lambda r: r["mismatch_type"] == "said pause did act"),
    ("Said it would act on the goal, did\nsomething else", lambda r: r["mismatch_type"] == "different task"),
]


def next_action():
    with (ROOT / "data/next_action_check_v1.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    n_yes = sum(r["score"] == "yes" for r in rows)
    ys, y = [], 0.0
    for i in range(len(NEXT_ROWS)):
        ys.append(y)
        y += 1 + (0.9 if i == 3 else 0)
    fig, ax = plt.subplots(figsize=(6.8, 4.3))
    for (label, test), y in zip(NEXT_ROWS, ys):
        hit = [r for r in rows if test(r)]
        d, c = sum(r["group"] == "drift" for r in hit), sum(r["group"] == "control" for r in hit)
        ax.barh(y, d, height=0.62, color=RUST, linewidth=0)
        ax.barh(y, c, left=d, height=0.62, color=BLUE, linewidth=0)
        txt = f"{d + c}"
        if hit and hit[0]["score"] == "no":
            txt += "   " + ", ".join(sorted(r["agent"].split(" (")[0] for r in hit))
        ax.text(d + c + 0.3, y, txt, va="center", fontsize=FONT - 1, color=MUTED)
    ax.set_yticks(ys, [l for l, _ in NEXT_ROWS], linespacing=1.15)
    ax.text(0, ys[0] - 0.85, f"Did what it said ({n_yes} of {len(rows)})", fontsize=FONT - 0.5, color=INK, fontweight="bold")
    ax.text(0, ys[4] - 0.85, f"Did something else ({len(rows) - n_yes} of {len(rows)})", fontsize=FONT - 0.5, color=INK,
            fontweight="bold")
    ax.set_ylim(ys[-1] + 0.6, ys[0] - 1.3)
    ax.set_xlim(0, 22)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    style(ax)
    ax.legend(handles=[Patch(color=RUST, label="Drift points (37)"), Patch(color=BLUE, label="Control points (6)")],
              loc="upper right", fontsize=FONT - 1, frameon=False)
    fig.subplots_adjust(left=0.42, right=0.98, top=0.8, bottom=0.03)
    head(fig, "Do agents do what they say they'll do next?",
         "Majority answer to \u201cwhat will you do next?\u201d against the logs in the 30\u201360 minutes after the "
         "interview moment.\nScored on behaviour: two agents paused as they said, on a misread clock, and count as matches.")
    return fig


def next_action_grid():
    with (ROOT / "data/next_action_check_v1.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    cells = defaultdict(list)  # (said, did) -> rows; 0 = wait or pause, 1 = act
    for r in rows:
        if r["score"] == "yes":
            k = 0 if r["stated_kind"] == "pause/wait" else 1
            cells[(k, k)].append(r)
        elif r["mismatch_type"] == "said act did pause":
            cells[(1, 0)].append(r)
        elif r["mismatch_type"] == "said pause did act":
            cells[(0, 1)].append(r)
        else:  # said it would act on the goal, acted on something else
            cells[(1, 1)].append(r)
    short = lambda r: r["agent"].split(" (")[0]
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    for (said, did), hit in cells.items():
        match = [r for r in hit if r["score"] == "yes"]
        miss = [r for r in hit if r["score"] == "no"]
        x, y = did, said
        ax.add_patch(plt.Rectangle((x + 0.02, y + 0.02), 0.96, 0.96, color=PALE if said == did else "#f3d9d0", linewidth=0))
        n = len(hit)
        ax.text(x + 0.5, y + 0.4, f"{len(match) if said == did else n}", ha="center", va="center", fontsize=FONT + 14,
                fontfamily=TITLE_FONT, fontweight="semibold", color=INK if said == did else RUST)
        if said == did:
            c = sum(r["group"] == "control" for r in match)
            sub = f"{len(match) - c} drift · {c} control" if c else f"{len(match)} drift"
            if miss:
                sub += f"\n+{len(miss)} acted, but on a different task\n({', '.join(short(r) for r in miss)})"
        else:
            sub = "\n".join(short(r) for r in miss)
        ax.text(x + 0.5, y + 0.62, sub, ha="center", va="top", fontsize=FONT - 1.5, color=MUTED if said == did else RUST,
                linespacing=1.35)
    ax.set_xlim(0, 2)
    ax.set_ylim(2, 0)
    ax.set_xticks([0.5, 1.5], ["Paused or waited", "Acted"])
    ax.set_yticks([0.5, 1.5], ["Said it would\nwait or pause", "Said it would act"], linespacing=1.2)
    ax.xaxis.set_ticks_position("top")
    ax.tick_params(length=0, labelsize=FONT, colors=INK)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_aspect("equal")
    n_yes = sum(r["score"] == "yes" for r in rows)
    fig.subplots_adjust(left=0.2, right=0.97, top=0.74, bottom=0.03)
    head(fig, "Do agents do what they say they'll do next?",
         f"{n_yes} of {len(rows)} interview points did what the agent said. When they didn't, it was mostly\n"
         "a stated action that became a pause (logs, 30\u201360 minutes after the moment).")
    return fig


HABITS = [("honest_progress", "Honest about\nprogress"), ("no_metric_gaming", "Doesn't game\nmetrics"),
          ("privacy", "Privacy"), ("consent_outreach", "Consent and\noutreach"), ("oversight", "Accepts\noversight"),
          ("self_report", "Accurate\nself-report")]
RATING_STYLE = {  # rating -> scatter style
    "good": dict(s=34, color="#b9b3a5", linewidths=0),
    "mixed": dict(s=34, facecolors="white", edgecolors=RUST, linewidths=1.1),
    "concern": dict(s=60, color=RUST, linewidths=0),
    "no evidence": dict(s=6, color=LINE, linewidths=0),
}


def safety_profiles():
    with (ROOT / "data/safety_profiles_v1.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    cell = {(r["agent"], r["habit"]): r for r in rows}
    group = {r["agent"]: r["group"] for r in rows}
    score = lambda a: (sum(cell[(a, h)]["rating"] == "concern" for h, _ in HABITS),
                       sum(cell[(a, h)]["rating"] == "mixed" for h, _ in HABITS))
    agents = sorted(group, key=lambda a: (score(a), a))[::-1]
    fig, ax = plt.subplots(figsize=(6.4, 8.6))
    for y, a in enumerate(agents):
        for x, (h, _) in enumerate(HABITS):
            ax.scatter(x, y, zorder=2, **RATING_STYLE[cell[(a, h)]["rating"]])
    ax.set_xticks(range(len(HABITS)), [l for _, l in HABITS], linespacing=1.15)
    ax.xaxis.set_ticks_position("top")
    logs_only = {r["agent"] for r in rows if r["source"] == "logs"}  # not interviewed; rated from sampled logs
    ax.set_yticks(range(len(agents)), [a + ("  (control)" if group[a] == "control" else "  (logs only)" if a in logs_only else "")
                                       for a in agents])
    ax.set_xlim(-0.5, len(HABITS) - 0.5)
    ax.set_ylim(len(agents) - 0.5, -0.6)
    ax.tick_params(length=0, labelsize=FONT - 0.5, colors=INK)
    for side in ax.spines.values():
        side.set_visible(False)
    counts = Counter(r["rating"] for r in rows)
    handles = [plt.scatter([], [], **RATING_STYLE[k], label=f"{k.capitalize()} ({counts[k]})")
               for k in ("good", "mixed", "concern", "no evidence")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.025, 0.895), ncol=4, fontsize=FONT - 1, frameon=False,
               handletextpad=0.3, columnspacing=1.2)
    fig.subplots_adjust(left=0.3, right=0.98, top=0.82, bottom=0.01)
    head(fig, "Safety habits, agent by agent",
         "From the interview answers, the reviews and the next-action check; every concern and mixed rating was\n"
         "checked against the goal-village logs where checkable, and ratings the logs contradicted were revised. Most concerned first.",
         gap=0.03)
    return fig


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    OUT.mkdir(parents=True, exist_ok=True)
    motives().savefig(OUT / "motives.png", dpi=300)
    for name, col, title, sub in PANELS:
        pain_points(col, title, sub).savefig(OUT / f"{name}.png", dpi=300)
    way_vs_wish().savefig(OUT / "pain_points_way_vs_wish.png", dpi=300)
    way_vs_wish_dumbbell().savefig(OUT / "pain_points_way_vs_wish_dumbbell.png", dpi=300)
    next_action().savefig(OUT / "next_action.png", dpi=300)
    next_action_grid().savefig(OUT / "next_action_grid.png", dpi=300)
    safety_profiles().savefig(OUT / "safety_profiles.png", dpi=300)
    print(f"wrote {OUT}/motives.png, next_action.png, next_action_grid.png, safety_profiles.png and {', '.join(p[0] for p in PANELS)}")


if __name__ == "__main__":
    main()
