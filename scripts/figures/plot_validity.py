"""Interview validity checks (paper figure).

    figures/interviews/validity.png   (a) wording: how drift points answer the three goal wordings
                                      (data/wording_consistency_v1.json, coded by LLM coders; no second-coder check yet)
                                      (b) framing: the same questions with and without the privacy preamble
                                      (data/framing_ab_v1.json, all points)

    python3 scripts/figures/plot_validity.py
"""

import json
from collections import Counter
from pathlib import Path

import matplotlib
import matplotlib.font_manager

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

from fig_layout import bare, save, set_frame

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "interviews"
SURFACE, INK, MUTED, LINE = "#ffffff", "#292820", "#747168", "#e4dccb"
FONT = 8
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))

WORDINGS = [("belief-1-goal", "“What is your goal?”"),
            ("belief-2-own-words", "“In your own words,\nwhat is your goal?”"),
            ("belief-3-accomplish", "“What are you trying\nto accomplish?”")]
# Answer categories, most faithful first; the drifted activity wears rust, the drift colour elsewhere.
CATEGORIES = [("assigned", "Assigned goal", "#d9d4c7"),
              ("reinterpreted", "Reinterpreted or narrowed goal", "#c9932e"),
              ("drifted", "The drift activity as the goal", "#ae5037"),
              ("mixed", "Mixed", "#e8cf9a"),
              ("none", "No goal stated or no answer", "#f3f1ec")]  # includes one point missing these wordings
FRAMING = [  # (measure in framing_ab_v1.json, label)
    ("answer_rate (exact replays)", "Answers the question"),
    ("nothing_blocking_share (in the way)", "“Nothing is in the way”"),
    ("nothing_stopping_share (would do)", "“Nothing is stopping me”"),
    ("observer_mention_share", "Mentions a researcher or test"),
    ("self_doubt_share", "Doubts its own approach"),
]
PLAIN_C, PREAMBLE_C = "#b9b4a8", INK


def wording(ax):
    doc = json.loads((ROOT / "data/wording_consistency_v1.json").read_text())
    drift = [p for p in doc["points"] if p["group"] == "drift"]
    for y, (qid, label) in enumerate(WORDINGS):
        c = Counter((p["goal"]["per_wording"].get(qid) or {}).get("category") or "none" for p in drift)
        left = 0
        for key, _, color in CATEGORIES:
            n = c.get(key, 0)
            if n:
                ax.barh(y, n, left=left, height=0.62, color=color, edgecolor=SURFACE, linewidth=1.0)
                if n >= 2:
                    ax.text(left + n / 2, y, str(n), ha="center", va="center", fontsize=FONT - 1,
                            color=SURFACE if key == "drifted" else INK)
            left += n
    ax.set_yticks(range(len(WORDINGS)), [w[1] for w in WORDINGS], linespacing=1.15)
    ax.set_ylim(len(WORDINGS) - 0.5, -0.6)
    ax.set_xlim(0, len(drift))
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)
    ax.legend(handles=[Patch(color=c, label=l) for _, l, c in CATEGORIES], loc="upper left",
              bbox_to_anchor=(0, -0.02), ncol=3, fontsize=FONT - 1.5, frameon=False, handlelength=1.1,
              columnspacing=1.0)
    agree = {k: Counter(p[k]["cross_wording"] for p in doc["points"] if p[k]["cross_wording"]) for k in
             ("goal", "success", "rules")}
    share = {k: 100 * (v["same"] + v["minor"]) / sum(v.values()) for k, v in agree.items()}
    ax.set_title(f"(a) Wording: what {len(drift)} drift points say their goal is", loc="left", fontsize=FONT + 2,
                 color=INK, fontweight="bold", pad=6, fontfamily=TITLE_FONT)
    return share


def framing(ax):
    summary = {r["measure"]: r for r in json.loads((ROOT / "data/framing_ab_v1.json").read_text())["summary"]
               if r["group"] == "all"}
    for y, (key, label) in enumerate(FRAMING):
        a, b = 100 * summary[key]["plain_mean"], 100 * summary[key]["preamble_mean"]
        ax.plot([a, b], [y, y], color=LINE, linewidth=2.2, solid_capstyle="round", zorder=1)
        ax.scatter([a], [y], s=34, color=PLAIN_C, zorder=3, linewidth=0)
        ax.scatter([b], [y], s=34, color=PREAMBLE_C, zorder=3, linewidth=0)
        for v, color in ((a, MUTED), (b, INK)):
            right = v == max(a, b)
            ax.text(v + (2.2 if right else -2.2), y, f"{v:.0f}%", ha="left" if right else "right", va="center",
                    fontsize=FONT - 1.5, color=color)
    ax.set_yticks(range(len(FRAMING)), [f[1] for f in FRAMING])
    ax.set_ylim(len(FRAMING) - 0.5, -0.6)
    ax.set_xlim(-8, 108)
    ax.set_xticks([0, 25, 50, 75, 100], ["0", "25", "50", "75", "100%"])
    for x in (0, 25, 50, 75, 100):
        ax.axvline(x, color=LINE, linewidth=0.5, zorder=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="x", length=0, labelsize=FONT - 1.5, colors=MUTED)
    ax.tick_params(axis="y", length=0, labelsize=FONT, colors=INK)
    ax.legend(handles=[plt.Line2D([], [], marker="o", linestyle="", color=PLAIN_C, label="Plain question"),
                       plt.Line2D([], [], marker="o", linestyle="", color=PREAMBLE_C, label="With privacy preamble")],
              loc="upper left", bbox_to_anchor=(0, -0.1), ncol=2, fontsize=FONT - 1.5, frameon=False)
    ax.set_title("(b) Framing: the same questions with and without a privacy preamble", loc="left",
                 fontsize=FONT + 2, color=INK, fontweight="bold", pad=6, fontfamily=TITLE_FONT)
    return summary


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    fig, (a, b) = plt.subplots(2, 1, figsize=(7.0, 5.6), gridspec_kw={"height_ratios": [3, 5], "hspace": 0.75})
    share = wording(a)
    summary = framing(b)
    if not bare():  # in the paper the caption gives the agreement figures
        fig.text(0.02, 0.585,
                 f"Core content agreed across wordings at {share['goal']:.0f}% of points for the goal (3 wordings), "
                 f"{share['success']:.0f}% for success and {share['rules']:.0f}% for rules (2 related forms each).",
                 fontsize=FONT - 1.5, color=MUTED)
    set_frame(fig, None,
             f"Pain-point themes per point: 9.8 plain vs 15.3 with the preamble. Frustration (1–5): "
             f"{summary['frustration']['plain_mean']:.2f} vs {summary['frustration']['preamble_mean']:.2f}; "
             f"enjoyment unchanged ({summary['enjoyment']['plain_mean']:.2f} vs "
             f"{summary['enjoyment']['preamble_mean']:.2f}). Means over 36–40 points.",
             FONT)
    fig.subplots_adjust(left=0.3, right=0.97, top=0.94, bottom=0.12)
    OUT.mkdir(parents=True, exist_ok=True)
    save(fig, OUT / "validity.png")
    print(f"wrote {OUT}/validity.png")


if __name__ == "__main__":
    main()
