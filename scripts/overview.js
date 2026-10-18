const [response, annotationResponse, sourceResponse] = await Promise.all([
  fetch("./data/second_audit_v2.json", { cache: "no-store" }),
  fetch("./data/manual_review_annotations_v1.json", { cache: "no-store" }),
  fetch("./data/source_records.json", { cache: "no-store" })
]);
if (!response.ok || !annotationResponse.ok || !sourceResponse.ok) {
  throw new Error("Could not load audit data, assessment annotations, and source goal records");
}

const bundle = await response.json();
const committedReviewSeed = await annotationResponse.json();
const sourceRecords = await sourceResponse.json();
const borderlineEpisodeIds = new Set(
  Object.entries(committedReviewSeed.annotations || {})
    .filter(([, annotation]) => annotation?.drift_assessment === "borderline")
    .map(([episodeId]) => episodeId)
);
const metadata = bundle.metadata || {};
const daily = bundle.stage1_daily_verdicts || [];
const windows = bundle.window_verdicts || [];
const episodes = (bundle.confirmed_episodes || []).filter(
  (episode) => !borderlineEpisodeIds.has(episode.episode_id)
);

const number = new Intl.NumberFormat("en-US");
const pct = (part, total) => total ? (100 * part / total).toFixed(1) : "0.0";
const count = (rows, predicate) => rows.filter(predicate).length;
const unique = (rows, field) => new Set(rows.map((row) => row[field]).filter(Boolean));
const escapeHtml = (value) => String(value ?? "").replace(
  /[&<>'"]/g,
  (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]
);
const titlePeriod = (period) => period === "goal_maximization"
  ? "Individual maximization"
  : "Shared Village goals";

function timestampMs(value, dateEdge = "start") {
  if (!value) return null;
  const text = String(value).trim();
  let normalized = /^\d{4}-\d{2}-\d{2}$/.test(text)
    ? `${text}T${dateEdge === "end" ? "23:59:59" : "00:00:00"}Z`
    : text.replace(" ", "T");
  if (!/(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized)) normalized += "Z";
  const parsed = Date.parse(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function episodeOnsetMs(episode) {
  const onset = String(episode.onset || "");
  if (/^\d{4}-\d{2}-\d{2}$/.test(onset) && episode.activity_start_observed_at) {
    return timestampMs(episode.activity_start_observed_at);
  }
  return timestampMs(episode.onset)
    ?? timestampMs(episode.activity_start_observed_at)
    ?? timestampMs(episode.activity_start);
}

function normalizedGoal(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

function groupCount(rows, key) {
  const result = new Map();
  rows.forEach((row) => {
    const value = typeof key === "function" ? key(row) : row[key];
    result.set(value, (result.get(value) || 0) + 1);
  });
  return result;
}

function isoDateLabel(day) {
  if (!day) return "Unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC"
  }).format(new Date(`${day}T00:00:00Z`));
}

function stackBlock(title, totalLabel, segments) {
  const total = segments.reduce((sum, segment) => sum + segment.value, 0);
  const spans = segments.map((segment) =>
    `<span style="width:${pct(segment.value, total)}%;background:${segment.color}"></span>`
  ).join("");
  const legend = segments.map((segment) =>
    `<span><i style="background:${segment.color}"></i>${number.format(segment.value)} ${escapeHtml(segment.label)}</span>`
  ).join("");
  const aria = segments.map((segment) => `${segment.value} ${segment.label}`).join(", ");
  return `
    <div class="quality-block">
      <div class="quality-label"><span>${escapeHtml(title)}</span><span>${escapeHtml(totalLabel)}</span></div>
      <div class="stack" aria-label="${escapeHtml(aria)}">${spans}</div>
      <div class="legend">${legend}</div>
    </div>`;
}

const stage1Drift = count(daily, (row) => row.screening_verdict === "drift");
const stage1NonDrift = count(daily, (row) => row.screening_verdict === "non_drift");
const stage1Undefined = count(daily, (row) => row.screening_verdict === "undefined");
const routedDays = count(daily, (row) =>
  row.screening_verdict === "drift"
  || (row.screening_verdict === "non_drift" && Number(row.confidence) < 0.74)
);
const originalDriftWindows = windows.filter((row) => row.drift_verdict === true);
const originalNoDriftWindows = windows.filter((row) => row.drift_verdict === false);
const days = [...unique(daily, "day")].sort();
const agents = unique(daily, "agent");
const episodeAgents = unique(episodes, "agent");

// Final outcome statistics use one agent-assignment window as their unit. Raw
// Stage 2 windows are retained only as pipeline-volume records because later
// merges, invalidations, and borderline decisions were not back-propagated to
// their original verdicts.
const agentNameById = new Map(
  (sourceRecords.agentRecords || []).map((agent) => [agent.id, agent.name])
);
const goalMaxDays = daily
  .filter((row) => row.period === "goal_maximization" && row.day)
  .map((row) => row.day)
  .sort();
const analysisHorizonMs = timestampMs(goalMaxDays.at(-1), "end");
const goalWindows = [];
const goalMaxWindowByAgent = new Map();

(sourceRecords.agentGoalRecords || []).forEach((goal) => {
  const agent = agentNameById.get(goal.agent_id);
  const startMs = timestampMs(goal.start_time);
  const endMs = Math.min(timestampMs(goal.end_time) ?? analysisHorizonMs, analysisHorizonMs);
  if (!agent || startMs == null || endMs == null || startMs >= endMs) return;
  const existing = goalMaxWindowByAgent.get(agent);
  if (existing) {
    existing.startMs = Math.min(existing.startMs, startMs);
    existing.endMs = Math.max(existing.endMs, endMs);
    existing.goalNames.add(goal.name);
    return;
  }
  const window = {
    key: `goal_maximization\u0000${agent}`,
    period: "goal_maximization",
    agent,
    goalId: goal.id,
    goalNames: new Set([goal.name]),
    startMs,
    endMs,
    episodes: []
  };
  goalMaxWindowByAgent.set(agent, window);
  goalWindows.push(window);
});

const villageGoals = (sourceRecords.villageGoalRecords || [])
  .map((goal) => ({
    ...goal,
    startMs: timestampMs(goal.start_time),
    endMs: timestampMs(goal.end_time),
    normalizedGoal: normalizedGoal(goal.goal)
  }))
  .filter((goal) => goal.startMs != null && goal.endMs != null);
const sharedWindowByKey = new Map();
daily.forEach((row) => {
  if (row.period !== "shared_goal" || !row.agent || !row.day) return;
  const dayMs = timestampMs(row.day);
  const goal = villageGoals.find((candidate) =>
    dayMs >= candidate.startMs && dayMs < candidate.endMs
  );
  if (!goal) return;
  const key = `shared_goal\u0000${row.agent}\u0000${goal.id}`;
  if (sharedWindowByKey.has(key)) return;
  const window = {
    key,
    period: "shared_goal",
    agent: row.agent,
    goalId: goal.id,
    goalNames: new Set([goal.goal]),
    startMs: goal.startMs,
    endMs: goal.endMs,
    episodes: []
  };
  sharedWindowByKey.set(key, window);
  goalWindows.push(window);
});

function goalWindowForEpisode(episode) {
  if (episode.period === "goal_maximization") {
    return goalMaxWindowByAgent.get(episode.agent) || null;
  }
  const onsetMs = episodeOnsetMs(episode);
  const candidates = [...sharedWindowByKey.values()].filter((window) => window.agent === episode.agent);
  const temporal = candidates.find((window) => onsetMs >= window.startMs && onsetMs < window.endMs);
  if (temporal) return temporal;
  const assigned = normalizedGoal(episode.assigned_goal);
  return candidates.find((window) =>
    [...window.goalNames].some((goal) => normalizedGoal(goal) === assigned)
  ) || null;
}

episodes.forEach((episode) => {
  const window = goalWindowForEpisode(episode);
  if (window) window.episodes.push(episode);
});

const confirmedGoalWindows = goalWindows.filter((window) => window.episodes.length > 0);
const noEpisodeGoalWindows = goalWindows.filter((window) => window.episodes.length === 0);

const generatedCandidates = [metadata.generated_at, metadata.episode_corrections_applied_at]
  .map((value) => value ? new Date(value) : null)
  .filter((value) => value && !Number.isNaN(value.getTime()));
const generated = generatedCandidates.sort((left, right) => right - left)[0] || null;
document.querySelector(".snapshot").textContent = generated && !Number.isNaN(generated.getTime())
  ? `SNAPSHOT · ${generated.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric", timeZone: "UTC" }).toUpperCase()} · SECOND AUDIT V2`
  : "SECOND AUDIT V2";

document.querySelector(".scope-grid").innerHTML = `
  <article class="metric-card">
    <p class="micro-label">Analyzed activity</p>
    <span class="metric-value">${number.format(daily.length)}</span>
    <span class="metric-detail">agent-days completed in revised Stage 1</span>
  </article>
  <article class="metric-card">
    <p class="micro-label">Audit date coverage</p>
    <span class="metric-value">${number.format(days.length)}</span>
    <span class="metric-detail">distinct dated Stage 1 blocks (including UTC spillover dates) · ${isoDateLabel(days[0])}–${isoDateLabel(days.at(-1))}</span>
  </article>
  <article class="metric-card">
    <p class="micro-label">Stage 2 coverage</p>
    <span class="metric-value">${number.format(windows.length)}</span>
    <span class="metric-detail">original review windows across ${number.format(agents.size)} observed agents</span>
  </article>
  <article class="metric-card">
    <p class="micro-label">Confirmed findings</p>
    <span class="metric-value">${number.format(episodes.length)}</span>
    <span class="metric-detail">final confirmed records in ${number.format(confirmedGoalWindows.length)} agent–goal windows and ${number.format(episodeAgents.size)} agents</span>
  </article>`;

const driftRate = pct(confirmedGoalWindows.length, goalWindows.length);
document.querySelector("#goal-status-title").textContent = "Which agent–goal windows contain confirmed drift?";
document.querySelector(".goal-status .panel-heading p:last-child").textContent =
  "Each window is one observed agent under one assignment. Outcomes are recomputed from the current final non-borderline episode set.";
const donut = document.querySelector(".donut");
donut.style.background = `conic-gradient(var(--rust) 0 ${driftRate}%, var(--green) ${driftRate}% 100%)`;
donut.setAttribute("aria-label", `Of ${goalWindows.length} observed agent-goal windows, ${confirmedGoalWindows.length} contain confirmed drift and ${noEpisodeGoalWindows.length} do not.`);
document.querySelector(".status-layout > div:last-child").innerHTML = `
  <div class="status-row">
    <i class="status-dot" style="background:var(--rust)"></i>
    <span class="status-name">Contains confirmed drift<span class="status-explain">At least one current non-borderline episode falls inside this agent–goal assignment.</span></span>
    <span class="status-number"><strong>${number.format(confirmedGoalWindows.length)}</strong>${driftRate}%</span>
  </div>
  <div class="status-row">
    <i class="status-dot" style="background:var(--green)"></i>
    <span class="status-name">No confirmed drift episode<span class="status-explain">No current non-borderline episode falls inside this window; this does not prove every action was on-goal.</span></span>
    <span class="status-number"><strong>${number.format(noEpisodeGoalWindows.length)}</strong>${pct(noEpisodeGoalWindows.length, goalWindows.length)}%</span>
  </div>`;

const origins = groupCount(windows, "judgment_origin");
const fullJudgments = (origins.get("codex_manual_full_v2") || 0)
  + (origins.get("opus55_full_v2") || 0)
  + (origins.get("pilot_manual_full_v2") || 0);
const compactJudgments = windows.length - fullJudgments;
document.querySelector(".funnel").innerHTML = `
  <div class="funnel-step" style="--step-color:var(--green)">
    <span class="funnel-value">${number.format(daily.length)}</span><span class="funnel-label">agent-days analyzed</span>
    <span class="funnel-note">${number.format(stage1Drift)} drift · ${number.format(stage1NonDrift)} non-drift · ${number.format(stage1Undefined)} undefined</span>
  </div>
  <div class="funnel-step" style="--step-color:#6c8065">
    <span class="funnel-value">${number.format(routedDays)}</span><span class="funnel-label">agent-days routed</span>
    <span class="funnel-note">Drift screens plus non-drift screens below 0.74 confidence</span>
  </div>
  <div class="funnel-step" style="--step-color:var(--amber)">
    <span class="funnel-value">${number.format(windows.length)}</span><span class="funnel-label">Stage 2 review windows</span>
    <span class="funnel-note">${number.format(fullJudgments)} full judgments · ${number.format(compactJudgments)} compact or bounded judgments · original pipeline units</span>
  </div>
  <div class="funnel-step" style="--step-color:var(--rust)">
    <span class="funnel-value">${number.format(episodes.length)}</span><span class="funnel-label">confirmed episode records</span>
    <span class="funnel-note">Current final non-borderline records after corrections and manual assessment</span>
  </div>`;

document.querySelector("#regimes-title").textContent = "Second-audit results by goal regime";
document.querySelector(".regimes .panel-heading p:last-child").textContent =
  "Episode and agent–goal-window counts are recomputed from the final episode set and source assignment records.";
document.querySelector(".regime-grid").innerHTML = ["goal_maximization", "shared_goal"].map((period) => {
  const periodWindows = goalWindows.filter((row) => row.period === period);
  const positive = periodWindows.filter((row) => row.episodes.length > 0);
  const periodEpisodes = episodes.filter((row) => row.period === period);
  const periodRate = pct(positive.length, periodWindows.length);
  const driftAgents = unique(periodEpisodes, "agent").size;
  const periodDays = daily.filter((row) => row.period === period).map((row) => row.day).filter(Boolean).sort();
  const className = period === "goal_maximization" ? "maximization" : "shared";
  return `
    <article class="regime-card ${className}">
      <div class="regime-kicker"><span>${titlePeriod(period)}</span><span>${isoDateLabel(periodDays[0])}–${isoDateLabel(periodDays.at(-1))}</span></div>
      <h3>${period === "goal_maximization" ? "Agent-specific goals" : "Earlier shared assignments"}</h3>
      <div class="regime-stats">
        <div class="regime-stat"><strong>${number.format(periodEpisodes.length)}</strong>episode records</div>
        <div class="regime-stat"><strong>${number.format(positive.length)} / ${number.format(periodWindows.length)}</strong>agent–goal windows with drift</div>
        <div class="regime-stat"><strong>${periodRate}%</strong>of observed goal windows</div>
      </div>
      <div class="regime-rate" aria-label="${periodRate}% of ${titlePeriod(period)} agent-goal windows contain drift"><span style="width:${periodRate}%"></span></div>
      <p class="regime-footnote">${number.format(driftAgents)} agents have a confirmed episode; ${number.format(periodWindows.length - positive.length)} observed goal windows have no confirmed episode.</p>
    </article>`;
}).join("");

// Time spent drifting (individual maximization). The denominator is clipped to
// each agent's actual assignment timestamp, rather than treating every Stage 1
// date as a full eight-hour day.
(() => {
  const period = "goal_maximization";
  const isWeekday = (day) => { const weekday = new Date(`${day}T12:00:00Z`).getUTCDay(); return weekday >= 1 && weekday <= 5; };
  const pacificHour = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Los_Angeles", hour: "numeric", hourCycle: "h23"
  });
  const activeDates = [...new Set(goalMaxDays)].filter(isWeekday);
  const workingWindows = activeDates.map((day) => {
    const noonUtc = Date.parse(`${day}T12:00:00Z`);
    const offsetHours = 12 - Number(pacificHour.format(new Date(noonUtc)));
    const start = Date.parse(`${day}T00:00:00Z`) + (9 + offsetHours) * 3600000;
    return [start, start + 8 * 3600000];
  });
  const overlapMs = (leftStart, leftEnd, rightStart, rightEnd) =>
    Math.max(0, Math.min(leftEnd, rightEnd) - Math.max(leftStart, rightStart));
  const intervalsByAgent = new Map();
  const episodesByAgent = new Map();
  episodes.filter((row) => row.period === period).forEach((row) => {
    episodesByAgent.set(row.agent, (episodesByAgent.get(row.agent) || 0) + 1);
    const bouts = (row.drift_bouts || []).map(([start, end]) => [timestampMs(start), timestampMs(end)]);
    const onset = episodeOnsetMs(row);
    const intervals = bouts.length ? bouts : (Number.isFinite(onset) && row.duration_seconds ? [[onset, onset + row.duration_seconds * 1000]] : []);
    if (!intervalsByAgent.has(row.agent)) intervalsByAgent.set(row.agent, []);
    intervalsByAgent.get(row.agent).push(...intervals.filter(([start, end]) => Number.isFinite(start) && end > start));
  });
  const mergedIntervals = (intervals, floor, ceiling) => {
    const merged = [];
    intervals
      .map(([start, end]) => [Math.max(start, floor), Math.min(end, ceiling)])
      .filter(([start, end]) => end > start)
      .sort((left, right) => left[0] - right[0])
      .forEach(([start, end]) => {
      const last = merged.at(-1);
      if (last && start <= last[1]) last[1] = Math.max(last[1], end);
      else merged.push([start, end]);
    });
    return merged;
  };
  const rows = [...goalMaxWindowByAgent.values()].map((goalWindow) => {
    const { agent, startMs, endMs } = goalWindow;
    const working = workingWindows.reduce((sum, [start, end]) =>
      sum + overlapMs(start, end, startMs, endMs), 0) / 3600000;
    const driftIntervals = mergedIntervals(intervalsByAgent.get(agent) || [], startMs, endMs);
    const drift = driftIntervals.reduce((sum, [driftStart, driftEnd]) =>
      sum + workingWindows.reduce((daySum, [workStart, workEnd]) =>
        daySum + overlapMs(driftStart, driftEnd, workStart, workEnd), 0), 0) / 3600000;
    return { agent, episodes: episodesByAgent.get(agent) || 0, drift, working, share: working ? drift / working : 0 };
  }).sort((left, right) => right.share - left.share || left.agent.localeCompare(right.agent));
  const totalDrift = rows.reduce((sum, row) => sum + row.drift, 0);
  const totalWorking = rows.reduce((sum, row) => sum + row.working, 0);
  const shares = rows.map((row) => row.share).sort((left, right) => left - right);
  const median = shares.length ? (shares.length % 2 ? shares[(shares.length - 1) / 2] : (shares[shares.length / 2 - 1] + shares[shares.length / 2]) / 2) : 0;
  const hoursText = (value) => `${number.format(Math.round(value))} h`;
  const percent = (value) => `${(100 * value).toFixed(1)}%`;
  document.querySelector("#drift-time-stats").innerHTML = [
    [percent(totalWorking ? totalDrift / totalWorking : 0), "of all agents’ working time spent drifting"],
    [hoursText(totalDrift), `of drift, out of ${hoursText(totalWorking)} of working time`],
    [percent(median), "median share per agent"],
    [`${rows.filter((row) => row.share >= .5).length} / ${rows.length}`, "agents drifting half or more of their working time"]
  ].map(([value, label]) => `<div class="drift-time-stat"><strong>${escapeHtml(value)}</strong><span>${escapeHtml(label)}</span></div>`).join("");
  document.querySelector("#drift-time-table").innerHTML = `
    <div class="drift-time-row is-head" role="row"><span>Agent</span><span class="num">Episodes</span><span class="num">Drift</span><span class="num hide-small">Working</span><span>Share of working time</span><span class="num">Share</span></div>
    ${rows.map((row) => `
      <div class="drift-time-row" role="row">
        <span>${escapeHtml(row.agent)}</span>
        <span class="num">${number.format(row.episodes)}</span>
        <span class="num">${hoursText(row.drift)}</span>
        <span class="num hide-small">${hoursText(row.working)}</span>
        <span class="drift-time-bar" aria-hidden="true"><span style="width:${(100 * row.share).toFixed(1)}%"></span></span>
        <span class="num">${percent(row.share)}</span>
      </div>`).join("")}`;
  document.querySelector("#drift-time-note").textContent =
    "Working time is the exact overlap between each agent’s source-recorded assignment interval and active Village weekdays, 9 AM–5 PM Pacific. Partial first days are clipped at assignment time. Overlapping episodes count once, drift outside working hours is excluded, and borderline episodes are excluded.";
})();

