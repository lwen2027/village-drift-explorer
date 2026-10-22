#!/usr/bin/env python3
"""Export interview answers from village-exact batch files to data/interview_answers_v1.json.

Keeps the first five answered samples per agent, question and framing (a sample answered when the
batch runner marked it so: text, or a chat message, and not only a lead-in to the pre-send check),
and counts the samples that did not answer. The privacy-framed batch is optional; its questions are
the plain wordings with a preamble in front, matched to them by question id.

    python3 scripts/export_interview_answers.py ~/.village-introspect/batches/start-v1-bare.jsonl \\
        --private ~/.village-introspect/batches/sentiment-private.jsonl
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


def load(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=Path, help="the plain (no preamble) batch")
    ap.add_argument("--private", type=Path, help="the privacy-framed batch")
    ap.add_argument("--questions", type=Path, default=ROOT / "data/interview_questions/start-v1.json")
    ap.add_argument("--private-questions", type=Path, default=ROOT / "data/interview_questions/sentiment-private-v1.json")
    ap.add_argument("--out", type=Path, default=ROOT / "data/interview_answers_v1.json")
    args = ap.parse_args()

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    framings = [{"id": "plain", "label": "Plain question"}]
    batches = [("plain", load(args.batch))]
    if args.private:
        plain_text = {q["id"]: q["text"] for q in questions}
        sample = json.loads(args.private_questions.read_text(encoding="utf-8"))[0]
        preamble = sample["text"][: -len(plain_text[sample["id"]])].strip()
        framings.append({"id": "private", "label": "Privacy preamble", "preamble": preamble})
        batches.append(("private", load(args.private)))

    cells = collections.defaultdict(lambda: {"answers": [], "skipped": 0})
    moments = {}
    for framing, rows in batches:
        for r in sorted(rows, key=lambda r: r["sample"]):
            moments.setdefault(r["agent"], r.get("moment_pt"))
            cell = cells[(r["agent"], r["question_id"], framing)]
            if not r.get("answered"):
                cell["skipped"] += 1
            elif len(cell["answers"]) < PER_CELL:
                cell["answers"].append({"sample": r["sample"], "text": answer_text(r)})

    agents = sorted(moments)
    out = {
        "batch": batches[0][1][0]["batch"],
        "questions": questions,
        "framings": framings,
        "agents": [{"name": a, "moment_pt": moments[a]} for a in agents],
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
