#!/usr/bin/env python3
"""Validate coverage and schema invariants for committed manual reviews."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from backfill_trigger_taxonomy import classify as classify_trigger_taxonomy


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
    "substack_message",
    "user_email",
    "user_message",
}
PAUSE_CONTEXTS = {
    "end_of_day",
    "monitoring_loop",
    "scheduled_wait",
    "dependency_wait",
    "calendar_boundary_confusion",
    "no_next_action",
}
VERIFICATION_STATUSES = {
    "needs_manual_verification",
    "raw_source_verified",
    "browser_verified",
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

    trigger_taxonomy = payload.get("trigger_taxonomy")
    if not isinstance(trigger_taxonomy, dict):
        fail("trigger_taxonomy must be an object")
    taxonomy_categories = trigger_taxonomy.get("categories")
    taxonomy_assignments = trigger_taxonomy.get("assignments")
    if not isinstance(taxonomy_categories, list) or not taxonomy_categories:
        fail("trigger_taxonomy.categories must be a non-empty list")
    if not isinstance(taxonomy_assignments, dict):
        fail("trigger_taxonomy.assignments must be an object")
    taxonomy_category_ids = [item.get("id") for item in taxonomy_categories]
    if any(not value for value in taxonomy_category_ids):
        fail("Every trigger-taxonomy category must have an id")
    if len(taxonomy_category_ids) != len(set(taxonomy_category_ids)):
        fail("Trigger-taxonomy category ids must be unique")
    for item in taxonomy_categories:
        if not all(str(item.get(field, "")).strip() for field in ("family", "label", "description")):
            fail(f"Incomplete trigger-taxonomy category: {item!r}")
    if set(taxonomy_assignments) != annotation_ids:
        fail(
            "Trigger-taxonomy coverage differs from reviewed annotations: "
            f"missing={sorted(annotation_ids - set(taxonomy_assignments))}, "
            f"extra={sorted(set(taxonomy_assignments) - annotation_ids)}"
        )
    invalid_taxonomy_assignments = (
        set(taxonomy_assignments.values()) - set(taxonomy_category_ids)
    )
    if invalid_taxonomy_assignments:
        fail(
            "Invalid trigger-taxonomy assignments: "
            f"{sorted(invalid_taxonomy_assignments)}"
        )
    stale_taxonomy_assignments = {
        episode_id: (taxonomy_assignments[episode_id], classify_trigger_taxonomy(episode_id, annotation))
        for episode_id, annotation in annotations.items()
        if taxonomy_assignments[episode_id]
        != classify_trigger_taxonomy(episode_id, annotation)
    }
    if stale_taxonomy_assignments:
        fail(
            "Trigger-taxonomy assignments are stale; rerun "
            "scripts/backfill_trigger_taxonomy.py: "
            f"{stale_taxonomy_assignments}"
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
        drift_assessment = annotation.get("drift_assessment", "confirmed")
        if drift_assessment not in {"confirmed", "borderline"}:
            errors.append(
                f"{episode_id}: invalid drift_assessment {drift_assessment!r}"
            )
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
        else:
            verification_status = annotation["provenance"].get(
                "verification_status"
            )
            if (verification_status is not None
                    and verification_status not in VERIFICATION_STATUSES):
                errors.append(
                    f"{episode_id}: invalid verification_status "
                    f"{verification_status!r}"
                )
    if errors:
        fail("Manual-review validation failed:\n" + "\n".join(errors))

    history = payload.get("annotation_history", {})
    if not isinstance(history, dict):
        fail("annotation_history must be an object")
    history_errors = []
    revision_ids = set()
    for episode_id, revisions in history.items():
        if not isinstance(revisions, list) or not revisions:
            history_errors.append(f"{episode_id}: history must be a non-empty list")
            continue
        for revision in revisions:
            revision_id = revision.get("revision_id")
            if not revision_id:
                history_errors.append(f"{episode_id}: history revision missing id")
            elif revision_id in revision_ids:
                history_errors.append(f"duplicate history revision {revision_id}")
            else:
                revision_ids.add(revision_id)
            if not isinstance(revision.get("annotation"), dict):
                history_errors.append(
                    f"{episode_id}: history revision missing annotation snapshot"
                )
            if not revision.get("origin") or not revision.get("superseded_by"):
                history_errors.append(
                    f"{episode_id}: history revision missing audit provenance"
                )
    if history_errors:
        fail("Annotation-history validation failed:\n" + "\n".join(history_errors))

    resolved_hashes = payload.get("resolved_browser_hashes", {})
    resolved_history = payload.get("resolved_browser_hash_history", {})
    if not isinstance(resolved_hashes, dict) or not isinstance(
        resolved_history, dict
    ):
        fail("Resolved browser hashes and their history must be objects")
    receipt_errors = []
    for episode_id, hashes in resolved_history.items():
        if not isinstance(hashes, list) or not all(
            isinstance(value, str) and value for value in hashes
        ):
            receipt_errors.append(
                f"{episode_id}: resolved browser hash history must be strings"
            )
        if len(hashes) != len(set(hashes)):
            receipt_errors.append(
                f"{episode_id}: duplicate resolved browser hash history"
            )
        if resolved_hashes.get(episode_id) in hashes:
            receipt_errors.append(
                f"{episode_id}: latest resolved hash duplicated in history"
            )
    if receipt_errors:
        fail("Browser-receipt validation failed:\n" + "\n".join(receipt_errors))

    actor_count = sum(bool(str(item["trigger_actor"]).strip()) for item in annotations.values())
    pause_count = sum("pause" in item["trigger_categories"] for item in annotations.values())
    print(
        f"Validated {len(annotations)} goal-max annotations: "
        f"actors={actor_count}, pauses={pause_count}, "
        f"taxonomy={len(taxonomy_category_ids)}, "
        f"history={len(revision_ids)}, seed={payload['seed_id']}"
    )


if __name__ == "__main__":
    main()
