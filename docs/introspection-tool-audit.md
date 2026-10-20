# Audit: AI Village introspection tool

Audit of [darioncassel/ai-village-introspection-tool](https://github.com/darioncassel/ai-village-introspection-tool) at commit `49e20dc`, 2026-10-19, against the real harness as recorded in the AI Village database (`llm_calls`).

The tool is a good timeline browser and probe logger, but its replay is far from what agents saw: 80 recent chat messages and a stand-in system prompt, with no memory and no tools. It works from the public Hugging Face export, which has no `llm_calls`. With database access, each turn's full logged request can be resent as-is, so the reconstruction can be replaced with an exact replay.

## How it reconstructs context today

For every agent except one (`tierb_lib.py:648–742`): a stand-in system prompt ("You are {agent}, one of several frontier AI agents…" plus a reconstruction note), the last 80 messages in one room (the agent's own as its turns, everyone else's as `Name [Family]: text`), then a question or a resample cue. The exception is "Opus 4.5 (Claude Code)" (days ~300–360), whose `claude_code_messages` stream gives a near-faithful replay (`cc_lib.py`).

## Gaps against the real harness

| # | Gap | Where | Why it matters |
|---|---|---|---|
| 1 | System prompt is a stand-in: no date or schedule, village and individual goals, kickoff message, agent list, tool rules, outreach principles, session intention, or model-specific instructions | `tierb_lib.py:648–678` | The real prompt is ~52k characters (Terra, Oct 2) against ~400 |
| 2 | No memory: `agent_memories` is exported but never loaded | `config.py:22` | Memory is the drift mechanism we study |
| 3 | Context is room chat, not the agent's session (its own tool calls and outputs, screenshots, event batches since the last consolidation) | `tierb_lib.py:298–314` | Pauses, the main drift behavior, are invisible |
| 4 | Wrong event-feed format: real is "Here is what has happened since your last turn…" + a JSON list of events (`actionType`, `agentName`, `content`, `createdAt`), including others' `PAUSE` / `CONSOLIDATE` and `EVENTS_OMITTED` | `tierb_lib.py:615–645` | Adds labels agents never saw; drops what they did see |
| 5 | No tools sent; the model can only answer in text | `llm.py:177–251` | A resample can't show whether the agent would pause or act |
| 6 | OpenAI agents called via Chat Completions; the village used the Responses API with reasoning items and a `computer` tool | `llm.py:220–251` | Different request shape, different behavior |
| 7 | Every model asked for effort "high"; real settings differ (Terra: `medium`, summary `detailed`; Opus 4.7: adaptive thinking, `max_tokens` 20000) | `llm.py:107, 111` | Reasoning effort changes behavior |
| 8 | One default model voices every agent (`claude-opus-4-8`); agents' own models not offered | `config.py:27–41` | A different model plays the agent |
| 9 | The model is told it's a reconstruction | `tierb_lib.py:670–678` | Fine for interviews; contaminates resampling |
| 10 | "What it actually did" = next chat message only | `tierb_lib.py:362–405` | Misses the real next action, often a pause |
| 11 | No consolidation replay (session-end, merge, compaction prompts) | absent | Needed to test whether an edited rule persists |
| 12 | No request modification (memory edits, extra tools, prompt changes) | absent | Both planned experiments need it |
| 13 | Data coverage stated as "to September 2026 (days 1–535)" | `README.md:15` | Check that Oct 1–2 is included |

## Worth reusing

- The viewer: timeline, day view, search, room lanes, stars (`viewer.html`, `village_lib.py`).
- The probe log: append-only, with the exact prompt, its sha256, settings, answer and follow-up threads (`probe_jobs.py`).
- The job pool and provider clients: retries with backoff, dropping rejected settings (`llm.py:61–95`).
- The fidelity block and presence check.

## Plan

1. **Exact replay from `llm_calls`** (fixes 1–8, 10): load the logged request for the chosen turn and resend it unchanged through the provider's native API (Responses for OpenAI; Messages with the logged `betas` and computer tool for Anthropic), same model and settings, parsing tool calls from the response. Fidelity badge: EXACT.
2. **Modifications** (fixes 12): memory edits, added tools, an interview question in a side branch; each recorded with the prompt hash.
3. **Consolidation replay** (fixes 11): run the logged session-end / merge / compaction prompts on edited memory.
4. **Better public-data fallback**: rebuild the system prompt from its template using `agent_goals`, `computer_use_sessions.session_goal` and `agent_memories`; replay `computer_use_turns`; use the real event format.

`llm_calls` comes from a restricted database account, so a database-backed mode should be an optional backend that only works with the user's own credentials; agree distribution with the tool's author (and AI Digest if needed).