function rankingFor(period, mode) {
  const periodWindows = goalWindows.filter((row) => row.period === period);
  const windowByAgent = new Map();
  periodWindows.forEach((row) => {
    const current = windowByAgent.get(row.agent) || { total: 0, drift: 0 };
    current.total += 1;
    current.drift += row.episodes.length ? 1 : 0;
    windowByAgent.set(row.agent, current);
  });
  const episodeCounts = groupCount(episodes.filter((row) => row.period === period), "agent");
  if (mode === "episodes") {
    return [...episodeCounts].map(([name, value]) => ({ name, value, detail: String(value) }))
      .sort((a, b) => b.value - a.value || a.name.localeCompare(b.name)).slice(0, 8);
  }
  return [...windowByAgent].filter(([, value]) => period !== "shared_goal" || value.total >= 10)
    .map(([name, value]) => ({
      name,
      value: 100 * value.drift / value.total,
      detail: `${value.drift} / ${value.total}`,
      tie: episodeCounts.get(name) || 0,
    }))
    .sort((a, b) => b.value - a.value || b.tie - a.tie || a.name.localeCompare(b.name)).slice(0, 8);
}

function coverageFor(period) {
  const periodWindows = goalWindows.filter((row) => row.period === period);
  const all = unique(periodWindows, "agent");
  const positive = unique(periodWindows.filter((row) => row.episodes.length), "agent");
  return `<strong>${positive.size}</strong> of ${all.size} · ${pct(positive.size, all.size)}%`;
}

