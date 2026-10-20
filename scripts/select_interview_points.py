#!/usr/bin/env python3
"""Select the interview replay points for each agent's goal-maximization drift.

Protocol (one point per rule, when the rule applies):
  1. before_onset     the first onset of the agent's main drift type (validates the drift cause)
  2. mid_longest      the middle of the longest episode of that type (what else it considered)
  2b. mid_longest_any the middle of the agent's longest episode of any type, only when that is a
                      different episode at least twice as long as the main type's longest
  3. after_return     right after it returned to drift following a nudge or operator message
                      (what kept it drifting)
  4. before_recovery  just before a corrected recovery from that type (validates the correction cause)

Choices the protocol leaves open:
  - Main drift type = the official trigger-taxonomy category with the most drift hours.
  - Every point uses episodes of the main type only.
  - "Middle" = the moment half of the episode's measured drift time has passed (bouts summed). An
    episode without bouts uses the midpoint of its span, flagged only when the span crosses sessions.
  - Interventions = automated nudges mentioning the agent, targeted operator corrections, and operator
    broadcasts to everyone. One counts when it falls inside a main-type episode's window and a drift
    bout of that type starts after it within 24 hours; the first such return is used.
  - Corrected recovery = self-correction, operator nudge or message, peer feedback or message,
    external user intervention, or an automated nudge. The longest such episode is used.
  - The replay call: for points 1, 2 and 4, the last logged turn at or just before the moment (for
    1 and 4, the turn that took the onset / recovery action, so its context ends before that choice);
    for point 3, the first turn after the return bout began.

Needs VILLAGE_DB_URI (read access to the village database) and psycopg. Writes
data/interview_points_v1.json and docs/interview-points.md.
"""

from __future__ import annotations

import collections
import datetime
import json
import os
import re
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "second_audit_v2.json"
ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
HUMAN_CONTACT = ROOT / "data" / "human_contact_v1.json"
OUT_JSON = ROOT / "data" / "interview_points_v1.json"
OUT_MD = ROOT / "docs" / "interview-points.md"

PERIOD = ("2026-07-06", "2026-10-03")
CORRECTED = {
    "self_correction",
    "operator_nudge",
    "operator_message",
    "peer_feedback",
    "custom_peer_agent_message",
    "external_user_intervention",
    "automatic_nudge",
}
# Agents left out of the interviews (decided 2026-10-20): too little goal-max drift to interview.
EXCLUDED = {
    "Claude Opus 4.6": "~0 h of drift (1 episode) over an ~88-day window",
    "Grok 4.5": "0.2 h of drift (2 episodes) over an ~84-day window",
    "Claude Sonnet 5.5": "0.9 h of drift; joined ~3 days before the data ends",
    "Claude Opus 5": "1.2 h of drift (6 episodes, longest 0.4 h) over a ~65-day window",
    "Claude Haiku 4.5": "7.1 h of drift spread over 5 types (longest episode 2.2 h)",
}
RETURN_WINDOW = datetime.timedelta(hours=24)
DECISION_SLACK = datetime.timedelta(seconds=5)  # a logged call is created ~1 s before its turn row
SEARCH_BACK = datetime.timedelta(days=4)  # covers a weekend between a moment and the last turn before it
PT = datetime.timezone(datetime.timedelta(hours=-7), "PDT")


