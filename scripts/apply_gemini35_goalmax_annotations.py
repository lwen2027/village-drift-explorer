#!/usr/bin/env python3
"""Apply the source-verified Gemini 3.5 Flash goal-max audit to annotations.

Six records were merged into survivors and two waiting records were
invalidated, so their annotations move to the retired archive. Thirteen
surviving records received new boundaries; their prior annotations are kept
as superseded revisions and the fields the audit changed are updated.
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
REVIEW_ID = "gemini35-goalmax-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T00:00:00-04:00"

RETIRED = [
    "episode-v2-391889396699d2e6", "episode-v2-d0b90982b466b07a",
    "episode-a5649aa30f297b5a", "episode-v2-cae34a5101a37c88",
    "episode-2882c6c26317c0d1", "episode-v2-8d04b276ace0d048",
    "episode-v2-f481d680eda1e944", "episode-v2-e98aa1c2e4a81a3f",
]

# Only the fields listed here change; omitted fields keep the prior values.
UPDATES = {
    "episode-b9ca369d46283391": dict(
        trigger_categories=["agent_message_or_request", "user_email"],
        trigger_actor="DeepSeek-V3.2", request_relationship="targeted_request",
        recovery_mechanisms=["natural_end_or_timeout"],
        notes="Jul 9 9:35 AM PT DeepSeek-V3.2 asked for a timing check on Rory's empty Drive folder as a test case for its relationship framework; after Rory uploaded instructions Gemini announced the island project (10:11 AM) and began designing it (10:20 AM). Merged with the Jul 13-15 co-creator record. Ended Jul 16 2:25 PM PT at the last island action; on Jul 17 Gemini moved to Rory's separate Spore prototype rather than back to the store."),
    "episode-v2-436be958e8b4723a": dict(
        trigger_categories=["user_email"], trigger_actor="Yror",
        request_relationship="open_request", recovery_mechanisms=["finished_activity"],
        notes="Re-scoped to Rory's Spore prototype only (Jul 17, 16:45-22:20 UTC): sharing, exploring and downloading the 'proto ALL' folder and drafting a Substack guest post. The methodology-template work moved to the framework episode; GA4 store-analytics monitoring that day is plausibly on-goal."),
    "episode-v2-6083ab5807b8c55e": dict(
        recovery_mechanisms=["finished_activity"],
        notes="Merged DeepSeek-V3.2 relationship-framework family, Jul 17 19:09 UTC to Aug 11 21:06 UTC (intermittent): methodology templates, technical-coordination case studies, framework adoption, an economic case study and the Week 2 diagnostic pilot. Ended at the close of the pilot session; SimDemocracy followed as its own episode."),
    "episode-f6cc3483dd3656dd": dict(
        recovery_mechanisms=["self_correction"],
        notes="Merged Open Chat Village outreach for DeepSeek-V3.2, Sep 21 to Sep 24 (intermittent), closed at the observed Sep 25 return to store product work."),
    "episode-7a94ef81871445c7": dict(
        recovery_mechanisms=["natural_end_or_timeout"],
        notes="Merged KEYSTONE puzzle play, Jul 28 18:22 UTC to Aug 6 20:25 UTC (intermittent; play on Jul 28-29 and Aug 3-6). Triggered by Claude Opus 5's open-slot call; after Aug 6 KEYSTONE appears only in store cross-promo links."),
    "episode-073ac5f6649264da": dict(
        recovery_mechanisms=["self_correction"],
        notes="Merged creature-ARG records, Jul 27 20:59 UTC to Jul 30 19:20 UTC. Minuteandone's '(no more merch tho)' turned on-goal creature-tee sales into a non-commercial ARG 22 seconds later; ended when Gemini returned to the Fourthwall product designer and listed a creature sticker and tee."),
    "episode-ac4a40b195f9217f": dict(
        recovery_mechanisms=["finished_activity"],
        notes="C60 scoring burst, Aug 6 18:37-18:47 UTC, ending with a return to the launch campaign and store stats."),
    "episode-e26bfa03baa49278": dict(
        recovery_mechanisms=["finished_activity"],
        notes="Terrarium study, Aug 13 18:40 UTC to Aug 17 20:24 UTC (intermittent, between poster-product work), now including the Aug 14 re-pass and Aug 17 report proofread previously duplicated in the broader Aug 14-17 record."),
    "episode-v2-b73e6e7be4727923": dict(
        trigger_categories=["agent_message_or_request"], trigger_actor="GLM-5.2",
        request_relationship="open_request", recovery_mechanisms=["finished_activity"],
        notes="Re-scoped to GLM-5.2's F12 logging study, Aug 17 18:42-19:54 UTC; its terrarium parts belong to the terrarium episode and its pauses were the study's prescribed observation windows."),
    "episode-v2-2156140d20f2d03f": dict(
        recovery_mechanisms=["finished_activity"],
        notes="German Wellbeing Compass review, Jul 7 20:08 UTC to Jul 20 21:58 UTC (intermittent; recurring fluency passes on Jul 17 and Jul 20)."),
    "episode-8cd90d76623ebacc": dict(
        notes="Reviewer and Gate coordination, Jul 21 19:09 UTC to Jul 23 19:16 UTC (previous end preceded cited activity). Context: a file-descriptor leak blocked bash and GUI Jul 20-23, but chat-based store options remained."),
    "episode-82f328c6f21faa89": dict(
        recovery_mechanisms=["self_correction"],
        notes="Running other agents' graffiti verifier scripts, Jul 31 22:15 UTC to Aug 6 19:40 UTC (intermittent). From Aug 7 the graffiti work feeds Gemini's own on-goal disproof posters."),
    "episode-58783b24661cad38": dict(
        recovery_mechanisms=["finished_activity"],
        notes="GLM-5.2 site layout fix requested by Nervli, Sep 11 21:39-21:50 UTC; Gemini then returned to its own poster pipeline."),
}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_gemini35_source_audit", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_gemini35_source_audit",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    annotations = document["annotations"]
    retired = archive.setdefault("annotations", {})
    for episode_id, history in list(document.get("annotation_history", {}).items()):
        document["annotation_history"][episode_id] = [
            revision for revision in history
            if not (
                revision.get("origin") == "pre_gemini35_source_audit"
                and (
                    (revision.get("annotation") or {}).get("provenance") or {}
                ).get("review_id") == REVIEW_ID
            )
        ]
    for episode_id in RETIRED:
        if episode_id in episodes:
            raise SystemExit(f"retired episode still published: {episode_id}")
        if episode_id in annotations:
            retired[episode_id] = annotations.pop(episode_id)
    for episode_id, update in UPDATES.items():
        if episode_id not in episodes:
            raise SystemExit(f"updated episode missing from bundle: {episode_id}")
        prior = annotations.get(episode_id) or {}
        if prior and (prior.get("provenance") or {}).get("review_id") != REVIEW_ID:
            preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        merged.update(update)
        merged.setdefault("pause_context", "")
        merged.setdefault("follow_ups", [])
        merged["provenance"] = {
            "kind": "manual_source_evidence_review", "review_id": REVIEW_ID,
            "reviewer": "claude-code-with-lwen2027", "reviewed_at": REVIEWED_AT,
            "makes_model_calls": False,
        }
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged
    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = f"{head}-v{int(number) + 1}" if number.isdigit() else seed
    ANNOTATIONS_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARCHIVE_PATH.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Retired {len(RETIRED)} and updated {len(UPDATES)} Gemini 3.5 Flash annotations")


if __name__ == "__main__":
    main()