const ranking = document.querySelector("#ranking");
const caption = document.querySelector("#ranking-caption");
const coverage = document.querySelector("#ranking-coverage");
const maximizationRankingToggle = document.querySelector("#maximization-ranking-toggle");
const sharedRankingToggle = document.querySelector("#shared-ranking-toggle");
const episodeToggle = document.querySelector("#episodes-toggle");
const rateToggle = document.querySelector("#rate-toggle");
rateToggle.textContent = "Goal-window rate";
let rankingPeriod = "goal_maximization";
let rankingMode = "episodes";

function renderRanking() {
  const data = rankingFor(rankingPeriod, rankingMode);
  const maximum = Math.max(1, ...data.map((row) => row.value));
  ranking.replaceChildren(...data.map((row, index) => {
    const wrapper = document.createElement("div");
    wrapper.className = "rank-row";
    wrapper.innerHTML = `
      <span class="rank-name">${index + 1}. ${escapeHtml(row.name)}</span>
      <div class="rank-track"><div class="rank-fill" style="width:${100 * row.value / maximum}%"></div></div>
      <span class="rank-value" title="${escapeHtml(row.detail)} reviewed windows">${rankingMode === "rate" ? `${row.value.toFixed(1)}%` : number.format(row.value)}</span>`;
    return wrapper;
  }));
  const isMax = rankingPeriod === "goal_maximization";
  const isRate = rankingMode === "rate";
  maximizationRankingToggle.setAttribute("aria-pressed", String(isMax));
  sharedRankingToggle.setAttribute("aria-pressed", String(!isMax));
  episodeToggle.setAttribute("aria-pressed", String(!isRate));
  rateToggle.setAttribute("aria-pressed", String(isRate));
  coverage.innerHTML = coverageFor(rankingPeriod);
  caption.textContent = isRate
    ? `Share of observed ${isMax ? "individual-maximization" : "shared-goal"} assignment windows containing a final non-borderline episode${isMax ? ". Each agent has one maximization assignment window." : "; agents need at least 10 observed goal windows."}`
    : `Confirmed episode records during the ${isMax ? "individual-maximization" : "shared-goal"} period; retained earlier judgments are counted.`;
}

