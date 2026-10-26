"""Publish a review export from answers.html as data/interview_reviews_v1.json.

The review panel keeps notes in the reviewer's browser only. This turns an exported CSV into a static file the
page shows read-only to every visitor (a visitor's own browser notes still take priority). Agents with no notes
are left out; imported drafts not yet marked reviewed are published with status "draft".

    python3 scripts/publish_reviews.py data/review_notes/interview_review_2026-10-26.csv [--edits fixes.csv]
"""

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = {"agent", "group", "moment_pt", "episode_id", "assigned_goal", "recorded_drift", "labelled_cause",
        "trigger", "mechanism", "memory_reinforced", "updated_at", "imported_from", "reviewed_at"}
# Export column names that differ from the panel's field ids.
FIELD_OF = {"constraints_pain_points": "constraints_notes"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv", type=Path)
    ap.add_argument("--out", type=Path, default=ROOT / "data/interview_reviews_v1.json")
    ap.add_argument("--edits", type=Path, action="append", default=[],
                    help="field-edit CSV (agent, field, old_value, new_value) applied on top of the export; "
                         "each field must still equal old_value")
    args = ap.parse_args()

    known = set()
    for name in ("interview_answers_v1.json", "interview_answers_control_v1.json"):
        known |= {a["name"] for a in json.loads((ROOT / "data" / name).read_text())["agents"]}

    reviews, stamps = {}, []
    with args.csv.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            fields = {FIELD_OF.get(k, k): v.strip() for k, v in row.items() if k not in META and (v or "").strip()}
            if not fields:
                continue
            if row["agent"] not in known:
                raise SystemExit(f"{row['agent']!r} is not on the answers page")
            draft = bool(row["imported_from"]) and not row["reviewed_at"]
            reviews[row["agent"]] = {**fields, "status": "draft" if draft else "reviewed"}
            stamps.append(row["updated_at"])

    # Corrections made outside the browser, so a republish from an older export keeps them.
    for path in args.edits:
        with path.open(encoding="utf-8-sig", newline="") as f:
            for e in csv.DictReader(f):
                field = FIELD_OF.get(e["field"], e["field"])
                review = reviews.get(e["agent"])
                if review is None:
                    raise SystemExit(f"{path.name}: {e['agent']!r} has no review")
                current = review.get(field, "")
                if current.strip() == e["new_value"].strip():
                    continue  # already applied in this export
                if current.strip() != e["old_value"].strip():
                    raise SystemExit(f"{path.name}: {e['agent']} · {e['field']} has changed since the edit was written")
                review[field] = e["new_value"].strip()

    out = {"source": args.csv.name, "edits": [p.name for p in args.edits], "exported_at": max(stamps), "reviews": reviews}
    args.out.write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n")
    drafts = sum(r["status"] == "draft" for r in reviews.values())
    print(f"{len(reviews)} reviews ({drafts} drafts) -> {args.out}")


if __name__ == "__main__":
    main()
