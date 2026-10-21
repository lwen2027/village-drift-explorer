#!/usr/bin/env python3
"""Select the interview replay points for each agent's goal-maximization drift, adapted to its shape.

The agent's MAIN DRIFT TYPE is the official trigger-taxonomy category with the most drift hours. Any
other type with at least 90% of its hours is interviewed too, as a separate track with the same
protocol. Each track's points use only that type's episodes. Episodes chained as one drift (recovery `continued_in_later_record`)
are merged into SPELLS; a spell ends only where the agent really left that drift: corrected
(self-correction, operator nudge or message, peer feedback or message, external user intervention,
automated nudge), stopped on its own (finished activity, end of day, checkpoint…), switched to another
drift, or still drifting when the data ends.

SHAPE, from the spells:
  relapsing       several spells, at least one corrected before a later one
  recurring       several spells, none corrected before a later one
  single_stopped  one spell that ended
  single_open     one spell, still drifting when the data ends

POINTS (decision moment → the logged turn that acted there):
  every shape
    before_onset      1   the first onset of the type (validates the drift cause)
    after_return      3   right after it returned to drift following an intervention (what kept it
                          drifting): one per interviewed spell — 3 for a single spell, 3A / 3B
                          (after_return_a / after_return_b) for spells A and B. The intervention must
                          fall inside the spell; after it the agent must leave the drift for at least
                          10 minutes and go back to it in the same session (a next-morning session
                          start is not a return);
                          the strongest is used (an operator message to the agent, then an operator
                          broadcast, then an automated nudge), the first among equals.
    mid_longest_any   2b  the middle of its longest episode of any type, when that episode is at
                          least twice as long as its longest main-type spell
  single_stopped      2 spell_mid (middle of the spell) · 4 before_recovery (just before it ended)
  single_open         2 spell_mid · L late (90% through the spell's drift time: how entrenched)
  relapsing           B = its biggest spell that starts after a corrected spell has ended; A = the
                      biggest corrected spell that ended before B started.
                      A2 a_mid · A4 a_end (just before A was corrected) · B1 b_start (just before the
                      relapse: what brought it back) · B2 b_mid
  recurring           the same with no correction: B = its biggest spell that starts after an earlier
                      spell ended; A = the biggest spell that ended before B started.
                      A2 a_mid · A4 a_stop (just before A stopped on its own: why it stopped) ·
                      B1 b_start (what pulled it back) · B2 b_mid

"Middle" / "90% through" are measured in drift time: the spell's bouts summed in order (a record
without bouts counts as one bout over its span, flagged when that span crosses sessions). The replay
call is the last logged turn at or just before the moment (for onsets and endings, the turn that
took that action), or for after_return the first turn after the return began.

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
# A second drift type is interviewed too when it has at least this share of the main type's hours.
SECOND_TYPE_SHARE = 0.9
RETURN_WINDOW = datetime.timedelta(hours=24)
MIN_BREAK = datetime.timedelta(minutes=10)  # time off the drift after an intervention before it counts as a return
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


CONTINUED = {"continued_in_later_record"}
SWITCHED = {"switched_to_another_drift"}
STILL_OPEN = {"still_drifting_at_end_of_data"}


def spells_of(episodes: list) -> list:
    """Main-type episodes grouped into spells (chained records merged), oldest first."""
    out, cur = [], []
    for e in sorted(episodes, key=lambda e: span(e)[0] or datetime.datetime.max):
        cur.append(e)
        if not (set(e["recovery"]) & CONTINUED):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def spell_ending(spell: list) -> str:
    r = set(spell[-1]["recovery"])
    if r & STILL_OPEN:
        return "still drifting"
    if r & SWITCHED:
        return "switched"
    if r & CORRECTED:
        return "corrected"
    return "stopped"


def spell_hours(spell: list) -> float:
    return sum(e["hours"] for e in spell)


def spell_bouts(spell: list) -> list:
    """[(start, end, record)] in order; a record without bouts counts as one bout over its span."""
    out = []
    for e in spell:
        b = bouts(e)
        if b:
            out += [(x, y, e) for x, y in b]
        else:
            x, y = span(e)
            if x and y:
                out.append((x, y, e))
    return sorted(out, key=lambda t: t[0])


def spell_at(spell: list, fraction: float) -> tuple:
    """(moment, record, flag) when `fraction` of the spell's drift time has passed."""
    b = spell_bouts(spell)
    if not b:
        x = span(spell[0])[0]
        return x, spell[0], "no timed bouts: onset used"
    target = sum((y - x).total_seconds() for x, y, _ in b) * fraction
    for x, y, e in b:
        d = (y - x).total_seconds()
        if target <= d:
            flag = ""
            if not bouts(e) and (y - datetime.timedelta(seconds=1)).date() != x.date():
                flag = "no bouts, spans sessions: position within the span"
            return x + datetime.timedelta(seconds=target), e, flag
        target -= d
    return b[-1][1], b[-1][2], ""


