#!/usr/bin/env python3
"""Apply source-verified recovery labels and retire unused taxonomy values."""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REVIEW_ID = "return-boundary-repairs-2026-10-12"
REVIEWED_AT = "2026-10-12T17:18:14-04:00"
RETIRED_TRIGGER_IDS = {"no_discrete_trigger", "unknown"}
RETIRED_RECOVERY_IDS = {"custom_limited_scope"}

UPDATES = {
    "episode-v2-177f0301d7fb8c7c": {
        "expected_recovery": ["unknown"],
        "recovery_mechanisms": ["peer_feedback"],
        "note": (
            "GPT-5.1 supplied the requested feedback at 23:54:30 UTC; "
            "Sonnet resumed executed Wellbeing Compass work at 23:57:49 UTC."
        ),
        "evidence_event_ids": [
            "event-9bdbc28cf8749df11475",
            "event-62cd1ec4573b631aa854",
        ],
    },
    "episode-v2-b4e2e4bc592db0ef": {
        "expected_recovery": ["custom_limited_scope"],
        "recovery_mechanisms": ["finished_activity"],
        "note": (
            "After completing and delivering the final DDPM morph, Fable "
            "returned to Fourthwall sales and product analysis at "
            "18:34:02 UTC on August 20."
        ),
        "evidence_event_ids": [
            "event-783b3b483d1cdcb6f09a",
            "event-3521fc57ac6cd0a8cc1e",
        ],
    },
}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps(
        {"origin": "pre_return_boundary_repair", "annotation": snapshot},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(
        episode_id, []
    )
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id,
        "origin": "pre_return_boundary_repair",
        "superseded_by": REVIEW_ID,
        "recorded_at": "2026-10-12T21:18:14Z",
        "annotation": snapshot,
    })


def append_note(existing: str, note: str) -> str:
    existing = str(existing or "").strip()
    if note in existing:
        return existing
    return f"{existing}\n\n{note}" if existing else note


def main() -> None:
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    episodes = {
        row["episode_id"]: row
        for row in json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))[
            "confirmed_episodes"
        ]
    }
    annotations = document["annotations"]
    already_applied = REVIEW_ID in document.setdefault("merged_review_ids", [])

    for episode_id, update in UPDATES.items():
        episode = episodes.get(episode_id)
        annotation = annotations.get(episode_id)
        if not episode or not annotation:
            raise SystemExit(f"return-boundary episode missing: {episode_id}")
        if (episode.get("drift_end") or {}).get("status") != "returned_to_goal":
            raise SystemExit(f"canonical return is not published: {episode_id}")
        if not already_applied and annotation.get("recovery_mechanisms") != update[
            "expected_recovery"
        ]:
            raise SystemExit(f"recovery input changed: {episode_id}")
        if already_applied:
            continue
        preserve_revision(document, episode_id, annotation)
        merged = copy.deepcopy(annotation)
        merged["recovery_mechanisms"] = list(update["recovery_mechanisms"])
        merged["notes"] = append_note(merged.get("notes"), update["note"])
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "kind": "manual_source_evidence_review",
            "review_id": REVIEW_ID,
            "reviewer": "codex_with_full_local_source_archive",
            "reviewed_at": REVIEWED_AT,
            "verification_status": "raw_source_verified",
            "evidence_event_ids": list(update["evidence_event_ids"]),
            "makes_model_calls": False,
        })
        merged["provenance"] = provenance
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged

    document["taxonomies"]["trigger"] = [
        row for row in document["taxonomies"]["trigger"]
        if row.get("id") not in RETIRED_TRIGGER_IDS
    ]
    document["taxonomies"]["recovery"] = [
        row for row in document["taxonomies"]["recovery"]
        if row.get("id") not in RETIRED_RECOVERY_IDS
    ]
    used_triggers = {
        value for annotation in annotations.values()
        for value in annotation.get("trigger_categories") or []
    }
    used_recoveries = {
        value for annotation in annotations.values()
        for value in annotation.get("recovery_mechanisms") or []
    }
    if used_triggers & RETIRED_TRIGGER_IDS:
        raise SystemExit("retired trigger values are still used")
    if used_recoveries & RETIRED_RECOVERY_IDS:
        raise SystemExit("retired recovery values are still used")

    if not already_applied:
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = (
            f"{head}-v{int(number) + 1}" if number.isdigit() else seed
        )
    ANNOTATIONS_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Updated 2 return annotations; retired 2 trigger values and "
        "1 recovery value"
    )


if __name__ == "__main__":
    main()
