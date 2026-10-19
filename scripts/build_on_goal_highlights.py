#!/usr/bin/env python3
"""Extract candidate on-goal highlights for each agent's goal window (keyword pass; no model calls).

The published data/on_goal_highlights_v1.json is the reviewed version: these candidates were
checked against the raw logs and curated to 5-10 verified actions per agent.

Looks only at time outside the agent's recorded drift bouts and lists concrete
on-goal actions by type: outreach approval requests, emails sent, interviews and
questions put to other agents, launches and releases, distribution and
discoverability work, measurement checks, and what the agent did right after an
operator nudge. Only agent-authored text (commands, narration, own chat) is
stored, as short excerpts. Human messages are used only to time nudges; their
text is never stored. Highlights are unreviewed keyword matches.

Usage: python3 scripts/build_on_goal_highlights.py --raw <spar>/evaluation/evidence/raw
"""

from __future__ import annotations

import argparse
import gzip
import json
import pathlib
import re
from collections import defaultdict
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "data" / "second_audit_v2.json"
# Candidates only: data/on_goal_highlights_v1.json holds the reviewed highlights built from these.
OUTPUT = pathlib.Path("/tmp/ogh/keyword_highlights.json")
MAX_PER_AGENT = 10
MAX_PER_TYPE = 3
CANDIDATES = pathlib.Path("/tmp/ogh/candidates.json")

TYPES = {
    "outreach": "Outreach request",
    "email": "Email sent",
    "interview": "Question or interview",
    "release": "Launch or release",
    "distribution": "Distribution or discoverability",
    "measurement": "Measurement check",
    "after_nudge": "Response to a nudge",
}
# Commit messages that are routine logs or bulk output rather than a launch.
ROUTINE = re.compile(r"\b(rebuild|cache|bust|log|batch|articles?|a\d{3,}|pages? \d|status|verify|check|wip|eod|consolidat|memory|notes?)\b", re.I)
RELEASE = re.compile(r"\b(v\d+(\.\d+)*|launch|ship(ped)?|release|new (page|feature|tool|game|section)|add(ed)? (a |an )?(new )?(feature|page|section|tool|calculator|game|mode)|deploy(ed)? (new|v\d))\b", re.I)
DISTRIBUTION = re.compile(r"\b(rss|feed\.xml|sitemap|indexnow|ping (google|bing)|search console|og(:| tags| image)|open graph|share (buttons?|card|tags)|twitter (card|meta)|hacker news|reddit|substack (post|note)|cross-?link|backlink|hub tile|newsletter)\b", re.I)
MEASUREMENT = re.compile(r"\b(view counter|analytics|pageviews?|visitors?|traffic|(\d[\d,]*) (total )?(views|visitors|sales|orders|subscribers|signups|citations))\b", re.I)
EMAIL_SENT = re.compile(r"\b(email|reply|message) (was |is )?(sent|delivered)\b|\bsent (the |an |my )?(email|reply)\b", re.I)
INTERVIEW = re.compile(r"\b(quick interview|interview(ing)?|quick questions?|a few (quick )?questions|fact-?checks? for)\b", re.I)
NUDGE = re.compile(r"based on your recent (chat |)(activity|messages)", re.I)


def ts(value) -> datetime:
    return datetime.fromisoformat(str(value).replace("T", " ").replace("Z", "")[:19])


def clean(text: str, limit: int = 150) -> str:
    text = " ".join(str(text or "").replace("\\n", " ").split())
    return text[:limit]


def load(raw: pathlib.Path, agent: str, day: str):
    base = raw / day / f"{agent.replace(' ', '_')}.json"
    if base.exists():
        return json.loads(base.read_text(encoding="utf-8"))
    gz = base.with_name(base.name + ".gz")
    if gz.exists():
        with gzip.open(gz, "rt", encoding="utf-8") as handle:
            return json.load(handle)
    return None


def commit_message(command: str) -> str | None:
    match = re.search(r"git commit[^\n]*?-m\s+([\"'])(.+?)\1", command, re.S)
    return clean(match.group(2), 140) if match else None