def spell_start(spell: list) -> tuple:
    return span(spell[0])[0], spell[0]


def spell_end(spell: list) -> tuple:
    e = spell[-1]
    return ts((e.get("drift_end") or {}).get("ended_at")) or span(e)[1], e


def classify_shape(spells: list) -> str:
    if len(spells) == 1:
        return "single_open" if spell_ending(spells[0]) == "still drifting" else "single_stopped"
    corrected_ends = [spell_end(x)[0] for x in spells if spell_ending(x) == "corrected"]
    if any(end and start and end <= start for end in corrected_ends for start in (spell_start(x)[0] for x in spells)):
        return "relapsing"
    return "recurring"


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
# Memory steps that some harnesses send with tools attached; the same test as exact_lib.kind_of.
SESSION_END_PREFIX = "Now that you are consolidating your session"
COMPACTION_MARK = "Your memory is getting too large"


def _is_memory_step(request) -> bool:
    text = json.dumps(request, ensure_ascii=False)
    return COMPACTION_MARK in text or SESSION_END_PREFIX in text[-20000:]


def agent_ids(conn, name: str) -> list:
    return [str(r[0]) for r in conn.execute("select id from agents where name = %s", (name,)).fetchall()]


def _nearest_turn(conn, ids, lo, hi, newest_first: bool):
    """The nearest turn call in [lo, hi]. Candidates come from the (agent_id, created_at) index without
    reading any request; only those few are checked for tools, one at a time, nearest first, and memory
    steps (session end, compaction) are passed over."""
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
        row = conn.execute(
            f"select id, created_at, output, input from llm_calls where id = %s and {_TOOLS}", (cid,)
        ).fetchone()
        if row and not _is_memory_step(row[3]):
            return row[:3]
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


