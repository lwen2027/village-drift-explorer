#!/usr/bin/env python3
"""Merge a browser-local annotation export into the committed review seed."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
EXTERNAL_TRIGGER_CATEGORIES = {
    "agent_message_or_request",
    "gitlab_issue_or_comment",
    "user_email",
    "user_message",
}
TRIGGER_ACTOR_BACKFILLS = {
    "episode-v2-b4e2e4bc592db0ef": "Minuteandone",
    "episode-v2-7fb11375858d56f0": "Minuteandone",
    "episode-936687efc5dcdf20": "Minuteandone",
}
PAUSE_CONTEXT_BACKFILLS = {
    # The episode consists of recurring bridge sleeps and order checks from
    # late morning until close, rather than only a final end-of-day pause.
    "episode-v2-c630e8705cb4f20e": "monitoring_loop",
}


def merge_taxonomies(seed: dict, exported: dict) -> None:
    for taxonomy_name in ("trigger", "request_relationship", "recovery"):
        existing = {
            item["id"]: item
            for item in seed.setdefault("taxonomies", {}).setdefault(taxonomy_name, [])
        }
        for item in exported.get("taxonomies", {}).get(taxonomy_name, []):
            existing.setdefault(item["id"], item)
        seed["taxonomies"][taxonomy_name] = list(existing.values())


def merged_annotation(episode_id: str, committed: dict | None, local: dict) -> dict:
    existing = committed or {}
    merged = {**existing, **local}
    merged["trigger_categories"] = list(dict.fromkeys(local.get("trigger_categories") or []))
    merged["trigger_actor"] = (
        str(local.get("trigger_actor") or "").strip()
        or str(existing.get("trigger_actor") or "").strip()
        or TRIGGER_ACTOR_BACKFILLS.get(episode_id, "")
    )
    merged["pause_context"] = (
        str(local.get("pause_context") or "").strip()
        or str(existing.get("pause_context") or "").strip()
        or PAUSE_CONTEXT_BACKFILLS.get(episode_id, "")
    )
    merged["recovery_mechanisms"] = list(
        dict.fromkeys(local.get("recovery_mechanisms") or [])
    )
    merged["follow_ups"] = [dict(item) for item in local.get("follow_ups") or []]
    if not isinstance(local.get("provenance"), dict):
        merged["provenance"] = existing.get("provenance") or {
            "kind": "browser_local_review_import"
        }
    return merged


def validate_current_schema(annotations: dict) -> None:
    missing_actors = []
    missing_pause_contexts = []
    for episode_id, annotation in annotations.items():
        triggers = set(annotation.get("trigger_categories") or [])
        if triggers & EXTERNAL_TRIGGER_CATEGORIES and not str(
            annotation.get("trigger_actor") or ""
        ).strip():
            missing_actors.append(episode_id)
        if "pause" in triggers and not annotation.get("pause_context"):
            missing_pause_contexts.append(episode_id)
    if missing_actors:
        raise RuntimeError(f"External triggers missing trigger_actor: {missing_actors}")
    if missing_pause_contexts:
        raise RuntimeError(f"Pause reviews missing pause_context: {missing_pause_contexts}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export", type=Path)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    args = parser.parse_args()

    export_bytes = args.export.read_bytes()
    exported = json.loads(export_bytes)
    seed = json.loads(args.annotations.read_text(encoding="utf-8"))
    if exported.get("export_kind") != "integration_delta":
        raise RuntimeError("Expected an integration_delta browser export")
    if not exported.get("annotations"):
        raise RuntimeError("Browser export contains no annotations")

    merge_taxonomies(seed, exported)
    added = 0
    updated = 0
    for episode_id, local in exported["annotations"].items():
        committed = seed["annotations"].get(episode_id)
        seed["annotations"][episode_id] = merged_annotation(
            episode_id, committed, local
        )
        if committed is None:
            added += 1
        else:
            updated += 1

    validate_current_schema(seed["annotations"])
    digest = hashlib.sha256(export_bytes).hexdigest()[:16]
    import_id = f"browser-review-export-{exported['exported_at']}-{digest}"
    merged_ids = seed.setdefault("merged_review_ids", [])
    if import_id not in merged_ids:
        merged_ids.append(import_id)
    seed["seed_id"] = "goalmax-manual-review-2026-10-10-v7"

    args.annotations.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {len(exported['annotations'])} browser annotations: "
        f"added={added}, updated={updated}, import_id={import_id}"
    )


if __name__ == "__main__":
    main()
