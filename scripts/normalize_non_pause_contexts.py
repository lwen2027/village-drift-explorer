#!/usr/bin/env python3
"""Add the non-applicable pause_context key to older non-pause reviews."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
EXPECTED_MISSING = 29


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text())
    annotations = payload["annotations"]
    missing = {
        episode_id: annotation
        for episode_id, annotation in annotations.items()
        if "pause_context" not in annotation
    }
    invalid = sorted(
        episode_id
        for episode_id, annotation in missing.items()
        if "pause" in (annotation.get("trigger_categories") or [])
    )
    if invalid:
        raise RuntimeError(
            "Refusing to assign an empty context to pause reviews: " + str(invalid)
        )
    if len(missing) != EXPECTED_MISSING:
        raise RuntimeError(
            f"Expected {EXPECTED_MISSING} missing non-pause keys, found {len(missing)}"
        )

    for annotation in missing.values():
        annotation["pause_context"] = ""

    payload["seed_id"] = "goalmax-manual-review-2026-10-11-v20"
    review_id = "goalmax-non-pause-context-normalization-2026-10-11-v1"
    merged_review_ids = payload.setdefault("merged_review_ids", [])
    if review_id not in merged_review_ids:
        merged_review_ids.append(review_id)
    ANNOTATIONS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Added pause_context to {len(missing)} older non-pause reviews")


if __name__ == "__main__":
    main()
