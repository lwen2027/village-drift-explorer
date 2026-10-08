#!/usr/bin/env python3
"""Copy the canonical second-audit bundle into the static explorer."""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil


ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_CANDIDATES = (
    # Explorer cloned inside spar-village-drift/artifacts/current.
    ROOT.parents[2] / "artifacts" / "final" / "second_audit_v2.json",
    # Explorer and spar-village-drift checked out as siblings.
    ROOT.parent / "spar-village-drift" / "artifacts" / "final"
    / "second_audit_v2.json",
)
DEFAULT_SOURCE = next(
    (path for path in DEFAULT_SOURCE_CANDIDATES if path.exists()),
    DEFAULT_SOURCE_CANDIDATES[-1],
)
DEFAULT_OUTPUT = ROOT / "data" / "second_audit_v2.json"


def migrate_episode_page() -> None:
    """Replace the legacy embedded episode array with the shared bundle."""
    path = ROOT / "index.html"
    html = path.read_text(encoding="utf-8")
    changed = False
    if "const episodes = [" in html:
        loader = """  <script type=\"module\">
    const auditBundleResponse = await fetch(\"./data/second_audit_v2.json\");
    if (!auditBundleResponse.ok) {
      throw new Error(`Could not load audit data (${auditBundleResponse.status})`);
    }
    const auditBundle = await auditBundleResponse.json();
    const episodes = auditBundle.confirmed_episodes;
"""
        pattern = re.compile(
            r"  <script>\n    const episodes = \[.*?\];\n", re.DOTALL
        )
        html, count = pattern.subn(loader, html, count=1)
        if count != 1:
            raise SystemExit("could not replace the embedded episode array")
        changed = True

    for name in ("periodEpisodes", "completeEpisodes"):
        pattern = re.compile(
            rf"    const {name} = \[.*?\];\n", re.DOTALL
        )
        html, count = pattern.subn("", html, count=1)
        changed = changed or count == 1
    if "const allEpisodes = completeEpisodes;" in html:
        html = html.replace(
            "const allEpisodes = completeEpisodes;",
            "const allEpisodes = episodes;",
            1,
        )
        changed = True
    html, comment_count = re.subn(
        r"    /\*\n    const legacySampleEpisodes = .*?\n    \*/\n",
        "",
        html,
        count=1,
        flags=re.DOTALL,
    )
    changed = changed or comment_count == 1
    if changed:
        path.write_text(html, encoding="utf-8")
        print("Updated index.html to load the shared audit bundle")


def migrate_overview_page() -> None:
    """Replace static overview behavior with bundle-derived rendering."""
    path = ROOT / "overview.html"
    html = path.read_text(encoding="utf-8")
    changed = False
    if "const rankingData =" in html:
        html, count = re.subn(
            r"  <script>\n    const rankingData = .*?\n  </script>",
            '  <script type="module" src="./scripts/overview.js"></script>',
            html,
            count=1,
            flags=re.DOTALL,
        )
        if count != 1:
            raise SystemExit("could not replace the overview inline script")
        changed = True
    if "<body>" in html:
        html = html.replace("<body>", '<body class="data-loading">', 1)
        changed = True
    if changed:
        path.write_text(html, encoding="utf-8")
        print("Updated overview.html to derive statistics from the bundle")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=pathlib.Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    with args.source.open(encoding="utf-8") as handle:
        bundle = json.load(handle)
    required = {
        "metadata",
        "stage1_daily_verdicts",
        "window_verdicts",
        "confirmed_episodes",
    }
    missing = sorted(required - bundle.keys())
    if missing:
        raise SystemExit(f"audit bundle is missing: {', '.join(missing)}")
    for name in required - {"metadata"}:
        if not isinstance(bundle[name], list):
            raise SystemExit(f"audit bundle field {name} must be an array")
    window_ids = [row.get("window_id") for row in bundle["window_verdicts"]]
    if None in window_ids or len(window_ids) != len(set(window_ids)):
        raise SystemExit("Stage 2 window ids must be present and unique")
    if any(row.get("decision_resolved") is not True
           or not isinstance(row.get("drift_verdict"), bool)
           for row in bundle["window_verdicts"]):
        raise SystemExit("every Stage 2 window must have a resolved boolean verdict")
    record_ids = [
        row.get("dataset_record_id") for row in bundle["confirmed_episodes"]
    ]
    if None in record_ids or len(record_ids) != len(set(record_ids)):
        raise SystemExit("episode dataset_record_id values must be present and unique")
    episode_ids = [row.get("episode_id") for row in bundle["confirmed_episodes"]]
    if None in episode_ids or len(episode_ids) != len(set(episode_ids)):
        raise SystemExit("episode_id values must be present and unique")
    if any(row.get("review_decision_resolved") is not True
           for row in bundle["confirmed_episodes"]):
        raise SystemExit("every exported episode must have a resolved decision")
    if any(not row.get("agent") or not row.get("activity")
           or not row.get("assigned_goal")
           for row in bundle["confirmed_episodes"]):
        raise SystemExit("every episode must identify its agent, activity, and goal")
    if any(row.get("period") not in {"shared_goal", "goal_maximization"}
           for row in bundle["confirmed_episodes"]):
        raise SystemExit("every episode must have a recognized goal period")
    repaired_ids = [
        row["repaired_candidate_dataset_record_id"]
        for row in bundle["confirmed_episodes"]
        if row.get("repaired_candidate_dataset_record_id")
    ]
    if len(repaired_ids) != len(set(repaired_ids)) or any(
            not value.startswith("v2-record-") for value in repaired_ids):
        raise SystemExit("repaired candidate record ids must be valid and unique")
    expected_counts = {
        "stage1_daily_verdicts": len(bundle["stage1_daily_verdicts"]),
        "window_verdicts": len(bundle["window_verdicts"]),
        "episode_records": len(bundle["confirmed_episodes"]),
    }
    for field, expected in expected_counts.items():
        if bundle["metadata"].get(field) != expected:
            raise SystemExit(
                f"metadata {field} does not match bundle rows: "
                f"{bundle['metadata'].get(field)!r} != {expected}"
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(args.output.suffix + ".tmp")
    shutil.copyfile(args.source, temporary)
    temporary.replace(args.output)
    migrate_episode_page()
    migrate_overview_page()
    print(
        f"Copied {len(bundle['stage1_daily_verdicts']):,} Stage 1 days, "
        f"{len(bundle['window_verdicts']):,} Stage 2 windows, and "
        f"{len(bundle['confirmed_episodes']):,} episode records to "
        f"{args.output}"
    )


if __name__ == "__main__":
    main()
