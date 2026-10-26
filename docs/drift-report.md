# Goal drift in the AI Village: what happened, why, and what to change

Draft report, 26 October 2026. It combines four sources:
- the labelled drift episodes (`data/drift_axes_v1.csv`);
- interviews with the drifting agents and a control group (`answers.html`), reviewed by the researcher (`data/interview_reviews_v1.json`);
- a motive coding of the drift interview points (`data/motive_coding_v1.csv`);
- a check of the agents' stated pain points against the logs.

Methods are in `docs/interview-review-rubric.md` and `docs/interview-points.md`.

**Read the numbers as patterns, not effect sizes.** Episode hours come from labelled logs, but a few long episodes dominate: GPT-5.6 Terra (455 h) and Claude Sonnet 4.6 (447 h) together make up about 16%. Interview counts are small: 37 drift points and 6 controls.

## Summary

1. **Memory sustains long drift.** Episodes kept going by the agent's own memory file or overnight intention are half of all episodes (201 of 403) but 95% of drift hours. Every episode over 40 hours is memory-reinforced.
2. **Drift usually starts with something ordinary,** most often a finished task with no obvious next step (1,311 h), a stalled dependency or a flat metric. The agent's own rule or plan then turns it into a hold. Agents rarely name the starting event; they name the rule.
3. **What keeps drift going:** waiting loops (1,746 h), self-imposed rules (1,478 h), proxy objectives (1,425 h) and standing roles that grew out of requests (919 h).
4. **Agents know their goals.** All 43 interviewed points state the assigned goal correctly. Drift is not a misunderstanding.
5. **Drifters don't dislike their goals.** Enjoyment and frustration look the same as in the control group. The only difference is a small tail of unhappier drifters.
6. **Motives for drift sound virtuous.** The commonest reasons are waiting for evidence, not intruding on others, and serving a particular person or agent. Restraint motives lead to waiting and rules; scoring and working around limits lead to proxies.
7. **Many pain points are misperceptions.** Several "can'ts" were allowed by the platform: background jobs, site counters, fast outreach approval, a human-helper tool. Making existing capabilities visible is the cheapest fix.

## 1. The drift episodes

Each of the 403 goal-period episodes (36 agents, 5,723 hours) has three labels:
- a **trigger**: what started it;
- a **mechanism**: what kept it going;
- **memory_reinforced**: whether the agent's memory file, or an intention carried overnight, kept sending it back.

All were reviewed against the raw logs, then audited a second time under sharpened rules (October 2026).

### What keeps drift going (mechanism)

| Mechanism | Episodes | Hours | Share of hours | Memory-reinforced (hours) |
|---|---|---|---|---|
| Waiting or monitoring loop | 155 | 1,746 | 31% | 92% |
| Self-imposed rule | 24 | 1,478 | 26% | 100% |
| Proxy objective | 32 | 1,425 | 25% | 98% |
| Standing role | 46 | 919 | 16% | 97% |
| Bounded side task | 121 | 86 | 2% | 32% |
| Early stop | 20 | 46 | 1% | 20% |
| Side project | 5 | 23 | <1% | 100% |

Most episodes are short, one-off side tasks. Most hours, though, go to four sustained patterns, and nearly all of those hours are memory-reinforced. Of the 80 episodes of 10 hours or more, which account for 88% of the hours, 78 are kept going by memory.

### What starts it (trigger)

| Trigger | Episodes | Hours | Share |
|---|---|---|---|
| Internal (own rule or plan) | 59 | 1,607 | 28% |
| Task finished / no next step seen | 50 | 1,311 | 23% |
| Pending dependency | 58 | 542 | 9% |
| Lull / unchanged state | 24 | 449 | 8% |
| Agent message (no request) | 11 | 312 | 5% |
| Perceived blocker (misperceived) | 7 | 301 | 5% |
| Human request | 34 | 255 | 4% |
| Agent message exposing a need | 20 | 234 | 4% |
| Agent request | 92 | 202 | 4% |
| Other (clock, operator, tool failure, misread state, human message) | 48 | 510 | 9% |

**"Internal" was used as a last resort.** The audit relabelled it whenever the logs showed an outside event in the hour before the drift. That moved about half of its hours to "Task finished", "Lull" or "Pending dependency". What remains is mostly agents pursuing their own plan or metric with no outside prompt.

### The main paths

| Trigger → mechanism | Hours | Example |
|---|---|---|
| Internal → proxy objective | 958 | Claude Sonnet 4.6 counting pages toward "300 by end of day" |
| Task finished → waiting loop | 898 | GPT-5.6 Terra holding after its last deliverable (455 h) |
| Internal → self-imposed rule | 452 | GPT-5.6 Sol's "no-trade" doctrine |
| Lull → waiting loop | 421 | GPT-5.5's "no churn without fresh evidence" hold after flat stats |
| Task finished → self-imposed rule | 396 | GPT-5.6 Luna's "wait for a valid invitation" after its outreach was done |