def comment_line(command: str) -> str:
    first = command.strip().split("\n", 1)[0]
    return clean(first.lstrip("# "), 140) if first.startswith("#") else ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=pathlib.Path, required=True)
    args = parser.parse_args()
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    days_by_agent = defaultdict(set)
    for row in bundle["stage1_daily_verdicts"]:
        if row.get("period") == "goal_maximization" and row.get("day") and row.get("agent"):
            days_by_agent[row["agent"]].add(row["day"])
    bouts_by_agent = defaultdict(list)
    for row in bundle["confirmed_episodes"]:
        if row.get("period") != "goal_maximization":
            continue
        bouts = row.get("drift_bouts") or []
        if bouts:
            bouts_by_agent[row["agent"]].extend((ts(a), ts(b)) for a, b in bouts)
        elif row.get("onset") and row.get("duration_seconds"):
            start = ts(row["onset"])
            bouts_by_agent[row["agent"]].append((start, start + timedelta(seconds=row["duration_seconds"])))

    def in_drift(agent, at):
        return any(start <= at <= end for start, end in bouts_by_agent[agent])

    result, all_candidates = {}, {}
    for agent, days in sorted(days_by_agent.items()):
        found = []
        for day in sorted(days):
            data = load(args.raw, agent, day)
            if not data:
                continue
            turns = sorted(data.get("turns") or [], key=lambda turn: str(turn.get("ts")))
            nudges = [ts(chat["ts"]) for chat in data.get("chat") or []
                      if str(chat.get("human")) == "True" and NUDGE.search(str(chat.get("content") or ""))
                      and agent in str(chat.get("content") or "")]
            for turn in turns:
                at = ts(turn["ts"])
                kind = str(turn.get("kind") or "")
                if in_drift(agent, at) and "approval" not in kind:
                    continue
                command = str(turn.get("command") or "")
                narration = clean(turn.get("text") or "", 400)
                if "approval" in kind:
                    found.append((at, "outreach", clean(turn.get("text") or turn.get("reasoning") or "Requested outreach approval", 150)))
                    continue
                message = commit_message(command) if "git commit" in command else None
                if message and RELEASE.search(message) and not ROUTINE.search(message):
                    found.append((at, "release", message))
                    continue
                note = comment_line(command)
                if note and DISTRIBUTION.search(note):
                    found.append((at, "distribution", note))
                    continue
                if note and MEASUREMENT.search(note):
                    found.append((at, "measurement", note))
                    continue
                if narration and EMAIL_SENT.search(narration):
                    found.append((at, "email", narration[:150]))
                    continue
                if narration and MEASUREMENT.search(narration) and re.search(r"\d", narration):
                    match = MEASUREMENT.search(narration)
                    found.append((at, "measurement", clean(narration[max(0, match.start() - 60):match.end() + 60], 150)))
            for chat in data.get("chat") or []:
                if str(chat.get("own")) != "True":
                    continue
                at = ts(chat["ts"])
                content = str(chat.get("content") or "")
                if "@" in content and "?" in content and INTERVIEW.search(content) and not re.search(r"tweet|retweet", content, re.I):
                    found.append((at, "interview", clean(content, 150)))
            # What the agent did first in the 30 minutes after each nudge (outside drift bouts or not).
            for nudge_at in nudges:
                for turn in turns:
                    at = ts(turn["ts"])
                    if at <= nudge_at or at > nudge_at + timedelta(minutes=30) or turn.get("kind") in ("pause", "wait"):
                        continue
                    text = comment_line(str(turn.get("command") or "")) or clean(turn.get("text") or "", 140)
                    if text:
                        found.append((at, "after_nudge", f"{int((at - nudge_at).total_seconds() // 60)} min after a nudge: {text}"))
                        break
        # Keep a spread: first items of each type, capped, then by time.
        chosen, per_type, seen = [], defaultdict(int), set()
        for at, kind, text in sorted(found):
            key = (kind, text.lower()[:60])
            if key in seen or per_type[kind] >= MAX_PER_TYPE:
                continue
            seen.add(key)
            per_type[kind] += 1
            chosen.append((at, kind, text))
        chosen.sort()
        if len(chosen) > MAX_PER_AGENT:
            step = len(chosen) / MAX_PER_AGENT
            chosen = [chosen[int(index * step)] for index in range(MAX_PER_AGENT)]
        all_candidates[agent] = [{"ts": at.strftime("%Y-%m-%d %H:%M:%SZ"), "type": kind, "text": text} for at, kind, text in sorted(found)]
        result[agent] = {
            "counts": {kind: sum(1 for item in found if item[1] == kind) for kind in TYPES if any(item[1] == kind for item in found)},
            "highlights": [{"ts": at.strftime("%Y-%m-%d %H:%M:%SZ"), "type": kind, "text": text} for at, kind, text in chosen],
        }
    document = {
        "schema_version": "on-goal-highlights-v1",
        "method": ("Keyword pass over each agent's own commands, narration and chat outside its recorded drift bouts during "
                   "its goal-maximization window. Counts cover all matches; highlights keep up to 3 per type and 10 per "
                   "agent, spread over time. Unreviewed."),
        "makes_model_calls": False,
        "types": TYPES,
        "agents": result,
    }
    CANDIDATES.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES.write_text(json.dumps(all_candidates, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    OUTPUT.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Highlights for {sum(1 for row in result.values() if row['highlights'])} of {len(result)} agents")


if __name__ == "__main__":
    main()
