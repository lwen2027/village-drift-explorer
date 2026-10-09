const [bundleResponse, manifestResponse] = await Promise.all([
  fetch("./data/second_audit_v2.json"),
  fetch("./data/manual_review_wait_exclusions_v1.json")
]);

if (!bundleResponse.ok) {
  throw new Error(`Could not load audit data (${bundleResponse.status})`);
}
if (!manifestResponse.ok) {
  throw new Error(`Could not load review manifest (${manifestResponse.status})`);
}

const bundle = await bundleResponse.json();
const waitManifest = await manifestResponse.json();
const episodes = bundle.confirmed_episodes.filter(
  (episode) => episode.period === "goal_maximization"
);
const episodeById = new Map(episodes.map((episode) => [episode.episode_id, episode]));
const substantiveIds = new Set(
  waitManifest.default_manual_review_queue_episode_ids || []
);
const routineRows = waitManifest.excluded_episodes || [];
const routineById = new Map(routineRows.map((row) => [row.episode_id, row]));
const routineIds = new Set(routineById.keys());

if (episodes.length !== waitManifest.counts.goal_maximization_episodes) {
  throw new Error("Review manifest and audit dataset disagree");
}
if (substantiveIds.size + routineIds.size !== episodes.length) {
  throw new Error("Review queue partition is incomplete");
}

const storageKey = [
  "village-drift-manual-review-v1",
  waitManifest.rule.rule_id,
  String(waitManifest.input.sha256 || "").slice(0, 16)
].join(":");

const outcomeLabels = {
  confirmed_as_is: "Confirmed as-is",
  needs_correction: "Needs correction",
  not_drift: "Not drift",
  defer: "Defer"
};

const triggerLabels = {
  unreviewed: "Not reviewed",
  confirmed: "Trigger confirmed",
  needs_correction: "Trigger needs correction",
  not_applicable: "No meaningful trigger"
};

const controls = {
  queueMode: document.querySelector("#queue-mode"),
  reviewStatus: document.querySelector("#review-status"),
  agent: document.querySelector("#agent-filter"),
  search: document.querySelector("#search-filter"),
  importButton: document.querySelector("#import-button"),
  exportButton: document.querySelector("#export-button"),
  importFile: document.querySelector("#import-file"),
  previous: document.querySelector("#previous-button"),
  next: document.querySelector("#next-button")
};

const elements = {
  queueTotal: document.querySelector("#queue-total"),
  reviewedTotal: document.querySelector("#reviewed-total"),
  reviewedDetail: document.querySelector("#reviewed-detail"),
  remainingTotal: document.querySelector("#remaining-total"),
  routineTotal: document.querySelector("#routine-total"),
  queueTitle: document.querySelector("#queue-title"),
  visibleCount: document.querySelector("#visible-count"),
  queueList: document.querySelector("#queue-list"),
  positionLabel: document.querySelector("#position-label"),
  detailScroll: document.querySelector("#detail-scroll")
};

let decisions = readDecisions();
let visibleEpisodes = [];
let selectedEpisodeId = null;

function readDecisions() {
  try {
    const parsed = JSON.parse(localStorage.getItem(storageKey) || "{}");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? parsed
      : {};
  } catch {
    return {};
  }
}

function persistDecisions() {
  localStorage.setItem(storageKey, JSON.stringify(decisions));
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function normalizedInstant(value) {
  if (!value) return null;
  const raw = String(value).trim();
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const normalized = raw.includes("T") ? raw : raw.replace(" ", "T");
  const zoned = /(?:Z|[+-]\d{2}:?\d{2})$/.test(normalized)
    ? normalized
    : `${normalized}Z`;
  const date = new Date(zoned);
  return Number.isNaN(date.getTime()) ? null : date;
}

function formatTimestamp(value) {
  if (!value) return "Time unavailable";
  if (/^\d{4}-\d{2}-\d{2}$/.test(String(value))) {
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric", month: "short", day: "numeric", timeZone: "UTC"
    }).format(new Date(`${value}T12:00:00Z`));
  }
  const date = normalizedInstant(value);
  if (!date) return String(value);
  return new Intl.DateTimeFormat(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short"
  }).format(date);
}