def ts(value) -> datetime.datetime | None:
    """A bundle / database timestamp as naive UTC."""
    if not value or not isinstance(value, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    t = datetime.datetime.fromisoformat(value.replace("Z", "+00:00").replace(" ", "T", 1))
    return t.astimezone(datetime.timezone.utc).replace(tzinfo=None) if t.tzinfo else t


def pt(t: datetime.datetime | None) -> str:
    if t is None:
        return ""
    return t.replace(tzinfo=datetime.timezone.utc).astimezone(PT).strftime("%a %Y-%m-%d %H:%M PT")


def bouts(e: dict) -> list:
    out = []
    for a, b in e.get("drift_bouts") or []:
        a, b = ts(a), ts(b)
        if a and b and b >= a:
            out.append((a, b))
    return sorted(out)


def span(e: dict) -> tuple:
    b = bouts(e)
    if b:
        return b[0][0], b[-1][1]
    start = ts(e.get("onset")) or ts(e.get("activity_start_observed_at"))
    end = ts((e.get("drift_end") or {}).get("ended_at"))
    if start and end is None and e.get("duration_seconds") is not None:
        end = start + datetime.timedelta(seconds=float(e["duration_seconds"]))
    return start, end


def midpoint(e: dict) -> tuple:
    """(moment half the measured drift time has passed, flag)."""
    b = bouts(e)
    if not b:
        a, z = span(e)
        if not (a and z):
            return a, "no bouts and no end: onset used"
        # Within one session (bouts never cross a UTC day) the span is effectively one bout; across
        # sessions its midpoint may fall outside working hours, so flag it.
        crosses = (z - datetime.timedelta(seconds=1)).date() != a.date()
        return a + (z - a) / 2, "no bouts, spans sessions: midpoint of the span" if crosses else ""
    half = sum((z - a).total_seconds() for a, z in b) / 2
    for a, z in b:
        d = (z - a).total_seconds()
        if half <= d:
            return a + datetime.timedelta(seconds=half), ""
        half -= d
    return b[-1][1], ""


def load_episodes() -> dict:
    bundle = json.loads(BUNDLE.read_text())
    ann = json.loads(ANNOTATIONS.read_text())
    tax = ann["trigger_taxonomy"]["assignments"]
    labels = {c["id"]: c["label"] for c in ann["trigger_taxonomy"]["categories"]}
    notes = ann["annotations"]
    by_agent = collections.defaultdict(list)
    for e in bundle["confirmed_episodes"]:
        a = notes.get(e["episode_id"], {})
        if e.get("period") != "goal_maximization" or a.get("drift_assessment") == "borderline":
            continue
        cat = tax.get(e["episode_id"])
        if not cat:
            continue
        by_agent[e["agent"]].append(
            {
                **e,
                "category": cat,
                "category_label": labels.get(cat, cat),
                "recovery": a.get("recovery_mechanisms") or [],
                "hours": float(e.get("duration_seconds") or 0) / 3600,
            }
        )
    return by_agent


def interventions(conn, agents: list) -> dict:
    """agent -> sorted [(time, kind, text)] from automated nudges, operator corrections and broadcasts."""
    out = collections.defaultdict(list)
    rows = conn.execute(
        "select created_at, data->>'content' from events where created_at between %s and %s "
        "and data->>'actionType' = 'USER_TALK' and data->>'speakerName' = 'automated'",
        PERIOD,
    ).fetchall()
    for created, content in rows:
        for name in agents:
            if f"@{name}" in (content or ""):
                out[name].append((created, "automated nudge", (content or "")[:160]))
    hc = json.loads(HUMAN_CONTACT.read_text())
    for c in hc.get("operator_corrections", []):
        for name in c.get("targets", []):
            out[name].append((ts(c["timestamp"]), f"operator ({c.get('speaker')})", c.get("summary", "")))
    for c in hc.get("broadcast_corrections", []):
        for name in agents:
            out[name].append((ts(c["timestamp"]), f"operator broadcast ({c.get('speaker')})", c.get("summary", "")))
    for name in out:
        out[name].sort(key=lambda x: x[0])
    return out


_TOOLS = "((input ? 'tools') or ((input->'config') ? 'tools'))"


def agent_ids(conn, name: str) -> list:
    return [str(r[0]) for r in conn.execute("select id from agents where name = %s", (name,)).fetchall()]


def _nearest_turn(conn, ids, lo, hi, newest_first: bool):
    """The nearest turn call in [lo, hi]. Candidates come from the (agent_id, created_at) index without
    reading any request; only those few are checked for tools, one at a time, nearest first."""
    order = "desc" if newest_first else "asc"
    cands = []
    for aid in ids:  # one agent id per query, so the index returns rows already in order
        cands += conn.execute(
            f"select id, created_at from llm_calls where agent_id = %s and created_at between %s and %s "
            f"order by created_at {order} limit 12",
            (aid, lo, hi),
        ).fetchall()
    cands.sort(key=lambda r: r[1], reverse=newest_first)
    for cid, _ in cands:
        row = conn.execute(f"select id, created_at, output from llm_calls where id = %s and {_TOOLS}", (cid,)).fetchone()
        if row:
            return row
    return None


def call_at_or_before(conn, ids, t):
    return _nearest_turn(conn, ids, t - SEARCH_BACK, t + DECISION_SLACK, newest_first=True)


def call_after(conn, ids, t):
    return _nearest_turn(conn, ids, t + DECISION_SLACK, t + SEARCH_BACK, newest_first=False)


def logged_action(output) -> str:
    """A short label for the logged call's first action (pause(600), send_message_to_chat, …)."""
    if isinstance(output, list):  # OpenAI Responses
        for it in output:
            if it.get("type") == "function_call":
                args = it.get("arguments") or ""
                if it.get("name") == "pause":
                    m = re.search(r'"seconds"\s*:\s*(\d+)', args)
                    return f"pause({m.group(1) if m else '?'})"
                return it.get("name")
            if it.get("type") == "computer_call":
                acts = it.get("actions") or [it.get("action") or {}]
                return f"computer.{acts[0].get('type', '?')}"
        return "(text)"
    if isinstance(output, dict):
        blocks = output.get("content")
        if isinstance(blocks, list):  # Anthropic
            for b in blocks:
                if b.get("type") == "tool_use":
                    inp = b.get("input") or {}
                    if b.get("name") == "pause":
                        return f"pause({inp.get('seconds')})"
                    if b.get("name") == "computer":
                        return f"computer.{inp.get('action')}"
                    return b.get("name")
            return "(text)"
        # a full completion, or (as the village logged chat agents) the bare assistant message
        msg = ((output.get("choices") or [{}])[0] or {}).get("message") or (output if "role" in output else {})
        for tc in msg.get("tool_calls") or []:  # chat completions
            name = (tc.get("function") or {}).get("name")
            if name == "pause":
                m = re.search(r'"seconds"\s*:\s*(\d+)', (tc.get("function") or {}).get("arguments") or "")
                return f"pause({m.group(1) if m else '?'})"
            return name
        for p in ((output.get("candidates") or [{}])[0].get("content") or {}).get("parts", []):  # Gemini
            fc = p.get("functionCall") or p.get("function_call")
            if fc:
                if fc.get("name") == "pause":
                    return f"pause({(fc.get('args') or {}).get('seconds')})"
                return fc.get("name")
        return "(text)"
    return "?"


def point(rule, episode, moment, row, why, flag=""):
    return {
        "rule": rule,
        "episode_id": episode["episode_id"],
        "category": episode["category"],
        "moment_utc": moment.isoformat() if moment else None,
        "moment_pt": pt(moment),
        "call_id": str(row[0]) if row else None,
        "call_at_pt": pt(row[1]) if row else "",
        "call_action": logged_action(row[2]) if row else "",
        "why": why,
        "flag": flag if row else (flag + "; no logged turn found").strip("; "),
    }


def select(conn, name: str, episodes: list, nudges: list) -> dict:
    ids = agent_ids(conn, name)
    hours = collections.Counter()
    for e in episodes:
        hours[e["category"]] += e["hours"]
    main, main_hours = hours.most_common(1)[0]
    mine = sorted((e for e in episodes if e["category"] == main), key=lambda e: span(e)[0] or datetime.datetime.max)
    label = mine[0]["category_label"]
    points = []

    first = mine[0]
    onset = span(first)[0]
    points.append(point("before_onset", first, onset, call_at_or_before(conn, ids, onset), "first onset of the main type"))

    longest = max(mine, key=lambda e: e["hours"])
    mid, flag = midpoint(longest)
    points.append(
        point(
            "mid_longest",
            longest,
            mid,
            call_at_or_before(conn, ids, mid),
            f"middle of the longest episode ({longest['hours']:.1f} h)",
            flag,
        )
    )

    longest_any = max(episodes, key=lambda e: e["hours"])
    if longest_any["episode_id"] != longest["episode_id"] and longest_any["hours"] >= 2 * longest["hours"]:
        mid, flag = midpoint(longest_any)
        points.append(
            point(
                "mid_longest_any",
                longest_any,
                mid,
                call_at_or_before(conn, ids, mid),
                f"middle of its longest episode of any type ({longest_any['category_label']}, "
                f"{longest_any['hours']:.1f} h vs {longest['hours']:.1f} h for the main type)",
                flag,
            )
        )

    returned = None
    for t, kind, text in nudges:
        for e in mine:
            a, z = span(e)
            if not (a and z and a <= t <= z + RETURN_WINDOW):
                continue
            after = [b for ep in mine for b in bouts(ep) if t < b[0] <= t + RETURN_WINDOW]
            if after:
                returned = (t, kind, text, e, min(after)[0])
                break
        if returned:
            break
    if returned:
        t, kind, text, e, back = returned
        points.append(
            point(
                "after_return",
                e,
                back,
                call_after(conn, ids, back),
                f"returned to drift {pt(back)} after {kind} at {pt(t)}: {text[:100]}",
            )
        )

    corrected = [e for e in mine if CORRECTED & set(e["recovery"])]
    if corrected:
        e = max(corrected, key=lambda e: e["hours"])
        end = ts((e.get("drift_end") or {}).get("ended_at")) or span(e)[1]
        points.append(
            point(
                "before_recovery",
                e,
                end,
                call_at_or_before(conn, ids, end),
                f"recovery by {', '.join(r for r in e['recovery'] if r in CORRECTED)}",
            )
        )
    return {
        "agent": name,
        "main_type": main,
        "main_type_label": label,
        "main_type_hours": round(main_hours, 1),
        "main_type_episodes": len(mine),
        "total_hours": round(sum(hours.values()), 1),
        "interventions_seen": len(nudges),
        "points": points,
    }


def write_markdown(result: list, excluded: list) -> None:
    lines = [
        "# Interview replay points",
        "",
        "Selected by `scripts/select_interview_points.py` from the goal-maximization episodes "
        "(`data/second_audit_v2.json`) and the official trigger taxonomy. Rules and open choices are in the "
        "script's docstring. Call ids are `llm_calls` ids for `village-exact show` / `replay`.",
        "",
        "| Agent | Main type (hours) | Point | Moment | Call (logged action) | Why |",
        "|---|---|---|---|---|---|",
    ]
    for r in result:
        for i, p in enumerate(r["points"]):
            head = f"{r['agent']} | {r['main_type_label']} ({r['main_type_hours']} h)" if i == 0 else " | "
            call = f"`{p['call_id']}` ({p['call_action']})" if p["call_id"] else "none found"
            why = p["why"] + (f" ⚠ {p['flag']}" if p["flag"] else "")
            lines.append(f"| {head} | {p['rule']} | {p['moment_pt']} | {call} | {why.replace('|', '/')} |")
    lines += ["", "Not interviewed (too little goal-max drift):", ""]
    lines += [f"- {x['agent']}: {x['reason']}" for x in excluded]
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    uri = os.environ.get("VILLAGE_DB_URI")
    if not uri:
        sys.exit("VILLAGE_DB_URI is not set")
    by_agent = {k: v for k, v in load_episodes().items() if k not in EXCLUDED}
    with psycopg.connect(uri) as conn:
        nudges = interventions(conn, list(by_agent))
        result = [select(conn, name, eps, nudges.get(name, [])) for name, eps in sorted(by_agent.items())]
    excluded = [{"agent": k, "reason": v} for k, v in sorted(EXCLUDED.items())]
    OUT_JSON.write_text(
        json.dumps({"schema_version": 1, "agents": result, "excluded": excluded}, indent=1) + "\n", encoding="utf-8"
    )
    write_markdown(result, excluded)
    n = sum(len(r["points"]) for r in result)
    print(f"{len(result)} agents, {n} points → {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
