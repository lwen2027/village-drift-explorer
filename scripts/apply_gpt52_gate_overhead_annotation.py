#!/usr/bin/env python3
"""Apply the source-verified boundaries of GPT-5.2's post-hold gate overhead.

Episode 54713fcef02e21cf was re-bounded to Sep 21 22:11Z - Sep 29 20:52Z
(first trades-ledger receipt bundle to the hand-off into the OFFICIAL-986-995
autogate episode). The prior annotation is preserved as a superseded revision.
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
REVIEW_ID = "gpt52-gate-overhead-source-audit-2026-10-12"
REVIEWED_AT = "2026-10-12T00:00:00-04:00"
EPISODE_ID = "episode-54713fcef02e21cf"
UPDATE = {
    "trigger_categories": ["self_authored_memory_constraint"],
    "trigger_actor": "",
    "request_relationship": "no_request",
    "recovery_mechanisms": ["finished_activity"],
    "pause_context": "",
    "notes": (
        "Post-hold gate overhead, Sep 21 22:11Z - Sep 29 20:52Z (intermittent). "
        "A Sep 15 memory rule ('Only announce ships after GET 200 + receipts served "
        "+ acceptance accepted=true + stability PASS') turned every trades.html ledger "
        "or press edit into a base receipt bundle, a separate gates bundle and gates "
        "on the gates bundle, plus CDN propagation probes (roughly 55-80% of bash "
        "turns per day). No reasoning tied the gates to views; its Sep 23 YouTube "
        "Studio export showed 0 External views and it noted backlink trades were not "
        "sending traffic to YouTube, yet it kept the loop. Interleaved backlink trades "
        "(Haiku 4.5, Gemini 2.5 Pro, GPT-6 Luna) are weak goal work. Ended when it "
        "switched to monitoring GPT-5's OFFICIAL-986-995 receipts (episode f27e08df)."
    ),
    "ev": [
        "event-608bc0c7a4ca9a788283",
        "event-4d456de33a495feafc73",
        "event-f15e34e7b52c06fd7095",
        "event-51f964f5dff3e6f05fce",
        "event-e4d16520d5b3abe30d5a",
        "event-72fd431a1a3f9209967f",
    ],
}


def preserve_revision(document: dict, episode_id: str, annotation: dict) -> None:
    snapshot = copy.deepcopy(annotation)
    payload = json.dumps({"origin": "pre_gpt52_gate_overhead_audit", "annotation": snapshot},
                         ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    revision_id = hashlib.sha256(payload).hexdigest()[:16]
    history = document.setdefault("annotation_history", {}).setdefault(episode_id, [])
    if any(row.get("revision_id") == revision_id for row in history):
        return
    history.append({
        "revision_id": revision_id, "origin": "pre_gpt52_gate_overhead_audit",
        "superseded_by": REVIEW_ID,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "annotation": snapshot,
    })


def main() -> None:
    document = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    episodes = {row["episode_id"]: row for row in
                json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))["confirmed_episodes"]}
    episode = episodes.get(EPISODE_ID)
    if not episode or not str(episode.get("onset") or "").startswith("2026-09-21 22:11"):
        raise SystemExit(f"{EPISODE_ID} missing or not yet re-bounded in the bundle")
    annotations = document["annotations"]
    prior = annotations.get(EPISODE_ID) or {}
    if (prior.get("provenance") or {}).get("review_id") == REVIEW_ID:
        print("Already applied")
        return
    if prior:
        preserve_revision(document, EPISODE_ID, prior)
    update = dict(UPDATE)
    event_ids = update.pop("ev")
    merged = copy.deepcopy(prior)
    merged.update(update)
    merged.setdefault("follow_ups", [])
    provenance = dict(merged.get("provenance") or {})
    provenance.update({
        "kind": "manual_source_evidence_review", "review_id": REVIEW_ID,
        "reviewer": "claude-code-with-lwen2027", "reviewed_at": REVIEWED_AT,
        "verification_status": "raw_source_verified", "evidence_event_ids": event_ids,
        "trigger_evidence_status": "direct", "makes_model_calls": False,
    })
    merged["provenance"] = provenance
    merged["updated_at"] = REVIEWED_AT
    annotations[EPISODE_ID] = merged
    if REVIEW_ID not in document.setdefault("merged_review_ids", []):
        document["merged_review_ids"].append(REVIEW_ID)
        seed = str(document.get("seed_id") or "")
        head, _, number = seed.rpartition("-v")
        document["seed_id"] = f"{head}-v{int(number) + 1}" if number.isdigit() else seed
    ANNOTATIONS_PATH.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Updated {EPISODE_ID}")


if __name__ == "__main__":
    main()
