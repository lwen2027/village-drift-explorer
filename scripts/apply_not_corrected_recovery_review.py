#!/usr/bin/env python3
"""Replace "Not corrected" primary recovery labels with the verified ending.

A raw-log review of every goal-max episode whose primary recovery was
not_corrected found that none was genuinely uncorrected: the drift was still
running when the agent's data ends, continued in a later record of the same
episode, gave way to a different drift, or ended for an existing reason. This
script adds the three new recovery labels to the taxonomy and swaps the primary
label for each reviewed episode. Prior annotations are preserved as superseded
revisions.
"""

from __future__ import annotations

import copy
import hashlib
import json
import pathlib
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
SPEC_PATH = pathlib.Path(__file__).with_name("not_corrected_recovery_review_spec.json")
REVIEW_ID = "not-corrected-recovery-review-2026-10-17"
REVIEWED_AT = "2026-10-17T00:00:00-04:00"
NEW_RECOVERIES = [
    {"id": "still_drifting_at_end_of_data", "label": "Still drifting at end of data", "custom": False},
    {"id": "continued_in_later_record", "label": "Continued in a later record", "custom": False},
    {"id": "switched_to_another_drift", "label": "Switched to another drift", "custom": False},
]


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_not_corrected_recovery_review", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_not_corrected_recovery_review",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["updates"]
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    recoveries = document["taxonomies"]["recovery"]
    known = {row["id"] for row in recoveries}
    index = next((i + 1 for i, row in enumerate(recoveries) if row["id"] == "not_corrected"), len(recoveries))
    for offset, item in enumerate(item for item in NEW_RECOVERIES if item["id"] not in known):
        recoveries.insert(index + offset, dict(item))
    known = {row["id"] for row in recoveries}
    annotations = document["annotations"]
    updated = 0
    for episode_id, update in spec.items():
        if episode_id not in episodes or episode_id not in annotations:
            raise SystemExit(f"episode or annotation missing: {episode_id}")
        if update["recovery"] not in known:
            raise SystemExit(f"unknown recovery label {update['recovery']}: {episode_id}")
        prior = annotations[episode_id]
        if (prior.get("provenance") or {}).get("recovery_review_id") == REVIEW_ID:
            continue
        current = list(prior.get("recovery_mechanisms") or [])
        if not current or current[0] != "not_corrected":
            raise SystemExit(f"primary recovery is no longer not_corrected: {episode_id}")
        preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        rest = [value for value in current[1:] if value not in {"not_corrected", update["recovery"]}]
        merged["recovery_mechanisms"] = [update["recovery"], *rest]
        merged["notes"] = (str(merged.get("notes") or "").rstrip() + " " + update["note"]).strip()
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "recovery_review_id": REVIEW_ID, "recovery_reviewed_by": "claude-code-with-lwen2027",
            "recovery_reviewed_at": REVIEWED_AT, "recovery_evidence_time": update["evidence"],
            "recovery_review_confidence": update["confidence"],
            "recovery_related_episode_id": update.get("related_episode_id"),
            "makes_model_calls": False,
        })
        merged["provenance"] = provenance
        merged["updated_at"] = REVIEWED_AT
        annotations[episode_id] = merged
        updated += 1
    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = f"{head}-v{int(number) + 1}" if number.isdigit() else seed
    ANNOTATIONS_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Relabelled {updated} annotations")


if __name__ == "__main__":
    main()
