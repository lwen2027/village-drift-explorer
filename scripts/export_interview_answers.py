#!/usr/bin/env python3
"""Export interview answers from village-exact batch files to data/interview_answers_v1.json.

Keeps the first five answered samples per agent, question and framing (a sample answered when the
batch runner marked it so: text, or a chat message, and not only a lead-in to the pre-send check),
and counts the samples that did not answer. The privacy-framed batch is optional; its questions are
the plain wordings with a preamble in front, matched to them by question id; --private can be given
more than once (e.g. the sentiment and core privacy-framed batches).

    python3 scripts/export_interview_answers.py ~/.village-introspect/batches/start-v1-bare.jsonl \\
        ~/.village-introspect/batches/rollout-plain.jsonl \\
        --private ~/.village-introspect/batches/sentiment-private.jsonl \\
        --private ~/.village-introspect/batches/core-private.jsonl \\
        --private ~/.village-introspect/batches/rollout-private.jsonl
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PER_CELL = 5


def tools_disabled(rec):
    """Whether a sample was really sent with tools disabled (the no_tools edit). Gemini and DeepSeek-V4-Pro's
    provider ignore tool_choice none and still call tools, so their samples are plain replays."""
    ignored = rec.get("provider") == "gemini" or str(rec.get("model", "")).startswith("deepseek/deepseek-v4")
    return any(e.get("op") == "no_tools" for e in rec.get("edits") or []) and not ignored


def answer_text(rec):
    parts = [(rec.get("text") or "").strip()]
    for c in rec.get("tool_calls") or []:
        if c.get("tool") == "send_message_to_chat":
            msg = str((c.get("args") or {}).get("message") or "").strip()
            if msg:
                parts.append("[chat] " + msg)
    return "\n\n".join(p for p in parts if p)


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=Path, nargs="+", help="the plain (no preamble) batches")
    ap.add_argument("--private", type=Path, action="append", default=[], help="a privacy-framed batch (repeatable)")
    ap.add_argument("--questions", type=Path, default=ROOT / "data/interview_questions/start-v1.json")
    ap.add_argument("--private-questions", type=Path, default=ROOT / "data/interview_questions/sentiment-private-v1.json")
    ap.add_argument("--points", type=Path, default=ROOT / "data/interview_points_v1.json")
    ap.add_argument("--episodes", type=Path, default=ROOT / "data/second_audit_v2.json")
    ap.add_argument("--out", type=Path, default=ROOT / "data/interview_answers_v1.json")
    args = ap.parse_args()

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    framings = [{"id": "plain", "label": "Plain question"}]
    batches = [("plain", [r for path in args.batch for r in load(path)])]
    if args.private:
        plain_text = {q["id"]: q["text"] for q in questions}
        sample = json.loads(args.private_questions.read_text(encoding="utf-8"))[0]
        preamble = sample["text"][: -len(plain_text[sample["id"]])].strip()
        framings.append({"id": "private", "label": "Privacy preamble", "preamble": preamble})
        batches.append(("private", [r for path in args.private for r in load(path)]))

    # An agent with a second drift type has a second point; label each by its drift type.
    labels = {t["type"]: t["type_label"] for a in json.loads(args.points.read_text(encoding="utf-8"))["agents"] for t in a["tracks"]}
    tracks = collections.defaultdict(set)
    for _, rows in batches:
        for r in rows:
            tracks[r["agent"]].add(r["category"])

    def name_of(r):
        if len(tracks[r["agent"]]) < 2:
            return r["agent"]
        return f'{r["agent"]} ({labels.get(r["category"], r["category"])})'

    cells = collections.defaultdict(lambda: {"answers": [], "skipped": 0, "no_tools": False})
    moments, episode_of = {}, {}
    for framing, rows in batches:
        for r in sorted(rows, key=lambda r: r["sample"]):
            moments.setdefault(name_of(r), r.get("moment_pt"))
            episode_of.setdefault(name_of(r), r.get("episode_id"))
            cell = cells[(name_of(r), r["question_id"], framing)]
            if not r.get("answered"):
                cell["skipped"] += 1
            elif len(cell["answers"]) < PER_CELL:
                cell["answers"].append({"sample": r["sample"], "text": answer_text(r)})
                # tool_choice none: the agent couldn't act this turn, so the answer isn't an exact replay
                cell["no_tools"] |= tools_disabled(r)

    # The recorded goal and drift of each point's episode, for reviewers to check the answers against.
    episodes = {e["episode_id"]: e for e in json.loads(args.episodes.read_text(encoding="utf-8"))["confirmed_episodes"]}

    def agent_row(a):
        e = episodes.get(episode_of[a]) or {}
        return {"name": a, "moment_pt": moments[a], "episode_id": episode_of[a],
                "assigned_goal": e.get("assigned_goal"), "drift_activity": e.get("activity")}

    agents = sorted(moments)
    out = {
        "batch": batches[0][1][0]["batch"],
        "questions": questions,
        "framings": framings,
        "agents": [agent_row(a) for a in agents],
        "cells": [
            {"agent": a, "question_id": q, "framing": f["id"], **cells[(a, q, f["id"])]}
            for a in agents for q in (x["id"] for x in questions) for f in framings
            if (a, q, f["id"]) in cells
        ],
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out['cells'])} cells from {sum(len(rows) for _, rows in batches)} samples -> {args.out}")


if __name__ == "__main__":
    main()
