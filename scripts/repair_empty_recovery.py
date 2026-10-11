#!/usr/bin/env python3
"""Fill the sole empty recovery using its validated completion boundary."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"
BUNDLE_PATH = ROOT / "data" / "second_audit_v2.json"
EPISODE_ID = "episode-936687efc5dcdf20"


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text())
    bundle = json.loads(BUNDLE_PATH.read_text())
    annotation = payload["annotations"][EPISODE_ID]
    if annotation.get("recovery_mechanisms") != []:
        raise RuntimeError("Refusing to replace a non-empty manually reviewed recovery")

    episode = next(
        item for item in bundle["confirmed_episodes"] if item["episode_id"] == EPISODE_ID
    )
    drift_end = episode.get("drift_end") or {}
    end_quote = ((drift_end.get("evidence") or {}).get("quote") or "").lower()
    if drift_end.get("status") != "activity_ended" or "final deliverable shipped" not in end_quote:
        raise RuntimeError("Expected validated activity-completion evidence is absent")

    annotation["recovery_mechanisms"] = ["finished_activity"]
    payload["seed_id"] = "goalmax-manual-review-2026-10-11-v22"
    review_id = "goalmax-empty-recovery-repair-2026-10-11-v1"
    merged_review_ids = payload.setdefault("merged_review_ids", [])
    if review_id not in merged_review_ids:
        merged_review_ids.append(review_id)
    ANNOTATIONS_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"Set {EPISODE_ID} recovery to finished_activity")


if __name__ == "__main__":
    main()
