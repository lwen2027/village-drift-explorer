"""Timeline of drift across the goal period, in the style of the findings page's goal atlas.

One row per agent with drift interview points: the agent's name and short goal, its goal window (a pale pill),
each goal-period drift episode as a rust pill from its first to its last drift bout, its interview points
(small triangles) and its total drift hours.

    python3 scripts/figures/plot_drift_timeline.py

Writes figures/drift/drift_timeline.png.
"""

import csv
import datetime as dt
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.font_manager
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

from fig_layout import save, set_frame

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
PERIOD = (dt.datetime(2026, 7, 6), dt.datetime(2026, 10, 3, 23, 59))
# The findings page palette.
SURFACE, INK, MUTED, LINE, WINDOW, RUST = "#ffffff", "#292820", "#747168", "#e4dccb", "#e8ddc5", "#ae5037"
FONT = 7.5
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def ts(value):
    if not value or not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def span(e):
    """First bout start to last bout end, as on the findings page; onset + duration when there are no bouts."""
    raw = e.get("drift_bouts") or []
    if isinstance(raw, str):
        raw = json.loads(raw.replace("'", '"'))
    bouts = [(ts(a), ts(b)) for a, b in raw if ts(a) and ts(b)]
    if bouts:
        return bouts[0][0], bouts[-1][1]
    start = ts(e.get("onset")) or ts(e.get("activity_start_observed_at"))
    end = ts((e.get("drift_end") or {}).get("ended_at"))
    if start and end is None and e.get("duration_seconds") is not None:
        end = start + dt.timedelta(seconds=float(e["duration_seconds"]))
    return (start, end) if start and end else (None, None)


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        axes = {r["episode_id"]: r for r in csv.DictReader(f)}
    episodes = {e["episode_id"]: e for e in json.loads((ROOT / "data/second_audit_v2.json").read_text())["confirmed_episodes"]}
    points = json.loads((ROOT / "data/interview_points_v1.json").read_text())
    points = points if isinstance(points, list) else points.get("agents", points)
    agents = [p["agent"] for p in points]

    spans, hours, count = defaultdict(list), defaultdict(float), defaultdict(int)
    for eid, r in axes.items():
        if r["agent"] in agents and eid in episodes:
            s, e = span(episodes[eid])
            if s:
                spans[r["agent"]].append((s, e))
            hours[r["agent"]] += float(r["hours"] or 0)
            count[r["agent"]] += 1

    src = json.loads((ROOT / "data/source_records.json").read_text())
    names = {a["id"]: a["name"] for a in src["agentRecords"]}
    goals = defaultdict(list)
    for g in src["agentGoalRecords"]:
        if names.get(g["agent_id"]) in agents and g.get("start_time"):
            goals[names[g["agent_id"]]].append(g)
    window, short = {}, {}
    for a in agents:
        mine = sorted(goals.get(a, []), key=lambda g: g["start_time"])
        start = ts(mine[0]["start_time"]) if mine else PERIOD[0]
        window[a] = (max(start, PERIOD[0]), PERIOD[1])
        short[a] = (mine[-1].get("short_name") or mine[-1].get("name")) if mine else ""

    moments = defaultdict(list)
    for a in json.loads((ROOT / "data/interview_answers_v1.json").read_text())["agents"]:
        base = re.sub(r" \([^)]*\)$", "", a["name"])
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) PT", a.get("moment_pt") or "")
        if base in agents and m:
            moments[base].append(dt.datetime.fromisoformat(m.group(1)) + dt.timedelta(hours=7))  # PDT -> UTC
    return agents, spans, hours, count, window, short, moments


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    agents, spans, hours, count, window, short, moments = load()
    order = sorted(agents, key=lambda a: -hours[a])
    fig, ax = plt.subplots(figsize=(7.2, 8.6))
    to_x = mdates.date2num

    for y, a in enumerate(order):
        if y:
            ax.axhline(y - 0.5, color=LINE, linewidth=0.5, zorder=0)
        g0, g1 = window[a]
        # Pills: thick lines with round caps, so a short episode is a dot, like the findings page.
        ax.plot([to_x(g0), to_x(g1)], [y, y], color=WINDOW, linewidth=6.5, solid_capstyle="round", zorder=1)
        for s, e in spans[a]:
            ax.plot([to_x(s), to_x(e)], [y, y], color=RUST, linewidth=3.6, solid_capstyle="round", zorder=2)
        for m in moments.get(a, []):
            ax.plot(to_x(m), y - 0.33, marker="v", markersize=3.4, color=INK, zorder=3, clip_on=False)
        ax.text(-0.012, y - 0.13, a, transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=FONT - 0.3, fontweight="bold", color=INK)
        ax.text(-0.012, y + 0.25, short[a], transform=ax.get_yaxis_transform(), ha="right", va="center",
                fontsize=FONT - 2, color=MUTED)
        ax.text(1.012, y, f"{hours[a]:,.0f} h · {count[a]} ep.", transform=ax.get_yaxis_transform(), va="center",
                fontsize=FONT - 1.2, color=MUTED, family="Menlo")

    ax.set_ylim(len(order) - 0.5, -0.7)
    ax.set_xlim(to_x(PERIOD[0]) - 1, to_x(PERIOD[1]) + 1)
    ax.set_yticks([])
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonthday=(1, 15)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.xaxis.tick_top()
    ax.tick_params(axis="x", labelsize=FONT - 1.2, colors=MUTED, length=3, color=LINE, pad=2)
    for label in ax.get_xticklabels():
        label.set_family("Menlo")
    for side in ("bottom", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["top"].set_color(LINE)
    ax.spines["top"].set_linewidth(0.6)
    set_frame(fig, "When each agent drifted during the goal period (Jul 6 – Oct 2, 2026)",
              "One row per interviewed agent, with its assigned goal under its name, sorted by total drift hours "
              "(right: hours · episodes).", 8)
    handles = [Line2D([], [], color=WINDOW, linewidth=6.5, solid_capstyle="round", label="Assigned to its goal"),
               Line2D([], [], color=RUST, linewidth=3.6, solid_capstyle="round", label="Drift episode (first to last off-goal stretch)"),
               Line2D([], [], marker="v", linestyle="", color=INK, markersize=4, label="Interview point")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.0, 1.022), ncol=3, fontsize=FONT - 1,
              frameon=False, handlelength=1.6, borderaxespad=0, columnspacing=1.4)
    fig.subplots_adjust(left=0.24, right=0.88, top=0.915, bottom=0.03)
    OUT.mkdir(parents=True, exist_ok=True)
    save(fig, OUT / "drift_timeline.png")
    print(f"wrote {OUT}/drift_timeline.png ({len(order)} agents)")


if __name__ == "__main__":
    main()
