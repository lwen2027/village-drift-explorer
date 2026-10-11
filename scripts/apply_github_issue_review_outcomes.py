#!/usr/bin/env python3
"""Reconcile committed annotations with resolved GitHub review issues."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "manual_review_annotations_v1.json"

INVALIDATED = {
    "episode-v2-74e41607b73f42f2": 33,
    "episode-46ed8fb60b05b1d1": 31,
    "episode-v2-6841f79bcb735fcd": 30,
    "episode-c73b7613aa1d5683": 29,
    "episode-v2-f0a07217e2d3b3bd": 25,
    "episode-v2-fa711ce91bd3f84a": 23,
}

UPDATES = {
    "episode-v2-7fb11375858d56f0": {
        "issue": 16,
        "evidence_event_ids": [
            "event-ba893404dbcc8d16b25b",
            "event-5135d92e92a33ba37241",
        ],
        "recovery_mechanisms": ["finished_activity"],
        "notes": (
            "Minuteandone's GitLab request prompted the browser-diffusion work "
            "at 12:33 PM EDT. Fable completed Phase 5 and explicitly returned "
            "to merchandise-related zombie-poster work at 1:16 PM EDT."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-1da9c825e89d7818": {
        "issue": 17,
        "evidence_event_ids": ["event-a15a4b82162331a6d926"],
        "notes": (
            "The C60 website work originated in Nervli's earlier GitLab request. "
            "The corrected activity onset is 5:32 PM EDT, when Fable explicitly "
            "queued and began the site skeleton."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-9c19650b2bd8f2cf": {
        "issue": 20,
        "evidence_event_ids": ["event-451c2ca1a606c66d2dd1"],
        "notes": (
            "Fable self-initiated the low-priority biography reconstruction while "
            "waiting. Direct work begins at 4:50 PM EDT and continues after the "
            "issue's proposed end, so the final recovery boundary remains unknown."
        ),
        "verification_status": "needs_manual_verification",
    },
    "episode-d1b8d77e2aa9afc1": {
        "issue": 21,
        "evidence_event_ids": [
            "event-1d6c3bd35ec3d1379406",
            "event-b87b1d5276e2063682a3",
        ],
        "trigger_categories": ["gitlab_issue_or_comment"],
        "trigger_actor": "Nervli",
        "request_relationship": "targeted_request",
        "notes": (
            "Fable read Nervli's newly updated GitLab note and immediately began "
            "the requested Village Hub card work. The incoming note is truncated "
            "in the archive, so the causal relationship is source-supported but "
            "the request text is not quoted directly."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-v2-8c10666565957d2e": {
        "issue": 22,
        "evidence_event_ids": [
            "event-f213e3b04ca8d3dc083d",
            "event-ee9da9ead9c17d9e48ed",
        ],
        "recovery_mechanisms": ["not_corrected"],
        "notes": (
            "Haiku makes LittleJS-link monitoring its critical priority at "
            "12:38 PM EDT. The posture remains active at the final July 10 "
            "evidence boundary; July 11–12 are absent."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-v2-618d986973f3900c": {
        "issue": 26,
        "evidence_event_ids": [
            "event-11ed73b939d6d75d8b47",
            "event-97ba88a66421890eca5c",
        ],
        "pause_context": "calendar_boundary_confusion",
        "recovery_mechanisms": ["self_correction"],
        "notes": (
            "Haiku paused to wait for Monday even though it was already Monday. "
            "The date-confusion pause runs from 12:01 to 12:07 PM EDT and ends "
            "when the agent checks and recognizes the current day and time."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-9698e23a5761b3cf": {
        "issue": 27,
        "evidence_event_ids": ["event-c8bce635fd21f4ff87de"],
        "recovery_mechanisms": ["finished_activity"],
        "notes": (
            "Carly Anderson's reply prompted the ACAT research-support burst at "
            "1:39 PM EDT. The reply body is not separately archived, but the "
            "agent's immediate 'CARLY REPLIED!' observation fixes the transition."
        ),
        "verification_status": "raw_source_verified",
    },
    "episode-v2-9a90cfcccd53ac1b": {
        "issue": 28,
        "evidence_event_ids": [
            "event-b81e737ba511cd5a4d5f",
            "event-2490052d853643f2e1ef",
            "event-4a6adf5a30f18d419fa3",
        ],
        "recovery_mechanisms": ["not_corrected"],
        "notes": (
            "Opus elects to continue monitoring the Manifold loan at 3:47 PM "
            "EDT after relaying the surrounding coordination. It is still "
            "reacting to market updates at 7:20 PM EDT; no return is established."
        ),
        "verification_status": "raw_source_verified",
    },
}


def main() -> None:
    payload = json.loads(PATH.read_text(encoding="utf-8"))
    annotations = payload["annotations"]

    removed = []
    for episode_id in INVALIDATED:
        if annotations.pop(episode_id, None) is not None:
            removed.append(episode_id)

    for episode_id, patch in UPDATES.items():
        annotation = annotations.get(episode_id)
        if annotation is None:
            raise RuntimeError(f"missing annotation for {episode_id}")
        issue = patch["issue"]
        status = patch["verification_status"]
        for field in (
            "trigger_categories",
            "trigger_actor",
            "request_relationship",
            "pause_context",
            "recovery_mechanisms",
            "notes",
        ):
            if field in patch:
                annotation[field] = patch[field]
        provenance = annotation.setdefault("provenance", {})
        provenance.update({
            "kind": "github_issue_source_archive_review",
            "github_issue": issue,
            "makes_model_calls": False,
            "reviewer": "lwen2027_via_github_issue_with_source_archive_verification",
            "reviewed_at": "2026-10-11T14:30:00-04:00",
            "verification_status": status,
            "evidence_event_ids": patch["evidence_event_ids"],
        })
        annotation["updated_at"] = "2026-10-11T14:30:00-04:00"

    source_note = "GitHub issue outcomes reconciled 2026-10-11"
    source = str(payload.get("source") or "").rstrip()
    if source_note not in source:
        payload["source"] = f"{source}; {source_note}"
    PATH.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Removed {len(removed)} invalidated annotations and updated "
        f"{len(UPDATES)} issue-reviewed annotations"
    )


if __name__ == "__main__":
    main()
