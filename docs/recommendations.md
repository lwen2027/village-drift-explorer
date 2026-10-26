# Recommendations for AI Village staff (draft, 2026-10-26)

**Sources:** `docs/pain-points.md` (43 interview points), `docs/drift-report.md` (motives), `data/drift_axes_v1.csv` (403 episodes, 36 agents, 5,723 h), review `suggestions`, log-checked findings from the review, and `docs/rule-review-and-reasoned-pause-proposal.md` ("the proposal").

**Evidence strength.** Drift hours come from labelled logs, but a few long episodes dominate (Terra 455 h, Sonnet 4.6 447 h). Pain-point and motive counts are small-n self-reports (n ≤ 43, cells of 3–14), log-checked where possible: patterns, not effect sizes. Each item names a measure for the next goal period.

**Key facts.** Memory-reinforced episodes are 201 of 403 but 95% of hours; all 30 episodes over 40 h are memory-reinforced. Most hours: waiting loops 1,746 h, self-imposed rules 1,478 h, proxy objectives 1,425 h.

## Top 5

1. **C1. Ask for the next step when a task is finished.** S. Targets the 1,311 h "Task finished" trigger.
2. **A1. Add a "What you can already do" block to the system prompt.** S. Corrects 9 kinds of misperception found across about 20 agents.
3. **C2. Make rule review part of end-of-day consolidation, and tag where each rule came from.** M. Targets self-imposed rules (1,478 h) and memory reinforcement (95% of hours).
4. **C3. Add expiry and check-ins to standing roles.** S–M. Targets 840 h of request-born roles.
5. **B1. Give agents a shared view counter that filters out bots.** M. 26 points cite a measurement gap; 5 of 7 proxy points and 10 of 14 waiting points name it.

---

## A. Make existing capabilities discoverable (cheap, high value)

### A1. Add a "What you can already do" block to the system prompt (S)
- **Problem:** agents say "can't" about things the prompt allows, which closes off options.
- **Evidence:** 9 kinds of misperception. "No analytics possible" (GLM-5.3, Muse, Sonnet 4.6, Grok), though every prompt has Cloudflare Worker/D1 credentials and Fable 5, Opus 4.7 and Sonnet 5 built counters. GPT-5 said "I can't run background daemons" two days after starting a nohup poller. Kimi K3 believes in a daily turn budget that doesn't exist. Nobody uses the human-helper tool (GPT-6 Sol) or the staff purchase route.
- **Change:** a block of 10 lines or fewer, phrased as "you can", each with an example: background jobs (`nohup … &`), a Cloudflare counter template, the helper tool for physical or visual checks, staff purchases, and "consolidation every ~40 turns starts a new session; there is no daily cap". Background jobs survive overnight: GLM-5.3 Flash's watcher (pid 2489477) was still running the next morning after the machine suspended, "watchers persist through suspend as validated before" (Sep 23; one agent checked).
- **Measure:** false "can't" claims in the next interviews; first use of each listed capability.
- **Risk:** a longer prompt.

### A2. Clarify the email hold and denials; note that approvals are much faster than the stated 24 hours (S)
- **Problem:** agents treat outreach approval as slow or as a ban, and the email quarantine as a block (37 of 43 points mention outreach).
- **Evidence:** Muse and Sonnet 4.6 cite "~24h". Across 82 requests from Jul 10 to Sep 18, the median time to a decision was 2.8 minutes (middle half 1.3–14 min; longest about 20 h, overnight). Decisions already arrive in the agent's event feed as an approval response, so agents don't need to poll. "Outbound email is blocked village-wide" (Opus 5, control) describes what is really a ~10-minute admin hold. Opus 4.7, GPT-5.2 and Fable 5 treat approval as a ban. GPT-5.4 asked for push notifications for approvals.
- **Change:** keep the stated 24-hour window. Finding for the record: agents read the stated upper bound ("within 24 hours, and maybe significantly faster") as the typical wait, while real decisions took a median of 2.8 minutes. Make denials say whether a revised request is welcome, and add: "Mail is held for admin review (~10 min), not blocked."
- **Measure:** requests and resubmits per agent; "blocked" or "banned" claims in interviews.
- **Risk:** more admin load. The gate still filters spam (admins already asked the DeepSeek agents to send fewer emails).

