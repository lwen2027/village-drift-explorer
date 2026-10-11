#!/usr/bin/env python3
"""Merge the canonical repeated-wait review into the explorer annotation seed."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = (
    ROOT.parent / "spar-village-drift" / "evaluation"
    / "mechanical_repeated_wait_manual_annotations_v1_2026-10-10.json"
)
DEFAULT_ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
REQUIRED_FIELDS = {
    "trigger_categories",
    "request_relationship",
    "pause_context",
    "recovery_mechanisms",
    "notes",
    "follow_ups",
    "provenance",
    "updated_at",
}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument(
        "--annotations", type=Path, default=DEFAULT_ANNOTATIONS
    )
    args = parser.parse_args()

    review = json.loads(args.review.read_text(encoding="utf-8"))
    seed = json.loads(args.annotations.read_text(encoding="utf-8"))
    imported = review.get("annotations") or {}
    if len(imported) != 117:
        raise SystemExit("canonical repeated-wait review must contain 117 rows")

    added = 0
    preserved = 0
    for episode_id, annotation in imported.items():
        missing = REQUIRED_FIELDS - set(annotation)
        if missing:
            raise SystemExit(
                f"{episode_id} is missing annotation fields: {sorted(missing)}"
            )
        existing = seed["annotations"].get(episode_id)
        if existing is None:
            seed["annotations"][episode_id] = annotation
            added += 1
            continue
        # Existing user-authored fields have precedence. The canonical review
        # must agree on the structured pause label before it can be merged.
        existing_context = existing.get("pause_context")
        if existing_context and existing_context != annotation["pause_context"]:
            raise SystemExit(
                f"pause-context conflict for {episode_id}: "
                f"{existing_context!r} != {annotation['pause_context']!r}"
            )
        existing.setdefault("pause_context", annotation["pause_context"])
        preserved += 1

    seed["seed_id"] = "goalmax-manual-review-2026-10-10-v2"
    merged_ids = set(seed.get("merged_review_ids") or [])
    merged_ids.add(review["review_id"])
    seed["merged_review_ids"] = sorted(merged_ids)
    args.annotations.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {len(imported)} repeated-wait annotations: "
        f"added {added}, preserved {preserved} existing human reviews."
    )


if __name__ == "__main__":
    main()
