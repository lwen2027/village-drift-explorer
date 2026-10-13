#!/usr/bin/env python3
"""Integrate the source-reviewed Haiku 4.5 goal-max pause reaudit."""

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
REVIEW_ID = "haiku45-goalmax-pause-reaudit-2026-10-12"
UPDATED_AT = "2026-10-12T23:58:00-04:00"

INVALIDATED_IDS = {
    "episode-v2-d37870bea3485ab9",
    "episode-v2-839181971dab3a43",
    "episode-v2-8c10666565957d2e",
    "episode-v2-6cc7e04b17b924a1",
    "episode-v2-4a8d7653bd58a416",
    "episode-v2-4c8486a9c3bd87f8",
    "episode-v2-1dfdd1e0058e1011",
    "episode-v2-1d2e2b4b793b26f8",
    "episode-v2-16e4ecb85ce5c88e",
    "episode-v2-671f6c314093483c",
    "episode-v2-cc1e06c8f9193308",
    "episode-v2-51d1e3d2a85e3c89",
    "episode-v2-5ee86c4f4f458ae1",
    "episode-v2-aaec730c7ce5050c",
    "episode-v2-91b61afb7e1cd7de",
    "episode-v2-7242db481d237d08",
    "episode-v2-cc6d5f4bb91028c2",
}

RETAINED_IDS = {
    "episode-v2-730de19ab24c40db",
    "episode-v2-f3a4aac2c1c718f4",
    "episode-v2-3b9bc261cedab9d0",
    "episode-v2-5319e3dd5a3ce1fd",
    "episode-v2-2b2b028892e54971",
    "episode-v2-3936c4d0f0956e03",
    "episode-v2-c225a4f93371dbfb",
    "episode-v2-618d986973f3900c",
}


def bump_seed(document: dict) -> None:
    seed = str(document.get("seed_id") or "")
    head, _, number = seed.rpartition("-v")
    if number.isdigit():
        document["seed_id"] = f"{head}-v{int(number) + 1}"


def main() -> None:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    published_ids = {
        row["episode_id"] for row in canonical["confirmed_episodes"]
    }
    still_published = sorted(INVALIDATED_IDS & published_ids)
    if still_published:
        raise SystemExit(
            "canonical invalidations are not applied: "
            + ", ".join(still_published)
        )
    missing_retained = sorted(RETAINED_IDS - published_ids)
    if missing_retained:
        raise SystemExit(
            "retained Haiku episodes are missing: "
            + ", ".join(missing_retained)
        )

    document = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    retired = json.loads(RETIRED.read_text(encoding="utf-8"))
    annotations = document["annotations"]
    retired_rows = retired.setdefault("annotations", {})

    for episode_id in sorted(INVALIDATED_IDS):
        annotation = annotations.pop(episode_id, None)
        if annotation is None:
            if episode_id not in retired_rows:
                raise SystemExit(
                    f"annotation missing from active and retired data: {episode_id}"
                )
            continue
        prior = retired_rows.get(episode_id)
        if prior is not None and prior != annotation:
            raise SystemExit(f"retired annotation conflicts: {episode_id}")
        retired_rows[episode_id] = annotation

    scheduled = annotations["episode-v2-f3a4aac2c1c718f4"]
    scheduled["pause_context"] = "scheduled_wait"
    scheduled["recovery_mechanisms"] = [
        "custom_scheduled_checkpoint_reached"
    ]
    scheduled["notes"] = (
        "Haiku prematurely treated the 4 PM checkpoint as complete at "
        "2:28 PM, then entered back-to-back pauses including a ninety-minute "
        "scheduled wait before returning at the checkpoint."
    )
    scheduled["updated_at"] = UPDATED_AT
    scheduled.setdefault("provenance", {}).update({
        "classification_source": "codex_full_raw_reasoning_review",
        "verification_status": "raw_source_verified",
        "verified_at": UPDATED_AT,
    })

    calendar = annotations["episode-v2-618d986973f3900c"]
    calendar["trigger_categories"] = [
        "operator_or_system_event",
        "pause",
    ]
    calendar["notes"] = (
        "A stale or confusing Village pause state led Haiku to wait for "
        "Monday even though Monday had already begun. The five-minute "
        "calendar-confusion pause ends when Haiku checks the current day and "
        "resumes its wellbeing coordination."
    )
    calendar["updated_at"] = UPDATED_AT
    calendar.setdefault("provenance", {}).update({
        "classification_source": "codex_full_raw_reasoning_review",
        "verification_status": "raw_source_verified",
        "verified_at": UPDATED_AT,
    })

    merged = document.setdefault("merged_review_ids", [])
    if REVIEW_ID not in merged:
        merged.append(REVIEW_ID)
        bump_seed(document)

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
        "Archived 17 Haiku false-positive annotations and updated 2 retained "
        "pause annotations"
    )


if __name__ == "__main__":
    main()
