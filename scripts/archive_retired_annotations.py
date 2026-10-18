#!/usr/bin/env python3
"""Move annotations for no-longer-published episodes into a traceable archive."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS = ROOT / "data" / "manual_review_annotations_v1.json"
ARCHIVE = ROOT / "data" / "retired_manual_review_annotations_v1.json"
SELF_AUTHORED_RULES = ROOT / "data" / "self_authored_rules_v1.json"
CANONICAL = ROOT.parent / "spar-village-drift" / "artifacts" / "final" / "second_audit_v2.json"


def main() -> None:
    document = json.loads(ANNOTATIONS.read_text(encoding="utf-8"))
    bundle = json.loads(CANONICAL.read_text(encoding="utf-8"))
    active_ids = {row["episode_id"] for row in bundle["confirmed_episodes"]}
    rows = document["annotations"]
    retired_ids = sorted(set(rows) - active_ids)
    retired = {episode_id: rows.pop(episode_id) for episode_id in retired_ids}
    assignments = (
        (document.get("trigger_taxonomy") or {}).get("assignments") or {}
    )
    for episode_id in retired_ids:
        assignments.pop(episode_id, None)

    prior = {"annotations": {}}
    if ARCHIVE.exists():
        prior = json.loads(ARCHIVE.read_text(encoding="utf-8"))
    prior.setdefault("annotations", {}).update(retired)
    prior.update({
        "schema_version": 1,
        "updated_at": "2026-10-18T03:00:00-04:00",
        "reason": (
            "Preserves human annotations for records removed from the canonical "
            "confirmed-episode publication by reviewed merges or invalidations."
        ),
    })

    ANNOTATIONS.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    ARCHIVE.write_text(
        json.dumps(prior, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if SELF_AUTHORED_RULES.exists():
        rules = json.loads(SELF_AUTHORED_RULES.read_text(encoding="utf-8"))
        episode_rules = rules.get("episodes") or {}
        for episode_id in retired_ids:
            episode_rules.pop(episode_id, None)
        SELF_AUTHORED_RULES.write_text(
            json.dumps(rules, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"Archived {len(retired)} retired annotation(s)")


if __name__ == "__main__":
    main()
