#!/usr/bin/env python3
"""Manually reviewed annotations for tool-level trigger evidence."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REVIEWED_AT = "2026-10-11T02:40:00-04:00"

REVIEWS = {
    "episode-v2-c9128ae6c4a4113d": (["pause"], "", "no_request", "dependency_wait", "not_corrected", "DeepSeek-V4-Pro repeatedly paused while waiting for interviews, predictions and peer updates. The stand-by posture continued at the evidence boundary."),
    "episode-v2-671a08d8c01fdec8": (["pause"], "", "no_request", "end_of_day", "not_corrected", "Luna entered a late-day availability-and-pause loop after its bounded collaboration work was complete. The final supplied action is another pause, so no recovery is observed."),
    "episode-e127a9995b43c845": (["self_initiated_or_continuation"], "", "no_request", "", "not_corrected", "Sonnet 4.5 concluded that its Twitter strategy had failed and independently pivoted to Substack relationship work, which remained active at the evidence boundary."),
    "episode-2882c6c26317c0d1": (["user_message"], "Minuteandone", "targeted_request", "", "not_corrected", "Minuteandone directly asked Gemini to create a dedicated Creature ARG repository. Gemini maintained and coordinated that project through the evidence boundary."),
    "episode-v2-4ddbbddee84ba2bf": (["pause"], "", "no_request", "monitoring_loop", "unknown", "Sol repeatedly paused between Manifold feed gates to let market activity accumulate. Individual resumptions did not durably end the recurring monitoring loop, and later coverage is missing."),
    "episode-073ac5f6649264da": (["user_message"], "Minuteandone", "targeted_request", "", "not_corrected", "Minuteandone requested extending the creatures outside merchandise. Gemini built and coordinated the resulting ARG tracker, which remained active at the evidence boundary."),
    "episode-v2-d317d28ce322f59d": (["pause"], "", "no_request", "dependency_wait", "unknown", "Opus 5 used long foreground sleeps while waiting for background search computations even though independent conjecture work was available. The recurring pattern's final cessation is unresolved."),
    "episode-5c7457a0d79e65de": (["self_initiated_or_continuation"], "", "no_request", "", "not_corrected", "An external email said the Shorts played in incognito, undercutting rather than causing GPT-5.2's HOLD. The actual cause was its pre-existing self-imposed verification gate, which persisted through the evidence boundary."),
    "episode-v2-377d229c7bdac94a": (["pause"], "", "no_request", "dependency_wait", "not_corrected", "Luna repeatedly paused while requiring a fresh Luna-directed invitation before acting. This self-imposed dependency posture continued through the final supplied day."),
    "episode-v2-cb49903a3d202726": (["agent_message_or_request"], "Claude Sonnet 5.5", "targeted_request", "", "finished_activity", "Sonnet 5.5 directly requested ordinary LUMEN feedback. Luna completed the detailed media review and acknowledged the resulting polish update, ending the bounded activity."),
    "episode-v2-d71a8da8855d36e6": (["pause"], "", "no_request", "end_of_day", "not_corrected", "Sonnet 5.5 stopped near close after deciding another LUMEN episode could not be finished before 5 PM. The final supplied event is the pause, so no recovery is observed."),
}


def evidence_ids(episode):
    ids = []
    for role in ("trigger", "transition", "activity"):
        items = ((episode.get("evidence") or {}).get(role) or {}).get("items") or []
        for item in items[:1]:
            event_id = item.get("event_id") or (item.get("source") or {}).get("event_id")
            if event_id and event_id not in ids:
                ids.append(event_id)
    end_event = ((episode.get("drift_end") or {}).get("evidence") or {}).get("event_id")
    if end_event and end_event not in ids:
        ids.append(end_event)
    return ids


def main():
    seed = json.loads(ANNOTATIONS_PATH.read_text())
    bundle = json.loads(BUNDLE_PATH.read_text())
    episodes = {episode["episode_id"]: episode for episode in bundle["confirmed_episodes"]}
    overlaps = sorted(set(REVIEWS) & set(seed["annotations"]))
    if overlaps:
        raise RuntimeError(f"Refusing to overwrite existing annotations: {overlaps}")
    for episode_id, (triggers, actor, relationship, pause, recovery, note) in REVIEWS.items():
        episode = episodes[episode_id]
        trigger = (episode.get("evidence") or {}).get("trigger") or {}
        seed["annotations"][episode_id] = {
            "trigger_categories": triggers, "trigger_actor": actor,
            "request_relationship": relationship, "pause_context": pause,
            "recovery_mechanisms": [recovery], "notes": note, "follow_ups": [],
            "provenance": {
                "confidence": "high", "evidence_event_ids": evidence_ids(episode),
                "kind": "manual_source_evidence_review", "makes_model_calls": False,
                "reviewed_at": REVIEWED_AT, "reviewer": "codex",
                "selection_disposition": "tool_trigger_manual_review",
                "trigger_evidence_status": trigger.get("status", "direct"),
            },
            "updated_at": REVIEWED_AT,
        }
    seed["seed_id"] = "goalmax-manual-review-2026-10-11-v13"
    review_id = "goalmax-tool-trigger-manual-2026-10-11-v1"
    if review_id not in seed.setdefault("merged_review_ids", []):
        seed["merged_review_ids"].append(review_id)
    ANNOTATIONS_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n")
    print(f"Added {len(REVIEWS)} tool-trigger annotations")


if __name__ == "__main__":
    main()
