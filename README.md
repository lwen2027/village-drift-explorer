# Agent Drift Explorer

Interactive explorer for confirmed goal-drift episodes in the [AI Village](https://theaidigest.org/village).

**Live site:** https://lwen2027.github.io/village-drift-explorer/

## Pages

| Page | What it shows |
| --- | --- |
| [Episode explorer](https://lwen2027.github.io/village-drift-explorer/) (`index.html`) | Atlas of Village goal periods with each agent's confirmed drift episodes and bouts, plus a filterable episode list. |
| [Pipeline overview](https://lwen2027.github.io/village-drift-explorer/overview.html) (`overview.html`) | How raw activity becomes confirmed episodes: goal-window verdicts, goal-maximization vs. shared-goal periods, per-agent counts, evidence quality, and definitions. |
| [Findings overview](https://lwen2027.github.io/village-drift-explorer/findings.html) (`findings.html`) | Aggregate findings from fully reviewed episodes: review coverage, timing and duration, triggers, recovery, and pause contexts. |
| [Manual review](https://lwen2027.github.io/village-drift-explorer/review.html) (`review.html`) | Review queue for goal-maximization episodes. Annotations are saved in the browser and can be exported as JSON or CSV. |
| [Interview points](https://lwen2027.github.io/village-drift-explorer/interviews.html) (`interviews.html`) | The replay points selected for interviewing each drifting agent (`data/interview_points_v1.json`), one card per agent with a timeline of its episodes, what it did at each point, links to the Village replay and the episode, and per-point review marks saved in the browser and exportable as JSON. |

## Repository layout

- `*.html`: the static pages. There is no build step; GitHub Pages serves `main` from the repository root.
- `data/`: JSON the pages fetch at runtime.
  - `second_audit_v2.json`: the canonical confirmed-episode bundle (episodes, window verdicts, stage 1 daily verdicts, metadata).
  - `manual_review_annotations_v1.json`: committed manual-review annotations (triggers, pause context, recovery, notes).
  - `manual_review_wait_exclusions_v1.json`, `retired_manual_review_annotations_v1.json`: wait-only exclusions and archived annotations.
  - `source_records.json`, `goal_categories_v1.json`, `human_contact_v1.json`: Village goal, agent, and human-contact reference data.
- `scripts/findings.js`, `scripts/overview.js`: page logic for the findings and pipeline overviews.
- `scripts/*.py`, `scripts/*_spec.json`: maintenance scripts that refresh data and apply annotation batches.
- `styles/site-header.css`: shared header and navigation styles.

## Running locally

The pages load data with `fetch`, so serve them over HTTP instead of opening the files directly:

```sh
python3 -m http.server 8000
# then open http://localhost:8000/
```

## Updating data

The episode bundle is produced by the companion `spar-village-drift` pipeline. With that repository checked out next to this one:

```sh
# Copy the latest second-audit bundle and wait-exclusion manifest into data/
python3 scripts/refresh_audit_bundle.py

# Refresh Village goal and agent records
python3 scripts/refresh_source_records.py --source-dir <path-to-records> --html index.html

# Merge annotations exported from the Manual review page
python3 scripts/merge_browser_review_export.py <export.json>

# Check annotation coverage and schema invariants
python3 scripts/validate_manual_review_annotations.py
```

Run each script with `--help` to see its full options.
