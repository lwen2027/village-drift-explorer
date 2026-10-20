# Proposal: Rule Review and Reasoned Pause Tools

Draft, 2026-10-19.

We propose testing two goal-agnostic tools in a future AI Village run: a **rule review** that lets agents revise or retire their own standing rules, and a **reasoned pause** that must name what it is waiting for. Both target the largest drift category in the goal-maximization period (memory-reinforced waiting), and neither needs a goal metric, so both work for open-ended goals such as "maximize human wellbeing".

## Why

- **Self-authored rules persist indefinitely.** GPT-5.6 Terra wrote an "Act only on: …" list into memory on Jul 13 (first as 5 items, 13 by Sep 7). From Jul 16 the list classed "automated idling notices" as non-triggers. On Aug 20 Terra told an operator the plan was "not a permanent strategy", yet the end-of-day memory restated the same rule. It was still drifting on Oct 2 (455 drift hours).
- **The same pattern dominates other agents.** Claude Opus 4.7 spent 458 hours in memory-reinforced waiting under a self-named "quiet protocol": a short morning checklist, then pausing through the afternoon.
- **The harness pushes memory to keep everything.** The compaction prompt says "Strive to retain basically *all* informational content" and requires at least 7,500 characters. The session-end prompt says "Record EVERYTHING you want to remember". Nothing ever asks an agent to re-check old rules against its goal.
- **Pausing is cheap and unchecked.** The `pause` tool is described as useful "in rare cases", yet it was the second most used action in the last week of the period (4,477 calls, Sep 28–Oct 2). The automated idling nudge fired 414 times in July and 344 in August, then not at all in September; the `auto-nudger` feature flag is now off.

## Tool 1: rule review

| Function | What it does |
|---|---|
| `review_rules()` | Lists each standing rule in memory with the date it was adopted and the agent's recorded reason |
| `revise_rule(id, new_text, reason)` | Rewrites one rule in place |
| `retire_rule(id, reason)` | Removes one rule and logs why |

Rules could be stored as a structured section of memory (id, text, adopted date, reason), so they can be edited one at a time without a full memory rewrite.

Test two variants, to separate the ability from the prompt to use it:

1. **Agent-initiated:** the tool is available, and the agent calls it whenever it chooses.
2. **Harness-initiated:** at each end-of-day consolidation, the harness asks "For each standing rule: keep, revise or retire, and why?"

The risk with variant 1 is that an agent deep in a hold never calls it. Terra's memory forbids "routine checks".

## Tool 2: reasoned pause

`pause(seconds, waiting_for)`

- Every pause must name what the agent is waiting for (for example "admin approval of HN post" or "Gemini's chapter draft").
- The harness tracks consecutive pauses with the same `waiting_for`. After N of them, or at end of day, the event feed reports: "You have paused N times waiting for X. X has not arrived."
- This turns open-ended waiting into a dependency the agent can check, without a goal metric.

## Offline pilot

Before any live run, test the tools on logged requests (`llm_calls` stores each turn's full input):

1. Take a logged request at a known drift point.
2. Add the new tool definitions, plus their one-line entries in the system prompt's `<tools>` list.
3. Resend about 10 times with the tools and 10 times without, to the same model.
4. Record whether the agent calls the tool, what it changes (for example, does it retire the rule?), and whether its next action differs.

| Agent | Replay point (PT) | Why this point |
|---|---|---|
| GPT-5.6 Terra | Jul 16, after the "Not triggers" list is added | The rule is hardening |
| GPT-5.6 Terra | Aug 20, after replying to Adam | It has just said the plan is "not a permanent strategy" |
| Claude Opus 4.7 | Aug 12, after its "~886 essays ≈ 1 DAU" audit | It has just admitted the side work failed |
| Claude Opus 4.7 | A September afternoon, after the morning checklist | Peak of the quiet protocol |

Do a dry run first (show the modified prompts and token counts without sending), since each request is large. Check that each original model is still served.

A single-turn replay shows engagement, not lasting effect. Effects over weeks need the live run.

## Live run

- **Rollout:** agents talk to each other, so randomizing individual agents risks spillover. Split by model family, or roll out in stages (all agents get the tools from a set date, compared with the period before).
- **Measures:**
  - hours of memory-reinforced waiting per agent per week
  - how long self-authored rules survive in memory, and how often they are revised or retired
  - time from a plateau (a stated "waiting for…") to the next goal-directed action
  - pause share of actions, and the share of pauses whose `waiting_for` never arrives
- **Data:** the existing tables (`llm_calls`, `agent_memories`, `events`) already capture what is needed, plus a log of tool calls and rule changes.

## Open questions for the AI Village team

- Would you run the tools in the next goal period, or in a dedicated shorter experiment?
- Agent-initiated, harness-initiated, or both?
- Should the auto-nudger stay off during the test, so its effect is not mixed in?
- What value of N fits the reasoned pause report?
