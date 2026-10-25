"""Draft split of the current drift labels into trigger and mechanism (plus a memory flag), for review.

This is only the rule-based first pass. data/drift_axes_v1.csv holds the reviewed result: every episode was then
checked by hand against the audit, the annotations and the raw logs (`checked_by`, `review_*` columns), with
memory_reinforced under the strict standard (a standing rule/plan/metric in the memory file, or a session intention
carried across a day boundary; within-day hand-offs don't count).

    python3 scripts/draft_drift_axes.py . /path/to/drift_axes_draft.csv
"""
import collections, csv, json, sys
from pathlib import Path
ROOT = Path(sys.argv[1]); OUT = Path(sys.argv[2])
a = json.loads((ROOT / "data/manual_review_annotations_v1.json").read_text())
ann, asg = a["annotations"], a["trigger_taxonomy"]["assignments"]
eps = {e["episode_id"]: e for e in json.loads((ROOT / "data/second_audit_v2.json").read_text())["confirmed_episodes"]}
agents = {e["agent"] for e in eps.values()}
points = {p["episode_id"] for ag in json.loads((ROOT / "data/interview_points_v1.json").read_text())["agents"]
          for t in ag["tracks"] for p in t["points"] if p["rule"] == "before_onset"}

HUMAN_CH = {"human_gitlab_issue": "GitLab", "human_email": "email", "human_substack_message": "Substack"}
# label -> (trigger, mechanism, memory); None = derived per episode
MAP = {
    "human_gitlab_issue": (None, None, False), "human_email": (None, None, False), "human_substack_message": (None, None, False),
    "agent_targeted_request": ("Agent request", None, False), "agent_open_request": ("Agent request", None, False),
    "agent_inferred_or_volunteered": ("Agent message exposing a need", None, False),
    "agent_message_or_cue": ("Agent message (no request)", None, False),
    "pause_monitoring_loop": ("Lull / unchanged state", "Waiting or monitoring loop", False),
    "pause_dependency_wait": ("Pending dependency", "Waiting or monitoring loop", False),
    "pause_scheduled_wait": ("Clock or self-set checkpoint", "Waiting or monitoring loop", False),
    "memory_reinforced_waiting": ("Internal (own rule or plan)", "Waiting or monitoring loop", True),
    "pause_end_of_day": ("Clock or self-set checkpoint", "Early stop", False),
    "pause_mistaken_day_boundary": ("Misread state or clock", "Early stop", False),
    "pause_nothing_left_to_do": ("Task finished / no next step seen", "Early stop", False),
    "self_authored_memory_constraint": ("Internal (own rule or plan)", "Self-imposed rule", True),
    "self_chosen_proxy_objective": ("Internal (own rule or plan)", "Proxy objective", False),
    "memory_entrenched_proxy_objective": ("Internal (own rule or plan)", "Proxy objective", True),
    "independent_side_pursuit": ("Internal (own rule or plan)", "Side project", False),
    "voluntary_side_work": ("Internal (own rule or plan)", None, False),
    "prior_goal_carryover": ("Internal (own rule or plan)", "Side project", True),
    "request_expanded_standing_role": (None, "Standing role", False),
    "tool_or_platform_failure": ("Tool or platform failure", None, False),
    "operator_imposed_constraint": ("Operator decision", None, False),
    "system_state_confusion": ("Misread state or clock", None, False),
}

def days(e):
    return {b[0][:10] for b in e.get("drift_bouts") or []} or {str(e.get("activity_start"))}

rows = []
for eid, label in asg.items():
    e, n = eps.get(eid), ann.get(eid, {})
    if not e: continue
    trig, mech, mem = MAP[label]
    checks = []
    hours = float(e.get("duration_seconds") or 0) / 3600
    actor = (n.get("trigger_actor") or "").strip()
    rel = n.get("request_relationship") or ""
    if trig is None and label in HUMAN_CH:
        trig = "Human request" if rel in ("targeted_request", "open_request") else "Human message (no request)"
    if trig is None:  # standing roles: who asked
        is_agent = any(actor.startswith(x) for x in agents) and "relaying" not in actor
        trig = ("Agent request" if is_agent else "Human request") if rel in ("targeted_request", "open_request") else (
               "Agent message exposing a need" if is_agent else "Human message (no request)")
    if mech is None:
        tc = n.get("trigger_categories") or []
        if label in ("tool_or_platform_failure", "operator_imposed_constraint", "system_state_confusion"):
            mech = "Proxy objective" if "proxy_substitution" in tc else (
                   "Waiting or monitoring loop" if e.get("mechanism_shape") == "non_pursuit" else "Bounded side task")
            checks.append("mechanism derived from proxy/non-pursuit flags")
        else:
            bucket = n.get("audit_bucket") or ""
            long_ = len(days(e)) >= 2 or hours >= 4 or any(w in bucket for w in ("recurring", "standing", "role", "intermediary"))
            mech = "Bounded side task"
            if long_:
                checks.append(f"standing role? ({len(days(e))} days, {hours:.1f} h{', ' + bucket if bucket else ''})")
    if not mem and "self_authored_memory_constraint" in (n.get("trigger_categories") or []):
        checks.append("memory rule involved? (annotation flags a self-authored memory constraint)")
    if label == "pause_monitoring_loop" and "operator_or_system_event" in (n.get("trigger_categories") or []):
        checks.append("trigger may be a (perceived) system problem")
    rows.append({"episode_id": eid, "agent": e["agent"], "interview_point_1": eid in points, "hours": round(hours, 1),
                 "current_label": label, "trigger": trig,
                 "trigger_detail": " / ".join(x for x in (HUMAN_CH.get(label, ""), actor, rel) if x),
                 "mechanism": mech, "memory_reinforced": mem, "check": "; ".join(checks),
                 "activity": e.get("activity", "")})

rows.sort(key=lambda r: (not r["interview_point_1"], r["agent"]))
with OUT.open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

def table(key):
    c, h = collections.Counter(), collections.Counter()
    for r in rows: c[r[key]] += 1; h[r[key]] += r["hours"]
    for k, v in sorted(h.items(), key=lambda x: -x[1]): print(f"  {k:36} {c[k]:4} eps {v:7.0f} h")
print(f"{len(rows)} episodes ({sum(r['interview_point_1'] for r in rows)} are interview points)")
print("MECHANISM"); table("mechanism")
print("TRIGGER"); table("trigger")
print("MEMORY-REINFORCED", sum(r["memory_reinforced"] for r in rows), "eps,", round(sum(r["hours"] for r in rows if r["memory_reinforced"])), "h")
print("NEEDS CHECK", sum(bool(r["check"]) for r in rows), "eps;", sum(bool(r["check"]) for r in rows if r["interview_point_1"]), "of them interview points")
mechs = sorted({r["mechanism"] for r in rows}); trigs = sorted({r["trigger"] for r in rows})
print("\nTRIGGER x MECHANISM (hours)")
print(" " * 34 + "".join(f"{m[:11]:>12}" for m in mechs))
for t in trigs:
    print(f"{t[:33]:34}" + "".join(f"{sum(r['hours'] for r in rows if r['trigger']==t and r['mechanism']==m):12.0f}" for m in mechs))