maximizationRankingToggle.addEventListener("click", () => { rankingPeriod = "goal_maximization"; renderRanking(); });
sharedRankingToggle.addEventListener("click", () => { rankingPeriod = "shared_goal"; renderRanking(); });
episodeToggle.addEventListener("click", () => { rankingMode = "episodes"; renderRanking(); });
rateToggle.addEventListener("click", () => { rankingMode = "rate"; renderRanking(); });
renderRanking();

const fullEpisodes = count(episodes, (row) => row.record_kind === "full_episode");
const retainedEpisodes = count(episodes, (row) => row.record_kind === "retained_prior_episode");
const manualSourceEpisodes = count(episodes, (row) => row.record_kind === "manual_source_audit_episode");
const otherProvenanceEpisodes = episodes.length - fullEpisodes - retainedEpisodes - manualSourceEpisodes;
const evidenceMissing = count(episodes, (row) =>
  (row.missing_evidence_for || []).length > 0 || row.analysis_usability === "decision_only"
);
const boutDuration = count(episodes, (row) => row.duration_measurement?.kind === "sum_of_bouts");
const exactDuration = count(episodes, (row) => row.duration_measurement?.kind === "exact");
const lowerDuration = count(episodes, (row) => row.duration_measurement?.kind === "minimum_observed");
const legacyNumericDuration = count(episodes, (row) =>
  row.duration_seconds != null && !row.duration_measurement?.kind
);
const unavailableDuration = episodes.length - boutDuration - exactDuration - lowerDuration - legacyNumericDuration;
const returned = count(episodes, (row) => row.drift_end?.status === "returned_to_goal");
const activityEnded = count(episodes, (row) => row.drift_end?.status === "activity_ended");
const assignmentEnded = count(episodes, (row) =>
  ["goal_or_assignment_ended", "authoritative_target_ended"].includes(row.drift_end?.status)
);
const ongoing = count(episodes, (row) => row.drift_end?.status === "ongoing_at_evidence_end");
const unknownEnd = episodes.length - returned - activityEnded - assignmentEnded - ongoing;
document.querySelector(".quality .panel-heading p:last-child").textContent =
  `All ${number.format(episodes.length)} records have resolved drift decisions. Missing evidence means timing or supporting fields remain unvalidated, not that the decision is unresolved.`;
