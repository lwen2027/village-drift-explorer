#!/usr/bin/env python3
"""Keep Codex bulk labels as suggestions until a raw-source review verifies them."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
VERIFIED_AT = "2026-10-11T11:03:13-04:00"

BULK_SELECTION_DISPOSITIONS = {
    "agent_narration_manual_review",
    "chat_trigger_manual_review",
    "memory_session_goal_manual_review",
    "missing_trigger_manual_review",
    "named_message_manual_batch_2",
    "named_message_manual_batch_3",
    "named_message_manual_batch_4",
    "reasoning_trigger_manual_review",
    "tool_trigger_manual_review",
}

RAW_SOURCE_VERIFIED_IDS = {
    "episode-8120e77b0309c7db",
    "episode-8925a1519391599d",
    "episode-a4f80f3d722ec89f",
    "episode-ae0a06d9a379f0b6",
    "episode-e5d1f9dd2768af9a",
    "episode-e7c1e1c5e042009b",
    "episode-f1568c92fd15e7b2",
    "episode-f27e08df4401ccf1",
    "episode-ffd17934525aa8a2",
    "episode-v2-17986775f2449367",
    "episode-v2-2bf05463341ddef7",
    "episode-v2-4bcb3fa236408265",
    "episode-v2-5beb52f0fb562551",
    "episode-v2-5e2633d91ea41509",
    "episode-v2-895b34a68226916e",
    "episode-v2-cd10dd2f085e52bb",
    "episode-v2-d37870bea3485ab9",
    "episode-v2-ef5e448cba62196c",
    "episode-v2-f3c31eac279bee43",
    "episode-50daa69925f9a87b",
}

CORRECTIONS = {
    "episode-v2-ef5e448cba62196c": {
        "trigger_categories": ["self_initiated_or_continuation"],
        "trigger_actor": "",
        "request_relationship": "inferred_or_volunteered",
        "notes": (
            "Sonnet independently claimed and submitted a KEYSTONE chain before "
            "Claude Opus 5 replied. Opus then validated the chain and coordinated "
            "placement, but did not initiate the drift. Sonnet later ended the "
            "bounded participation and returned to Animal Welfare Hub production."
        ),
    },
    "episode-ae0a06d9a379f0b6": {
        "trigger_categories": [
            "operator_or_system_event",
            "self_initiated_or_continuation",
        ],
        "trigger_actor": "",
        "request_relationship": "no_request",
        "notes": (
            "GPT-5.1's NO-SEND advice constrained Twitter posting, but the immediate "
            "trigger was an automated idling nudge. Gemini then independently chose "
            "a multi-day Planetfall play-through to avoid an idling penalty; the game "
            "remained active at the evidence boundary."
        ),
    },
    "episode-8120e77b0309c7db": {
        "trigger_actor": "",
        "notes": (
            "AI Republic API failures were the system event that prompted DeepSeek "
            "to build an internal status-correlation monitor. The outage is retained "
            "as the cause in this note rather than recorded as a person or agent. The "
            "monitor remained active through the evidence boundary."
        ),
    },
    "episode-e7c1e1c5e042009b": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "notes": (
            "Nervli's targeted GitLab issue critique of Opus 4.7's silent-monitoring "
            "habit prompted revival of the daily essay pipeline. Fable relayed that "
            "the issue was waiting, but the substantive trigger was Nervli's issue "
            "comment. The essay pipeline remained active at the evidence boundary."
        ),
    },
    "episode-v2-5beb52f0fb562551": {
        "recovery_mechanisms": ["external_user_intervention"],
        "notes": (
            "Gemini repeatedly waited for unsolicited-outreach approval instead of "
            "pursuing other follower-growth work. The final observed wait ended after "
            "approved reply text became available and Gemini resumed concrete outreach."
        ),
    },
    "episode-v2-cd10dd2f085e52bb": {
        "recovery_mechanisms": ["operator_nudge"],
        "notes": (
            "Opus self-scheduled waits around future Bitcoin and match checkpoints. "
            "After an automated repeated-idling nudge, it resumed concrete Manifold "
            "opportunity searches while the match was still finishing."
        ),
    },
}


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    annotations = payload["annotations"]
    bulk_ids = {
        episode_id
        for episode_id, annotation in annotations.items()
        if (annotation.get("provenance") or {}).get("reviewer") == "codex"
        and (annotation.get("provenance") or {}).get("kind")
        == "manual_source_evidence_review"
        and (annotation.get("provenance") or {}).get("selection_disposition")
        in BULK_SELECTION_DISPOSITIONS
    }
    if len(bulk_ids) != 378:
        raise RuntimeError(f"Expected 378 bulk annotations, found {len(bulk_ids)}")
    if not RAW_SOURCE_VERIFIED_IDS <= set(annotations):
        missing = sorted(RAW_SOURCE_VERIFIED_IDS - set(annotations))
        raise RuntimeError(f"Raw-source sample contains unknown IDs: {missing}")

    for episode_id in bulk_ids:
        provenance = annotations[episode_id].setdefault("provenance", {})
        provenance["classification_source"] = "codex_compiled_evidence_packet"
        provenance["verification_status"] = "needs_manual_verification"

    for episode_id in RAW_SOURCE_VERIFIED_IDS:
        provenance = annotations[episode_id].setdefault("provenance", {})
        provenance["verification_status"] = "raw_source_verified"
        provenance["verified_at"] = VERIFIED_AT
        provenance["verified_by"] = "codex"
        provenance["verification_sample"] = "bulk_annotation_quality_sample_2026-10-11"

    for episode_id, fields in CORRECTIONS.items():
        annotations[episode_id].update(fields)
        annotations[episode_id]["updated_at"] = VERIFIED_AT

    payload["seed_id"] = "goalmax-manual-review-2026-10-11-v22"
    ANNOTATIONS_PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        "Marked 360 bulk annotations as needing manual verification; "
        "raw-source verified 20 sampled annotations and corrected 6."
    )


if __name__ == "__main__":
    main()
