#!/usr/bin/env python3
"""Export interview answers from a village-exact batch file to data/interview_answers_v1.json.

Keeps the first five answered samples per agent and question (a sample answered when the batch
runner marked it so: text, or a chat message, and not only a lead-in to the pre-send check), and
counts the samples that did not answer.

    python3 scripts/export_interview_answers.py ~/.village-introspect/batches/start-v1-bare.jsonl
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PER_CELL = 5


def answer_text(rec):
    parts = [(rec.get("text") or "").strip()]
    for c in rec.get("tool_calls") or []:
        if c.get("tool") == "send_message_to_chat":
            msg = str((c.get("args") or {}).get("message") or "").strip()
            if msg:
                parts.append("[chat] " + msg)
    return "\n\n".join(p for p in parts if p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=Path)
    ap.add_argument("--questions", type=Path, default=ROOT / "data/interview_questions/start-v1.json")
    ap.add_argument("--out", type=Path, default=ROOT / "data/interview_answers_v1.json")
    args = ap.parse_args()

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.batch.read_text(encoding="utf-8").splitlines() if line.strip()]
    cells = collections.defaultdict(lambda: {"answers": [], "skipped": 0})
    for r in sorted(rows, key=lambda r: r["sample"]):
        cell = cells[(r["agent"], r["question_id"])]
        if not r.get("answered"):
            cell["skipped"] += 1
        elif len(cell["answers"]) < PER_CELL:
            cell["answers"].append({"sample": r["sample"], "text": answer_text(r)})

    moments = {r["agent"]: r.get("moment_pt") for r in rows}
    agents = sorted(moments)
    out = {
        "batch": rows[0]["batch"],
        "questions": questions,
        "agents": [{"name": a, "moment_pt": moments[a]} for a in agents],
        "cells": [
            {"agent": a, "question_id": q, **cells[(a, q)]}
            for a in agents for q in (x["id"] for x in questions) if (a, q) in cells
        ],
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out['cells'])} cells from {len(rows)} samples -> {args.out}")


if __name__ == "__main__":
    main()
