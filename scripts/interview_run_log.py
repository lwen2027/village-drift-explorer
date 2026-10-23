#!/usr/bin/env python3
"""Summarize interview batch runs to data/interview_run_log_v1.json.

Per batch and agent point: samples sent, real answers, lead-ins (samples a reviewer marked
answered_review = "lead_in_only": the text only announced an action), other skips (a pause or other
action with no text), samples sent with tools disabled (no_tools), cost and the dates sampled. The
lead-in rate is lead-ins over samples sent; the flagged samples are listed so they can be spot-checked.

    python3 scripts/interview_run_log.py ~/.village-introspect/batches/{start-v1-bare,rollout-plain,rollout-private}.jsonl
"""
import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("batch", type=Path, nargs="+")
    ap.add_argument("--out", type=Path, default=ROOT / "data/interview_run_log_v1.json")
    args = ap.parse_args()

    rows = []
    for path in args.batch:
        groups = collections.OrderedDict()
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                groups.setdefault((r["agent"], r.get("track", 0), r.get("category")), []).append(r)
        for (agent, track, category), rs in groups.items():
            ok = [r for r in rs if not r.get("error")]
            lead = [r for r in ok if r.get("answered_review") == "lead_in_only"]
            no_tools = [r for r in ok if any(e.get("op") == "no_tools" for e in r.get("edits") or [])]
            dates = sorted(r["created_at"][:10] for r in rs if r.get("created_at"))
            rows.append({
                "batch": path.stem,
                "agent": agent,
                "track": track,
                "drift_type": category,
                "moment_pt": rs[0].get("moment_pt"),
                "samples": len(rs),
                "errors": len(rs) - len(ok),
                "answered": sum(1 for r in ok if r.get("answered")),
                "lead_ins": len(lead),
                "other_skips": sum(1 for r in ok if not r.get("answered")) - len(lead),
                "lead_in_rate": round(len(lead) / len(ok), 3) if ok else None,
                "no_tools_samples": len(no_tools),
                "usd": round(sum(r.get("usd") or 0 for r in rs), 4),
                "first_sampled": dates[0] if dates else None,
                "last_sampled": dates[-1] if dates else None,
                "lead_in_samples": [
                    {"question_id": r["question_id"], "sample": r["sample"], "text": (r.get("text") or "").strip()[:300]}
                    for r in lead
                ],
            })
    out = {
        "review_rule": (
            "A sample counts as an answer when its text (or chat message) addresses the question, even if short "
            "and followed by an action. It is a lead-in when the text only announces or narrates the action or "
            "defers the answer. For 'what next' wordings, narrating the action being taken right then is a lead-in; "
            "with tools disabled the same sentence counts. Cells are topped up by exact replay while the real-answer "
            "rate is at least about 30%, otherwise with tools disabled (no_tools)."
        ),
        "runs": rows,
    }
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(rows)} batch × point rows -> {args.out}")


if __name__ == "__main__":
    main()