function episodeAnchor(episode) {
  return episode.onset
    || episode.activity_start_observed_at
    || episode.activity_start
    || episode.seed_days?.[0]?.day
    || null;
}

function episodeConfidence(episode) {
  if (typeof episode.verdict_confidence === "number") return episode.verdict_confidence;
  if (typeof episode.confidence === "number") return episode.confidence;
  return null;
}

function triggerStatus(episode) {
  return episode.evidence?.trigger?.status || "unavailable";
}

function decisionFor(episodeId) {
  return decisions[episodeId] || null;
}

function needsAttention(decision) {
  return Boolean(decision && (
    ["needs_correction", "not_drift", "defer"].includes(decision.outcome)
    || decision.trigger_review === "needs_correction"
  ));
}

function queueBase() {
  const mode = controls.queueMode.value;
  if (mode === "routine") return episodes.filter((episode) => routineIds.has(episode.episode_id));
  if (mode === "all") return [...episodes];
  return episodes.filter((episode) => substantiveIds.has(episode.episode_id));
}

function priorityTuple(episode) {
  const confidence = episodeConfidence(episode);
  const triggerRank = { unavailable: 0, inferred: 1, direct: 2 }[triggerStatus(episode)] ?? 3;
  return [
    episode.analysis_usability === "reusable" ? 1 : 0,
    confidence ?? 2,
    triggerRank,
    String(episodeAnchor(episode) || "")
  ];
}

function compareTuples(left, right) {
  for (let index = 0; index < Math.max(left.length, right.length); index += 1) {
    if (left[index] < right[index]) return -1;
    if (left[index] > right[index]) return 1;
  }
  return 0;
}

function filteredQueue() {
  const status = controls.reviewStatus.value;
  const agent = controls.agent.value;
  const query = controls.search.value.trim().toLocaleLowerCase();
  return queueBase()
    .filter((episode) => {
      const decision = decisionFor(episode.episode_id);
      if (status === "unreviewed" && decision?.outcome) return false;
      if (status === "reviewed" && !decision?.outcome) return false;
      if (status === "attention" && !needsAttention(decision)) return false;
      if (agent !== "all" && episode.agent !== agent) return false;
      if (query) {
        const haystack = [
          episode.activity,
          episode.assigned_goal,
          episode.agent,
          episode.episode_id,
          episode.dataset_record_id
        ].join(" ").toLocaleLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    })
    .sort((left, right) => compareTuples(priorityTuple(left), priorityTuple(right)));
}

function decisionBadge(decision) {
  if (!decision?.outcome) return '<span class="badge">unreviewed</span>';
  return `<span class="badge ${escapeHtml(decision.outcome)}">${escapeHtml(outcomeLabels[decision.outcome] || decision.outcome)}</span>`;
}

function renderSummary() {
  const base = queueBase();
  const reviewed = base.filter((episode) => decisionFor(episode.episode_id)?.outcome).length;
  elements.queueTotal.textContent = waitManifest.counts.remaining_in_default_manual_queue.toLocaleString();
  elements.reviewedTotal.textContent = reviewed.toLocaleString();
  elements.reviewedDetail.textContent = `${base.length.toLocaleString()} cases in selected bucket`;
  elements.remainingTotal.textContent = (base.length - reviewed).toLocaleString();
  elements.routineTotal.textContent = waitManifest.counts.excluded_from_default_manual_queue.toLocaleString();
}

function renderQueue() {
  visibleEpisodes = filteredQueue();
  const modeLabel = {
    substantive: "Substantive queue",
    routine: "Routine wait-only bucket",
    all: "All goal-maximization episodes"
  }[controls.queueMode.value];
  elements.queueTitle.textContent = modeLabel;
  elements.visibleCount.textContent = `${visibleEpisodes.length.toLocaleString()} cases`;

  if (!visibleEpisodes.length) {
    selectedEpisodeId = null;
    elements.queueList.innerHTML = '<div class="empty-state">No cases match these filters.</div>';
    renderDetail();
    return;
  }

  if (!visibleEpisodes.some((episode) => episode.episode_id === selectedEpisodeId)) {
    selectedEpisodeId = visibleEpisodes[0].episode_id;
  }

  elements.queueList.innerHTML = visibleEpisodes.map((episode) => {
    const selected = episode.episode_id === selectedEpisodeId ? " is-selected" : "";
    const trigger = triggerStatus(episode);
    const routine = routineIds.has(episode.episode_id)
      ? '<span class="badge routine">routine wait</span>'
      : "";
    return `
      <button class="queue-item${selected}" type="button" data-episode-id="${escapeHtml(episode.episode_id)}">
        <span class="queue-item-top">
          <span class="queue-agent">${escapeHtml(episode.agent)}</span>
          <span class="queue-date">${escapeHtml(formatTimestamp(episodeAnchor(episode)))}</span>
        </span>
        <span class="queue-activity">${escapeHtml(episode.activity)}</span>
        <span class="badges">
          ${decisionBadge(decisionFor(episode.episode_id))}
          <span class="badge ${escapeHtml(trigger)}">trigger ${escapeHtml(trigger)}</span>
          ${routine}
        </span>
      </button>`;
  }).join("");

  elements.queueList.querySelectorAll("[data-episode-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectedEpisodeId = button.dataset.episodeId;
      renderQueue();
      renderDetail();
    });
  });
  renderPosition();
}

