"""Timeline of drift across the goal period: one row per drifting agent, drift bouts in red.

Each row shows the agent's goal period (light band), every drift bout of its goal-period episodes in
data/drift_axes_v1.csv (red, at true times from data/second_audit_v2.json; a minimum width keeps short bouts
visible), its interview points (black triangles) and its total drift hours. Weekends are shaded.

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
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "figures" / "drift"
PERIOD = (dt.datetime(2026, 7, 6), dt.datetime(2026, 10, 3, 23, 59))
SURFACE, INK, INK_2, BAND, WEEKEND = "#ffffff", "#0b0b0b", "#52514e", "#e9e8e4", "#f6f5f2"
RED = "#d93a39"
MIN_WIDTH_H = 2.5  # hours; keeps a 20-minute bout visible at this scale
FONT = 7.5
TITLE_FONT = "Lora"
for _f in (Path(__file__).parent / "fonts").glob("*.ttf"):
    matplotlib.font_manager.fontManager.addfont(str(_f))


def ts(value):
    if not value or not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    t = dt.datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    return t.astimezone(dt.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def bouts(e):
    raw = e.get("drift_bouts") or []
    if isinstance(raw, str):
        raw = json.loads(raw.replace("'", '"'))
    out = [(ts(a), ts(b)) for a, b in raw if ts(a) and ts(b)]
    if out:
        return out
    start = ts(e.get("onset")) or ts(e.get("activity_start_observed_at"))
    end = ts((e.get("drift_end") or {}).get("ended_at"))
    if start and end is None and e.get("duration_seconds") is not None:
        end = start + dt.timedelta(seconds=float(e["duration_seconds"]))
    return [(start, end)] if start and end else []


def load():
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        axes = {r["episode_id"]: r for r in csv.DictReader(f)}
    episodes = {e["episode_id"]: e for e in json.loads((ROOT / "data/second_audit_v2.json").read_text())["confirmed_episodes"]}
    points = json.loads((ROOT / "data/interview_points_v1.json").read_text())
    points = points if isinstance(points, list) else points.get("agents", points)
    agents = [p["agent"] for p in points]

    drift, hours = defaultdict(list), defaultdict(float)
    for eid, r in axes.items():
        if r["agent"] in agents and eid in episodes:
            drift[r["agent"]] += bouts(episodes[eid])
            hours[r["agent"]] += float(r["hours"] or 0)

    src = json.loads((ROOT / "data/source_records.json").read_text())
    names = {a["id"]: a["name"] for a in src["agentRecords"]}
    starts = defaultdict(list)
    for g in src["agentGoalRecords"]:
        if names.get(g["agent_id"]) in agents and g.get("start_time"):
            starts[names[g["agent_id"]]].append(ts(g["start_time"]))
    goal = {}
    for a in agents:
        first = min([t for t in starts.get(a, []) if t] or [PERIOD[0]])
        goal[a] = (max(first, PERIOD[0]), PERIOD[1])

    moments = defaultdict(list)
    for a in json.loads((ROOT / "data/interview_answers_v1.json").read_text())["agents"]:
        base = re.sub(r" \([^)]*\)$", "", a["name"])
        m = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}) PT", a.get("moment_pt") or "")
        if base in agents and m:
            local = dt.datetime.fromisoformat(m.group(1))
            # PT is UTC-7 throughout the period (PDT until Nov 1).
            moments[base].append(local + dt.timedelta(hours=7))
    return agents, drift, hours, goal, moments


def main():
    plt.rcParams.update({"font.family": "Helvetica Neue", "figure.facecolor": SURFACE, "axes.facecolor": SURFACE})
    agents, drift, hours, goal, moments = load()
    order = sorted(agents, key=lambda a: -hours[a])
    fig, ax = plt.subplots(figsize=(7.2, 6.4))

    day = PERIOD[0]
    while day < PERIOD[1]:
        if day.weekday() >= 5:
            ax.axvspan(day, day + dt.timedelta(days=1), color=WEEKEND, zorder=0, linewidth=0)
        day += dt.timedelta(days=1)

    min_w = dt.timedelta(hours=MIN_WIDTH_H)
    for y, a in enumerate(order):
        g0, g1 = goal[a]
        ax.barh(y, mdates.date2num(g1) - mdates.date2num(g0), left=mdates.date2num(g0), height=0.56,
                color=BAND, linewidth=0, zorder=1)
        for s, e in drift[a]:
            width = max(e - s, min_w)
            ax.barh(y, mdates.date2num(s + width) - mdates.date2num(s), left=mdates.date2num(s), height=0.56,
                    color=RED, linewidth=0, zorder=2)
        for m in moments.get(a, []):
            ax.plot(m, y - 0.42, marker="v", markersize=3.6, color=INK, zorder=3, clip_on=False)
        ax.text(1.005, y, f"{hours[a]:,.0f} h", transform=ax.get_yaxis_transform(), va="center",
                fontsize=FONT - 1, color=INK_2)

    ax.set_yticks(range(len(order)), order, fontsize=FONT - 0.5, color=INK)
    ax.set_ylim(len(order) - 0.4, -0.9)
    ax.set_xlim(PERIOD[0], PERIOD[1])
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.tick_params(axis="x", which="major", labelsize=FONT, colors=INK_2, length=4, color=INK_2)
    ax.tick_params(axis="x", which="minor", length=2, color=INK_2)
    ax.tick_params(axis="y", length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(INK_2)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.set_title("Drift across the goal period (6 Jul – 3 Oct 2026)", loc="left", fontsize=FONT + 2,
                 fontfamily=TITLE_FONT, fontweight="semibold", color=INK, pad=14)
    handles = [Patch(color=BAND, label="Goal period"), Patch(color=RED, label="Drift"),
               Line2D([], [], marker="v", linestyle="", color=INK, markersize=4, label="Interview point"),
               Patch(facecolor=WEEKEND, edgecolor=BAND, linewidth=0.6, label="Weekend")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=4, fontsize=FONT - 0.5,
              frameon=False, handlelength=1.2, borderaxespad=0.1, columnspacing=1.4)
    fig.subplots_adjust(left=0.2, right=0.93, top=0.92, bottom=0.05)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "drift_timeline.png", dpi=300)
    print(f"wrote {OUT}/drift_timeline.png ({len(order)} agents)")


if __name__ == "__main__":
    main()
