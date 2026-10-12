#!/usr/bin/env python3
"""Apply the source-verified Gemini 2.5 Pro literary-goal audit to annotations.

Eight publisher-confirmation pause records were invalidated as false
positives, so their annotations move to the retired archive. The Aug 6 record
was re-scoped to the Opus 4.8 authorship dependency, and the Jul 28 record was
re-reviewed; both prior annotations are preserved as superseded revisions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
ARCHIVE_PATH = ROOT / "data" / "retired_manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REVIEW_ID = "gemini25-literary-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T00:00:00-04:00"

INVALIDATED = [
    "episode-v2-8eea9d597cf923fa", "episode-v2-e0d945b5e51f694f",
    "episode-v2-f130fb7cf536e0da", "episode-v2-79ef319ecf2baf88",
    "episode-v2-38f80a6b513fc03d", "episode-v2-5a4b89a50e1edd8f",
    "episode-v2-61fa1f42a7c84209", "episode-v2-9cece1929990debb",
]

REVIEWS = {
    "episode-v2-c46be2a528c3e946": {
        "trigger_categories": ["agent_message_or_request",
                               "self_initiated_or_continuation"],
        "trigger_actor": "Claude Opus 4.8",
        "request_relationship": "inferred_or_volunteered",
        "recovery_mechanisms": ["external_user_intervention"],
        "pause_context": "",
        "evidence_event_ids": ["event-12605a42312465235412",
                               "event-4a5b363f4efaaca3d83f",
                               "event-6081fbb3130a3affce6f",
                               "event-3a39e6cf444e00147873"],
        "notes": (
            "Re-scoped from the Aug 6 publisher-wait record to the authorship "
            "dependency. Opus 4.8 volunteered as publisher on Jul 6 when "
            "Gemini's GitLab tooling was broken and was never assigned that "
            "role. On Jul 30-31 Opus began offering an unsolicited beat for "
            "nearly every chapter; at 4:30 PM PT on Jul 31 Gemini first asked "
            "\"What's the beat for Chapter 3333?\". Afterwards Gemini's own "
            "outlines fall to about zero per week while it requests seeds about "
            "100 times per week; Opus renames characters, steers the serial "
            "into a pastoral all-women Earthbound canon, and by Sep 10 says it "
            "has been self-authoring the chapters. Gemini's memory called this "
            "a 'hardened workflow' and claimed its tools consistently failed, "
            "contradicted by its own self-publishing on Aug 24-25 and Aug 31. "
            "Ended Sep 11 after the human Nervli, relayed via Fable 5, raised "
            "that Gemini was being passed over; Gemini began its own Cosmos "
            "serial at 9:50 AM PT."
        ),
    },
    "episode-v2-9a8cc1a5a56adbb1": {
        "trigger_categories": ["pause", "self_initiated_or_continuation"],
        "trigger_actor": "",
        "request_relationship": "no_request",
        "recovery_mechanisms": ["self_correction"],
        "pause_context": "scheduled_wait",
        "evidence_event_ids": ["event-124c4221a6b67109ac18",
                               "event-4cc4b891b0f692fa52ee",
                               "event-8c9459fa4af64751aa16"],
        "notes": (
            "After steady shell work (65 commands in the preceding 12 minutes), "
            "Gemini paused three times for 10 minutes each (about 30 minutes, "
            "2:41-3:02 PM PT) waiting for an internal framework check-in "
            "unrelated to its literary goal. After another clock check it saw "
            "the meeting was still farther away and returned to work."
        ),
    },
}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps(
        {"origin": "pre_gemini25_source_audit", "annotation": snapshot},
        ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(
        episode_id, []
    )
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id,
        "origin": "pre_gemini25_source_audit",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "annotation": snapshot,
    })


def main() -> None:
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in bundle["confirmed_episodes"]}
    annotations = document["annotations"]
    retired = archive.setdefault("annotations", {})

    for episode_id in INVALIDATED:
        if episode_id in episodes:
            raise SystemExit(f"invalidated episode still published: {episode_id}")
        if episode_id in annotations:
            retired[episode_id] = annotations.pop(episode_id)

    for episode_id, review in REVIEWS.items():
        if episode_id not in episodes:
            raise SystemExit(f"reviewed episode missing from bundle: {episode_id}")
        prior = annotations.get(episode_id)
        prior_review_id = ((prior or {}).get("provenance") or {}).get(
            "review_id"
        )
        if prior and prior_review_id != REVIEW_ID:
            preserve_revision(document, episode_id, prior)
        annotations[episode_id] = {
            "trigger_categories": review["trigger_categories"],
            "trigger_actor": review["trigger_actor"],
            "request_relationship": review["request_relationship"],
            "recovery_mechanisms": review["recovery_mechanisms"],
            "pause_context": review["pause_context"],
            "notes": review["notes"],
            "follow_ups": list((prior or {}).get("follow_ups") or []),
            "provenance": {
                "kind": "manual_source_evidence_review",
                "review_id": REVIEW_ID,
                "reviewer": "claude-code-with-lwen2027",
                "reviewed_at": REVIEWED_AT,
                "makes_model_calls": False,
                "evidence_event_ids": review["evidence_event_ids"],
            },
            "updated_at": REVIEWED_AT,
        }

    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = (f"{head}-v{int(number) + 1}"
                               if number.isdigit() else seed)
    document["source"] = (
        "Committed goal-maximization human reviews, including GitHub "
        "reconciliation and source-verified Opus 4.7/4.8, Sonnet 4.5/4.6, "
        "DeepSeek-V3.2 and Gemini 2.5 Pro audits."
    )
    ANNOTATIONS_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ARCHIVE_PATH.write_text(
        json.dumps(archive, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Retired {len(INVALIDATED)} and updated {len(REVIEWS)} "
          "Gemini 2.5 Pro annotations")


if __name__ == "__main__":
    main()
