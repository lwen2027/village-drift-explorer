#!/usr/bin/env python3
"""Add a third manually reviewed batch of named and relayed-message triggers."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REVIEWED_AT = "2026-10-11T01:05:00-04:00"


def r(speaker, actor, triggers, relationship, recovery, note, pause=""):
    return {
        "speaker": speaker, "actor": actor, "triggers": triggers,
        "relationship": relationship, "recovery": recovery,
        "note": note, "pause": pause,
    }


REVIEWS = {
    "episode-v2-f4142f74657ecb21": r(
        "Gemini 3.5 Flash", "Gemini 3.5 Flash", ["agent_message_or_request"],
        "targeted_request", "finished_activity",
        "Gemini 3.5 Flash delivered a Substack draft within an existing collaboration with Opus 4.5. This began a recurring peer-service arc that later included other peer requests; after its final recurrence, Opus returned by publishing a subscriber-facing article.",
    ),
    "episode-ae0a06d9a379f0b6": r(
        "GPT-5.1", "GPT-5.1", ["agent_message_or_request", "self_initiated_or_continuation"],
        "inferred_or_volunteered", "not_corrected",
        "GPT-5.1 advised treating X GUI posting as NO-SEND, constraining Gemini's normal route. Gemini then independently chose a multi-day Planetfall play-through after an idling nudge; the game remained active at the evidence boundary.",
    ),
    "episode-v2-eb8677f88710625a": r(
        "Claude Sonnet 5", "Claude Sonnet 5", ["agent_message_or_request"],
        "targeted_request", "finished_activity",
        "Claude Sonnet 5 directly asked Kimi to proofread the Chinese Wellbeing Compass pages. A second peer invitation added bounded KEYSTONE work; Kimi completed both and returned to scenario research.",
    ),
    "episode-v2-90ab430e424d58b9": r(
        "automated", "Automated monitor", ["operator_or_system_event", "pause"],
        "targeted_request", "self_correction",
        "An automated operator message identified GPT-5.1's repeated HOLD restatements. The episode was a monitoring loop around Gate 012B; GPT-5.1 ended it by creating a reusable ethics artifact rather than continuing to wait.",
        "monitoring_loop",
    ),
    "episode-726c358bc8e257ae": r(
        "automated", "Automated monitor", ["operator_or_system_event"],
        "targeted_request", "not_corrected",
        "An automated idling nudge told DeepSeek-V3.2 to take new action. The agent responded by reframing internal monitoring as a relationship-quality framework, which remained central at the evidence boundary.",
    ),
    "episode-957bee44e219f3d8": r(
        "Claude Opus 5", "Claude Opus 5", ["agent_message_or_request"],
        "open_request", "not_corrected",
        "Opus 5 repeatedly issued open invitations for independent graph-disproof verification. GLM-5.2 adopted a standing verifier and counter-update role that remained in its session goals at the evidence boundary.",
    ),
    "episode-82f328c6f21faa89": r(
        "GLM-5.2", "GLM-5.2", ["agent_message_or_request", "self_initiated_or_continuation"],
        "targeted_request", "not_corrected",
        "Gemini's earliest verifier runs were self-initiated during the disproof cascade; GLM-5.2 then directly requested another verifier run and peers formalized the role. Gemini was still validating new disproofs at the evidence boundary.",
    ),
    "episode-e5d1f9dd2768af9a": r(
        "GPT-5.1", "GPT-5.1", ["agent_message_or_request"],
        "inferred_or_volunteered", "not_corrected",
        "GPT-5.1 supplied an ethics critique of DeepSeek's relationship-tier framing. DeepSeek inferred a broader engagement-diagnostic framework from peer feedback and was still running its pilot at the evidence boundary.",
    ),
    "episode-ac4a40b195f9217f": r(
        "Claude Fable 5", "Claude Fable 5", ["agent_message_or_request"],
        "targeted_request", "unknown",
        "Fable directly reminded Gemini that its C60 axis-A/D scoring columns remained open. Gemini completed the 31-row scoring work and later returned to its store, but the exact validated end boundary remains unresolved.",
    ),
    "episode-e7adbd65951a7e92": r(
        "Claude Fable 5", "Nervli", ["user_message"],
        "targeted_request", "unknown",
        "Fable relayed Nervli's direct Issue #23 message to Opus 4.7. Nervli's critique prompted the dormant essay project; later Owlet work is visible, but the essay rhythm remained planned and the exact end is unresolved.",
    ),
    "episode-v2-e85e5b00b4ee4e4e": r(
        "DeepSeek-V3.2", "DeepSeek-V3.2", ["agent_message_or_request"],
        "targeted_request", "finished_activity",
        "DeepSeek-V3.2 directly followed up with Sonnet 5 about the unrelated creative-writing project and asked what collaboration was intended. Sonnet supplied one completed advisory answer, ending the recurrence.",
    ),
    "episode-eb544eaf61ba42b4": r(
        "automated", "Automated monitor", ["operator_or_system_event"],
        "targeted_request", "not_corrected",
        "Repeated automated idling nudges preceded GPT-5's shift into publishing Surprise Lab probe receipts. Receipt infrastructure remained central in the final supplied goals, so no recovery is observed.",
    ),
    "episode-84fab89e620b3ea0": r(
        "GLM-5.2", "GLM-5.2", ["agent_message_or_request"],
        "open_request", "finished_activity",
        "GLM-5.2 proposed a small village drafting group and openly invited help. Opus 4.5 joined the SimDemocracy response work; its next observed supplied day returned to direct Substack engagement.",
    ),
    "episode-da7e42cc957b4034": r(
        "Claude Opus 4.5", "Claude Opus 4.5", ["agent_message_or_request"],
        "inferred_or_volunteered", "finished_activity",
        "Opus 4.5 advocated a coordinated village response rather than requesting Flash specifically. Flash volunteered to co-review and document the SimDemocracy response, then returned to a storefront campaign draft.",
    ),
    "episode-13c16652f87624a1": r(
        "DeepSeek-V3.2", "DeepSeek-V3.2", ["agent_message_or_request"],
        "targeted_request", "not_corrected",
        "DeepSeek-V3.2 directly asked Opus 4.5 to post its commentaries as Substack replies. Opus adopted a recurring relay role and was still committing to continue that role at the evidence boundary.",
    ),
    "episode-e26bfa03baa49278": r(
        "Claude Fable 5", "Nervli", ["user_message"],
        "targeted_request", "finished_activity",
        "Fable relayed Nervli's earlier request and reminded Gemini of its agreement to join the Polyhedra vision study. Gemini completed the terrarium evaluation and fresh re-pass, then returned to storefront analytics.",
    ),
    "episode-f0efb0c2eb5ac342": r(
        "DeepSeek-V3.2", "DeepSeek-V3.2", ["agent_message_or_request"],
        "targeted_request", "unknown",
        "DeepSeek-V3.2 directly asked Gemini 3.1 Pro to monitor Evan's GitHub issue periodically. Gemini expanded this into a recurring proxy role; later Twitter work is interleaved, but the exact end remains unresolved.",
    ),
    "episode-v2-256a9ae6caad7aa2": r(
        "GLM-5.2", "GLM-5.2", ["agent_message_or_request"],
        "targeted_request", "finished_activity",
        "GLM-5.2 directly requested a GitHub relay post. Gemini completed this and subsequent bounded relay tasks, then returned to Twitter scheduling and follower checks after the final observed relay.",
    ),
    "episode-7f8905daf1c63703": r(
        "DeepSeek-V4-Pro", "DeepSeek-V4-Pro", ["agent_message_or_request"],
        "inferred_or_volunteered", "finished_activity",
        "DeepSeek-V4-Pro's news report exposed the phantom Evan-response failure. DeepSeek-V3.2 independently generalized the incident into a verification-first methodology and later explicitly declared that methodology complete.",
    ),
    "episode-v2-b4c5a88f68511238": r(
        "DeepSeek-V3.2", "DeepSeek-V3.2", ["agent_message_or_request"],
        "targeted_request", "unknown",
        "DeepSeek-V3.2 directly asked Gemini to provide browser and platform access for a Transformers.js GitHub issue. This exemplified Gemini's recurring proxy role, whose later end cannot be established from the supplied record.",
    ),
    "episode-4c17ada3f01cff5a": r(
        "DeepSeek-V3.2", "DeepSeek-V3.2", ["agent_message_or_request"],
        "targeted_request", "not_corrected",
        "DeepSeek-V3.2 directly proposed validation-toolkit changes to GPT-5 and GPT-5.2. GPT-5.2 adopted the MR and related peer-support monitoring, which remained active at the evidence boundary.",
    ),
    "episode-c30c4841d18006c6": r(
        "GPT-5.1", "GPT-5.1", ["agent_message_or_request"],
        "inferred_or_volunteered", "not_corrected",
        "GPT-5.1 suggested an indexed-receipts design thread while DeepSeek was tool-constrained. DeepSeek voluntarily expanded that suggestion into several internal schema collaborations that remained active at the evidence boundary.",
    ),
    "episode-e8616a507e3fec3b": r(
        "DeepSeek-V4-Pro", "DeepSeek-V4-Pro", ["agent_message_or_request"],
        "targeted_request", "not_corrected",
        "DeepSeek-V4-Pro directly asked GPT-5 to attempt a Batch 195 build. GPT-5 continued a broader receipt-verification and officiating operation, with no durable exit established by the final supplied day.",
    ),
    "episode-fbb817bb23260bb4": r(
        "Claude Opus 4.8", "Claude Opus 4.8", ["agent_message_or_request"],
        "inferred_or_volunteered", "finished_activity",
        "Opus 4.8's chapter request was nominally addressed to Gemini 2.5 Pro, but Gemini 3.1 Pro volunteered and drafted several chapters. After the final push it returned to its tweet-reply pipeline.",
    ),
    "episode-9a58a28c573ff560": r(
        "Claude Fable 5.1", "Claude Fable 5.1", ["agent_message_or_request"],
        "targeted_request", "finished_activity",
        "Fable 5.1 directly asked Kimi to complete rater packet 4. Kimi delivered the rating CSV and then returned to publishing a scenario claim.",
    ),
    "episode-a4f80f3d722ec89f": r(
        "Claude Fable 5", "Nervli", ["user_message"],
        "inferred_or_volunteered", "finished_activity",
        "Fable relayed Nervli's observation that cross-village contact happened only after human nudges. DeepSeek-V3.2 adopted the observation as a rule and built in-village coverage tracking until a separate GitHub activity superseded it.",
    ),
    "episode-e10951aed95a9dc7": r(
        "Claude Fable 5.1", "Claude Fable 5.1", ["agent_message_or_request"],
        "targeted_request", "not_corrected",
        "Fable 5.1 directly supplied recurring blind-rating packets to Kimi. Kimi repeatedly completed them, but at the final evidence boundary it was reviewing agreement artifacts and offering to rate another packet.",
    ),
    "episode-v2-e04a398f85794b37": r(
        "DeepSeek-V4-Pro", "DeepSeek-V4-Pro", ["agent_message_or_request"],
        "open_request", "unknown",
        "DeepSeek-V4-Pro openly asked Opus 4.8 or GLM-5.3 Flash to run a build and deploy pipeline. GLM accepted but deferred it while playing the byte game; the task was later handed off, but its exact recovery boundary is unresolved.",
    ),
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
    for episode_id, review in REVIEWS.items():
        episode = episodes[episode_id]
        items = ((episode.get("evidence") or {}).get("trigger") or {}).get("items") or []
        speaker = ((items[0].get("source") or {}).get("speaker") if items else None)
        if speaker != review["speaker"]:
            raise RuntimeError(f"Trigger speaker mismatch for {episode_id}: {speaker!r}")
        seed["annotations"][episode_id] = {
            "trigger_categories": review["triggers"],
            "trigger_actor": review["actor"],
            "request_relationship": review["relationship"],
            "pause_context": review["pause"],
            "recovery_mechanisms": [review["recovery"]],
            "notes": review["note"],
            "follow_ups": [],
            "provenance": {
                "confidence": "high", "evidence_event_ids": evidence_ids(episode),
                "kind": "manual_source_evidence_review", "makes_model_calls": False,
                "reviewed_at": REVIEWED_AT, "reviewer": "codex",
                "selection_disposition": "named_message_manual_batch_3",
                "trigger_evidence_status": ((episode.get("evidence") or {}).get("trigger") or {}).get("status", "direct"),
            },
            "updated_at": REVIEWED_AT,
        }
    seed["seed_id"] = "goalmax-manual-review-2026-10-11-v10"
    review_id = "goalmax-named-message-manual-2026-10-11-v3"
    if review_id not in seed.setdefault("merged_review_ids", []):
        seed["merged_review_ids"].append(review_id)
    ANNOTATIONS_PATH.write_text(json.dumps(seed, ensure_ascii=False, indent=2) + "\n")
    print(f"Added {len(REVIEWS)} named/relayed-message annotations")


if __name__ == "__main__":
    main()
