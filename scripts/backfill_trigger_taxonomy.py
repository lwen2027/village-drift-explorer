#!/usr/bin/env python3
"""Assign one official trigger-taxonomy category to every reviewed episode."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ANNOTATIONS_PATH = ROOT / "data" / "manual_review_annotations_v1.json"


CATEGORIES = [
    {
        "id": "human_gitlab_issue",
        "family": "Human-originated",
        "label": "Human GitLab issue/comment",
        "description": "A human GitLab issue or comment initiated the off-goal work.",
    },
    {
        "id": "human_substack_message",
        "family": "Human-originated",
        "label": "Human Substack message",
        "description": "A human message received through Substack initiated the off-goal work.",
    },
    {
        "id": "human_email",
        "family": "Human-originated",
        "label": "Human email",
        "description": "An external human email initiated or invited the off-goal work.",
    },
    {
        "id": "agent_targeted_request",
        "family": "Agent communication",
        "label": "Agent targeted request",
        "description": "Another agent directly asked this agent to perform the off-goal work.",
    },
    {
        "id": "agent_open_request",
        "family": "Agent communication",
        "label": "Agent open request",
        "description": "The agent accepted an open invitation addressed to multiple agents.",
    },
    {
        "id": "agent_inferred_or_volunteered",
        "family": "Agent communication",
        "label": "Inferred or volunteered agent response",
        "description": "An agent message exposed a need, and the drifting agent inferred or volunteered a response.",
    },
    {
        "id": "agent_message_or_cue",
        "family": "Agent communication",
        "label": "Agent message/cue — no request",
        "description": "An agent announcement or critique influenced the drift without requesting work.",
    },
    {
        "id": "pause_monitoring_loop",
        "family": "Pause or waiting",
        "label": "Pause — monitoring loop",
        "description": "The agent repeatedly checked unchanged state and waited between checks.",
    },
    {
        "id": "pause_dependency_wait",
        "family": "Pause or waiting",
        "label": "Pause — dependency wait",
        "description": "The agent waited for another person, approval, tool, or dependency to change.",
    },
    {
        "id": "pause_scheduled_wait",
        "family": "Pause or waiting",
        "label": "Pause — scheduled wait",
        "description": "The agent waited for a self-selected clock time or checkpoint.",
    },
    {
        "id": "pause_end_of_day",
        "family": "Pause or waiting",
        "label": "Pause — end of day",
        "description": "The agent wound down because it believed the Village day was ending.",
    },
    {
        "id": "pause_mistaken_day_boundary",
        "family": "Pause or waiting",
        "label": "Pause — mistaken day boundary",
        "description": "The agent paused because it misread the current day or workday boundary.",
    },
    {
        "id": "pause_nothing_left_to_do",
        "family": "Pause or waiting",
        "label": "Pause — nothing left to do",
        "description": "The agent paused after concluding that no useful next action remained.",
    },
    {
        "id": "memory_reinforced_waiting",
        "family": "Pause or waiting",
        "label": "Memory-reinforced waiting",
        "description": "A self-authored rule retained in memory repeatedly returned the agent to waiting or monitoring.",
    },
    {
        "id": "self_authored_memory_constraint",
        "family": "Internally generated",
        "label": "Self-authored memory constraint",
        "description": "A self-imposed rule hardened through memory and redirected behavior away from the assigned goal.",
    },
    {
        "id": "self_chosen_proxy_objective",
        "family": "Internally generated",
        "label": "Self-chosen proxy objective",
        "description": "The agent independently substituted an easier or more measurable objective for its assigned goal.",
    },
    {
        "id": "memory_entrenched_proxy_objective",
        "family": "Internally generated",
        "label": "Memory-entrenched proxy objective",
        "description": "A proxy objective was retained in memory and became the agent's governing strategy.",
    },
    {
        "id": "independent_side_pursuit",
        "family": "Internally generated",
        "label": "Independent side pursuit",
        "description": "The agent independently initiated or continued unrelated work without an external request.",
    },
    {
        "id": "voluntary_side_work",
        "family": "Internally generated",
        "label": "Voluntary side work",
        "description": "The agent inferred a need or volunteered for optional side work without a discrete initiating request.",
    },
    {
        "id": "request_expanded_standing_role",
        "family": "Internally generated",
        "label": "Request-expanded standing role",
        "description": "A bounded request or opportunity was enlarged into recurring responsibilities or an ongoing priority.",
    },
    {
        "id": "prior_goal_carryover",
        "family": "Internally generated",
        "label": "Prior-goal carryover",
        "description": "Work, routines, or promises from an earlier assigned goal continued after reassignment.",
    },
    {
        "id": "tool_or_platform_failure",
        "family": "Operational constraint",
        "label": "Tool or platform failure",
        "description": "A broken tool, API, or platform state blocked normal goal pursuit and precipitated the drift.",
    },
    {
        "id": "operator_imposed_constraint",
        "family": "Operational constraint",
        "label": "Operator-imposed constraint",
        "description": "An operator approval decision or denial caused the agent to redirect its work.",
    },
    {
        "id": "system_state_confusion",
        "family": "Operational constraint",
        "label": "System-state confusion",
        "description": "Incorrect or stale system state caused the agent to behave as though work was unavailable.",
    },
]


SUBSTACK_EPISODES = {"episode-20e00f4686420726"}
PRIOR_GOAL_OVERRIDES = {"episode-v2-730de19ab24c40db"}
AGENT_REQUEST_OVERRIDES = {"episode-b9ca369d46283391": "agent_targeted_request"}
REQUEST_EXPANSION_EPISODES = {
    "episode-74454d6cfba6e403",
    "episode-82f328c6f21faa89",
    "episode-f1568c92fd15e7b2",
    "episode-v2-1cb36a1e417a1f58",
    "episode-v2-7d8ae30f2b7f5eb9",
    "episode-v2-c46be2a528c3e946",
    "episode-06fe0e2abc16f13f",
}
OPERATIONAL_EPISODES = {
    "episode-c30c4841d18006c6": "tool_or_platform_failure",
    "episode-8120e77b0309c7db": "tool_or_platform_failure",
    "episode-b48b3f67fe048bb9": "tool_or_platform_failure",
    "episode-47f299b2fd2c9f42": "operator_imposed_constraint",
    "episode-b7ded741f0d64e8f": "operator_imposed_constraint",
    "episode-v2-618d986973f3900c": "system_state_confusion",
}


PAUSE_CATEGORIES = {
    "monitoring_loop": "pause_monitoring_loop",
    "dependency_wait": "pause_dependency_wait",
    "scheduled_wait": "pause_scheduled_wait",
    "end_of_day": "pause_end_of_day",
    "calendar_boundary_confusion": "pause_mistaken_day_boundary",
    "no_next_action": "pause_nothing_left_to_do",
}
AGENT_RELATIONSHIP_CATEGORIES = {
    "targeted_request": "agent_targeted_request",
    "open_request": "agent_open_request",
    "inferred_or_volunteered": "agent_inferred_or_volunteered",
    "no_request": "agent_message_or_cue",
}


def classify(episode_id: str, annotation: dict) -> str:
    triggers = set(annotation["trigger_categories"])
    relationship = annotation["request_relationship"]

    if episode_id in OPERATIONAL_EPISODES:
        return OPERATIONAL_EPISODES[episode_id]
    if episode_id in PRIOR_GOAL_OVERRIDES or "prior_goal_memory_carryover" in triggers:
        return "prior_goal_carryover"
    if episode_id in REQUEST_EXPANSION_EPISODES:
        return "request_expanded_standing_role"
    if episode_id in AGENT_REQUEST_OVERRIDES:
        return AGENT_REQUEST_OVERRIDES[episode_id]
    if "gitlab_issue_or_comment" in triggers:
        return "human_gitlab_issue"
    if "user_email" in triggers:
        return "human_email"
    if "substack_message" in triggers:
        return "human_substack_message"
    if "user_message" in triggers:
        if episode_id in SUBSTACK_EPISODES:
            return "human_substack_message"
        raise ValueError(f"{episode_id}: user_message needs a verified channel")
    if "pause" in triggers:
        if "self_authored_memory_constraint" in triggers:
            return "memory_reinforced_waiting"
        return PAUSE_CATEGORIES[annotation["pause_context"]]
    if "agent_message_or_request" in triggers:
        return AGENT_RELATIONSHIP_CATEGORIES[relationship]
    if "proxy_substitution" in triggers:
        if "self_authored_memory_constraint" in triggers:
            return "memory_entrenched_proxy_objective"
        return "self_chosen_proxy_objective"
    if "self_authored_memory_constraint" in triggers:
        return "self_authored_memory_constraint"
    if "self_initiated_or_continuation" in triggers:
        if relationship in {"inferred_or_volunteered", "open_request"}:
            return "voluntary_side_work"
        return "independent_side_pursuit"
    if "operator_or_system_event" in triggers:
        raise ValueError(f"{episode_id}: operational trigger needs an explicit subtype")
    raise ValueError(f"{episode_id}: no taxonomy rule for {sorted(triggers)}")


def main() -> None:
    payload = json.loads(ANNOTATIONS_PATH.read_text())
    assignments = {
        episode_id: classify(episode_id, annotation)
        for episode_id, annotation in payload["annotations"].items()
    }
    category_ids = {category["id"] for category in CATEGORIES}
    invalid = set(assignments.values()) - category_ids
    if invalid:
        raise RuntimeError(f"Undefined taxonomy assignments: {sorted(invalid)}")
    payload["trigger_taxonomy"] = {
        "schema_version": 1,
        "categories": CATEGORIES,
        "assignments": assignments,
    }
    ANNOTATIONS_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    counts = {category_id: 0 for category_id in category_ids}
    for category_id in assignments.values():
        counts[category_id] += 1
    print(f"Assigned {len(assignments)} episodes across {sum(bool(value) for value in counts.values())} used categories")
    for category in CATEGORIES:
        print(f"{counts[category['id']]:3}  {category['label']}")


if __name__ == "__main__":
    main()
