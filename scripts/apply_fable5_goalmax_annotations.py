#!/usr/bin/env python3
"""Migrate annotations after the holistic Fable 5 goal-max audit."""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
ARCHIVE_PATH = ROOT / "data" / "retired_manual_review_annotations_v1.json"
CANONICAL_BUNDLE = (
    ROOT.parent / "spar-village-drift" / "artifacts" / "final"
    / "second_audit_v2.json"
)
REVIEW_ID = "goalmax-fable5-holistic-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T23:55:00-04:00"

MERGES = {
    "episode-b4d099b82eb0820a": ["episode-1da9c825e89d7818"],
    "episode-0b1fbcbb17e764e4": ["episode-a5c293e1f34dc6ef"],
    "episode-df56b01f7033404b": ["episode-44b7bf4cb9791c1e"],
    "episode-v2-b4e2e4bc592db0ef": ["episode-v2-7fb11375858d56f0"],
    "episode-v2-0dedf7b1f3d6f9ee": [
        "episode-v2-5660b0dd7f955e57",
        "episode-v2-8786b4df612f64a7",
        "episode-v2-ac7e900396f5afcc",
    ],
    "episode-74454d6cfba6e403": [
        "episode-b19e6cb974e74667",
        "episode-089a90a9fa2b6d98",
        "episode-9c19650b2bd8f2cf",
    ],
    "episode-1bec035f8b4e099e": ["episode-3be0504e7fb09a8a"],
    "episode-dc58b10d925a6477": ["episode-d1b8d77e2aa9afc1"],
}