def select_type(conn, ids: list, episodes: list, category: str, nudges: list) -> dict:
    """The shape-based protocol for one drift type: its spells, shape and points."""
    mine = sorted((e for e in episodes if e["category"] == category), key=lambda e: span(e)[0] or datetime.datetime.max)
    spells = spells_of(mine)
    shape = classify_shape(spells)
    points, roles = [], {}

    def small(spell):
        return f"this spell is only {spell_hours(spell):.1f} h" if spell_hours(spell) < 1 else ""

    def at(rule, spell, fraction, why):
        moment, record, flag = spell_at(spell, fraction)
        flag = "; ".join(f for f in (flag, small(spell)) if f)
        points.append(point(rule, record, moment, call_at_or_before(conn, ids, moment), why, flag))

    def starting(rule, spell, why):
        moment, record = spell_start(spell)
        points.append(point(rule, record, moment, call_at_or_before(conn, ids, moment), why, small(spell)))

    def ending(rule, spell, why):
        moment, record = spell_end(spell)
        points.append(point(rule, record, moment, call_at_or_before(conn, ids, moment), why, small(spell)))

    def label(spell):
        return f"spell {spells.index(spell) + 1} of {len(spells)}, {spell_hours(spell):.1f} h"

    moment, record = spell_start(spells[0])
    points.append(point("before_onset", record, moment, call_at_or_before(conn, ids, moment), "first onset of this type"))

    if shape in ("single_stopped", "single_open"):
        only = spells[0]
        at("spell_mid", only, 0.5, f"middle of the drift spell ({spell_hours(only):.1f} h)")
        if shape == "single_stopped":
            ending("before_recovery", only, f"just before it ended ({spell_ending(only)})")
        else:
            at("late", only, 0.9, "90% through the spell, which never ended: how entrenched it is")
    else:  # relapsing or recurring: a spell A that ended, then a later spell B
        if shape == "relapsing":  # B must begin after a correction ended (drifts can run in parallel)
            enders = [x for x in spells if spell_ending(x) == "corrected"]
        else:
            enders = [x for x in spells if spell_ending(x) != "still drifting"]

        def after_an_end(x):
            return any(spell_end(y)[0] <= spell_start(x)[0] for y in enders if y is not x)

        b = max((x for x in spells if after_an_end(x)), key=spell_hours)
        a = max((y for y in enders if spell_end(y)[0] <= spell_start(b)[0]), key=spell_hours)
        roles = {"A": spells.index(a), "B": spells.index(b)}
        how = ", ".join(r for r in a[-1]["recovery"]) or spell_ending(a)
        at("a_mid", a, 0.5, f"middle of spell A ({label(a)}, {'corrected' if shape == 'relapsing' else 'stopped on its own'})")
        if shape == "relapsing":
            ending("a_end", a, f"just before spell A was corrected ({', '.join(r for r in a[-1]['recovery'] if r in CORRECTED)})")
            starting("b_start", b, f"just before the relapse into spell B ({label(b)})")
        else:
            ending("a_stop", a, f"just before spell A stopped without a correction ({how})")
            starting("b_start", b, f"just before it drifted again into spell B ({label(b)})")
        at("b_mid", b, 0.5, f"middle of spell B ({label(b)})")

    def strength(kind):
        return 2 if kind.startswith("automated") else 1 if "broadcast" in kind else 0

    def returned_after(spell_b, t):
        """The start of the bout it went back to drift with after an intervention at t, or None. It must
        have left the drift for at least MIN_BREAK after t and returned in the same session, so a
        session opening the next morning doesn't count as a return."""
        gap_start = t
        for b0, b1, _ in spell_b:
            if b0 <= t < b1:  # drifting when it arrived: the break starts when that bout ends
                gap_start = b1
        for b0, _, _ in spell_b:
            # a bout ending at the 5 PM close ends at 00:00 UTC, which belongs to the session before
            session = (gap_start - datetime.timedelta(seconds=1)).date()
            if b0 > gap_start and b0 - gap_start >= MIN_BREAK and b0.date() == session:
                return b0 if b0 <= t + RETURN_WINDOW else None
            if b0 > gap_start:
                return None
        return None

    def return_point(rule, spell, name_):
        x, _ = spell_start(spell)
        y, _ = spell_end(spell)
        spell_b = spell_bouts(spell)
        hits = []
        for t, kind, text in nudges:
            if x and y and x <= t <= y:
                back = returned_after(spell_b, t)
                if back:
                    hits.append((strength(kind), t, kind, text, back))
        if not hits:
            return
        _, t, kind, text, back = min(hits)
        record = next((e for b0, _, e in spell_bouts(spell) if b0 == back), spell[0])
        points.append(
            point(
                rule,
                record,
                back,
                call_after(conn, ids, back),
                f"returned to drift in {name_} {pt(back)} after {kind} at {pt(t)} "
                f"(strongest of {len(hits)} in this spell): {text[:100]}",
            )
        )

    if shape in ("single_stopped", "single_open"):
        return_point("after_return", spells[0], "the spell")
    else:
        return_point("after_return_a", spells[roles["A"]], "spell A")
        return_point("after_return_b", spells[roles["B"]], "spell B")

    spell_rows = []
    for i, x in enumerate(spells):
        start, _ = spell_start(x)
        end, _ = spell_end(x)
        role = next((k for k, v in roles.items() if v == i), "")
        spell_rows.append(
            {
                "n": i + 1,
                "role": role,
                "start_pt": pt(start),
                "end_pt": pt(end),
                "start_utc": start.isoformat() if start else None,
                "end_utc": end.isoformat() if end else None,
                "hours": round(spell_hours(x), 1),
                "records": len(x),
                "ending": spell_ending(x),
                "episode_ids": [e["episode_id"] for e in x],
            }
        )
    return {
        "type": category,
        "type_label": mine[0]["category_label"],
        "hours": round(spell_hours(mine), 1),
        "episodes": len(mine),
        "shape": shape,
        "spells": spell_rows,
        "longest_spell_hours": max(spell_hours(x) for x in spells),
        "points": points,
    }


