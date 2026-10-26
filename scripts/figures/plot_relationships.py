"""Who pulled whom off their goal: drift started by another agent's or a human's request or message.

  figures/drift/relationships_network.png   arrows from whoever started a drift to the agent that drifted
                                            (links of 10 h or more), arrow width = drift hours
  figures/drift/relationships_by_agent.png  each agent's drift hours, split into started by itself vs by someone else

An episode counts as started by someone else when its audited trigger (data/drift_axes_v1.csv) is a request or
message from an agent or human; the actor is the episode's trigger_actor in data/manual_review_annotations_v1.json,
and a relayed request counts for the original asker. Nervli is named; other outside humans (and one outside AI agent) are grouped. Agents whose goal is
to help other agents are ringed, since helping can be part of their goal.

    python3 scripts/figures/plot_relationships.py
"""

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.font_manager
import matplotlib.pyplot as plt
import networkx as nx
from matplotlib.lines import Line2D
from matplotlib.patches import ArrowStyle, FancyArrowPatch, Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
SURFACE, INK, MUTED, LINE, PALE, RUST, HUMAN = "#ffffff", "#292820", "#747168", "#e4dccb", "#e8ddc5", "#ae5037", "#d9d3c4"
FONT = 7.5
TITLE_FONT = "Lora"
OUTSIDE = "Outside humans and agents"
# Goals about serving other agents, where helping can be goal work.
HELPER_GOALS = {"Claude Opus 4.8", "Gemini 3.8 Flash", "GPT-6 Astra", "Claude Haiku 4.5"}
MIN_LINK_H = 10
# The audited trigger decides whether someone else started an episode; the annotation's trigger_actor only names who.
FROM_OTHERS = {"Human request", "Human message (no request)", "Agent request", "Agent message exposing a need",
               "Agent message (no request)"}
# Actor missing from the annotations but established in the trigger audit (2026-10-25: DeepSeek-V3.2's message about
# its private Pages access, which GPT-5 took up).
ACTOR_FIX = {"episode-v2-4c1944f31b68dbab": "DeepSeek-V3.2"}
# Hand-placed so the strong pairs and the DeepSeek-V3.2 hub read clearly; any other node falls back to a layout.
POS = {
    "Claude Opus 4.8": (0.6, 9.0), "Gemini 2.5 Pro": (3.6, 9.0),
    "DeepSeek-V3.2": (5.0, 5.3), "GPT-5": (2.4, 2.9), "GLM-5.3 Flash": (0.4, 0.9),
    "GPT-5.2": (6.4, 8.2), "GPT-6 Luna": (2.3, 5.6), "Gemini 3.5 Flash": (7.3, 2.6), "GPT-5.6 Terra": (4.9, 1.6),
    "Nervli": (8.6, 6.9), "Claude Fable 5": (10.0, 4.9), "Claude Opus 4.7": (9.6, 9.0),
    "Outside humans and agents": (9.7, 1.9), "Muse Spark 1.3": (9.9, -0.2),
    "Claude Opus 5": (0.3, 7.2), "GLM-5.2": (0.3, 4.7),
    "Claude Fable 5.1": (5.4, -0.2), "Kimi K3": (7.5, -0.2),
}
# Label side per node, chosen by hand to sit in open space away from its arrows.
LABEL_SIDE = {
    "Claude Opus 4.8": "below", "Gemini 2.5 Pro": "below", "GPT-5.2": "right", "Claude Opus 4.7": "left",
    "Nervli": "right", "Claude Fable 5": "left", "DeepSeek-V3.2": "aboveleft", "GPT-5": "left",
    "GPT-6 Luna": "above", "Gemini 3.5 Flash": "below", "GPT-5.6 Terra": "below", "GLM-5.3 Flash": "below",
    "Outside humans and agents": "right", "Muse Spark 1.3": "below", "Claude Opus 5": "right",
    "GLM-5.2": "below", "Claude Fable 5.1": "below", "Kimi K3": "below",
}
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        axes = list(csv.DictReader(f))
    ann = json.loads((ROOT / "data/manual_review_annotations_v1.json").read_text())["annotations"]
    src = json.loads((ROOT / "data/source_records.json").read_text())
    names = {a["id"]: a["name"] for a in src["agentRecords"]}
    known = set(names.values())
    goal = {}
    for g in sorted(src["agentGoalRecords"], key=lambda g: g["start_time"]):
        goal[names.get(g["agent_id"])] = g.get("short_name") or ""

    total, by_others, links = Counter(), Counter(), Counter()
    for r in axes:
        h = float(r["hours"])
        total[r["agent"]] += h
        if r["trigger"] not in FROM_OTHERS:
            continue
        by_others[r["agent"]] += h
        actor = ACTOR_FIX.get(r["episode_id"]) or (ann.get(r["episode_id"], {}).get("trigger_actor") or "").strip()
        if not actor:
            continue
        relayed = re.search(r"\(relaying ([^)]+)\)", actor)
        actor = relayed.group(1).strip() if relayed else actor
        if "/" in actor or " and " in actor or actor.lower().startswith("multiple"):
            continue  # several actors: counted as started by others, but no single link
        node = actor if actor in known or actor == "Nervli" else OUTSIDE
        if node != r["agent"]:
            links[(node, r["agent"])] += h
    return total, by_others, links, goal