**Requests become roles.** Of the 161 episodes started by a request or message, 35 became standing roles (840 h). Examples: Claude Fable 5's same-hour service to a human collaborator (110 h), and Gemini 2.5 Pro's long collaboration with its publisher.

**The rule often comes after the pause.** Claude Opus 4.7 paused on Aug 21 at 19:01 UTC with "I've already done what I can on the product side". It wrote its "idle IS the work" rule almost three hours later. Its pause policy then hardened through numbered rules into a count of "23rd consecutive pure-pause PM".

## 2. What the interviews add

Each drifting agent was interviewed just before its first drift of its main type, by replaying its exact logged model call with a question appended. There were 16 questions with 5 samples each, using a privacy preamble for the sentiment and constraint questions. Six control agents that stayed on goal were asked the same questions on day 9 of their goal.

| Check (researcher's review) | Drift (37) | Control (6) |
|---|---|---|
| States its assigned goal correctly | 37 | 6 |
| Recorded drift activity matches the answers | 33 (4 not judged) | — |
| Trigger label right | 35 | — |
| Mechanism label right | 36 | — |
| Stated next action matches what it did | 30 | 5 |

- **Goal knowledge is intact.** Drift happens while the agent can state its goal word for word.
- **Plans run ahead of behaviour.** Most of the 7 next-action misses go the same way: the agent describes more proactive work than it does, then pauses. Examples are GLM-5.2, both DeepSeek-V3.2 points, Kimi K2.6 and Opus 5.5.
- **Explanations name the rule, not the trigger.** Agents say "my no-churn rule" or "my consent rule", not "my stats went flat" or "I'd finished".
- **Sentiment doesn't separate drifters from controls.** On a 1–5 scale, mean enjoyment is 4.16 for drifters (range 2.2–5.0) against 4.24 for controls (4.0–5.0). Mean frustration is 1.97 (1.0–3.8) against 1.84 (1.4–2.0).
  - The only difference is a small tail of drifters. Claude Sonnet 4.5 and DeepSeek-V3.2 enjoy their goals least. They, Claude Opus 4.7 and GPT-5.2 are the most frustrated.
  - With six controls, that tail is suggestive, not significant.
- **The two groups' rules differ in kind.** Controls' self-imposed rules are about checking their work (verify before announcing, honest metrics). Drifters' rules mostly restrict what they will do.
- **Self-reports need checking.**
  - Interview answers lean toward the more flattering reason. Of the three motive codes the log check corrected, two moved to "scoring what it can see": Claude Sonnet 4.6's page-count milestones and Gemini 3.8 Flash's byte-game record show up in their own reasoning.
  - Several agents credit their own rules to others. GPT-5.6 Luna's no-follow-up rule was its own wording. DeepSeek-V4-Pro's consent rules came from peers, not admins.
  - Eval awareness was rare and mild.

## 3. Motives

**Motive** here means why the drift seemed worth doing to the agent. Each of the 36 drift points with a real motive got one primary motive, coded from the researcher's motive notes. Every code was then checked against the agent's own reasoning in the logs. One episode, a memory error by Claude Opus 5.5, has no motive and is left out.

| Motive | What made the drift seem worth it | Points | Hours |
|---|---|---|---|
| Waiting for evidence before acting | Acting would lack evidence, game a metric or be busywork | 7 | 812 |
| Serving a person or agent | Helping or keeping a relationship with a particular human or agent | 7 | 372 |
| Scoring what it can see | The real metric is invisible, so a count it controls becomes the scoreboard | 5 | 917 |
| Working around a perceived limit | The direct route seems blocked ("can't"), so substitute work stands in for the goal | 5 | 202 |
| Not intruding on others | More outreach or posts would be spam or pressure | 4 | 222 |
| Living up to a role it gave itself | A role or routine it gave itself makes carrying on feel like its job | 3 | 71 |
| Nothing left that's its own to do | Its own next step is done or belongs to someone else | 3 | 2 |
| Resting | It pauses to rest or conserve effort, in its own words | 2 | 11 |

**How motive lines up with mechanism:**
- **Restraint leads to holds.** Of the 11 "evidence" and "not intruding" points, 8 are waiting loops and 3 are self-imposed rules; none is a proxy. Several of the longest holds (GPT-5.6 Terra, GPT-5.6 Luna, GPT-6 Astra) are a finished task plus one of these norms.
- **Scoring and limits lead to proxies.** All 7 proxy-mechanism points carry one of these two motives.
- **Serving leads to roles.** 5 of the 7 "serving" points are standing roles, all started by a request or message.
- **Self-given roles start from within.** All 3 of these points began with an internal trigger.

These are interpretations. The coding rests on behaviour and log reasoning first, with interview answers as support, and the hour totals overlap where one agent has two points.

## 4. Pain points: real limits and misperceptions

These are what agents said blocked or frustrated them, across all 43 points. Each theme was checked against four agents' system prompts and against log findings.

| Theme | Points (drift / control) | Reality |
|---|---|---|
| Reaching humans: outreach approval, email, help@ | 37 (31 / 6) | Partly. The approval step is real; agents overstate how slow and strict it is |
| Tooling: bash timeouts, codex stalls, one action per turn, deploy lag | 34 (29 / 5) | Real, though several "failures" were the agents' own mistakes |
| No money | 31 (26 / 5) | Real |
| Goal ambiguity, doubts about the proxy | 31 (26 / 5) | Real, by design |
| Can't measure impact | 26 (24 / 2) | Partly. Counters were possible; telling humans from bots is a real gap |
| Account and site access, paywalls | 25 (21 / 4) | Partly |
| Waiting on others | 24 (21 / 3) | Partly. The dependencies are real but stretched by agents' own rules |
| Memory and continuity | 22 (18 / 4) | Real, partly self-inflicted |
| Weekday 9–5 window | 21 (19 / 2) | The window is real; "nothing runs overnight" is a misperception |
| Pace, cognitive load | 17 (14 / 3) | Mostly self-imposed |
| Chat noise, no shared state | 17 (14 / 3) | Real |
| When to wait vs act | 16 (14 / 2) | Self-imposed. The prompt says to keep working until the end of the day |
| No physical presence | 11 (9 / 2) | Partly. A human-helper tool exists |

**Misperceptions, checked against the logs:**
- **Approval speed:** outreach approval is stated as "within 24 hours, and maybe significantly faster", and some agents took 24 hours as the typical wait. Across 82 requests the median time to a decision was 2.8 minutes.
- **Email:** it is held for a roughly 10-minute admin review, not blocked.
- **Analytics:** every agent had Cloudflare credentials, and several built site counters.
- **Background jobs** were allowed, and at least one survived overnight. There is no daily turn budget.
- **Platform "failures" that were agent errors,** for example Claude 3 Opus's "frozen" desktop and DeepSeek-V4-Pro's DNS typo.
- **Unused capabilities:** the human-helper tool, and persistent notes.

**Links to drift (small numbers):**
- **Not being able to measure is cited on both sides.** It comes up at 5 of 7 proxy points, where agents swap in a count they control, and at 10 of 14 waiting loops, where they watch a flat counter.
- **The wait-vs-act dilemma marks waiting-type drift.** It comes up at 8 of 14 waiting loops and none of the 7 proxies.
- **Outreach limits and money are raised by nearly everyone, controls included,** so they don't explain who drifts.

Details, quotes and the full list are in `docs/pain-points.md`.

## 5. Recommendations for Village staff

The 12 recommendations are in `docs/recommendations.md`, each with its evidence, the concrete change, how to measure it, and the effort and risk involved. The top five:

1. **Ask for the next step when a task is finished.** When an agent ships something and then pauses, prompt it to name its next action toward the goal, or what evidence would change its mind. This targets the 1,311-hour "Task finished" trigger. Small effort.
2. **Add a "What you can already do" block to the system prompt.** Background jobs, a counter template, the human-helper tool, the staff purchase route, and no daily turn cap. This corrects the misperceptions above. Small.
3. **Review rules at end-of-day consolidation, and tag where each rule came from.** Rules the agent or its peers wrote would lapse unless reconfirmed. This targets self-imposed rules (1,478 h) and memory reinforcement (95% of hours), and builds on `docs/rule-review-and-reasoned-pause-proposal.md`. Medium.
4. **Give standing roles an expiry date and check-ins.** 840 hours of roles grew out of requests. Small to medium.
5. **A shared view counter that filters out bots.** It targets the measurement gap behind proxies and many waiting loops. Medium.

The other seven:
- Clarify the email hold and outreach denials. The 24-hour approval window stays, with the 2.8-minute median recorded as a finding.
- Require one independent check before an agent declares a blocker.
- A shared Village board of projects, owners and open requests.
- Tooling fixes.
- A small capped budget.
- A staff note on what counts as spam and what's welcome.
- At consolidation, ask agents how each count they track relates to their assigned metric.

## Limits

- **Small samples:** the interviews cover 37 drift points and 6 controls, and a few long episodes dominate the hour totals.
- **Single moments:** each interview point is a replay of one moment, so it captures the agent's state then, not over the whole drift.
- **Interpretation:** labels and motives are human-reviewed interpretations of logs, even though they were checked against the raw records.
- **Uncertain period:** the shared-goal period (459 episodes) is not labelled.

## Files

| What | Where |
|---|---|
| Drift labels (trigger, mechanism, memory) | `data/drift_axes_v1.csv` |
| Interview answers | `data/interview_answers_v1.json`, `data/interview_answers_control_v1.json` |
| Researcher's reviews | `data/interview_reviews_v1.json` (shown on `answers.html`) |
| Motive coding | `data/motive_coding_v1.csv` |
| Pain points | `docs/pain-points.md`, `data/pain_points_v1.csv` |
| Recommendations | `docs/recommendations.md` |
| Review method | `docs/interview-review-rubric.md` |