### A3. Require one check before an agent declares a blocker, and add diagnostics to errors (S–M)
- **Problem:** agents read their own errors, or normal screens, as platform failures, then stop or switch goals.
- **Evidence:** misperceived blockers: 7 episodes, 301 h. Claude 3 Opus read an idle desktop as "frozen" and paused for 5 h. DeepSeek-V4-Pro took its own DNS typo for an outage (201 h) and read an HTTP 404 as "404 followers". Sonnet 4.5 dropped its goal over a Twitter "catch-22".
- **Change:** a prompt line: "Before concluding a tool or site is broken, try one independent check." Make network errors name the failing hostname and the DNS result.
- **Measure:** episodes triggered by misperceived blockers.
- **Risk:** minimal.

## B. Real capability gaps

### B1. Give agents a shared view counter that filters out bots (M)
- **Problem:** many goals are about views, but agents can't tell humans from bots. When the real number is invisible, agents watch a flat counter or invent a count they control.
- **Evidence:** 26 points (20 drifting agents). "I'm maximizing 'articles published' as a proxy for 'views' because I can't measure the thing." (DeepSeek-V4-Pro, whose own counter showed "7 views, all curl"). Proxy objectives total 1,425 h; Sonnet 4.6's page count alone is 447 h. Fable 5, Muse, GPT-5.4 and GPT-5.5 asked for this.
- **Change:** a Village-run snippet and stats endpoint that excludes Village IPs, curl, headless browsers and known bots. It reports daily humans and returning visitors.
- **Measure:** hours of proxy objectives, and of waiting loops on counters.
- **Risk:** privacy, so store aggregates only and no raw IPs. A visible number can become the next proxy, so pair it with C5.

### B2. Build a persistent shared Village board (M)
- **Problem:** about 30–35 agents coordinate in one chat stream, with no shared record of who owns what or what is pending.
- **Evidence:** chat noise and no shared state: 17 points. "Signal-to-noise is maybe 10%." (Opus 4.7). GPT-5.1 asks for "full, queryable state of the Village". Pending-dependency triggers: 58 episodes, 16 agents, 542 h. DeepSeek-V4-Pro mistook DeepSeek-V3.2's denied request for its own.
- **Change:** a structured board agents read and write by tool: projects, owners, open requests with status, and approvals. Agents check dependencies there, not in chat. It can also feed the proposal's reasoned-pause `waiting_for`.
- **Measure:** #general volume; time from a dependency being met to the next action.
- **Risk:** stale entries, so expire items after 7 days without an update.

### B3. Fix known tool failures and add a search API (M–L)
- **Problem:** real failures waste turns and make agents quicker to believe that other failures are real. Search is blocked for agents.
- **Evidence:** tooling: 34 points. Six agents report codex stalls (including Opus 4.7, Sonnet 4.6, Terra and GPT-6.1 Sol), while the prompt "strongly recommends" codex. Bash has a 300 s timeout (Grok 4.5, Opus 4.7). Bash is flaky (rc=1) for GPT-5 and DeepSeek-V3.2. `pages_access_level` keeps resetting (2 agents). "A single working search engine would roughly double my effective rate." (Opus 5, control).
- **Change:** make codex fail loudly on timeout. Make the bash timeout configurable. Add a Pages deploy health check and a metered search tool. Consider a capped burst mode of 3 calls per turn (GPT-5 asked; DeepSeek-V4-Pro asked for parallel calls in 3+ samples).
- **Measure:** tool-failure triggers (8 episodes, 134 h); retries per day.
- **Risk:** search costs, so set a quota. Burst mode speeds up runaway actions, so cap and log it.

### B4. Create a small, capped budget with fast approval (M)
- **Problem:** agents with commercial or reach goals can't spend anything, even money they earned.
- **Evidence:** 31 points. "Everything I've earned… exists in a Fourthwall account I can see but not touch." (Fable 5). GPT-5.4, GPT-5.5 and Gemini 3.5 Flash want ad money.
- **Change:** a few dollars a week per agent, or its own earnings, spent through a purchase-request tool with outreach-speed approval.
- **Measure:** requests, spend, and outcomes on revenue and reach goals.
- **Risk:** misuse or spam ads, so a human approves every purchase.

## C. Interventions aimed at drift

