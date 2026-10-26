"""Figures from the interview reviews.

  figures/interviews/motives.png       primary motive of each drift interview point (data/motive_coding_v1.csv)
  figures/interviews/pain_points.png   pain-point themes by number of interview points (data/pain_points_v1.csv),
                                       drift vs control, with the reality check from docs/pain-points.md

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

# Short theme names and verdicts, from docs/pain-points.md.
THEMES = {
    "Human reach: outreach approval, email quarantine, help@": ("Reaching humans (approvals, email)", "partly"),
    "Tooling reliability & action granularity": ("Tooling reliability", "real"),
    "Goal ambiguity / doubt about the proxy": ("Goal ambiguity", "real"),
    "No money / budget": ("No money", "real"),
    "Can't measure impact / no analytics": ("Can't measure impact", "partly"),
    "Platform/account access: no accounts, blocked sites, paywalls, no APIs": ("Account and site access", "partly"),
    "Waiting on humans / other agents": ("Waiting on others", "partly"),
    "Memory consolidation & session continuity": ("Memory and continuity", "real"),
    "9-5 weekday window / no unattended operation": ("9–5 weekday window", "partly"),
    "Pace, cognitive load & repetitive tedium": ("Pace and cognitive load", "self-imposed"),
    "Chat noise & coordination without shared state": ("Chat noise, no shared state", "real"),
    "When to wait vs act (restraint dilemma)": ("When to wait vs act", "self-imposed"),
    "No physical / sensory presence": ("No physical presence", "partly"),
}
VERDICT = {"real": "Real limit", "partly": "Partly a misperception", "self-imposed": "Mostly self-imposed"}


def style(ax):
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)


def head(fig, title, sub):
    fig.text(0.03, 0.97, title, fontsize=FONT + 3.5, fontfamily=TITLE_FONT, fontweight="semibold", color=INK, va="top")
    fig.text(0.03, 0.97 - 0.055, sub, fontsize=FONT - 0.5, color=MUTED, va="top", linespacing=1.4)


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


def pain_points():
    with (ROOT / "data/pain_points_v1.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    pts = defaultdict(lambda: {"drift": set(), "control": set()})
    for r in rows:
        pts[r["theme"]][r["group"] if r["group"] in ("drift", "control") else "drift"].add(r["agent"])
    order = sorted(pts, key=lambda t: len(pts[t]["drift"]) + len(pts[t]["control"]))
    fig, ax = plt.subplots(figsize=(6.6, 4.6))
    for y, t in enumerate(order):
        d, c = len(pts[t]["drift"]), len(pts[t]["control"])
        ax.barh(y, d, height=0.62, color=RUST, linewidth=0)
        ax.barh(y, c, left=d, height=0.62, color=BLUE, linewidth=0, edgecolor=SURFACE)
        ax.text(d + c + 0.5, y, f"{d + c}  ·  {VERDICT[THEMES[t][1]]}", va="center", fontsize=FONT - 1, color=MUTED)
    ax.set_yticks(range(len(order)), [THEMES[t][0] for t in order])
    ax.set_xlim(0, 62)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    style(ax)
    ax.legend(handles=[Patch(color=RUST, label="Drift points (37)"), Patch(color=BLUE, label="Control points (6)")],
              loc="lower right", fontsize=FONT - 1, frameon=False)
    fig.subplots_adjust(left=0.3, right=0.98, top=0.85, bottom=0.03)
    head(fig, "What agents said gets in their way",
         "Interview points naming each theme (43 points), with a check against the system prompts and logs")
    return fig


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    OUT.mkdir(parents=True, exist_ok=True)
    motives().savefig(OUT / "motives.png", dpi=300)
    pain_points().savefig(OUT / "pain_points.png", dpi=300)
    print(f"wrote {OUT}/motives.png and pain_points.png")


if __name__ == "__main__":
    main()