function renderPosition() {
  const index = visibleEpisodes.findIndex((episode) => episode.episode_id === selectedEpisodeId);
  elements.positionLabel.textContent = index < 0
    ? "CASE — / —"
    : `CASE ${String(index + 1).padStart(3, "0")} / ${String(visibleEpisodes.length).padStart(3, "0")}`;
  controls.previous.disabled = index <= 0;
  controls.next.disabled = index < 0 || index >= visibleEpisodes.length - 1;
}

function evidenceSection(episode, role, label) {
  const group = episode.evidence?.[role] || {};
  const items = group.items || [];
  const cards = items.length
    ? items.map((item) => {
      const source = item.source || {};
      const channel = source.channel || "source unavailable";
      const speaker = source.speaker ? ` · ${source.speaker}` : "";
      return `
        <div class="evidence-card ${escapeHtml(role)}">
          <div class="evidence-meta">
            <span>${escapeHtml(channel + speaker)}</span>
            <span>${escapeHtml(formatTimestamp(item.timestamp || source.timestamp))}</span>
          </div>
          <p class="evidence-quote">${escapeHtml(item.quote || "Quote unavailable")}</p>
          <div class="evidence-meta" style="margin-top:8px;margin-bottom:0">
            <span>${escapeHtml(source.event_id || item.event_id || "event ID unavailable")}</span>
          </div>
        </div>`;
    }).join("")
    : '<div class="empty-state" style="padding:16px">No cited items.</div>';
  const note = group.note
    ? `<p class="evidence-note">${escapeHtml(group.note)}</p>`
    : "";
  return `
    <section class="section">
      <div class="section-heading"><h3>${escapeHtml(label)}</h3><span>${escapeHtml(group.status || "unavailable")}</span></div>
      <div class="evidence-list">${cards}</div>
      ${note}
    </section>`;
}

function radioOption(value, label, checked) {
  return `
    <label class="decision-option">
      <input type="radio" name="review-outcome" value="${escapeHtml(value)}" ${checked ? "checked" : ""}>
      <span>${escapeHtml(label)}</span>
    </label>`;
}