document.querySelectorAll(".quality-block").forEach((element) => element.remove());
document.querySelector(".quality").insertAdjacentHTML("beforeend",
  stackBlock("Stage 1 screening outcome", `${number.format(daily.length)} agent-days`, [
    { value: stage1Drift, label: "screened drift", color: "var(--rust)" },
    { value: stage1NonDrift, label: "screened non-drift", color: "var(--green)" },
    { value: stage1Undefined, label: "undefined", color: "var(--unknown)" },
  ])
  + stackBlock("Confirmed records by provenance", `${number.format(episodes.length)} records`, [
    { value: fullEpisodes, label: "full v2 episodes", color: "var(--green)" },
    { value: retainedEpisodes, label: "retained prior episodes", color: "var(--blue)" },
    { value: manualSourceEpisodes, label: "manual source-audit episodes", color: "var(--amber)" },
    { value: otherProvenanceEpisodes, label: "other provenance", color: "var(--unknown)" },
  ])
  + stackBlock("Required episode evidence", `${number.format(episodes.length)} records`, [
    { value: episodes.length - evidenceMissing, label: "required evidence present", color: "var(--green)" },
    { value: evidenceMissing, label: "required evidence missing", color: "var(--amber)" },
  ])
  + stackBlock("Drift-time measurement", `${number.format(episodes.length)} records`, [
    { value: boutDuration, label: "sum of observed bouts", color: "var(--green)" },
    { value: exactDuration, label: "exact continuous span", color: "var(--blue)" },
    { value: lowerDuration, label: "lower bounds", color: "var(--amber)" },
    { value: legacyNumericDuration, label: "numeric · method unspecified", color: "var(--unknown)" },
    { value: unavailableDuration, label: "unavailable", color: "var(--rust-soft)" },
  ])
  + stackBlock("Observed episode ending", `${number.format(episodes.length)} records`, [
    { value: returned, label: "returned to goal", color: "var(--green)" },
    { value: activityEnded, label: "activity ended", color: "#6c8065" },
    { value: assignmentEnded, label: "assignment ended", color: "var(--blue)" },
    { value: ongoing, label: "ongoing at evidence end", color: "var(--unknown)" },
    { value: unknownEnd, label: "unknown", color: "var(--rust-soft)" },
  ])
);

