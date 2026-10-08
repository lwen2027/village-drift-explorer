const response = await fetch("./data/second_audit_v2.json");
if (!response.ok) throw new Error(`Could not load audit data (${response.status})`);

const bundle = await response.json();
const metadata = bundle.metadata || {};
const daily = bundle.stage1_daily_verdicts || [];
const windows = bundle.window_verdicts || [];
const episodes = bundle.confirmed_episodes || [];

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
const driftWindows = windows.filter((row) => row.drift_verdict === true);
const noDriftWindows = windows.filter((row) => row.drift_verdict === false);
const days = [...unique(daily, "day")].sort();
const agents = unique(daily, "agent");
const episodeAgents = unique(episodes, "agent");

const generated = metadata.generated_at ? new Date(metadata.generated_at) : null;
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
    <p class="micro-label">Calendar coverage</p>
    <span class="metric-value">${number.format(days.length)}</span>
    <span class="metric-detail">distinct Village days · ${isoDateLabel(days[0])}–${isoDateLabel(days.at(-1))}</span>
  </article>
  <article class="metric-card">
    <p class="micro-label">Stage 2 coverage</p>
    <span class="metric-value">${number.format(windows.length)}</span>
    <span class="metric-detail">review windows across ${number.format(agents.size)} observed agents</span>
  </article>
  <article class="metric-card">
    <p class="micro-label">Confirmed findings</p>
    <span class="metric-value">${number.format(episodes.length)}</span>
    <span class="metric-detail">episode records covering ${number.format(driftWindows.length)} positive windows and ${number.format(episodeAgents.size)} agents</span>
  </article>`;

const driftRate = pct(driftWindows.length, windows.length);
document.querySelector("#goal-status-title").textContent = "Which Stage 2 windows contain confirmed drift?";
document.querySelector(".goal-status .panel-heading p:last-child").textContent =
  "Each row is a reviewed evidence window from the timestamp-corrected second audit. Window outcomes are mutually exclusive.";
const donut = document.querySelector(".donut");
donut.style.background = `conic-gradient(var(--rust) 0 ${driftRate}%, var(--green) ${driftRate}% 100%)`;
donut.setAttribute("aria-label", `Of ${windows.length} Stage 2 windows, ${driftWindows.length} contain confirmed drift and ${noDriftWindows.length} do not.`);
document.querySelector(".status-layout > div:last-child").innerHTML = `
  <div class="status-row">
    <i class="status-dot" style="background:var(--rust)"></i>
    <span class="status-name">Contains confirmed drift<span class="status-explain">The v2 review resolved this window as containing at least one drift episode.</span></span>
    <span class="status-number"><strong>${number.format(driftWindows.length)}</strong>${driftRate}%</span>
  </div>
  <div class="status-row">
    <i class="status-dot" style="background:var(--green)"></i>
    <span class="status-name">No confirmed drift<span class="status-explain">The v2 review resolved this window without a confirmed episode.</span></span>
    <span class="status-number"><strong>${number.format(noDriftWindows.length)}</strong>${pct(noDriftWindows.length, windows.length)}%</span>
  </div>`;

const origins = groupCount(windows, "judgment_origin");
const fullJudgments = (origins.get("codex_manual_full_v2") || 0) + (origins.get("opus55_full_v2") || 0);
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
    <span class="funnel-note">${number.format(fullJudgments)} full judgments · ${number.format(compactJudgments)} compact or bounded judgments</span>
  </div>
  <div class="funnel-step" style="--step-color:var(--rust)">
    <span class="funnel-value">${number.format(episodes.length)}</span><span class="funnel-label">confirmed episode records</span>
    <span class="funnel-note">Duplicates retained when v2 preserved an earlier judgment</span>
  </div>`;

document.querySelector("#regimes-title").textContent = "Second-audit results by goal regime";
document.querySelector(".regimes .panel-heading p:last-child").textContent =
  "Counts are recomputed from each record's period field whenever the audit bundle changes.";
document.querySelector(".regime-grid").innerHTML = ["goal_maximization", "shared_goal"].map((period) => {
  const periodWindows = windows.filter((row) => row.period === period);
  const positive = periodWindows.filter((row) => row.drift_verdict);
  const periodEpisodes = episodes.filter((row) => row.period === period);
  const periodRate = pct(positive.length, periodWindows.length);
  const driftAgents = unique(positive, "agent").size;
  const periodDays = daily.filter((row) => row.period === period).map((row) => row.day).filter(Boolean).sort();
  const className = period === "goal_maximization" ? "maximization" : "shared";
  return `
    <article class="regime-card ${className}">
      <div class="regime-kicker"><span>${titlePeriod(period)}</span><span>${isoDateLabel(periodDays[0])}–${isoDateLabel(periodDays.at(-1))}</span></div>
      <h3>${period === "goal_maximization" ? "Agent-specific goals" : "Earlier shared assignments"}</h3>
      <div class="regime-stats">
        <div class="regime-stat"><strong>${number.format(periodEpisodes.length)}</strong>episode records</div>
        <div class="regime-stat"><strong>${number.format(positive.length)} / ${number.format(periodWindows.length)}</strong>review windows with drift</div>
        <div class="regime-stat"><strong>${periodRate}%</strong>of reviewed windows</div>
      </div>
      <div class="regime-rate" aria-label="${periodRate}% of ${titlePeriod(period)} review windows contain drift"><span style="width:${periodRate}%"></span></div>
      <p class="regime-footnote">${number.format(driftAgents)} agents have a positive window; ${number.format(periodWindows.length - positive.length)} reviewed windows have no confirmed drift.</p>
    </article>`;
}).join("");