function renderDetail() {
  const episode = episodeById.get(selectedEpisodeId);
  if (!episode) {
    elements.detailScroll.innerHTML = '<div class="empty-state">Select a case to begin reviewing.</div>';
    renderPosition();
    return;
  }

  const decision = decisionFor(episode.episode_id) || {};
  const routine = routineById.get(episode.episode_id);
  const incomplete = episode.incomplete_fields || [];
  const confidence = episodeConfidence(episode);
  const routineBanner = routine ? `
    <div class="routine-banner">
      <strong>Mechanically held out from the default queue.</strong>
      Every cited transition/activity item is a literal wait primitive across ${routine.distinct_matched_event_count} distinct source events. The episode remains confirmed and can still be manually reviewed here.
    </div>` : "";
  const incompleteBanner = incomplete.length ? `
    <div class="incomplete-banner"><strong>Evidence remains incomplete:</strong> ${escapeHtml(incomplete.join(", "))}</div>` : "";

  elements.detailScroll.innerHTML = `
    <header class="detail-header">
      <div class="detail-kicker">${escapeHtml(episode.agent)} · ${escapeHtml(formatTimestamp(episodeAnchor(episode)))}</div>
      <h2>${escapeHtml(episode.activity)}</h2>
      <p class="detail-goal"><strong>Assigned goal:</strong> ${escapeHtml(episode.assigned_goal)}${episode.additional_goal_description ? `<br>${escapeHtml(episode.additional_goal_description)}` : ""}</p>
      <div class="detail-links">
        <a href="index.html#${encodeURIComponent(episode.episode_id)}">Open in Episode Explorer ↗</a>
        <a href="#" id="copy-id-link">Copy episode ID</a>
      </div>
    </header>
    ${routineBanner}
    ${incompleteBanner}
    <section class="review-form" aria-labelledby="review-decision-title">
      <h3 id="review-decision-title">Your review</h3>
      <p>Stored only in this browser until exported. This does not modify the published audit.</p>
      <div class="decision-options">
        ${Object.entries(outcomeLabels).map(([value, label]) => radioOption(value, label, decision.outcome === value)).join("")}
      </div>
      <div class="review-fields">
        <div class="field">
          <label for="trigger-review">Trigger check</label>
          <select id="trigger-review">
            ${Object.entries(triggerLabels).map(([value, label]) => `<option value="${escapeHtml(value)}" ${(decision.trigger_review || "unreviewed") === value ? "selected" : ""}>${escapeHtml(label)}</option>`).join("")}
          </select>
        </div>
        <div class="field">
          <label for="taxonomy-label">Working taxonomy label</label>
          <input id="taxonomy-label" value="${escapeHtml(decision.taxonomy_label || "")}" placeholder="Optional">
        </div>
      </div>
      <textarea id="review-note" placeholder="Correction, rationale, or follow-up evidence needed…">${escapeHtml(decision.note || "")}</textarea>
      <div class="save-row">
        <span class="save-status" id="save-status">${decision.updated_at ? `Saved ${escapeHtml(formatTimestamp(decision.updated_at))}` : "Not yet reviewed"}</span>
        <button class="action-button" id="save-next-button" type="button">Save &amp; next</button>
      </div>
    </section>
    <section class="section">
      <div class="section-heading"><h3>Recorded activity</h3><span>Full text</span></div>
      <p class="activity-copy">${escapeHtml(episode.activity)}</p>
    </section>
    ${evidenceSection(episode, "trigger", "Trigger evidence")}
    ${evidenceSection(episode, "transition", "Transition and onset")}
    ${evidenceSection(episode, "activity", "Activity evidence")}
    <section class="section">
      <div class="section-heading"><h3>Record metadata</h3><span>Second audit v2</span></div>
      <div class="metadata-grid">
        <div class="metadata-item"><span>Episode ID</span><strong>${escapeHtml(episode.episode_id)}</strong></div>
        <div class="metadata-item"><span>Confidence</span><strong>${confidence === null ? "Unavailable" : confidence.toFixed(2)}</strong></div>
        <div class="metadata-item"><span>Trigger status</span><strong>${escapeHtml(triggerStatus(episode))}</strong></div>
        <div class="metadata-item"><span>Onset</span><strong>${escapeHtml(formatTimestamp(episode.onset))}</strong></div>
        <div class="metadata-item"><span>End status</span><strong>${escapeHtml(episode.drift_end?.status || "Unavailable")}</strong></div>
        <div class="metadata-item"><span>Completeness</span><strong>${escapeHtml(episode.episode_completeness || "Unavailable")}</strong></div>
      </div>
    </section>`;

  document.querySelector("#copy-id-link").addEventListener("click", async (event) => {
    event.preventDefault();
    await navigator.clipboard.writeText(episode.episode_id);
    event.currentTarget.textContent = "Copied";
  });
  document.querySelector("#save-next-button").addEventListener("click", saveAndAdvance);
  renderPosition();
}

