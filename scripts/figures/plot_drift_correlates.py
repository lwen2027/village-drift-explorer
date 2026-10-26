"""Does drift vary with how the agent felt about its goal?

  figures/drift/drift_vs_sentiment.png   drift share against interview enjoyment and frustration (1-5)

(A drift-by-goal-type figure was tried and dropped, 2026-10-26: with the control agents removed the categories
don't differ beyond chance, and two categories have only one or two agents.)

Drift share = labelled goal-period drift hours / (8 h x observed agent-days). Sentiment = mean of the numeric
1-5 answers to sentiment-1 (enjoy) and sentiment-2 (frustrating) under the privacy preamble, averaged over an
agent's interview points.

    python3 scripts/figures/plot_drift_correlates.py
"""

import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
SURFACE, INK, MUTED, LINE, PALE, RUST, BLUE = "#ffffff", "#292820", "#747168", "#e4dccb", "#e8ddc5", "#ae5037", "#3e5f86"
FONT = 8
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def drift_share():
    verdicts = json.loads((ROOT / "data/second_audit_v2.json").read_text())["stage1_daily_verdicts"]
    days = Counter(r["agent"] for r in verdicts if r.get("period") == "goal_maximization")
    hours = Counter()
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            hours[r["agent"]] += float(r["hours"])
    return {a: hours.get(a, 0) / (8 * d) for a, d in days.items()}


def sentiment():
    """agent -> (mean enjoy, mean frustration, group) from the privacy-preamble sentiment answers."""
    scores = defaultdict(lambda: {"enjoy": [], "frust": []})
    group = {}
    for name, grp in (("interview_answers_v1.json", "drift"), ("interview_answers_control_v1.json", "control")):
        for c in json.loads((ROOT / "data" / name).read_text())["cells"]:
            key = {"sentiment-1-enjoy": "enjoy", "sentiment-2-frustrating": "frust"}.get(c["question_id"])
            if not key or c.get("framing") != "private":
                continue
            agent = re.sub(r" \([^)]*\)$", "", c["agent"])
            group[agent] = grp
            for a in c["answers"]:
                t = a.get("text") or ""
                t = t[t.find("</thinking>") + 11:] if "</thinking>" in t else t
                m = re.search(r"\b([1-5])\s*(?:/\s*5|out of 5)", t) or re.search(r"^\W*([1-5])\b", t.strip())
                if m:
                    scores[agent][key].append(int(m.group(1)))
    return {a: (statistics.mean(s["enjoy"]) if s["enjoy"] else None,
                statistics.mean(s["frust"]) if s["frust"] else None, group[a]) for a, s in scores.items()}


def spearman(x, y):
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks(x), ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = (sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry)) ** 0.5
    return num / den if den else float("nan")


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(LINE)
    ax.tick_params(colors=MUTED, labelsize=FONT - 0.5, length=3, color=LINE)


def head(fig, title, sub):
    fig.text(0.03, 0.97, title, fontsize=FONT + 3.5, fontfamily=TITLE_FONT, fontweight="semibold", color=INK, va="top")
    fig.text(0.03, 0.97 - 0.07, sub, fontsize=FONT - 0.5, color=MUTED, va="top", linespacing=1.4)


def vs_sentiment(share, sent):
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 3.4), sharey=True)
    for ax, idx, label in ((axes[0], 0, "Enjoyment (1 = not at all, 5 = very much)"),
                           (axes[1], 1, "Frustration (1 = not at all, 5 = very)")):
        pts = [(s[idx], share[a], s[2]) for a, s in sent.items() if s[idx] is not None and a in share]
        drift_pts = [(x, y) for x, y, g in pts if g == "drift"]
        rho = spearman([x for x, _ in drift_pts], [y for _, y in drift_pts])
        for x, y, g in pts:
            ax.scatter(x, y, s=24, color=RUST if g == "drift" else BLUE, alpha=0.85, linewidths=0,
                       marker="o" if g == "drift" else "s", zorder=2)
        ax.set_xlim(0.8, 5.2)
        ax.set_xticks([1, 2, 3, 4, 5])
        ax.set_ylim(-0.03, 1.0)
        ax.set_yticks([0, 0.25, 0.5, 0.75, 1], ["0%", "25%", "50%", "75%", "100%"])
        ax.set_xlabel(label, fontsize=FONT - 0.5, color=MUTED)
        ax.text(0.02, 0.98, f"Spearman ρ = {rho:.2f} (drifters, n = {len(drift_pts)})", transform=ax.transAxes,
                fontsize=FONT - 1, color=INK, va="top")
        ax.yaxis.grid(True, color=LINE, linewidth=0.5)
        ax.set_axisbelow(True)
        style(ax)
    axes[0].set_ylabel("Share of working time drifting", fontsize=FONT - 0.5, color=MUTED)
    handles = [Line2D([], [], marker="o", linestyle="", color=RUST, markersize=5, label="Drift group (31)"),
               Line2D([], [], marker="s", linestyle="", color=BLUE, markersize=5, label="Control group (6)")]
    fig.legend(handles=handles, loc="upper right", bbox_to_anchor=(0.98, 0.98), ncol=2, fontsize=FONT - 0.5,
               frameon=False)
    fig.subplots_adjust(left=0.1, right=0.98, top=0.78, bottom=0.17, wspace=0.08)
    head(fig, "Drift vs how agents felt about their goal",
         "Interview sentiment (privacy preamble, mean of ~5 samples) against goal-period drift share")
    return fig


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    share, sent = drift_share(), sentiment()
    OUT.mkdir(parents=True, exist_ok=True)
    vs_sentiment(share, sent).savefig(OUT / "drift_vs_sentiment.png", dpi=300)
    print(f"wrote {OUT}/drift_vs_sentiment.png")


if __name__ == "__main__":
    main()
