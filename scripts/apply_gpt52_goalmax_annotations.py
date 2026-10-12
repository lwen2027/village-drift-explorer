#!/usr/bin/env python3
"""Apply the source-verified GPT-5.2 goal-max audit to annotations.

Retires annotations for merged and invalidated records, updates the
re-bounded records with source-verified fields, and adds the existing
self_authored_memory_constraint trigger to memory-driven episodes. Prior annotations are
preserved as superseded revisions.
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
SPEC_PATH = pathlib.Path(__file__).with_name("gpt52_goalmax_annotation_spec.json")
REVIEW_ID = "gpt52-goalmax-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T00:00:00-04:00"
MEMORY_TRIGGER = "self_authored_memory_constraint"


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_gpt52_source_audit", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_gpt52_source_audit", "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    if MEMORY_TRIGGER not in {row["id"] for row in document["taxonomies"]["trigger"]}:
        raise SystemExit(f"{MEMORY_TRIGGER} taxonomy is missing")
    annotations = document["annotations"]
    retired = archive.setdefault("annotations", {})
    for episode_id in spec["retired"]:
        if episode_id in episodes:
            raise SystemExit(f"retired episode still published: {episode_id}")
        if episode_id in annotations:
            retired[episode_id] = annotations.pop(episode_id)
    for episode_id, update in spec["updates"].items():
        if episode_id not in episodes:
            raise SystemExit(f"updated episode missing from bundle: {episode_id}")
        prior = annotations.get(episode_id) or {}
        if prior:
            preserve_revision(document, episode_id, prior)
        update = dict(update)
        event_ids = update.pop("ev")
        merged = copy.deepcopy(prior)
        merged.update(update)
        merged.setdefault("follow_ups", [])
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "kind": "manual_source_evidence_review", "review_id": REVIEW_ID,
            "reviewer": "claude-code-with-lwen2027", "reviewed_at": REVIEWED_AT,
            "verification_status": "raw_source_verified", "evidence_event_ids": event_ids,
            "makes_model_calls": False,
        })
        merged["provenance"] = provenance
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged
    for episode_id, note in spec["tags"].items():
        prior = annotations.get(episode_id)
        if not prior or episode_id not in episodes:
            raise SystemExit(f"tagged episode missing: {episode_id}")
        if MEMORY_TRIGGER in prior.get("trigger_categories", []):
            continue
        preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        merged["trigger_categories"] = [*merged.get("trigger_categories", []), MEMORY_TRIGGER]
        merged["notes"] = (str(merged.get("notes") or "").rstrip() + " " + note).strip()
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged
    for episode_id, event_ids in spec.get("verify", {}).items():
        prior = annotations.get(episode_id)
        if not prior or episode_id not in episodes:
            raise SystemExit(f"verified episode missing: {episode_id}")
        preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "verification_status": "raw_source_verified", "verification_review_id": REVIEW_ID,
            "verified_by": "claude-code-with-lwen2027", "verified_at": REVIEWED_AT,
            "evidence_event_ids": event_ids, "makes_model_calls": False,
        })
        merged["provenance"] = provenance
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged
    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = f"{head}-v{int(number) + 1}" if number.isdigit() else seed
    ANNOTATIONS_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARCHIVE_PATH.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Retired {len(spec['retired'])}, updated {len(spec['updates'])}, "
          f"tagged {len(spec['tags'])} annotations")


if __name__ == "__main__":
    main()
