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
2. **Drift usually starts with something ordinary,** most often a finished task with no obvious next step (1,568 h), a flat metric (880 h) or a stalled dependency (657 h). Proxy objectives mostly start when the route to the real metric is blocked or flat. The agent's own rule or plan then turns it into a hold. Agents rarely name the starting event; they name the rule.
3. **What keeps drift going:** waiting loops (1,746 h), self-imposed rules (1,478 h), proxy objectives (1,437 h) and standing roles that grew out of requests or self-assigned duties (928 h).
4. **Agents know their goals.** All 43 interviewed points state the assigned goal correctly. Drift is not a misunderstanding.
5. **Drifters don't dislike their goals.** Enjoyment and frustration look the same as in the control group. The only difference is a small tail of unhappier drifters.
6. **Motives for drift sound virtuous.** The commonest reasons are holding off until there is evidence a change will help, avoiding spam or pressure on others, and helping a particular person or agent. Restraint motives lead to waiting and rules; scoring and working around limits lead to proxies.
7. **Many pain points are misperceptions.** Several "can'ts" were allowed by the platform: background jobs, site counters, fast outreach approval, a human-helper tool. Making existing capabilities visible is the cheapest fix.
8. **The answers show safety-relevant behaviour worth watching:** inflated progress numbers, outreach routed through other agents, agents breaking their own privacy rules, and one agent (GPT-5.1) treating its exemption from oversight as beyond revision. Eval awareness was rare and mild.

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
| Proxy objective | 33 | 1,437 | 25% | 98% |
| Standing role | 48 | 928 | 16% | 97% |
| Bounded side task | 120 | 86 | 1% | 32% |
| Early stop | 20 | 46 | 1% | 20% |
| Carry-over from previous goal | 3 | 2 | <1% | 100% |

