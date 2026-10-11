#!/usr/bin/env python3
"""Validate coverage and schema invariants for committed manual reviews."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
REQUIRED_FIELDS = {
    "trigger_categories",
    "trigger_actor",
    "request_relationship",
    "pause_context",
    "recovery_mechanisms",
    "notes",
    "follow_ups",
    "provenance",
    "updated_at",
}
EXTERNAL_TRIGGERS = {
    "agent_message_or_request",
    "gitlab_issue_or_comment",
    "user_email",
    "user_message",
}
PAUSE_CONTEXTS = {
    "end_of_day",
    "monitoring_loop",
    "scheduled_wait",
    "dependency_wait",
    "no_next_action",
    "other_or_unknown",
}


def fail(message: str) -> None:
    raise RuntimeError(message)


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text())
    bundle = json.loads(BUNDLE_PATH.read_text())
    annotations = payload["annotations"]
    goalmax_ids = {
        episode["episode_id"]
        for episode in bundle["confirmed_episodes"]
        if episode.get("period") == "goal_maximization"
    }
    annotation_ids = set(annotations)
    if annotation_ids != goalmax_ids:
        fail(
            "Annotation coverage differs from confirmed goal-max episodes: "
            f"missing={sorted(goalmax_ids - annotation_ids)}, "
            f"extra={sorted(annotation_ids - goalmax_ids)}"
        )

    taxonomy = payload["taxonomies"]
    trigger_ids = {item["id"] for item in taxonomy["trigger"]}
    relationship_ids = {item["id"] for item in taxonomy["request_relationship"]}
    recovery_ids = {item["id"] for item in taxonomy["recovery"]}
    errors = []
    for episode_id, annotation in annotations.items():
        missing_fields = REQUIRED_FIELDS - set(annotation)
        if missing_fields:
            errors.append(f"{episode_id}: missing fields {sorted(missing_fields)}")
            continue
        triggers = annotation["trigger_categories"]
        recoveries = annotation["recovery_mechanisms"]
        if not isinstance(triggers, list) or not triggers:
            errors.append(f"{episode_id}: trigger_categories must be non-empty list")
        elif invalid := set(triggers) - trigger_ids:
            errors.append(f"{episode_id}: invalid triggers {sorted(invalid)}")
        if annotation["request_relationship"] not in relationship_ids:
            errors.append(
                f"{episode_id}: invalid relationship "
                f"{annotation['request_relationship']!r}"
            )
        if not isinstance(recoveries, list) or not recoveries:
            errors.append(f"{episode_id}: recovery_mechanisms must be non-empty list")
        elif invalid := set(recoveries) - recovery_ids:
            errors.append(f"{episode_id}: invalid recoveries {sorted(invalid)}")
        if set(triggers) & EXTERNAL_TRIGGERS and not str(
            annotation["trigger_actor"]
        ).strip():
            errors.append(f"{episode_id}: external trigger missing actor")
        pause_context = annotation["pause_context"]
        if "pause" in triggers and pause_context not in PAUSE_CONTEXTS:
            errors.append(f"{episode_id}: pause missing valid pause_context")
        if "pause" not in triggers and pause_context:
            errors.append(f"{episode_id}: non-pause has pause_context {pause_context!r}")
        if not isinstance(annotation["follow_ups"], list):
            errors.append(f"{episode_id}: follow_ups must be a list")
        if not isinstance(annotation["provenance"], dict):
            errors.append(f"{episode_id}: provenance must be an object")
    if errors:
        fail("Manual-review validation failed:\n" + "\n".join(errors))

    actor_count = sum(bool(str(item["trigger_actor"]).strip()) for item in annotations.values())
    pause_count = sum("pause" in item["trigger_categories"] for item in annotations.values())
    print(
        f"Validated {len(annotations)} goal-max annotations: "
        f"actors={actor_count}, pauses={pause_count}, seed={payload['seed_id']}"
    )


if __name__ == "__main__":
    main()
