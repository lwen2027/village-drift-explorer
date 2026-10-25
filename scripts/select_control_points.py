#!/usr/bin/env python3
"""Select on-goal interview points for agents that had a personal goal but barely drifted (the control group).

The drifting agents are interviewed just before their first drift onset, which came a median of 9 days into
their goal. Each control agent is interviewed once, at the same offset: the last logged turn at or before noon PT
on day 9 of its goal (the next Monday when that day is a weekend), passing over session-end memory steps. An agent
whose day 9 falls after the data ends is interviewed on day 2 instead. A moment inside one of the agent's few drift episodes moves to the last turn before that episode began,
so every control point is on goal.

Needs VILLAGE_DB_URI (read access to the village database) and psycopg. Writes
data/interview_points_control_v1.json, in the same format as data/interview_points_v1.json so the batch
runner can read it.
"""

from __future__ import annotations

import datetime
import json
import os
import sys

import psycopg

from select_interview_points import (
    BUNDLE,
    PERIOD,
    PT,
    ROOT,
    agent_ids,
    call_at_or_before,
    logged_action,
    pt,
    span,
    ts,
)

SOURCE = ROOT / "data" / "source_records.json"
OUT_JSON = ROOT / "data" / "interview_points_control_v1.json"
OFFSET_DAYS, FALLBACK_DAYS = 9, 2
NOON_PT = datetime.time(12, 0)
DATA_END = datetime.datetime.fromisoformat(PERIOD[1]).replace(hour=23, minute=59)
# Agents with a personal goal and under ~2 h of drift. Claude Haiku 4.5 is left out: it has ~19 h of drift
# across all periods, too much for a clean control.
CONTROL = ["GPT-6 Sol", "GPT-6.1 Sol", "Grok 4.5", "Claude Sonnet 5.5", "Claude Opus 5", "Claude Opus 4.6"]
TYPE, TYPE_LABEL = "on_goal_control", "On goal (control)"


def goal_records() -> dict:
    src = json.loads(SOURCE.read_text())
    names = {a["id"]: a["name"] for a in src["agentRecords"]}
    out = {}
    for g in src["agentGoalRecords"]:
        out.setdefault(names.get(g["agent_id"]), []).append(g)
    return out


def drift_spans() -> tuple:
    """(agent -> [(start, end, episode id)] for every confirmed episode in any period (naive UTC),
    agent -> goal-maximization drift hours)."""
    out, hours = {}, {}
    for e in json.loads(BUNDLE.read_text())["confirmed_episodes"]:
        a, b = span(e)
        if a and b:
            out.setdefault(e["agent"], []).append((a, b, e["episode_id"]))
        if e.get("period") == "goal_maximization":
            hours[e["agent"]] = hours.get(e["agent"], 0) + float(e.get("duration_seconds") or 0) / 3600
    return out, hours


def main() -> None:
    uri = os.environ.get("VILLAGE_DB_URI")
    if not uri:
        sys.exit("VILLAGE_DB_URI is not set")
    goals, (spans, hours) = goal_records(), drift_spans()
    result = []
    with psycopg.connect(uri) as conn:
        for name in CONTROL:
            ids = agent_ids(conn, name)
            mine = sorted(goals.get(name, []), key=lambda g: g["start_time"])
            if not mine:
                print(f"{name}: no goal record, skipped")
                continue
            start = ts(mine[0]["start_time"])
            points = []
            for days in (OFFSET_DAYS, FALLBACK_DAYS):
                day = (start.replace(tzinfo=datetime.timezone.utc).astimezone(PT) + datetime.timedelta(days=days)).date()
                while day.weekday() >= 5:  # the Village doesn't run at weekends
                    day += datetime.timedelta(days=1)
                moment = datetime.datetime.combine(day, NOON_PT, PT).astimezone(datetime.timezone.utc).replace(tzinfo=None)
                if moment <= DATA_END:
                    break
            else:
                print(f"{name}: goal too short for day {FALLBACK_DAYS}, skipped")
                continue
            flag = ""
            for a, b, eid in spans.get(name, []):
                if a <= moment <= b:
                    moment, flag = a, f"moved before drift episode {eid}"
            row = call_at_or_before(conn, ids, moment)
            # A session-end memory step isn't a working turn; use the turn before it.
            while row and logged_action(row[2]) == "consolidate":
                row = call_at_or_before(conn, ids, row[1] - datetime.timedelta(seconds=10))
            goal = max((g for g in mine if ts(g["start_time"]) <= moment), key=lambda g: g["start_time"])
            points.append({
                "rule": f"control_day{days}",
                "episode_id": None,
                "category": TYPE,
                "moment_utc": moment.isoformat(),
                "moment_pt": pt(moment),
                "call_id": str(row[0]) if row else None,
                "call_at_pt": pt(row[1]) if row else "",
                "call_action": logged_action(row[2]) if row else "",
                "why": f"on goal, day {days} of its goal ({goal['short_name']}), noon PT",
                "flag": flag if row else (flag + "; no logged turn found").strip("; "),
                "track": 0,
                "assigned_goal": goal["name"],
            })
            track = {"type": TYPE, "type_label": TYPE_LABEL, "hours": 0, "episodes": 0, "shape": "control",
                     "spells": [], "points": points}
            result.append({
                "agent": name,
                "main_type": TYPE,
                "main_type_label": TYPE_LABEL,
                "main_type_hours": 0,
                "main_type_episodes": 0,
                "total_hours": round(hours.get(name, 0), 1),
                "shape": "control",
                "spells": [],
                "goal": mine[-1]["name"],
                "goal_start_pt": pt(start),
                "tracks": [track],
                "points": points,
            })
    OUT_JSON.write_text(json.dumps({"schema_version": 3, "agents": result}, indent=1) + "\n", encoding="utf-8")
    for r in result:
        for p in r["points"]:
            print(f"{r['agent']:18} {p['rule']:14} {p['call_at_pt']:24} {p['call_action']:24} {p['flag']}")
    print(f"{len(result)} agents, {sum(len(r['points']) for r in result)} points → {OUT_JSON.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