function rankingFor(period, mode) {
  const periodWindows = windows.filter((row) => row.period === period);
  const windowByAgent = new Map();
  periodWindows.forEach((row) => {
    const current = windowByAgent.get(row.agent) || { total: 0, drift: 0 };
    current.total += 1;
    current.drift += row.drift_verdict ? 1 : 0;
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
  const periodWindows = windows.filter((row) => row.period === period);
  const all = unique(periodWindows, "agent");
  const positive = unique(periodWindows.filter((row) => row.drift_verdict), "agent");
  return `<strong>${positive.size}</strong> of ${all.size} · ${pct(positive.size, all.size)}%`;
}

const ranking = document.querySelector("#ranking");
const caption = document.querySelector("#ranking-caption");
const coverage = document.querySelector("#ranking-coverage");
const maximizationRankingToggle = document.querySelector("#maximization-ranking-toggle");
const sharedRankingToggle = document.querySelector("#shared-ranking-toggle");
const episodeToggle = document.querySelector("#episodes-toggle");
const rateToggle = document.querySelector("#rate-toggle");
rateToggle.textContent = "Window rate";
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
    ? `Share of ${isMax ? "individual-maximization" : "shared-goal"} Stage 2 windows resolved as drift${isMax ? "." : "; agents need at least 10 reviewed windows."}`
    : `Confirmed episode records during the ${isMax ? "individual-maximization" : "shared-goal"} period; retained earlier judgments are counted.`;
}

maximizationRankingToggle.addEventListener("click", () => { rankingPeriod = "goal_maximization"; renderRanking(); });
sharedRankingToggle.addEventListener("click", () => { rankingPeriod = "shared_goal"; renderRanking(); });
episodeToggle.addEventListener("click", () => { rankingMode = "episodes"; renderRanking(); });
rateToggle.addEventListener("click", () => { rankingMode = "rate"; renderRanking(); });
renderRanking();

const fullEpisodes = count(episodes, (row) => row.record_kind === "full_episode");
const retainedEpisodes = count(episodes, (row) => row.record_kind === "retained_prior_episode");
const candidateEpisodes = count(episodes, (row) => row.record_kind === "confirmed_episode_candidate");
const evidenceMissing = count(episodes, (row) =>
  (row.missing_evidence_for || []).length > 0 || row.analysis_usability === "decision_only"
);
const exactDuration = count(episodes, (row) =>
  row.duration_seconds != null || row.duration_measurement?.kind === "exact"
);
const lowerDuration = count(episodes, (row) => row.duration_measurement?.kind === "minimum_observed");
const unavailableDuration = episodes.length - exactDuration - lowerDuration;
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
    { value: candidateEpisodes, label: "decision-only candidates", color: "var(--amber)" },
  ])
  + stackBlock("Required episode evidence", `${number.format(episodes.length)} records`, [
    { value: episodes.length - evidenceMissing, label: "required evidence present", color: "var(--green)" },
    { value: evidenceMissing, label: "required evidence missing", color: "var(--amber)" },
  ])
  + stackBlock("Confirmed-episode elapsed span", `${number.format(episodes.length)} records`, [
    { value: exactDuration, label: "exact wall-clock spans", color: "var(--green)" },
    { value: lowerDuration, label: "lower bounds", color: "var(--amber)" },
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
  <div class="definition"><strong>Stage 2 window</strong>A contiguous evidence window assembled around routed Stage 1 days. It is the denominator used for the ${driftRate}% reviewed-window drift share.</div>
  <div class="definition"><strong>Episode record</strong>A full v2 episode, a retained earlier episode, or an evidence-limited candidate accepted as drift. Semantically overlapping records are intentionally preserved.</div>`;
document.querySelector(".source-note").textContent =
  `SOURCE · ${metadata.dataset || "second audit v2"} · ${number.format(daily.length)} Stage 1 days · ${number.format(windows.length)} Stage 2 windows · ${number.format(episodes.length)} episode records · Generated ${generated ? generated.toISOString() : "date unavailable"} · Read-only research prototype`;

document.body.classList.remove("data-loading");
document.body.classList.add("data-ready");