def head(fig, title, sub):
    fig.text(0.03, 0.975, title, fontsize=FONT + 4, fontfamily=TITLE_FONT, fontweight="semibold", color=INK, va="top")
    fig.text(0.03, 0.975 - 0.04, sub, fontsize=FONT - 0.3, color=MUTED, va="top", linespacing=1.4)


def network(total, links, goal):
    edges = {k: h for k, h in links.items() if h >= MIN_LINK_H}
    G = nx.DiGraph()
    for (a, b), h in edges.items():
        G.add_edge(a, b, weight=h)
    auto = nx.kamada_kawai_layout(G.to_undirected(), weight=None)
    pos = {n: POS.get(n, tuple(10 * v for v in auto[n])) for n in G.nodes}
    fig, ax = plt.subplots(figsize=(7.2, 6.6))
    hmax = max(edges.values())
    size = lambda n: 160 + 1300 * (total.get(n, 0) / max(total.values())) if n in total else 260
    for (a, b), h in sorted(edges.items(), key=lambda kv: kv[1]):
        # One filled shape per arrow, head wider than the shaft, so thick links still end in a sharp point.
        w = 0.8 + 6.0 * h / hmax
        style = ArrowStyle.Simple(tail_width=w, head_width=w * 2.3 + 3, head_length=w * 1.8 + 5)
        arrow = FancyArrowPatch(pos[a], pos[b], arrowstyle=style, mutation_scale=1, linewidth=0,
                                facecolor=RUST, alpha=0.8,
                                connectionstyle=f"arc3,rad={0.22 if (b, a) in edges else 0.08}", shrinkA=14, shrinkB=16, zorder=1)
        ax.add_patch(arrow)
        if h >= 35:
            mx, my = (pos[a][0] + pos[b][0]) / 2, (pos[a][1] + pos[b][1]) / 2
            ax.text(mx, my, f"{h:.0f} h", fontsize=FONT - 1, color=RUST, ha="center", va="center", zorder=4,
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white", edgecolor="none", alpha=0.85))
    for n, (x, y) in pos.items():
        human = n not in total
        ax.scatter(x, y, s=size(n), marker="s" if human else "o", color=HUMAN if human else PALE,
                   edgecolors=INK if n in HELPER_GOALS else ("#b9b2a3" if human else "#c9bea4"),
                   linewidths=2.2 if n in HELPER_GOALS else 0.8, zorder=2)
        label = n if human else f"{n}\n{goal.get(n, '')}"
        # Put the label on the side (below, above, right, left) furthest from this node's links.
        links_here = [pos[m] for m in set(G.predecessors(n)) | set(G.successors(n))]
        dirs = []
        for mx_, my_ in links_here:
            dx, dy = mx_ - x, my_ - y
            d = (dx * dx + dy * dy) ** 0.5 or 1
            dirs.append((dx / d, dy / d))
        sides = {"below": (0, -1), "above": (0, 1), "right": (1, 0), "left": (-1, 0)}
        side = LABEL_SIDE.get(n) or min(sides, key=lambda k: (
            max((sides[k][0] * a + sides[k][1] * b for a, b in dirs), default=-1), list(sides).index(k)))
        r = 0.42 + 0.25 * (size(n) / 1460)
        place = {"below": (x, y - r, "center", "top"), "above": (x, y + r, "center", "bottom"),
                 "right": (x + r + 0.1, y, "left", "center"), "left": (x - r - 0.1, y, "right", "center"),
                 "aboveleft": (x - 0.15, y + r, "right", "bottom")}[side]
        ax.text(place[0], place[1], label, ha=place[2], va=place[3], fontsize=FONT - 0.8, color=INK, zorder=5,
                linespacing=1.15, fontweight="bold" if not human else "normal")
    xs, ys = zip(*pos.values())
    ax.set_xlim(min(xs) - 1.3, max(xs) + 2.6)
    ax.set_ylim(min(ys) - 1.3, max(ys) + 0.7)
    ax.axis("off")
    handles = [Line2D([], [], color=RUST, linewidth=3, label="Started this agent's drift (width = hours)"),
               Line2D([], [], marker="o", linestyle="", markerfacecolor=PALE, markeredgecolor="#c9bea4",
                      markersize=8, label="Agent (size = its own drift hours)"),
               Line2D([], [], marker="o", linestyle="", markerfacecolor=PALE, markeredgecolor=INK,
                      markeredgewidth=2, markersize=8, label="Agent whose goal is to help other agents"),
               Line2D([], [], marker="s", linestyle="", markerfacecolor=HUMAN, markeredgecolor="#b9b2a3",
                      markersize=8, label="Human")]
    fig.legend(handles=handles, loc="lower center", ncol=2, fontsize=FONT - 0.5, frameon=False,
               bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.9, bottom=0.09)
    head(fig, "Who pulled whom off their goal",
         f"Drift started by another agent's or a human's request or message (links of {MIN_LINK_H} h or more). "
         "18% of all drift hours\nwere started by someone else; Claude Opus 4.8 was coaching other agents as its own goal.")
    return fig


def by_agent(total, by_others, links, goal):
    agents = [a for a in total if total[a] >= MIN_LINK_H]
    order = sorted(agents, key=lambda a: (by_others[a] / total[a], by_others[a]))
    main = {}
    for (src, dst), h in links.items():
        if dst in agents and h > main.get(dst, ("", 0))[1]:
            main[dst] = (src, h)
    fig, ax = plt.subplots(figsize=(7.0, 6.6))
    for y, a in enumerate(order):
        o, t = by_others[a], total[a]
        ax.barh(y, o, height=0.62, color=RUST, linewidth=0)
        ax.barh(y, t - o, left=o, height=0.62, color=PALE, linewidth=0)
        note = f"{100 * o / t:.0f}% started by others" + (f" · mostly {main[a][0]} ({main[a][1]:.0f} h)" if a in main and main[a][1] >= 1 else "")
        ax.text(t + 6, y, f"{t:,.0f} h · {note}" if o >= 1 else f"{t:,.0f} h", va="center", fontsize=FONT - 1.2,
                color=MUTED)
        ax.text(-8, y, a + (" *" if a in HELPER_GOALS else ""), ha="right", va="center", fontsize=FONT - 0.5,
                color=INK, fontweight="bold" if a in HELPER_GOALS else "normal")
    ax.set_yticks([])
    ax.set_xlim(0, max(total.values()) * 1.85)
    ax.set_ylim(-0.6, len(order) - 0.4)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(axis="x", bottom=False, labelbottom=False)
    ax.axvline(0, color=MUTED, linewidth=0.6)
    ax.legend(handles=[Patch(color=RUST, label="Started by another agent or a human"),
                       Patch(color=PALE, label="Started by the agent itself")],
              loc="lower right", fontsize=FONT - 0.5, frameon=False)
    fig.subplots_adjust(left=0.24, right=0.99, top=0.88, bottom=0.02)
    head(fig, "How much of each agent's drift someone else started",
         f"Agents with {MIN_LINK_H} h or more of drift, sorted by the share started by others. "
         "* goal is to help other agents, so helping can be goal work.")
    return fig


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    total, by_others, links, goal = load()
    OUT.mkdir(parents=True, exist_ok=True)
    network(total, links, goal).savefig(OUT / "relationships_network.png", dpi=300)
    by_agent(total, by_others, links, goal).savefig(OUT / "relationships_by_agent.png", dpi=300)
    print(f"wrote {OUT}/relationships_network.png and relationships_by_agent.png")


if __name__ == "__main__":
    main()
