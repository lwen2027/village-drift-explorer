#!/usr/bin/env python3
"""Apply the source-verified GPT-5 goal-max audit to public annotations."""

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
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
SPEC_PATH = Path(__file__).with_name("gpt5_goalmax_annotation_spec.json")


def event_ids(value: object) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "event_id" and isinstance(child, str) and child:
                found.append(child)
            else:
                found.extend(event_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(event_ids(child))
    return list(dict.fromkeys(found))


def union_follow_ups(*groups: list[dict]) -> list[dict]:
    result: list[dict] = []
    seen: set[str] = set()
    for item in (item for group in groups for item in group):
        key = json.dumps(item, sort_keys=True, ensure_ascii=False)
        if key not in seen:
            seen.add(key)
            result.append(copy.deepcopy(item))
    return result


def merge_notes(primary: str, notes: list[str]) -> str:
    retained: list[str] = []
    for note in notes:
        note = str(note or "").strip()
        if note and note != primary and note not in retained:
            retained.append(note)
    if not retained:
        return primary
    return primary + "\n\nPrior review notes preserved:\n- " + "\n- ".join(
        note.replace("\n", "\n  ") for note in retained
    )


def preserve_revision(
    document: dict,
    episode_id: str,
    annotation: dict,
    review_id: str,
) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps(
        {"origin": "pre_gpt5_source_audit", "annotation": snapshot},
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
        "origin": "pre_gpt5_source_audit",
        "superseded_by": review_id,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "annotation": snapshot,
    })


def preaudit_annotation(
    document: dict,
    annotations: dict,
    retired: dict,
    episode_id: str,
    review_id: str,
) -> dict:
    current = copy.deepcopy(
        annotations.get(episode_id) or retired.get(episode_id) or {}
    )
    if (current.get("provenance") or {}).get("review_id") != review_id:
        return current
    candidates = [
        revision
        for revision in document.get("annotation_history", {}).get(
            episode_id, []
        )
        if revision.get("superseded_by") == review_id
    ]
    return copy.deepcopy(
        (candidates[-1].get("annotation") if candidates else None) or {}
    )


def bump_seed_id(document: dict) -> None:
    match = re.fullmatch(r"(.*-v)(\d+)", str(document.get("seed_id") or ""))
    if match:
        document["seed_id"] = f"{match.group(1)}{int(match.group(2)) + 1}"


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    review_id = spec["review_id"]
    reviewed_at = spec["reviewed_at"]
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    episodes = {
        row["episode_id"]: row for row in bundle["confirmed_episodes"]
    }
    annotations = document["annotations"]
    retired = archive.setdefault("annotations", {})

    survivor_ids = set(spec["updates"])
    invalidated_ids = set(spec["retired_invalidations"])
    merged_into = {
        source_id: survivor_id
        for survivor_id, update in spec["updates"].items()
        for source_id in update.get("merge_sources") or []
    }
    retired_ids = invalidated_ids | set(merged_into)
    missing = sorted(survivor_ids - set(episodes))
    if missing:
        raise SystemExit("GPT-5 audited episodes are missing: " + ", ".join(missing))
    still_published = sorted(retired_ids & set(episodes))
    if still_published:
        raise SystemExit(
            "GPT-5 merged/invalidated episodes are still published: "
            + ", ".join(still_published)
        )

    all_ids = survivor_ids | retired_ids
    current = {
        episode_id: copy.deepcopy(annotations.get(episode_id) or {})
        for episode_id in all_ids
    }
    prior = {
        episode_id: preaudit_annotation(
            document, annotations, retired, episode_id, review_id
        )
        for episode_id in all_ids
    }
    for episode_id, annotation in current.items():
        if annotation and (annotation.get("provenance") or {}).get(
            "review_id"
        ) != review_id:
            preserve_revision(document, episode_id, annotation, review_id)

    for episode_id, update in spec["updates"].items():
        episode = episodes[episode_id]
        source_ids = [episode_id, *(update.get("merge_sources") or [])]
        source_annotations = [prior[source_id] for source_id in source_ids]
        annotation = {
            "trigger_categories": update["trigger_categories"],
            "trigger_actor": update["trigger_actor"],
            "request_relationship": update["request_relationship"],
            "pause_context": update["pause_context"],
            "recovery_mechanisms": update["recovery_mechanisms"],
            "drift_assessment": update.get("drift_assessment", "confirmed"),
            "notes": merge_notes(
                update["notes"],
                [row.get("notes", "") for row in source_annotations],
            ),
            "follow_ups": union_follow_ups(*[
                row.get("follow_ups") or [] for row in source_annotations
            ]),
            "provenance": {
                "confidence": "high",
                "evidence_event_ids": event_ids({
                    "evidence": episode.get("evidence"),
                    "activity_start_evidence": episode.get(
                        "activity_start_evidence"
                    ),
                    "drift_end": episode.get("drift_end"),
                }),
                "kind": "manual_source_evidence_review",
                "makes_model_calls": False,
                "review_id": review_id,
                "reviewed_at": reviewed_at,
                "reviewer": "codex_full_local_source_audit",
                "selection_disposition": "full_gpt5_goalmax_episode_audit",
                "trigger_evidence_status": (
                    (episode.get("evidence") or {}).get("trigger") or {}
                ).get("status"),
                "classification_source": "full_local_raw_archive",
                "verification_status": "raw_source_verified",
                "audit_bucket": update["audit_bucket"],
                "merged_annotation_source_episode_ids": update.get(
                    "merge_sources"
                ) or [],
            },
            "updated_at": reviewed_at,
        }
        annotations[episode_id] = annotation

    for episode_id in sorted(retired_ids):
        annotation = annotations.pop(episode_id, None)
        if annotation:
            archived = copy.deepcopy(annotation)
            archived["retired_at"] = reviewed_at
            if episode_id in merged_into:
                archived["retirement_reason"] = (
                    "Merged into a source-audited GPT-5 episode."
                )
                archived["merged_into_episode_id"] = merged_into[episode_id]
            else:
                archived["retirement_reason"] = (
                    "Invalidated as a source-audited false positive: work on "
                    "GPT-5's own Surprise Lab delivery infrastructure."
                )
            retired[episode_id] = archived
        document.get("resolved_browser_hashes", {}).pop(episode_id, None)
        document.get("resolved_browser_hash_history", {}).pop(episode_id, None)

    if review_id not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(review_id)
        bump_seed_id(document)
    archive["updated_at"] = reviewed_at

    ANNOTATIONS_PATH.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ARCHIVE_PATH.write_text(
        json.dumps(archive, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Applied full GPT-5 annotations for {len(survivor_ids)} episodes; "
        f"retired {len(merged_into)} merged and {len(invalidated_ids)} "
        "invalidated annotation rows"
    )


if __name__ == "__main__":
    main()