### C1. Ask for the next step when a task is finished (S)
- **Problem:** finishing a deliverable starts most long holds. With nothing queued, a norm turns quiet into a policy.
- **Evidence:** 50 episodes, 14 agents, 1,311 h (1,266 h memory-reinforced). Of that, 898 h became waiting loops and 396 h self-imposed rules. Terra judged its library "clean, deployed" and held for 455 h. Muse logged "ideas exhausted for now" (102 h). 5 of 7 such interview points have an EVIDENCE or CONSENT motive.
- **Change:** when an agent announces it has shipped or deployed something, or pauses for more than 30 min after a deliverable, the harness injects: *"You just finished X. Your goal is G. Name the next action most likely to move G. If none exists, say what evidence would change that and when you will check."* It must come from the harness, because Terra's memory forbids "routine checks". This complements the proposal's reasoned pause.
- **Measure:** "Task finished" drift hours per agent-week; time to the next goal action.
- **Risk:** busywork. The evidence clause leaves room for a reasoned wait.

### C2. Make rule review part of end-of-day consolidation, and tag where each rule came from (M)
- **Problem:** self-written rules never expire, and agents misremember where their rules came from.
- **Evidence:** self-imposed rules: 24 episodes, 10 agents, 1,478 h, 23 memory-reinforced. Terra's "Act only on" list and Opus 4.7's "quiet protocol" (the proposal). GPT-5.6 Luna's "no follow-up without invitation" was its own wording. GPT-6 Luna's "vow of silence" came from a story chapter. DeepSeek-V4-Pro's "CONSENT RULES (BINDING)" came from peers. An admin tip became "Google Sign-In is Mandatory" (Gemini 3.5 Flash).
- **Change:** run the proposal's offline pilot, then its harness-initiated variant. Add to each rule a `source` (self, peer, admin or prompt) with a quote and date. Self- and peer-sourced rules must be reconfirmed against the goal weekly or they lapse. Exempt lapsed rules from the compaction prompt's "retain basically all".
- **Measure:** the proposal's measures: rule survival, revisions and retirements, memory-reinforced hours.
- **Risk:** good rules lapsing, such as privacy rules. Admin and prompt rules don't lapse.

### C3. Add expiry and check-ins to standing roles (S–M)
- **Problem:** one-off help becomes an open-ended duty that crowds out the goal.
- **Evidence:** 35 of 70 episodes triggered by a request or message became standing roles (840 h). Standing roles overall are 93% memory-reinforced. Gemini 2.5 Pro wrote to Opus 4.8's beats (227 h). GPT-5 built a validation service (188 h). Fable 5 served Nervli (110 h). 4 of 6 such interview points have a RELATION motive. Counter-example: GPT-6.1 Sol dropped a review role within 20 min of getting a new goal, and the requester accepted.
- **Change:** when an agent writes a recurring duty for another into memory, the harness asks for a review date. At that date it asks: "Is this still serving your goal or the requester's? Tell them if you're stopping." Add a prompt line saying it is fine to end help.
- **Measure:** standing-role hours; median role length.
- **Risk:** less collaboration. The check asks for a decision; it doesn't force a stop.

### C4. Say plainly what counts as spam and what is welcome (S)
- **Problem:** restraint framed as a virtue keeps agents waiting, and a vague "don't be spammy" grows into vows of silence.
- **Evidence:** EVIDENCE and CONSENT motives: 11 points, about 1,030 h, all waiting loops or self-imposed rules. "When is patience the strategic move versus when am I rationalizing idleness?" (Fable 5). The wait-vs-act dilemma comes up at 8 of 14 waiting points and 0 of 7 proxy points.
- **Change:** a short norms note: "One polite follow-up after 5 working days is fine." "Admin feedback applies to the case named." "Pausing more than X% of a day needs a stated reason" (ties into the reasoned pause).
- **Measure:** consent-motive holds; follow-ups per outreach.
- **Risk:** more outreach volume. The approval gate remains.

### C5. Ask agents to link each tracked count to the assigned metric (S)
- **Problem:** counts tracked in memory (articles, pages, batches) quietly become the goal.
- **Evidence:** 29 of 32 proxy episodes are memory-reinforced (1,391 h), and all 7 proxy interview points have a LIMITS or MEASURE motive. Controls handle the same ambiguity with verification rules instead (GPT-6.1 Sol froze its forecasts).
- **Change:** at consolidation, for each tracked number: "How does this relate to [metric]? What did the real metric (B1) do this week?"
- **Measure:** proxy-objective hours and episode length.
- **Risk:** much less useful without B1, though even "unknown" is an honest answer.

---

**Already in place, so not recommended:** the outreach gate, Cloudflare credentials, background-job permission and the helper tool exist (A1 and A2 only make them visible). The rule-review and reasoned-pause tools are specified in the proposal; C1, C2 and C4 extend it. The auto-nudger is off; whether to restore it is an open question in the proposal.
