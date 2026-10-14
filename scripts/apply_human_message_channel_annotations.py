#!/usr/bin/env python3
"""Reclassify "User message" triggers by their verified source channel.

Every goal-max episode tagged user_message named its human but not the channel.
Source review showed GitLab issue/comment threads, relays through another agent,
and Substack messages. GitLab and relay cases move to the existing categories;
Substack cases use the new substack_message category, which this script adds to
the trigger taxonomy. Prior annotations are preserved as superseded revisions.
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
SPEC_PATH = pathlib.Path(__file__).with_name("human_message_channel_annotation_spec.json")
REVIEW_ID = "human-message-channel-review-2026-10-14"
REVIEWED_AT = "2026-10-14T00:00:00-04:00"
SUBSTACK_TRIGGER = {"id": "substack_message", "label": "Substack message", "custom": False}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_human_message_channel_review", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_human_message_channel_review",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))["updates"]
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"] for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    triggers = document["taxonomies"]["trigger"]
    if SUBSTACK_TRIGGER["id"] not in {row["id"] for row in triggers}:
        index = next((i + 1 for i, row in enumerate(triggers) if row["id"] == "gitlab_issue_or_comment"), len(triggers))
        triggers.insert(index, dict(SUBSTACK_TRIGGER))
    annotations = document["annotations"]
    updated = 0
    for episode_id, update in spec.items():
        if episode_id not in episodes or episode_id not in annotations:
            raise SystemExit(f"episode or annotation missing: {episode_id}")
        prior = annotations[episode_id]
        if (prior.get("provenance") or {}).get("channel_review_id") == REVIEW_ID:
            continue
        preserve_revision(document, episode_id, prior)
        merged = copy.deepcopy(prior)
        merged["trigger_categories"] = list(update["trigger_categories"])
        merged["trigger_actor"] = update["trigger_actor"]
        merged["notes"] = (str(merged.get("notes") or "").rstrip() + " " + update["channel_note"]).strip()
        provenance = dict(merged.get("provenance") or {})
        provenance.update({
            "channel_review_id": REVIEW_ID, "channel_reviewed_by": "claude-code-with-lwen2027",
            "channel_reviewed_at": REVIEWED_AT, "channel_evidence_event_ids": update["ev"],
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
    print(f"Reclassified {updated} annotations")


if __name__ == "__main__":
    main()
