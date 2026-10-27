"""Export the audited drift labels (data/drift_axes_v1.csv) as JSON for the site pages.

    data/drift_axes_v1.json   {episode_id: {trigger, trigger_detail, mechanism, memory_reinforced, started_by, ...}}

started_by names who started an episode when the trigger is another agent's or a human's request or message: the
manual annotation's trigger_actor, corrected where the trigger audits established it (same rule as
scripts/figures/plot_relationships.py). The manual annotations themselves are not changed.

    python3 scripts/export_drift_axes_json.py
"""

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "figures"))
from plot_relationships import ACTOR_FIX, FROM_OTHERS  # noqa: E402

TRIGGER_ORDER = ["Task finished / no next step seen", "Lull / unchanged state", "Pending dependency",
                 "Perceived blocker (misperceived)", "Direct route blocked", "Tool or platform failure",
                 "Misread state or clock", "Clock or self-set checkpoint", "Agent request", "Agent message exposing a need",
                 "Agent message (no request)", "Human request or message", "Operator decision",
                 "Unprompted (own plan or routine)"]
MECHANISM_ORDER = ["Waiting or monitoring loop", "Self-imposed rule", "Proxy objective", "Standing role",
                   "Bounded side task", "Early stop", "Carry-over from previous goal"]


def main():
    ann = json.loads((ROOT / "data/manual_review_annotations_v1.json").read_text())["annotations"]
    with (ROOT / "data/drift_axes_v1.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    episodes = {}
    for r in rows:
        actor = ""
        if r["trigger"] in FROM_OTHERS:
            actor = ACTOR_FIX.get(r["episode_id"]) or (ann.get(r["episode_id"], {}).get("trigger_actor") or "").strip()
            relayed = re.search(r"\(relaying ([^)]+)\)", actor)
            actor = relayed.group(1).strip() if relayed else actor
        episodes[r["episode_id"]] = {
            "agent": r["agent"],
            "hours": float(r["hours"]),
            "trigger": r["trigger"],
            "trigger_detail": r["trigger_detail"],
            "started_by_others": r["trigger"] in FROM_OTHERS,
            "started_by": actor,
            "mechanism": r["mechanism"],
            "memory_reinforced": r["memory_reinforced"] == "True",
            "pre_audit_trigger": r["pre_audit_trigger"],
            "pre_audit_mechanism": r["pre_audit_mechanism"],
            "audit_note": r["audit_note"],
        }
    out = {"schema_version": 1, "source": "data/drift_axes_v1.csv", "trigger_order": TRIGGER_ORDER,
           "mechanism_order": MECHANISM_ORDER, "episodes": episodes}
    missing = {e["trigger"] for e in episodes.values()} - set(TRIGGER_ORDER)
    missing |= {e["mechanism"] for e in episodes.values()} - set(MECHANISM_ORDER)
    if missing:
        raise SystemExit(f"labels missing from the display order: {sorted(missing)}")
    (ROOT / "data/drift_axes_v1.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n")
    print(f"wrote data/drift_axes_v1.json ({len(episodes)} episodes)")


if __name__ == "__main__":
    main()
