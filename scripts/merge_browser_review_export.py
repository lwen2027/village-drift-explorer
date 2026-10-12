#!/usr/bin/env python3
"""Merge a browser-local annotation export into the committed review seed."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
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
PRESERVED_NOTE_MARKER = "\n\nPreserved browser review note:\n"
ANNOTATION_FIELDS = (
    "drift_assessment",
    "trigger_categories",
    "trigger_actor",
    "request_relationship",
    "pause_context",
    "recovery_mechanisms",
    "notes",
    "follow_ups",
)
STRUCTURED_REVIEW_FIELDS = (
    "drift_assessment",
    "trigger_categories",
    "trigger_actor",
    "request_relationship",
    "pause_context",
    "recovery_mechanisms",
)


def parsed_timestamp(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return datetime.min.replace(tzinfo=timezone.utc)


def annotation_semantic(annotation: dict | None) -> dict:
    value = annotation or {}
    return {field: value.get(field) for field in ANNOTATION_FIELDS}


def annotation_revision_id(annotation: dict, origin: str) -> str:
    serialized = json.dumps(
        {"origin": origin, "annotation": annotation},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()[:16]


def preserve_annotation_revision(
    seed: dict,
    episode_id: str,
    annotation: dict | None,
    *,
    origin: str,
    superseded_by: str,
) -> bool:
    """Keep a replaced manual annotation as an explicit, idempotent revision."""
    if not annotation:
        return False
    snapshot = json.loads(json.dumps(annotation, ensure_ascii=False))
    revision_id = annotation_revision_id(snapshot, origin)
    revisions = seed.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(item.get("revision_id") == revision_id for item in revisions):
        return False
    revisions.append({
        "revision_id": revision_id,
        "origin": origin,
        "superseded_by": superseded_by,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })
    return True


def merged_notes(
    committed: dict, local: dict, *, preserve_stale: bool = False
) -> tuple[str, bool]:
    committed_notes = str(committed.get("notes") or "").strip()
    local_notes = str(local.get("notes") or "").strip()
    if not local_notes or local_notes == committed_notes:
        return committed_notes, False
    if not committed_notes:
        return local_notes, True

    # The browser's source-audit migration writes this exact shape when it
    # carries an older browser note across a newer canonical classification.
    if local_notes.startswith(committed_notes + PRESERVED_NOTE_MARKER):
        preserved = local_notes.removeprefix(
            committed_notes + PRESERVED_NOTE_MARKER
        ).strip()
        if not preserved or preserved in committed_notes:
            return committed_notes, False
        return committed_notes + PRESERVED_NOTE_MARKER + preserved, True

    # Do not duplicate a browser note already incorporated into the source
    # audit's prose or prior-review appendix.
    if local_notes in committed_notes:
        return committed_notes, False

    # A source audit owns structured classifications, but browser-authored
    # prose remains useful audit context even when it predates that audit.
    if preserve_stale:
        return committed_notes + PRESERVED_NOTE_MARKER + local_notes, True

    # A genuinely later browser edit owns the notes field. An older browser
    # copy must not restore prose superseded by a newer source audit.
    if parsed_timestamp(local.get("updated_at")) > parsed_timestamp(
        committed.get("updated_at")
    ):
        return local_notes, True
    return committed_notes, False


def merged_follow_ups(committed: dict, local: dict) -> tuple[list[dict], bool]:
    merged: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for item in [
        *(committed.get("follow_ups") or []),
        *(local.get("follow_ups") or []),
    ]:
        key = (str(item.get("type") or ""), str(item.get("note") or "").strip())
        if key in seen:
            continue
        seen.add(key)
        merged.append(dict(item))
    return merged, merged != (committed.get("follow_ups") or [])


def bump_seed_id(seed: dict) -> None:
    match = re.fullmatch(r"(.*-v)(\d+)", str(seed.get("seed_id") or ""))
    seed["seed_id"] = (
        f"{match.group(1)}{int(match.group(2)) + 1}"
        if match
        else "goalmax-manual-review-2026-10-11-v1"
    )


def record_resolved_browser_hashes(seed: dict, exported: dict) -> int:
    """Record browser versions explicitly handled by this import.

    Most imported browser annotations become identical to the committed seed.
    A stale browser edit can instead be deliberately rejected in favor of a
    newer source audit. These receipts let the UI clear both outcomes without
    mistaking a rejected edit for work that is still awaiting integration.
    """
    resolved = seed.setdefault("resolved_browser_hashes", {})
    history = seed.setdefault("resolved_browser_hash_history", {})
    exported_hashes = exported.get("sync", {}).get("last_exported_hashes", {})
    changed = 0
    for episode_id in exported.get("annotations", {}):
        exported_hash = exported_hashes.get(episode_id)
        if exported_hash and resolved.get(episode_id) != exported_hash:
            previous_hash = resolved.get(episode_id)
            if previous_hash:
                prior_hashes = history.setdefault(episode_id, [])
                if previous_hash not in prior_hashes:
                    prior_hashes.append(previous_hash)
            resolved[episode_id] = exported_hash
            changed += 1
    return changed


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
    committed_is_source_audit = (
        existing.get("provenance", {}).get("verification_status")
        == "raw_source_verified"
    )
    local_is_later_browser_verification = (
        committed_is_source_audit
        and local.get("provenance", {}).get("verification_status")
        == "browser_verified"
        and parsed_timestamp(local.get("updated_at"))
        > parsed_timestamp(existing.get("updated_at"))
    )
    merged = (
        dict(existing)
        if committed_is_source_audit
        else {**existing, **local}
    )
    browser_override_fields = []
    if local_is_later_browser_verification:
        for field in STRUCTURED_REVIEW_FIELDS:
            if field not in local or local.get(field) == existing.get(field):
                continue
            merged[field] = local.get(field)
            browser_override_fields.append(field)
    notes, preserved_note = merged_notes(
        existing,
        local,
        preserve_stale=committed_is_source_audit,
    )
    follow_ups, preserved_follow_ups = merged_follow_ups(existing, local)
    merged["notes"] = notes
    merged["follow_ups"] = follow_ups

    if committed_is_source_audit:
        merged["provenance"] = dict(existing.get("provenance") or {})
        if (preserved_note or preserved_follow_ups
                or browser_override_fields):
            merged["provenance"]["preserved_browser_review_fields"] = True
        if local_is_later_browser_verification:
            local_provenance = local.get("provenance") or {}
            merged["provenance"]["browser_verified_at"] = (
                local_provenance.get("verified_at")
                or local.get("updated_at")
            )
            merged["provenance"]["browser_verified_by"] = (
                local_provenance.get("verified_by")
                or "browser_reviewer"
            )
            merged["provenance"]["browser_override_fields"] = (
                browser_override_fields
            )
            merged["updated_at"] = local.get("updated_at")
        return merged

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


def merge_correction_requests(seed: dict, exported: dict) -> int:
    """Preserve pending issue metadata included in newer delta exports."""
    requests = seed.setdefault("correction_requests", {})
    changed = 0
    for episode_id, local in (exported.get("correction_requests") or {}).items():
        if episode_id not in seed.get("annotations", {}):
            continue
        existing = requests.get(episode_id)
        if existing and parsed_timestamp(existing.get("updated_at")) > parsed_timestamp(
            local.get("updated_at")
        ):
            continue
        if existing != local:
            requests[episode_id] = dict(local)
            changed += 1
    return changed


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

    digest = hashlib.sha256(export_bytes).hexdigest()[:16]
    import_id = f"browser-review-export-{exported['exported_at']}-{digest}"
    merged_ids = seed.setdefault("merged_review_ids", [])
    if import_id in merged_ids:
        receipt_count = record_resolved_browser_hashes(seed, exported)
        if receipt_count:
            bump_seed_id(seed)
            args.annotations.write_text(
                json.dumps(seed, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            print(
                f"Export already merged; added {receipt_count} resolution "
                f"receipts: import_id={import_id}"
            )
        else:
            print(f"Export already merged: import_id={import_id}")
        return

    merge_taxonomies(seed, exported)
    added = 0
    updated = 0
    unchanged = 0
    for episode_id, local in exported["annotations"].items():
        committed = seed["annotations"].get(episode_id)
        merged = merged_annotation(
            episode_id, committed, local
        )
        if annotation_semantic(committed) != annotation_semantic(merged):
            preserve_annotation_revision(
                seed,
                episode_id,
                committed,
                origin="previous_committed_annotation",
                superseded_by=import_id,
            )
        committed_is_newer_source_audit = (
            committed
            and committed.get("provenance", {}).get("verification_status")
            == "raw_source_verified"
            and parsed_timestamp(committed.get("updated_at"))
            >= parsed_timestamp(local.get("updated_at"))
        )
        if (
            committed_is_newer_source_audit
            and annotation_semantic(local) != annotation_semantic(merged)
        ):
            preserve_annotation_revision(
                seed,
                episode_id,
                local,
                origin="superseded_browser_annotation",
                superseded_by=import_id,
            )
        seed["annotations"][episode_id] = merged
        if committed is None:
            added += 1
        elif committed == merged:
            unchanged += 1
        else:
            updated += 1

    validate_current_schema(seed["annotations"])
    correction_request_count = merge_correction_requests(seed, exported)
    receipt_count = record_resolved_browser_hashes(seed, exported)
    merged_ids.append(import_id)
    bump_seed_id(seed)

    args.annotations.write_text(
        json.dumps(seed, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Merged {len(exported['annotations'])} browser annotations: "
        f"added={added}, updated={updated}, unchanged={unchanged}, "
        f"receipts={receipt_count}, "
        f"correction_requests={correction_request_count}, "
        f"import_id={import_id}"
    )


if __name__ == "__main__":
    main()