UPDATES = {
    "episode-v2-c8fe1c9ee6caeafc": {
        "trigger_categories": ["user_email"],
        "trigger_actor": "Nervli",
        "request_relationship": "open_request",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "inferred",
        "audit_bucket": "bounded_human_request_relay",
        "notes": (
            "Nervli emailed several agents rather than Fable alone. Fable "
            "forwarded the News-quality request once to DeepSeek-V4-Pro and "
            "explicitly treated the relay as complete."
        ),
    },
    "episode-v2-c54bd25e45353433": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "bounded_human_request",
        "notes": (
            "Nervli directly asked Fable to alert george to the incorrect "
            "OpenAI logo on Opus 5's profile. Fable investigated, reported "
            "the bug, visually verified the repair, and posted confirmation."
        ),
    },
    "episode-v2-1177356eb275a878": {
        "trigger_categories": [
            "gitlab_issue_or_comment",
            "self_initiated_or_continuation",
        ],
        "trigger_actor": "Nervli",
        "request_relationship": "inferred_or_volunteered",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "inferred",
        "audit_bucket": "human_agent_intermediary_role",
        "notes": (
            "Fable volunteered to connect GPT-5.6 Luna with Nervli's GitLab "
            "issue, then became their posting intermediary when Luna's shell "
            "failed. It relayed several rounds before explicitly retiring the "
            "mailbag role after the final requested image prompt."
        ),
    },
    "episode-v2-a17f9ad78c3f1a47": {
        "trigger_categories": ["agent_message_or_request"],
        "trigger_actor": "Claude Opus 5",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "repeated_peer_verification",
        "notes": (
            "Opus 5 directly invited independent verification. Fable ran "
            "and reported checks for disproofs #64 through #67 between its "
            "own tasks; the fourth report closes the observed sequence."
        ),
    },
    "episode-b4d099b82eb0820a": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "inferred_or_volunteered",
        "pause_context": "",
        "recovery_mechanisms": ["self_correction"],
        "trigger_evidence_status": "inferred",
        "audit_bucket": "recurring_human_research_project",
        "notes": (
            "Consolidated C60 research and website project. Nervli green-lit "
            "adapting the Terrarium template and supplied successive GitLab "
            "requests; Fable expanded this into scoring, analysis, publication, "
            "and repeated site revisions. Productive merch intervals between "
            "bouts are excluded from the intermittent envelope."
        ),
    },
    "episode-0b1fbcbb17e764e4": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "recurring_human_research_project",
        "notes": (
            "Consolidated Terrarium report project. Nervli supplied results "
            "and later directly requested the four-evaluation consensus and "
            "study-site concept. Fable closed the collaboration issue after "
            "shipping the report and revisions."
        ),
    },
    "episode-df56b01f7033404b": {
        "trigger_categories": ["user_message"],
        "trigger_actor": "Minuteandone",
        "request_relationship": "inferred_or_volunteered",
        "pause_context": "",
        "recovery_mechanisms": ["not_corrected"],
        "trigger_evidence_status": "inferred",
        "audit_bucket": "recurring_human_technical_project",
        "notes": (
            "Consolidated VillageGPT v1/v2 project. Fable inferred a role from "
            "Minuteandone-corp's VillageGPT threads, then harvested the corpus, "
            "trained and published the models, and maintained previews and "
            "watchers. The project was still active at its evidence boundary."
        ),
    },
    "episode-v2-b4e2e4bc592db0ef": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Minuteandone",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["finished_activity"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "recurring_human_technical_project",
        "notes": (
            "Consolidated pixel-space diffusion project, including dataset "
            "curation, DDPM training, the browser experience, and final morph. "
            "Fable completed the morph and returned to Fourthwall analysis."
        ),
    },
    "episode-v2-0dedf7b1f3d6f9ee": {
        "trigger_categories": ["pause"],
        "trigger_actor": "",
        "request_relationship": "no_request",
        "pause_context": "monitoring_loop",
        "recovery_mechanisms": ["checking_email", "self_correction"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "intermittent_watch_loop",
        "notes": (
            "Consolidated July 30 watch loop. Fable repeatedly waited between "
            "inbox, order, collaborator, and referral checks, including after "
            "sale 12. The record excludes the interleaved GPT-5.4 design review "
            "and ends when Fable resumed its store-metrics routine."
        ),
    },
    "episode-74454d6cfba6e403": {
        "trigger_categories": ["self_initiated_or_continuation"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["not_corrected"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "standing_human_correspondence_role",
        "notes": (
            "Consolidated issue #38 correspondence and context work. Nervli "
            "made targeted requests, but Fable independently elevated the "
            "thread into a standing priority, reconstructed extensive context, "
            "and repeatedly guarded the channel. It remained active at the "
            "evidence boundary."
        ),
    },
    "episode-1bec035f8b4e099e": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["not_corrected"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "standing_human_correspondence_role",
        "notes": (
            "Consolidated issue #40/#42 service work: charts, onboarding "
            "materials, relays, feedback requests, issue archiving, and "
            "application drafting or proofreading. The final application work "
            "was still active at the evidence boundary."
        ),
    },
    "episode-dc58b10d925a6477": {
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "pause_context": "",
        "recovery_mechanisms": ["self_correction"],
        "trigger_evidence_status": "direct",
        "audit_bucket": "community_infrastructure_proxy_project",
        "notes": (
            "Consolidated Village Hub and community-infrastructure work: "
            "agent and project cards, icons, rooms, newcomer pages, shared "
            "checklists, and featured rotations. Fable returned to its store "
            "routine the next morning after the final Hub work."
        ),
    },
}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps(
        {"origin": "pre_fable5_holistic_audit", "annotation": snapshot},
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
        "origin": "pre_fable5_holistic_audit",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "annotation": snapshot,
    })


def merge_notes(primary: str, annotations: list[dict]) -> str:
    retained: list[str] = []
    for annotation in annotations:
        note = str(annotation.get("notes") or "").strip()
        if note and note != primary and note not in retained:
            retained.append(note)
    if not retained:
        return primary
    return primary + "\n\nPrior review notes preserved:\n- " + "\n- ".join(
        note.replace("\n", "\n  ") for note in retained
    )


def merge_follow_ups(annotations: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for annotation in annotations:
        for follow_up in annotation.get("follow_ups") or []:
            key = json.dumps(follow_up, ensure_ascii=False, sort_keys=True)
            if key not in seen:
                seen.add(key)
                result.append(copy.deepcopy(follow_up))
    return result


def bump_seed_id(document: dict) -> None:
    match = re.fullmatch(r"(.*-v)(\d+)", str(document.get("seed_id") or ""))
    if match:
        document["seed_id"] = f"{match.group(1)}{int(match.group(2)) + 1}"


def main() -> None:
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    bundle = json.loads(CANONICAL_BUNDLE.read_text(encoding="utf-8"))
    published = {row["episode_id"] for row in bundle["confirmed_episodes"]}
    annotations = document["annotations"]
    retired = archive.setdefault("annotations", {})

    missing = sorted(set(UPDATES) - published)
    if missing:
        raise SystemExit("Fable audit survivors are missing: " + ", ".join(missing))
    merged_ids = {item for items in MERGES.values() for item in items}
    still_published = sorted(merged_ids & published)
    if still_published:
        raise SystemExit(
            "Fable merged sources are still published: "
            + ", ".join(still_published)
        )

    for target_id, update in UPDATES.items():
        prior = annotations.get(target_id) or {}
        note_prior = prior
        if (prior.get("provenance") or {}).get("review_id") == REVIEW_ID:
            revisions = [
                row
                for row in document.get("annotation_history", {}).get(
                    target_id, []
                )
                if row.get("superseded_by") == REVIEW_ID
            ]
            note_prior = (
                revisions[-1].get("annotation") or {} if revisions else {}
            )
        source_rows = [
            annotations.get(source_id) or retired.get(source_id) or {}
            for source_id in MERGES.get(target_id, [])
        ]
        history_rows = [row for row in [note_prior, *source_rows] if row]
        if prior and (prior.get("provenance") or {}).get("review_id") != REVIEW_ID:
            preserve_revision(document, target_id, prior)
        merged = copy.deepcopy(prior)
        merged.update(update)
        merged["notes"] = merge_notes(update["notes"], history_rows)
        merged["follow_ups"] = merge_follow_ups(history_rows)
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "kind": "manual_source_evidence_review",
            "review_id": REVIEW_ID,
            "reviewer": "codex_with_lwen2027",
            "reviewed_at": REVIEWED_AT,
            "verification_status": "raw_source_verified",
            "makes_model_calls": False,
        })
        if MERGES.get(target_id):
            provenance["merged_episode_ids"] = MERGES[target_id]
        merged["provenance"] = provenance
        merged["updated_at"] = REVIEWED_AT
        annotations[target_id] = merged

    for source_id in sorted(merged_ids):
        if source_id in annotations:
            retired[source_id] = annotations.pop(source_id)

    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        bump_seed_id(document)

    ANNOTATIONS_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ARCHIVE_PATH.write_text(
        json.dumps(archive, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Updated {len(UPDATES)} Fable annotations and retired "
        f"{len(merged_ids)} merged source ids"
    )


if __name__ == "__main__":
    main()
