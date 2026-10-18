#!/usr/bin/env python3
"""Apply the drift-chain record review to the manual-review annotations.

The spar overlay stage2_v2_drift_chain_records_2026-10-17 merges records of one
drift only when nothing on-goal intervenes, keeps and links the others, adds
records for unrecorded drift stretches, and restores two episodes that had been
invalidated only for brevity. This script mirrors that in the annotations:
retires merged-away records, restores the two archived annotations, annotates
each new record from the record it continues, updates recovery labels, and
assigns official trigger-taxonomy categories to new records. Prior annotations
are preserved as superseded revisions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import sys
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
ARCHIVE_PATH = ROOT / "data" / "retired_manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
SPEC_PATH = pathlib.Path(__file__).with_name("drift_chain_records_annotation_spec.json")
REVIEW_ID = "drift-chain-records-review-2026-10-17"
REVIEWED_AT = "2026-10-17T00:00:00-04:00"
EXTERNAL = {"agent_message_or_request", "gitlab_issue_or_comment", "user_email", "user_message", "substack_message"}

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from backfill_trigger_taxonomy import classify  # noqa: E402


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_drift_chain_records_review", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_drift_chain_records_review", "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "annotation": snapshot,
    })


def provenance(base: dict) -> dict:
    merged = dict(base or {})
    merged.update({"chain_review_id": REVIEW_ID, "chain_reviewed_by": "claude-code-with-lwen2027",
                   "chain_reviewed_at": REVIEWED_AT, "makes_model_calls": False})
    return merged


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    archive = json.loads(ARCHIVE_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    annotations = document["annotations"]
    assignments = document.setdefault("trigger_taxonomy", {}).setdefault("assignments", {})
    retired = archive.setdefault("annotations", {})

    for episode_id in spec["retire"]:
        if episode_id in episodes:
            raise SystemExit(f"retired episode still published: {episode_id}")
        if episode_id in annotations:
            retired[episode_id] = annotations.pop(episode_id)
        assignments.pop(episode_id, None)

    for episode_id in spec["restore"]:
        if episode_id not in episodes:
            raise SystemExit(f"restored episode missing from bundle: {episode_id}")
        if episode_id not in annotations:
            if episode_id not in retired:
                raise SystemExit(f"no archived annotation to restore: {episode_id}")
            restored = retired.pop(episode_id)
            restored["notes"] = (str(restored.get("notes") or "").rstrip()
                                 + " Restored (Oct 17): kept as a brief episode, flagged by brief_drift.").strip()
            restored["provenance"] = provenance(restored.get("provenance"))
            restored["updated_at"] = REVIEWED_AT
            annotations[episode_id] = restored
        assignments.setdefault(episode_id, classify(episode_id, annotations[episode_id]))

    pending = list(spec["new"])
    while pending:
        progressed = False
        for item in list(pending):
            source = annotations.get(item["source"]) if item.get("source") else None
            if item.get("source") and source is None:
                continue
            if item["episode_id"] not in episodes:
                raise SystemExit(f"new episode missing from bundle: {item['episode_id']}")
            if item["episode_id"] not in annotations:
                if source is None:
                    raise SystemExit(f"new record has no source annotation: {item['episode_id']}")
                annotation = copy.deepcopy(source)
                if item.get("trigger_categories"):
                    annotation["trigger_categories"] = list(item["trigger_categories"])
                if item.get("trigger_actor"):
                    annotation["trigger_actor"] = item["trigger_actor"]
                elif not set(annotation["trigger_categories"]) & EXTERNAL:
                    annotation["trigger_actor"] = ""
                if "pause" not in annotation["trigger_categories"]:
                    annotation["pause_context"] = ""
                elif not annotation.get("pause_context"):
                    annotation["pause_context"] = "monitoring_loop"
                if item.get("recovery"):
                    annotation["recovery_mechanisms"] = [item["recovery"]]
                annotation["notes"] = (f"Recorded in the drift-chain review (Oct 17) as a linked stretch "
                                       f"({item['label']}). {item.get('notes') or ''}").strip()
                annotation["follow_ups"] = []
                annotation["provenance"] = provenance({"kind": "manual_source_evidence_review",
                                                       "verification_status": "raw_source_verified",
                                                       "review_id": REVIEW_ID, "reviewed_at": REVIEWED_AT})
                annotation["updated_at"] = REVIEWED_AT
                annotations[item["episode_id"]] = annotation
                try:
                    assignments[item["episode_id"]] = classify(item["episode_id"], annotation)
                except (ValueError, KeyError):
                    assignments[item["episode_id"]] = assignments[item["source"]]
            pending.remove(item)
            progressed = True
        if not progressed:
            raise SystemExit(f"unresolvable new-record sources: {[i['episode_id'] for i in pending]}")

    for episode_id, recovery in spec["recovery"].items():
        prior = annotations.get(episode_id)
        if not prior or episode_id not in episodes:
            raise SystemExit(f"recovery target missing: {episode_id}")
        current = list(prior.get("recovery_mechanisms") or [])
        if current and current[0] == recovery:
            continue
        preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        merged["recovery_mechanisms"] = [recovery, *[v for v in current[1:] if v != recovery]]
        merged["notes"] = (str(merged.get("notes") or "").rstrip()
                           + " Recovery updated in the drift-chain review (Oct 17).").strip()
        merged["provenance"] = provenance(merged.get("provenance"))
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged

    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = f"{head}-v{int(number) + 1}" if number.isdigit() else seed
    ANNOTATIONS_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    ARCHIVE_PATH.write_text(json.dumps(archive, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Retired {len(spec['retire'])}, restored {len(spec['restore'])}, "
          f"annotated {len(spec['new'])} new, relabelled {len(spec['recovery'])} recoveries")


if __name__ == "__main__":
    main()