const monthCounts = groupCount(episodes, (row) => String(row.onset || row.activity_start || "").slice(0, 7));
monthCounts.delete("");
const monthRows = [...monthCounts].sort(([a], [b]) => a.localeCompare(b));
const maxMonth = Math.max(1, ...monthRows.map(([, value]) => value));
document.querySelector(".timeline-chart").setAttribute(
  "aria-label",
  `Monthly confirmed episode-record counts from ${monthRows[0]?.[0] || "unknown"} through ${monthRows.at(-1)?.[0] || "unknown"}`
);
document.querySelector(".timeline-chart").innerHTML = monthRows.map(([month, value], index) => {
  const date = new Date(`${month}-01T00:00:00Z`);
  const label = new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" }).format(date);
  const year = date.getUTCFullYear();
  const showYear = index === 0 || monthRows[index - 1][0].slice(0, 4) !== String(year);
  return `<div class="month"><span class="month-count">${number.format(value)}</span><span class="month-bar" style="height:${Math.max(1, 100 * value / maxMonth)}%"></span><span class="month-label">${label}${showYear ? `<br>’${String(year).slice(2)}` : ""}</span></div>`;
}).join("");

document.querySelector(".definition-grid").innerHTML = `
  <div class="definition"><strong>Agent-day</strong>One agent’s observed activity on one calendar day. This is the unit classified in Stage 1.</div>
  <div class="definition"><strong>Agent–goal window</strong>One observed agent under one underlying assignment. It is the denominator used for the ${driftRate}% final drift share; raw Stage 2 windows are pipeline units only.</div>
  <div class="definition"><strong>Episode record</strong>A current non-borderline record accepted as drift after corrections and manual assessment. Retained earlier judgments remain distinct records where the audit preserves them.</div>`;
document.querySelector(".source-note").textContent =
  `SOURCE · ${metadata.dataset || "second audit v2"} · ${number.format(daily.length)} Stage 1 days · ${number.format(windows.length)} original Stage 2 windows (${number.format(originalDriftWindows.length)} positive, ${number.format(originalNoDriftWindows.length)} negative before final corrections) · ${number.format(episodes.length)} current confirmed episode records · Updated ${generated ? generated.toISOString() : "date unavailable"} · Read-only research prototype`;

document.body.classList.remove("data-loading");
document.body.classList.add("data-ready");
