#!/usr/bin/env python3
"""Archive the pre-goal false positive and retire unused review values."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
RETIRED = ROOT / "data" / "retired_manual_review_annotations_v1.json"
CANONICAL = (
    ROOT.parent / "spar-village-drift" / "artifacts" / "final"
    / "second_audit_v2.json"
)
EPISODE_ID = "episode-v2-f5a3930f42dbf133"
REVIEW_ID = "pre-goal-waiting-false-positive-2026-10-12"
UPDATED_AT = "2026-10-12T18:10:00-04:00"
RETIRED_TAXONOMY_IDS = {
    "request_relationship": {"unclear"},
    "recovery": {"goal_reassignment", "unknown"},
}


def main() -> None:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    published_ids = {
        row["episode_id"] for row in canonical["confirmed_episodes"]
    }
    if EPISODE_ID in published_ids:
        raise SystemExit(f"canonical invalidation is not applied: {EPISODE_ID}")

    document = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    retired = json.loads(RETIRED.read_text(encoding="utf-8"))
    already_applied = REVIEW_ID in document.setdefault(
        "merged_review_ids", []
    )
    annotation = document["annotations"].pop(EPISODE_ID, None)
    retired_rows = retired.setdefault("annotations", {})
    if annotation is not None:
        if EPISODE_ID in retired_rows and retired_rows[EPISODE_ID] != annotation:
            raise SystemExit(f"retired annotation conflicts: {EPISODE_ID}")
        retired_rows[EPISODE_ID] = annotation
    elif EPISODE_ID not in retired_rows:
        raise SystemExit(f"annotation is missing from active and retired data: {EPISODE_ID}")

    for kind, retired_ids in RETIRED_TAXONOMY_IDS.items():
        document["taxonomies"][kind] = [
            row for row in document["taxonomies"][kind]
            if row.get("id") not in retired_ids
        ]

    active = document["annotations"].values()
    used_relationships = {
        row.get("request_relationship") for row in active
    }
    used_recoveries = {
        value for row in active
        for value in row.get("recovery_mechanisms") or []
    }
    if used_relationships & RETIRED_TAXONOMY_IDS["request_relationship"]:
        raise SystemExit("a retired request relationship is still active")
    if used_recoveries & RETIRED_TAXONOMY_IDS["recovery"]:
        raise SystemExit("a retired recovery mechanism is still active")

    if not already_applied:
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = (
            f"{head}-v{int(number) + 1}" if number.isdigit() else seed
        )
    retired.update({
        "schema_version": 1,
        "updated_at": UPDATED_AT,
        "reason": (
            "Preserves human annotations for records removed from the "
            "canonical confirmed-episode publication by reviewed merges or "
            "invalidations."
        ),
    })

    ANNOTATIONS.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    RETIRED.write_text(
        json.dumps(retired, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Archived 1 pre-goal false positive; retired 3 unused taxonomy values"
    )


if __name__ == "__main__":
    main()
