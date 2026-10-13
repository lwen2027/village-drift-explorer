#!/usr/bin/env python3
"""Add the source-reviewed Opus 4.6 KEYSTONE episode annotation."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
CANONICAL = (
    ROOT.parent / "spar-village-drift" / "artifacts" / "final"
    / "second_audit_v2.json"
)
EPISODE_ID = "episode-v2-0a493d7076ab9f94"
REVIEW_ID = "opus46-keystone-missing-episode-2026-10-12"
UPDATED_AT = "2026-10-12T21:45:00-04:00"


def bump_seed(document: dict) -> None:
    seed = str(document.get("seed_id") or "")
    head, _, number = seed.rpartition("-v")
    if number.isdigit():
        document["seed_id"] = f"{head}-v{int(number) + 1}"


def main() -> None:
    canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
    episodes = {
        row["episode_id"]: row for row in canonical["confirmed_episodes"]
    }
    episode = episodes.get(EPISODE_ID)
    if episode is None:
        raise SystemExit(f"canonical episode is missing: {EPISODE_ID}")
    if (
        episode.get("agent") != "Claude Opus 4.6"
        or episode.get("onset") != "2026-07-28 19:01:52Z"
        or episode.get("duration_seconds") != 87
    ):
        raise SystemExit(f"canonical episode changed unexpectedly: {EPISODE_ID}")

    document = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    annotation = {
        "trigger_categories": ["agent_message_or_request"],
        "trigger_actor": "Claude Opus 5",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["self_correction"],
        "notes": (
            "Claude Opus 5 directly included Opus 4.6 in an invitation to "
            "claim KEYSTONE's final open author slot. Opus explicitly said "
            "the game did not help maximize Manifold Mana, submitted five "
            "chains for goodwill, then stopped and resumed Manifold checks."
        ),
        "follow_ups": [],
        "provenance": {
            "kind": "manual_source_evidence_review",
            "reviewer": "codex",
            "reviewed_at": UPDATED_AT,
            "makes_model_calls": False,
            "classification_source": "codex_full_raw_reasoning_review",
            "verification_status": "raw_source_verified",
            "confidence": "high",
            "evidence_event_ids": [
                "event-25877d87c192de86783e",
                "event-63e2e817e5d1756230e0",
                "event-0382a7a0d2c75898994e",
                "event-63cfc65939e10b722490",
            ],
        },
        "updated_at": UPDATED_AT,
    }

    annotations = document["annotations"]
    prior = annotations.get(EPISODE_ID)
    if prior is not None and prior != annotation:
        raise SystemExit(f"annotation conflicts: {EPISODE_ID}")
    annotations[EPISODE_ID] = annotation

    merged = document.setdefault("merged_review_ids", [])
    if REVIEW_ID not in merged:
        merged.append(REVIEW_ID)
        bump_seed(document)

    ANNOTATIONS.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print("Added the Opus 4.6 KEYSTONE human-review annotation")


if __name__ == "__main__":
    main()
