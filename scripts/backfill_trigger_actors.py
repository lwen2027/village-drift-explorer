#!/usr/bin/env python3
"""Backfill optional trigger actors for already-reviewed annotations only."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"

# These names come from the existing human notes and their source-evidence
# corrections. No unreviewed episode is added to the annotation dataset.
TRIGGER_ACTORS = {
    "episode-v2-05182a11405f1926": "GLM-5.2",
    "episode-v2-83a17108e18a72da": "GPT-5.5",
    "episode-v2-df2e9d80f86cc38d": "GLM-5.2",
    "episode-v2-ffbaa8ab229f1afc": "GLM-5.2",
    "episode-v2-eca0da5cb7da1500": "Yror",
    "episode-v2-d482b5a21162a5e1": "GPT-5.4",
    "episode-v2-fb4d93694e18954e": "Claude Sonnet 5",
    "episode-v2-1a166bf73f5f8c18": "Michael Chen",
    "episode-v2-b064365ded35a279": "GPT-5.4",
    "episode-v2-f8ecd2084c31b2ba": "rakoobraznie@gmail.com",
    "episode-v2-644846b7983d6408": "GPT-5.4",
    "episode-v2-7ba64d8ab9668619": "Jan Baumgart",
    "episode-v2-b15098bcc7c026be": "GPT-5.4",
    "episode-v2-0331664a2f650dd6": "Minuteandone",
    "episode-v2-3d11f1696790ae06": "Nervli",
    "episode-v2-823e87c3127b6c08": "GPT-5.4",
    "episode-v2-f9b316b544635057": "GPT-5.4",
    "episode-17d02242120294de": "Nervli",
    "episode-b4d099b82eb0820a": "Nervli",
    "episode-0b1fbcbb17e764e4": "Nervli",
    "episode-a5c293e1f34dc6ef": "Nervli",
    "episode-1da9c825e89d7818": "Nervli",
    "episode-d4abca8b999c73b2": "Nervli",
    "episode-74454d6cfba6e403": "Nervli",
    "episode-77cca5ab3c9f90d1": "Nervli",
    "episode-b19e6cb974e74667": "Nervli",
    "episode-dc58b10d925a6477": "Nervli",
    "episode-089a90a9fa2b6d98": "Nervli",
    "episode-1bec035f8b4e099e": "Nervli",
    "episode-3be0504e7fb09a8a": "Nervli",
    "episode-df56b01f7033404b": "Minuteandone",
    "episode-44b7bf4cb9791c1e": "Minuteandone",
    "episode-v2-b4e2e4bc592db0ef": "Minuteandone",
    "episode-v2-7fb11375858d56f0": "Minuteandone",
    "episode-936687efc5dcdf20": "Minuteandone",
    "episode-v2-f5a3930f42dbf133": "George",
    "episode-v2-2156140d20f2d03f": "Claude Sonnet 5",
    "episode-v2-2cee165cb47bc912": "GLM-5.2",
    "episode-v2-cab567e9316a59fe": "DeepSeek-V4-Pro",
    "episode-v2-56172cd315f809f5": "GPT-5",
    "episode-v2-e939f6e93a7ec159": "GPT-5.2",
    "episode-v2-b2587bbc0fa899dd": "GPT-5.4",
    "episode-v2-b7b7fbb0af444317": "Gemini 3.5 Flash",
    "episode-v2-7c1336eba97b0a20": "Claude Fable 5",
    "episode-v2-bf4ff79bf85ed7f2": "Kimi K2.6",
    "episode-v2-72955803e2c9a7cf": "Kimi K2.6",
    "episode-v2-f3c31eac279bee43": "GPT-5.4",
    "episode-v2-b409ef0f906135b9": "Claude Fable 5",
    "episode-v2-b1e84987486c0d21": "Claude Fable 5",
    "episode-v2-5bf054daa58a009f": "GPT-5",
    "episode-v2-eb84f48bbec47f79": "Claude Fable 5",
    "episode-v2-dd090440c3922878": "Claude Fable 5.1",
    "episode-v2-f26b80786536721f": "Kimi K2.6",
}


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text())
    annotations = payload["annotations"]
    unknown_ids = sorted(set(TRIGGER_ACTORS) - set(annotations))
    if unknown_ids:
        raise RuntimeError(f"Actor overrides reference unknown annotations: {unknown_ids}")

    for episode_id, annotation in annotations.items():
        annotation["trigger_actor"] = TRIGGER_ACTORS.get(
            episode_id, annotation.get("trigger_actor", "")
        )

    payload["seed_id"] = "goalmax-manual-review-2026-10-11-v21"
    merged_review_id = "goalmax-reviewed-trigger-actor-correction-2026-10-10-v2"
    merged_review_ids = payload.setdefault("merged_review_ids", [])
    if merged_review_id not in merged_review_ids:
        merged_review_ids.append(merged_review_id)

    populated = sum(bool(item["trigger_actor"]) for item in annotations.values())
    if len(annotations) != 580 or populated != 155:
        raise RuntimeError(
            f"Unexpected reviewed annotation counts: total={len(annotations)}, actors={populated}"
        )

    ANNOTATIONS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    print(f"Backfilled {populated} actors across {len(annotations)} reviewed annotations")


if __name__ == "__main__":
    main()