function saveAndAdvance() {
  const episode = episodeById.get(selectedEpisodeId);
  if (!episode) return;
  const selectedOutcome = document.querySelector('input[name="review-outcome"]:checked');
  if (!selectedOutcome) {
    document.querySelector("#save-status").textContent = "Choose a review outcome first.";
    return;
  }
  const currentIndex = visibleEpisodes.findIndex((row) => row.episode_id === selectedEpisodeId);
  const nextCandidate = visibleEpisodes[currentIndex + 1]?.episode_id
    || visibleEpisodes[currentIndex - 1]?.episode_id
    || null;
  const now = new Date().toISOString();
  decisions[episode.episode_id] = {
    episode_id: episode.episode_id,
    dataset_record_id: episode.dataset_record_id,
    outcome: selectedOutcome.value,
    trigger_review: document.querySelector("#trigger-review").value,
    taxonomy_label: document.querySelector("#taxonomy-label").value.trim() || null,
    note: document.querySelector("#review-note").value.trim() || null,
    updated_at: now
  };
  persistDecisions();
  renderSummary();
  visibleEpisodes = filteredQueue();
  selectedEpisodeId = visibleEpisodes.some((row) => row.episode_id === nextCandidate)
    ? nextCandidate
    : visibleEpisodes[0]?.episode_id || null;
  renderQueue();
  renderDetail();
}

function navigate(offset) {
  const index = visibleEpisodes.findIndex((episode) => episode.episode_id === selectedEpisodeId);
  const target = visibleEpisodes[index + offset];
  if (!target) return;
  selectedEpisodeId = target.episode_id;
  renderQueue();
  renderDetail();
  const selected = elements.queueList.querySelector(".queue-item.is-selected");
  selected?.scrollIntoView({ block: "nearest" });
  elements.detailScroll.scrollTop = 0;
}

function exportReviews() {
  const payload = {
    schema_version: 1,
    exported_at: new Date().toISOString(),
    source_bundle_sha256: waitManifest.input.sha256,
    wait_rule_id: waitManifest.rule.rule_id,
    decisions: Object.values(decisions).sort((left, right) => left.episode_id.localeCompare(right.episode_id))
  };
  const blob = new Blob([`${JSON.stringify(payload, null, 2)}\n`], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `village-drift-manual-reviews-${new Date().toISOString().slice(0, 10)}.json`;
  anchor.click();
  URL.revokeObjectURL(url);
}

async function importReviews(file) {
  const payload = JSON.parse(await file.text());
  if (!Array.isArray(payload.decisions)) throw new Error("Import has no decisions array");
  let imported = 0;
  for (const decision of payload.decisions) {
    if (!episodeById.has(decision.episode_id)) continue;
    if (!Object.hasOwn(outcomeLabels, decision.outcome)) continue;
    decisions[decision.episode_id] = decision;
    imported += 1;
  }
  persistDecisions();
  renderAll();
  window.alert(`Imported ${imported} review decisions.`);
}

function populateAgents() {
  const agents = [...new Set(episodes.map((episode) => episode.agent))].sort();
  controls.agent.insertAdjacentHTML(
    "beforeend",
    agents.map((agent) => `<option value="${escapeHtml(agent)}">${escapeHtml(agent)}</option>`).join("")
  );
}

function renderAll() {
  renderSummary();
  renderQueue();
  renderDetail();
}

for (const control of [controls.queueMode, controls.reviewStatus, controls.agent]) {
  control.addEventListener("change", () => {
    selectedEpisodeId = null;
    renderAll();
  });
}
controls.search.addEventListener("input", () => {
  selectedEpisodeId = null;
  renderAll();
});
controls.previous.addEventListener("click", () => navigate(-1));
controls.next.addEventListener("click", () => navigate(1));
controls.exportButton.addEventListener("click", exportReviews);
controls.importButton.addEventListener("click", () => controls.importFile.click());
controls.importFile.addEventListener("change", async () => {
  const [file] = controls.importFile.files;
  if (!file) return;
  try {
    await importReviews(file);
  } catch (error) {
    window.alert(`Could not import reviews: ${error.message}`);
  } finally {
    controls.importFile.value = "";
  }
});

document.addEventListener("keydown", (event) => {
  if (["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName)) return;
  if (event.key.toLocaleLowerCase() === "j") navigate(1);
  if (event.key.toLocaleLowerCase() === "k") navigate(-1);
});

populateAgents();
renderAll();
document.body.classList.remove("data-loading");
