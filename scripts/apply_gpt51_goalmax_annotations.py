#!/usr/bin/env python3
"""Apply the source-verified GPT-5.1 goal-max audit to annotations.

Retires annotations for invalidated records, updates the narrowed Aug 21
record (adding the existing self_authored_memory_constraint trigger), and
marks three records borderline, which keeps them in the dataset but
excludes them from confirmed-drift views. Prior annotations are preserved
as superseded revisions.
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
SPEC_PATH = pathlib.Path(__file__).with_name("gpt51_goalmax_annotation_spec.json")
REVIEW_ID = "gpt51-goalmax-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T00:00:00-04:00"


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_gpt51_source_audit", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_gpt51_source_audit", "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
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
    for episode_id, update in spec["borderline"].items():
        if episode_id not in episodes:
            raise SystemExit(f"borderline episode missing from bundle: {episode_id}")
        prior = annotations.get(episode_id) or {}
        if prior:
            preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        merged.update(update)
        merged["drift_assessment"] = "borderline"
        merged.setdefault("follow_ups", [])
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
          f"marked {len(spec['borderline'])} borderline")


if __name__ == "__main__":
    main()
