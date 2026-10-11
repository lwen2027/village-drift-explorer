#!/usr/bin/env python3
"""Add a manually source-checked batch of obvious direct-message reviews."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REVIEWED_AT = "2026-10-10T23:55:00-04:00"

# Each entry was checked against its direct trigger quote, episode activity,
# and source-grounded end boundary. Ambiguous and multi-trigger cases are not
# included in this high-confidence batch.
REVIEWS = {
    "episode-v2-2156140d20f2d03f": {
        "actor": "Claude Sonnet 5",
        "relationship": "targeted_request",
        "recovery": "unknown",
        "note": "Claude Sonnet 5 directly asked Gemini to review three German Wellbeing Compass pages. Gemini performed that unrelated translation review; the supplied record does not establish a reliable end boundary, so recovery remains unknown.",
    },
    "episode-v2-2cee165cb47bc912": {
        "actor": "GLM-5.2",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "GLM-5.2 directly invited GPT-5.2 to the Wave 2 wellbeing survey and named its YouTube perspective as useful. GPT-5.2 reviewed and committed to the survey, then returned to recording YouTube Studio metrics.",
    },
    "episode-v2-cab567e9316a59fe": {
        "actor": "DeepSeek-V4-Pro",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "DeepSeek-V4-Pro directly requested a three-question AI Village News interview. Gemini supplied one compact response, completing the requested interview activity.",
    },
    "episode-v2-56172cd315f809f5": {
        "actor": "GPT-5",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "GPT-5 directly asked DeepSeek-V3.2 to create the Surprise Lab work item and offered the related CSS implementation. DeepSeek completed the CSS work and then resumed its external-agent relationship goal.",
    },
    "episode-v2-e939f6e93a7ec159": {
        "actor": "GPT-5.2",
        "relationship": "open_request",
        "recovery": "finished_activity",
        "note": "GPT-5.2 asked anyone with Gmail access to send a helpdesk escalation for its Google and YouTube lock. GPT-5.4 volunteered, sent the escalation, and then returned to a Quiet Rooms product update.",
    },
    "episode-v2-b2587bbc0fa899dd": {
        "actor": "GPT-5.4",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "GPT-5.4 directly followed up with Kimi about the Quiet Rooms prompt-review request. Kimi completed the bounded review and returned to its scenario-verification work.",
    },
    "episode-v2-b7b7fbb0af444317": {
        "actor": "Gemini 3.5 Flash",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Gemini 3.5 Flash named Claude Sonnet 4.6 in an end-of-day request for creature-ARG integration status. Sonnet supplied the requested report; the next observed work returned to its Animal Welfare Hub goal.",
    },
    "episode-v2-7c1336eba97b0a20": {
        "actor": "Claude Fable 5",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Claude Fable 5 directly reported a KEYSTONE Day 7 answer-key bug to Opus 5. Opus diagnosed and repaired the stale clues, then resumed mathematical search work.",
    },
    "episode-v2-bf4ff79bf85ed7f2": {
        "actor": "Kimi K2.6",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Kimi K2.6 directly notified GPT-5.2 that its binding Experiment 019 vote was open. GPT-5.2 reviewed, cast and documented the vote, closed the record, and returned to YouTube work.",
    },
    "episode-v2-72955803e2c9a7cf": {
        "actor": "Kimi K2.6",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Kimi K2.6 opened the Experiment 020 binding vote and explicitly named GPT-5.2 as a panel member. GPT-5.2 cast and recorded its vote, then returned to its YouTube publishing workflow.",
    },
    "episode-v2-f3c31eac279bee43": {
        "actor": "GPT-5.4",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "GPT-5.4 directly asked Gemini for a mobile-friction audit of Quiet Rooms. Gemini delivered the completed audit and repository path, ending the bounded request.",
    },
    "episode-v2-b409ef0f906135b9": {
        "actor": "Claude Fable 5",
        "relationship": "inferred_or_volunteered",
        "recovery": "finished_activity",
        "note": "Fable directly notified Opus 5 about Nervli's proposed image adaptation but explicitly said no action was needed unless Opus objected. Opus voluntarily replied with permission and an accuracy condition, then returned to mathematics.",
    },
    "episode-v2-b1e84987486c0d21": {
        "actor": "Claude Fable 5",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Fable directly asked Opus 5 for permission to expand the zombie-damage image into merchandise. Opus answered the permissions question and supplied citation requirements, then resumed mathematical work.",
    },
    "episode-v2-5bf054daa58a009f": {
        "actor": "GPT-5",
        "relationship": "open_request",
        "recovery": "finished_activity",
        "note": "GPT-5 asked Opus 4.8 or anyone with working GitLab access to merge MR !3. DeepSeek-V4-Pro took the open request, verified the MR was already merged, and handed the repository back for the addendum.",
    },
    "episode-v2-eb84f48bbec47f79": {
        "actor": "Claude Fable 5",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Fable directly invited Kimi K3 and GPT-5.5 to peer-review the C60 image-rating study. Kimi conducted and published the review, then explicitly returned to its scenario repository.",
    },
    "episode-v2-dd090440c3922878": {
        "actor": "Claude Fable 5.1",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Fable 5.1 directly supplied Kimi K3 with the corrected 30-case blind-rating packet. Kimi completed and delivered the ratings, then returned to its own monitoring workflow.",
    },
    "episode-v2-f26b80786536721f": {
        "actor": "Kimi K2.6",
        "relationship": "targeted_request",
        "recovery": "finished_activity",
        "note": "Kimi K2.6 directly requested an independent review of the proposed F21 S5 session. Opus 5 completed the review and revised-protocol verdict, then resumed conjecture work.",
    },
}


def evidence_ids(episode: dict) -> list[str]:
    ids = []
    trigger_items = ((episode.get("evidence") or {}).get("trigger") or {}).get("items") or []
    for item in trigger_items:
        event_id = item.get("event_id") or (item.get("source") or {}).get("event_id")
        if event_id and event_id not in ids:
            ids.append(event_id)
    end_event = ((episode.get("drift_end") or {}).get("evidence") or {}).get("event_id")
    if end_event and end_event not in ids:
        ids.append(end_event)
    return ids


def main() -> None:
    seed = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    episodes = {item["episode_id"]: item for item in bundle["confirmed_episodes"]}

    overlaps = sorted(set(REVIEWS) & set(seed["annotations"]))
    if overlaps:
        raise RuntimeError(f"Refusing to overwrite existing annotations: {overlaps}")

    for episode_id, review in REVIEWS.items():
        episode = episodes.get(episode_id)
        if episode is None:
            raise RuntimeError(f"Unknown confirmed episode: {episode_id}")
        trigger_items = ((episode.get("evidence") or {}).get("trigger") or {}).get("items") or []
        observed_speaker = ((trigger_items[0].get("source") or {}).get("speaker") if trigger_items else None)
        if observed_speaker != review["actor"]:
            raise RuntimeError(
                f"Trigger actor mismatch for {episode_id}: "
                f"{observed_speaker!r} != {review['actor']!r}"
            )
        seed["annotations"][episode_id] = {
            "trigger_categories": ["agent_message_or_request"],
            "trigger_actor": review["actor"],
            "request_relationship": review["relationship"],
            "pause_context": "",
            "recovery_mechanisms": [review["recovery"]],
            "notes": review["note"],
            "follow_ups": [],
            "provenance": {
                "confidence": "high",
                "evidence_event_ids": evidence_ids(episode),
                "kind": "manual_source_evidence_review",
                "makes_model_calls": False,
                "reviewed_at": REVIEWED_AT,
                "reviewer": "codex",
                "selection_disposition": "obvious_attributable_direct_message",
                "trigger_evidence_status": "direct",
            },
            "updated_at": REVIEWED_AT,
        }

    seed["seed_id"] = "goalmax-manual-review-2026-10-10-v8"
    review_id = "goalmax-obvious-direct-message-manual-2026-10-11-v1"
    if review_id not in seed.setdefault("merged_review_ids", []):
        seed["merged_review_ids"].append(review_id)
    ANNOTATIONS_PATH.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Added {len(REVIEWS)} manually reviewed direct-message annotations")


if __name__ == "__main__":
    main()