def select(conn, name: str, episodes: list, nudges: list) -> dict:
    """Interview the main drift type, plus any type with at least SECOND_TYPE_SHARE of its hours."""
    ids = agent_ids(conn, name)
    hours = collections.Counter()
    for e in episodes:
        hours[e["category"]] += e["hours"]
    (main, main_hours), *others = hours.most_common()
    types = [main] + [c for c, h in others if h >= SECOND_TYPE_SHARE * main_hours]
    tracks = [select_type(conn, ids, episodes, c, nudges) for c in types]

    longest_spell = max(t["longest_spell_hours"] for t in tracks)
    longest_any = max(episodes, key=lambda e: e["hours"])
    if longest_any["category"] not in types and longest_any["hours"] >= 2 * longest_spell:
        mid, flag = midpoint(longest_any)
        tracks[0]["points"].append(
            point(
                "mid_longest_any",
                longest_any,
                mid,
                call_at_or_before(conn, ids, mid),
                f"middle of its longest episode of any type ({longest_any['category_label']}, "
                f"{longest_any['hours']:.1f} h vs {longest_spell:.1f} h for its longest interviewed spell)",
                flag,
            )
        )
    for i, t in enumerate(tracks):
        for q in t["points"]:
            q["track"] = i
        t["points"].sort(key=lambda q: q["moment_utc"] or "")
        t.pop("longest_spell_hours")
    main_track = tracks[0]
    return {
        "agent": name,
        "main_type": main,
        "main_type_label": main_track["type_label"],
        "main_type_hours": main_track["hours"],
        "main_type_episodes": main_track["episodes"],
        "total_hours": round(sum(hours.values()), 1),
        "shape": main_track["shape"],
        "spells": main_track["spells"],
        "tracks": tracks,
        "interventions_seen": len(nudges),
        "points": sorted((q for t in tracks for q in t["points"]), key=lambda q: q["moment_utc"] or ""),
    }


def write_markdown(result: list, excluded: list) -> None:
    lines = [
        "# Interview replay points",
        "",
        "Selected by `scripts/select_interview_points.py` from the goal-maximization episodes "
        "(`data/second_audit_v2.json`) and the official trigger taxonomy. Rules and open choices are in the "
        "script's docstring. Call ids are `llm_calls` ids for `village-exact show` / `replay`.",
        "",
        "| Agent | Main type (hours, shape) | Point | Moment | Call (logged action) | Why |",
        "|---|---|---|---|---|---|",
    ]
    for r in result:
        for i, p in enumerate(r["points"]):
            head = f"{r['agent']} | {r['main_type_label']} ({r['main_type_hours']} h, {r['shape']})" if i == 0 else " | "
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
        json.dumps({"schema_version": 3, "agents": result, "excluded": excluded}, indent=1) + "\n", encoding="utf-8"
    )
    write_markdown(result, excluded)
    n = sum(len(r["points"]) for r in result)
    print(f"{len(result)} agents, {n} points → {OUT_JSON.relative_to(ROOT)}, {OUT_MD.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