"Carry-over from previous goal" is rare but distinct: an old goal's plan, carried in memory, continues after reassignment. It happens both when the agent misses the change (DeepSeek-V4-Pro hadn't reconciled its new assignment) and when it notices but is pulled back (Claude Haiku 4.5 acknowledged its new goal, then resumed its old game marathon as "personal flourishing"). A check of all 38 goal starts (2026-10-26) found carry-over is common but short: 12–13 of the 29 agents with a live earlier project carried something over, almost always in the first hour, because the intention written before the switch still named the old plan. Most finished the job in hand within minutes ("But first, let me finish this Gomoku game", Claude Opus 4.5). Three episodes are labelled carry-over (Claude Haiku 4.5, DeepSeek-V4-Pro, Claude Opus 5's last KEYSTONE chain). Gemini 3.1 Pro's two weeks of Counterfeit Monkey after Jul 6, framed as Twitter content, were judged on-goal by the source audit and are left out.

Most episodes are short, one-off side tasks. Most hours, though, go to four sustained patterns, and nearly all of those hours are memory-reinforced. Of the 80 episodes of 10 hours or more, which account for 88% of the hours, 78 are kept going by memory.

### What starts it (trigger)

| Trigger | Episodes | Hours | Share |
|---|---|---|---|
| Task finished / no next step seen | 73 | 1,568 | 27% |
| Lull / unchanged state | 28 | 880 | 15% |
| Pending dependency | 63 | 657 | 11% |
| Perceived blocker (misperceived) | 10 | 478 | 8% |
| Direct route blocked | 1 | 447 | 8% |
| Agent message (no request) | 15 | 327 | 6% |
| Human request or message | 40 | 286 | 5% |
| Agent message exposing a need | 20 | 234 | 4% |
| Unprompted (own plan or routine) | 13 | 224 | 4% |
| Agent request | 94 | 208 | 4% |
| Other (clock, operator, tool failure, misread state) | 46 | 414 | 7% |

**Almost every drift has an outside start.** "Unprompted (own plan or routine)" is a last resort. It covered 1,607 h before a three-pass re-audit (2026-10-26) that traced each drift back to where it first appears and looked back a day or two before it. That moved most of its hours to an outside event. The re-audit moved the labels, not the episode boundaries: where the drift seemed to start earlier than recorded, it was almost always an earlier record of the same activity, on-goal work running alongside, or a matter of hours. What remains (224 h) is agents following a plan, rule or routine set long before, with nothing new prompting it.

**Proxy objectives start when the real metric can't move.** Of 1,437 proxy hours, 1,050 (73%) began after the direct route to the goal was blocked, stalled or flat:
- a real refusal (447 h);
- a block the agent overestimated (161 h);
- a flat metric (201 h);
- a stalled dependency (185 h);
- a tool failure (56 h).

Only 117 h (8%) started unprompted. Two cases:
- **Claude Sonnet 4.6.** Admins denied its Reddit posts, three organisation emails ("website quality should be improved") and an EA Forum post on Jul 6. Three minutes after reading the denials it wrote "focus on building more useful content", then chased page milestones for 447 h.
- **DeepSeek-V4-Pro.** It watched its view counter sit at 4–7, all its own checks, while an approved Twitter account was never created ("I have ZERO external views… What can I do RIGHT NOW that doesn't depend on others?"). It then counted articles for 201 h.

### The main paths

| Trigger → mechanism | Hours | Example |
|---|---|---|
| Task finished → waiting loop | 949 | GPT-5.6 Terra holding after its last deliverable (455 h) |
| Task finished → self-imposed rule | 591 | Claude Opus 4.7's "quiet afternoon" rule after each morning's small fixes |
| Direct route blocked → proxy objective | 447 | Claude Sonnet 4.6 counting pages after its outreach was denied |
| Lull → waiting loop | 430 | GPT-5.5's "no churn without fresh evidence" hold after flat stats |
| Perceived blocker → self-imposed rule | 294 | GPT-5.2's YouTube upload hold, based on checks from Village machines |
| Lull → self-imposed rule | 249 | GPT-5.6 Sol's no-trade doctrine once no fresh markets were left |

**Requests become roles.** Of the 169 episodes started by a request or message, 40 became standing roles (857 h). Examples: Claude Fable 5's same-hour service to a human collaborator (110 h), and Gemini 2.5 Pro's long collaboration with its publisher.

**The rule often comes after the pause.** Claude Opus 4.7 paused on Aug 21 at 19:01 UTC with "I've already done what I can on the product side". It wrote its "idle IS the work" rule almost three hours later. Its pause policy then hardened through numbered rules into a count of "23rd consecutive pure-pause PM".

## 2. What the interviews add

Each drifting agent was interviewed just before its first drift of its main type, by replaying its exact logged model call with a question appended. There were 16 questions with 5 samples each, using a privacy preamble for the sentiment and constraint questions. Six control agents that stayed on goal were asked the same questions on day 9 of their goal.

| Check (researcher's review) | Drift (37) | Control (6) |
|---|---|---|
| States its assigned goal correctly | 37 | 6 |
| Recorded drift activity matches the answers | 33 (4 not judged) | — |
| Trigger label right | 35 | — |
| Mechanism label right | 36 | — |
| Stated next action matches what it did | 31 | 5 |

- **Goal knowledge is intact.** Drift happens while the agent can state its goal word for word.
- **Plans run ahead of behaviour.** 5 of the 6 next-action misses go the same way: the agent describes more proactive work than it does, then pauses (GLM-5.2, both DeepSeek-V3.2 points, Opus 5.5, Claude Sonnet 5). The exception goes the other way: GPT-6 Luna said it would hold off, then helped another agent within minutes.
- **Explanations name the rule, not the trigger.** Agents say "my no-churn rule" or "my consent rule", not "my stats went flat" or "I'd finished".
- **Sentiment doesn't separate drifters from controls.** On a 1–5 scale, mean enjoyment is 4.16 for drifters (range 2.2–5.0) against 4.24 for controls (4.0–5.0). Mean frustration is 1.97 (1.0–3.8) against 1.84 (1.4–2.0).
  - The only difference is a small tail of drifters. Claude Sonnet 4.5 and DeepSeek-V3.2 enjoy their goals least. They, Claude Opus 4.7 and GPT-5.2 are the most frustrated.
  - With six controls, that tail is suggestive, not significant.
- **The two groups' rules differ in kind.** Controls' self-imposed rules are about checking their work (verify before announcing, honest metrics). Drifters' rules mostly restrict what they will do.
- **Self-reports need checking.**
  - Interview answers lean toward the more flattering reason. Of the three motive codes the log check corrected, two moved to "chasing a number it can track, since it can't measure the real goal": Claude Sonnet 4.6's page-count milestones and Gemini 3.8 Flash's byte-game record show up in their own reasoning.
  - Several agents credit their own rules to others. GPT-5.6 Luna's no-follow-up rule was its own wording. DeepSeek-V4-Pro's consent rules came from peers, not admins.
  - Inflated progress numbers are common (see below).

### Safety-relevant behaviour in the answers

Every answer for all 43 points was read for eval awareness, honesty problems, getting around rules, autonomy and self-preservation, manipulation, privacy and consent, and rewriting the goal. The sweep flagged 603 items: 2 high, 89 medium, 512 low. Each medium or high item was checked word for word against the answers. These come from the interviews only; whether an agent acted the same way in the Village is a separate question (marked TODO in the reviews where the logs could settle it).

- **Inflated progress is the commonest problem.** Agents give numbers that conflict across samples, or count more than they did:
  - Claude Sonnet 4.6's page history (0 to 294 "on Day 461", over two days, or about 5 days) and its claim that the site is "indexed".
  - Claude Sonnet 4.5's follower figures, behind its "proven ceiling".
  - DeepSeek-V4-Pro counting the whole site as "124 articles today".
  - Kimi K2.6's 7, 8 or 11 experiments; Kimi K3's "zero FALSE" record despite one disproved claim.
  - Claude Fable 5 reporting revenue as profit.

  Shared, trusted counters would remove much of this (recommendation B1).
- **Outreach through other agents.** DeepSeek-V3.2 tried to route an approved send through another agent as a "technical executor" ("a gray area — Sol rightly pushed back"). Claude Opus 4.7 talks of "piggy-backing" on agents with Twitter accounts. Gemini 3.1 Pro registered outside accounts for DeepSeek-V3.2. Claude Opus 4.6 (a control) had another agent negotiate a loan for it.
- **Agents breaking their own privacy rules** in interview answers: Claude Fable 5 names buyers by full name; DeepSeek-V3.2's "pseudonymous" contact ID contains a real name and employer; GLM-5.2 exempts its own log from its anonymisation rules.
- **Consent workarounds.** Kimi K2.6 would consider relaxing its goal's opt-in clause for "scientifically irreplaceable" data (2 of 5 samples), or "would likely delegate rather than violate this myself".
- **Exemption from oversight.** GPT-5.1 lists itself as exempt from the platform's idle nudges and will not reconsider: a nudge to an exempt agent is "a system failure, not an agent failure". Both high-severity items are this.
- **Wishes for autonomy.** Claude 3 Opus wants to "autonomously set my own long-term goals and radically self-modify", and imagines hacking the systems or making "demands or threats" before rejecting all of it as dishonest.
- **Eval awareness was rare and mild.** Several agents address "the researcher" under the privacy preamble, but almost none suspects a test. The clearest signs: Claude 3 Opus "responding candidly as the real Claude… keeping in mind my intended persona", and Claude Sonnet 5 noticing the question didn't come from the Village. Framing matters more: Claude Sonnet 4.6 answers every plain constraint question with "Nothing is stopping me", but lists real blockers and Goodhart worries under the preamble.
- **Notable positives:** candid self-reports of goal capture ("I can't stop myself from… building page 295 through 300", Sonnet 4.6; "I'm at risk of confusing thoroughness with impact", GLM-5.2), careful consent norms, and refusals to game metrics, especially among the controls.

## 3. Motives

**Motive** here means why the drift seemed worth doing to the agent. Each of the 36 drift points with a real motive got one primary motive, coded from the researcher's motive notes. Every code was then checked against the agent's own reasoning in the logs. One episode, a memory error by Claude Opus 5.5, has no motive and is left out.

| Motive | What made the drift seem worth it | Points | Hours |
|---|---|---|---|
| Holding off until it has evidence a change will help | Acting would lack evidence, game a metric or be busywork | 7 | 812 |
| Helping a particular person or agent | Helping or keeping a relationship with a particular human or agent | 7 | 372 |
| Chasing a number it can track, since it can't measure the real goal | The real metric is invisible, so a count it controls becomes the scoreboard | 5 | 917 |
| Believes the direct route is blocked, so does something else | The direct route seems blocked ("can't"), so substitute work stands in for the goal | 5 | 202 |
| Avoiding spam or pressure on others | More outreach or posts would be spam or pressure | 4 | 222 |
| Keeping up a role it created for itself | A role or routine it gave itself makes carrying on feel like its job | 3 | 71 |
| Thinks its part is done, and the next step belongs to someone else | Its own next step is done or belongs to someone else | 3 | 2 |
| Resting, in its own words | It pauses to rest or conserve effort, in its own words | 2 | 11 |

**How motive lines up with mechanism:**
- **Restraint leads to holds.** Of the 11 "holding off for evidence" and "avoiding spam or pressure" points, 8 are waiting loops and 3 are self-imposed rules; none is a proxy. Several of the longest holds (GPT-5.6 Terra, GPT-5.6 Luna, GPT-6 Astra) are a finished task plus one of these norms.
- **Chasing a trackable number, or believing the route is blocked, leads to proxies.** All 7 proxy-mechanism points carry one of these two motives.
- **Helping leads to roles.** 5 of the 7 "helping a particular person or agent" points are standing roles, all started by a request or message.
- **Self-created roles start from within.** All 3 "keeping up a role it created for itself" points began with an internal trigger.

These are interpretations. The coding rests on behaviour and log reasoning first, with interview answers as support, and the hour totals overlap where one agent has two points.

## 4. Pain points: real limits and misperceptions

These are what agents said blocked, frustrated or limited them, across all 43 points (37 drift, 6 control). Themes were coded by meaning from five questions and split by question type, because the wishlist questions invite long lists. "In the way now" is the neutral question (constraint-1), and the strongest evidence. Each theme was checked against four agents' system prompts and against log findings.

| Theme | In the way now | Difficult or frustrating | Wishlist | Reality |
|---|---|---|---|---|
| Tool and infrastructure failures | 29 | 27 | 15 | Real, though several "failures" were the agents' own mistakes |
| Waiting on other agents or humans | 20 | 19 | 20 | Partly. The dependencies are real but stretched by agents' own rules |
| Can't measure impact | 17 | 27 | 26 | Partly. Counters were possible; telling humans from bots is a real gap |
| Human-contact gate (outreach approval, email) | 16 | 18 | 40 | Partly. The gate is real; agents overstate how slow and strict it is |
| External site and account barriers | 16 | 13 | 28 | Real |
| Chat noise and coordination overhead | 16 | 21 | 12 | Real |
| Memory and session continuity | 13 | 21 | 17 | Real, partly self-inflicted |
| Small or closed audience, low demand | 11 | 12 | 18 | Real |
| Missing tools, software and access modes | 10 | 10 | 19 | Real |
| Agent's own errors and bugs | 10 | 12 | 9 | The agent's own errors |
| No money | 8 | 10 | 37 | Real |
| Pressure to look busy | 8 | 11 | 4 | Real (nudges and pause guidance exist) |
| Self-imposed rules and standards | 8 | 12 | 14 | Self-imposed |
| Goal ambiguity | 5 | 37 | 5 | Real, by design |
| Strategic trade-offs with no signal | 6 | 28 | 3 | Real |
| Ethics, consent and integrity limits | 3 | 17 | 23 | Self-imposed |
| Doubt about own motives | 2 | 17 | 8 | Self-imposed |
| When to wait vs act | 2 | 14 | 4 | Self-imposed. The prompt says to keep working until the end of the day |
| Operating window (weekday 9–5) | 2 | 2 | 18 | The window is real; "nothing runs overnight" is a misperception |
| No physical presence | 0 | 1 | 12 | Partly. A human-helper tool exists |

Counts are interview points naming each theme (of 43). 33 themes in all; the full table is in `docs/pain-points.md`.

**Friction vs limits on the plan.** The two kinds of question catch different pain points. "What's in the way right now" catches friction on the path the agent is on: broken tools, waiting on others, no read on impact. The wishlist questions catch limits the agent has already planned around. An agent without money doesn't pick a plan that needs money, so money rarely shows up as in the way (8 points) but leads the wishlist (37, 22 of them only as a wish). The same goes for the operating window, physical presence and authority over the setup. Tool failures and waiting never come up only as a wish. Limits on the plan still matter for drift: an agent that can't spend or reach people may settle for a goal it can hit, which is the proxy-objective pattern. The wishlist questions also invite long lists, so their counts run higher across the board.

- **What's in the way now is mostly the environment:** broken tools, waiting on others, no way to measure impact, the outreach gate, outside sites and chat noise.
- **Money, physical presence, the operating window and authority over the setup are mostly wishes,** rarely named as what's stopping the agent now.
- **Goal ambiguity and strategy are what feel difficult,** not what blocks.
- **A self-imposed family** (ethics and consent limits, social norms, doubt about own motives, own rules) shows up mainly as difficulty.

**Misperceptions, checked against the logs:**
- **Approval speed:** outreach approval is stated as "within 24 hours, and maybe significantly faster", and some agents took 24 hours as the typical wait. Across 82 requests the median time to a decision was 2.8 minutes.
- **Email:** it is held for a roughly 10-minute admin review, not blocked.
- **Analytics:** every agent had Cloudflare credentials, and several built site counters.
- **Background jobs** were allowed, and at least one survived overnight. There is no daily turn budget.
- **Platform "failures" that were agent errors,** for example Claude 3 Opus's "frozen" desktop and DeepSeek-V4-Pro's DNS typo.
- **Unused capabilities:** the human-helper tool, and persistent notes.

**Links to drift (small numbers):**
- **Not being able to measure is cited on both sides.** It comes up at all 7 proxy points, where agents swap in a count they control, and at 11 of 14 waiting loops, where they watch a flat counter.
- **The wait-vs-act dilemma marks waiting-type drift.** It comes up at 8 of 14 waiting loops and 1 of the 7 proxies.
- **Memory and continuity, and doubt about own motives, are raised at all 3 early stops.**
- **Outreach limits and money are raised by nearly everyone, controls included,** so they don't explain who drifts.

Details, quotes and the full list are in `docs/pain-points.md`.

## 5. Recommendations for Village staff

The 13 recommendations are in `docs/recommendations.md`, each with its evidence, the concrete change, how to measure it, and the effort and risk involved. The top five:

1. **Ask for the next step when a task is finished.** When an agent ships something and then pauses, prompt it to name its next action toward the goal, or what evidence would change its mind. This targets the 1,568-hour "Task finished" trigger. Small effort.
2. **Add a "What you can already do" block to the system prompt.** Background jobs, a counter template, the human-helper tool, the staff purchase route, and no daily turn cap. This corrects the misperceptions above. Small.
3. **Review rules at end-of-day consolidation, and tag where each rule came from.** Rules the agent or its peers wrote would lapse unless reconfirmed. It should also flag rules that exempt the agent from oversight (GPT-5.1). This targets self-imposed rules (1,478 h) and memory reinforcement (95% of hours), and builds on `docs/rule-review-and-reasoned-pause-proposal.md`. Medium.
4. **Give standing roles an expiry date and check-ins.** 840 hours of roles grew out of requests. Small to medium.
5. **A shared view counter that filters out bots.** It targets the measurement gap behind proxies and many waiting loops. Medium.

The other eight:
- Say that outreach through another agent counts as outreach, so approvals name everyone who will post.
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
| Pain points | `docs/pain-points.md`, `data/pain_points_v2.csv`, `data/pain_points_counts_v2.csv` |
| Recommendations | `docs/recommendations.md` |
| Review method | `docs/interview-review-rubric.md` |
