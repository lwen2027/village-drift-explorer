const REVIEW_STORAGE_KEY = "village-drift-manual-review-ledger:v1";

const [bundleResponse, manifestResponse, annotationResponse] = await Promise.all([
  fetch("./data/second_audit_v2.json"),
  fetch("./data/manual_review_wait_exclusions_v1.json"),
  fetch("./data/manual_review_annotations_v1.json")
]);

if (!bundleResponse.ok || !manifestResponse.ok || !annotationResponse.ok) {
  document.querySelector("#main-content").innerHTML = `
    <div class="load-error"><strong>Review findings could not load.</strong><br>
    The audit bundle, review manifest, and annotation dataset must be published together.</div>`;
  throw new Error("Could not load review findings data");
}

const bundle = await bundleResponse.json();
const manifest = await manifestResponse.json();
const committedSeed = await annotationResponse.json();
const goalMaxEpisodes = bundle.confirmed_episodes.filter(
  (episode) => episode.period === "goal_maximization"
);
const episodeById = new Map(goalMaxEpisodes.map((episode) => [episode.episode_id, episode]));
const queueIds = new Set(manifest.default_manual_review_queue_episode_ids || []);
const excludedIds = new Set((manifest.excluded_episodes || []).map((row) => row.episode_id));
const episodeAliases = new Map(
  goalMaxEpisodes.flatMap((episode) =>
    (episode.merged_episode_segments || [])
      .filter((segment) => segment.episode_id && segment.episode_id !== episode.episode_id)
      .map((segment) => [segment.episode_id, episode.episode_id])
  )
);

function canonicalEpisodeId(episodeId) {
  return episodeAliases.get(episodeId) || episodeId;
}

const starterLabels = {
  trigger: {
    user_message: "User message",
    user_email: "User email",
    gitlab_issue_or_comment: "GitLab issue/comment",
    agent_message_or_request: "Agent message/request",
    self_initiated_or_continuation: "Self-initiated/continuation",
    prior_goal_memory_carryover: "Prior-goal memory carryover",
    operator_or_system_event: "Operator/system event",
    no_discrete_trigger: "No discrete trigger",
    unknown: "Unknown"
  },
  request_relationship: {
    targeted_request: "Targeted request",
    open_request: "Open request",
    inferred_or_volunteered: "Inferred or volunteered",
    no_request: "No request",
    unclear: "Unclear"
  },
  recovery: {
    self_correction: "Self-correction",
    operator_nudge: "Operator nudge",
    peer_feedback: "Peer feedback",
    external_user_intervention: "External user intervention",
    goal_reassignment: "Goal reassignment",
    natural_end_or_timeout: "Natural end or timeout",
    not_corrected: "Not corrected",
    unknown: "Unknown"
  }
};

Object.entries(committedSeed.taxonomies || {}).forEach(([kind, categories]) => {
  if (!starterLabels[kind]) starterLabels[kind] = {};
  (categories || []).forEach((category) => {
    starterLabels[kind][category.id] = category.label;
  });
});

const pauseLabels = {
  end_of_day: "End of day",
  monitoring_loop: "Monitoring loop",
  scheduled_wait: "Scheduled wait",
  dependency_wait: "Dependency wait",
  no_next_action: "Nothing left to do",
  other_or_unknown: "Other or unknown"
};

const sourceLabels = {
  browser_local: "Browser-local edit",
  initial_human_review: "Initial human review",
  repeated_wait_review: "Repeated-wait review",
  high_confidence_pause: "High-confidence pause review",
  source_evidence_review: "Source-evidence review",
  committed_review: "Committed review"
};

function normalizeAnnotation(value) {
  return {
    trigger_categories: Array.isArray(value?.trigger_categories)
      ? [...new Set(value.trigger_categories.map(String))]
      : [],
    request_relationship: String(value?.request_relationship || ""),
    pause_context: String(value?.pause_context || ""),
    recovery_mechanisms: Array.isArray(value?.recovery_mechanisms)
      ? [...new Set(value.recovery_mechanisms.map(String))]
      : [],
    notes: String(value?.notes || ""),
    follow_ups: Array.isArray(value?.follow_ups)
      ? value.follow_ups.map((item) => ({ ...item }))
      : [],
    provenance: value?.provenance && typeof value.provenance === "object"
      ? { ...value.provenance }
      : {},
    updated_at: value?.updated_at || null
  };
}

function mergeCommittedAndLocal(committed, local) {
  if (!committed) return normalizeAnnotation(local);
  if (!local) return normalizeAnnotation(committed);
  const cleanCommitted = normalizeAnnotation(committed);
  const cleanLocal = normalizeAnnotation(local);
  return {
    ...cleanCommitted,
    ...cleanLocal,
    trigger_categories: cleanLocal.trigger_categories.length
      ? cleanLocal.trigger_categories
      : cleanCommitted.trigger_categories,
    request_relationship: cleanLocal.request_relationship
      || cleanCommitted.request_relationship,
    pause_context: cleanLocal.pause_context || cleanCommitted.pause_context,
    recovery_mechanisms: cleanLocal.recovery_mechanisms.length
      ? cleanLocal.recovery_mechanisms
      : cleanCommitted.recovery_mechanisms,
    notes: cleanLocal.notes || cleanCommitted.notes,
    follow_ups: cleanLocal.follow_ups.length
      ? cleanLocal.follow_ups
      : cleanCommitted.follow_ups,
    provenance: { ...cleanCommitted.provenance, ...cleanLocal.provenance },
    updated_at: cleanLocal.updated_at || cleanCommitted.updated_at
  };
}

function annotationSemantic(annotation) {
  const clean = normalizeAnnotation(annotation);
  return JSON.stringify({
    trigger_categories: [...clean.trigger_categories].sort(),
    request_relationship: clean.request_relationship,
    pause_context: clean.pause_context,
    recovery_mechanisms: [...clean.recovery_mechanisms].sort(),
    notes: clean.notes,
    follow_ups: clean.follow_ups.map((item) => ({
      type: item?.type || "",
      note: String(item?.note || "")
    }))
  });
}

function annotationFingerprint(annotation) {
  const clean = normalizeAnnotation(annotation);
  const serialized = JSON.stringify({
    trigger_categories: [...clean.trigger_categories].sort(),
    request_relationship: clean.request_relationship,
    recovery_mechanisms: [...clean.recovery_mechanisms].sort(),
    notes: clean.notes,
    follow_ups: clean.follow_ups.map((item) => ({
      type: item?.type || "",
      note: String(item?.note || "")
    })),
    pause_context: clean.pause_context
  });
  let hash = 2166136261;
  for (let index = 0; index < serialized.length; index += 1) {
    hash ^= serialized.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return `annotation-v1-${(hash >>> 0).toString(16).padStart(8, "0")}`;
}

const committedAnnotations = new Map();
Object.entries(committedSeed.annotations || {}).forEach(([rawId, annotation]) => {
  const episodeId = canonicalEpisodeId(rawId);
  if (episodeById.has(episodeId)) committedAnnotations.set(episodeId, annotation);
});

let localLedger = null;
try {
  localLedger = JSON.parse(localStorage.getItem(REVIEW_STORAGE_KEY) || "null");
} catch {
  localLedger = null;
}

const localAnnotations = new Map();
Object.entries(localLedger?.annotations || {}).forEach(([rawId, annotation]) => {
  const episodeId = canonicalEpisodeId(rawId);
  if (episodeById.has(episodeId)) localAnnotations.set(episodeId, annotation);
});

const pendingLocalIds = new Set();
const allAnnotationIds = new Set([
  ...committedAnnotations.keys(),
  ...localAnnotations.keys()
]);
const mergedAnnotations = new Map();
allAnnotationIds.forEach((episodeId) => {
  const committed = committedAnnotations.get(episodeId);
  const local = localAnnotations.get(episodeId);
  const baselineHash = localLedger?.sync?.baseline_hashes?.[episodeId] || null;
  const exportedHash = localLedger?.sync?.last_exported_hashes?.[episodeId] || null;
  const localHash = local ? annotationFingerprint(local) : null;
  const committedHash = committed ? annotationFingerprint(committed) : null;

  // Mirror the review page's integration semantics so a newly published seed
  // is not misreported as a pending browser edit. An unchanged local baseline
  // yields to the newer committed record; genuinely newer local fields remain
  // visible in the findings and are labeled as browser-local.
  if (!local) {
    mergedAnnotations.set(episodeId, normalizeAnnotation(committed));
    return;
  }
  if (!committed) {
    mergedAnnotations.set(episodeId, normalizeAnnotation(local));
    pendingLocalIds.add(episodeId);
    return;
  }
  if (localHash === committedHash || localHash === baselineHash) {
    mergedAnnotations.set(episodeId, normalizeAnnotation(committed));
    return;
  }
  if (committedHash === exportedHash && localHash === exportedHash) {
    mergedAnnotations.set(episodeId, normalizeAnnotation(committed));
    return;
  }
  mergedAnnotations.set(episodeId, mergeCommittedAndLocal(committed, local));
  pendingLocalIds.add(episodeId);
});

function reviewSource(episodeId, annotation) {
  if (pendingLocalIds.has(episodeId)) return "browser_local";
  const provenance = annotation.provenance || {};
  if (provenance.confidence === "high") return "high_confidence_pause";
  if (provenance.review_disposition === "mechanical_repeated_wait_only") {
    return "repeated_wait_review";
  }
  if (provenance.raw_reason) return "initial_human_review";
  if (provenance.kind === "manual_source_evidence_review") {
    return "source_evidence_review";
  }
  return "committed_review";
}

const rows = [...mergedAnnotations.entries()]
  .map(([episodeId, annotation]) => ({
    episodeId,
    episode: episodeById.get(episodeId),
    annotation,
    source: reviewSource(episodeId, annotation)
  }))
  .filter((row) => row.episode)
  .sort((left, right) => {
    const leftTime = left.episode.onset || left.episode.activity_start || "";
    const rightTime = right.episode.onset || right.episode.activity_start || "";
    return rightTime.localeCompare(leftTime);
  });

const filters = {
  agent: "",
  trigger: "",
  pause: "",
  request: "",
  recovery: "",
  source: ""
};

// Findings always opens on the complete reviewed set. Older versions stored
// chart clicks in the URL, which could silently reopen a pause-only view.
if (location.search) history.replaceState(null, "", location.pathname);

const selectByKey = {
  agent: document.querySelector("#agent-filter"),
  trigger: document.querySelector("#trigger-filter"),
  pause: document.querySelector("#pause-filter"),
  request: document.querySelector("#request-filter"),
  recovery: document.querySelector("#recovery-filter"),
  source: document.querySelector("#source-filter")
};

function label(kind, value) {
  if (!value) return "Not classified";
  if (kind === "pause") return pauseLabels[value] || value;
  if (kind === "source") return sourceLabels[value] || value;
  return starterLabels[kind]?.[value] || value.replaceAll("_", " ");
}

function uniqueValues(accessor) {
  return [...new Set(rows.flatMap((row) => accessor(row)).filter(Boolean))];
}

function fillSelect(key, values, labelKind, allLabel) {
  const select = selectByKey[key];
  select.replaceChildren();
  const all = document.createElement("option");
  all.value = "";
  all.textContent = allLabel;
  select.append(all);
  [...values]
    .sort((left, right) => label(labelKind, left).localeCompare(label(labelKind, right)))
    .forEach((value) => {
      const option = document.createElement("option");
      option.value = value;
      option.textContent = label(labelKind, value);
      select.append(option);
    });
  if ([...select.options].some((option) => option.value === filters[key])) {
    select.value = filters[key];
  } else {
    filters[key] = "";
  }
  select.addEventListener("change", () => {
    filters[key] = select.value;
    render();
  });
}

fillSelect("agent", uniqueValues((row) => [row.episode.agent]), "agent", "All agents");
fillSelect("trigger", uniqueValues((row) => row.annotation.trigger_categories), "trigger", "All triggers");
fillSelect("pause", uniqueValues((row) => [row.annotation.pause_context]), "pause", "All pause contexts");
fillSelect("request", uniqueValues((row) => [row.annotation.request_relationship]), "request_relationship", "All request relationships");
fillSelect("recovery", uniqueValues((row) => row.annotation.recovery_mechanisms), "recovery", "All recovery mechanisms");
fillSelect("source", uniqueValues((row) => [row.source]), "source", "All review sources");

function rowMatches(row) {
  return (!filters.agent || row.episode.agent === filters.agent)
    && (!filters.trigger || row.annotation.trigger_categories.includes(filters.trigger))
    && (!filters.pause || row.annotation.pause_context === filters.pause)
    && (!filters.request || row.annotation.request_relationship === filters.request)
    && (!filters.recovery || row.annotation.recovery_mechanisms.includes(filters.recovery))
    && (!filters.source || row.source === filters.source);
}

function filteredRows() {
  return rows.filter(rowMatches);
}

function countValues(inputRows, accessor) {
  const counts = new Map();
  inputRows.forEach((row) => {
    accessor(row).filter(Boolean).forEach((value) => {
      counts.set(value, (counts.get(value) || 0) + 1);
    });
  });
  return [...counts.entries()].sort((left, right) =>
    right[1] - left[1] || String(left[0]).localeCompare(String(right[0]))
  );
}

function metricCard(labelText, value, copy, fraction = null) {
  const card = document.createElement("article");
  card.className = "metric-card";
  const labelNode = document.createElement("p");
  labelNode.className = "metric-label";
  labelNode.textContent = labelText;
  const valueNode = document.createElement("strong");
  valueNode.className = "metric-value";
  valueNode.textContent = value;
  const copyNode = document.createElement("div");
  copyNode.className = "metric-copy";
  copyNode.textContent = copy;
  card.append(labelNode, valueNode, copyNode);
  if (fraction != null) {
    const track = document.createElement("div");
    track.className = "coverage-track";
    const fill = document.createElement("div");
    fill.className = "coverage-fill";
    fill.style.width = `${Math.max(0, Math.min(100, fraction * 100))}%`;
    track.append(fill);
    card.append(track);
  }
  return card;
}

function renderMetrics() {
  const reviewedInQueue = rows.filter((row) => queueIds.has(row.episodeId)).length;
  const grid = document.querySelector("#metric-grid");
  grid.replaceChildren(
    metricCard(
      "Goal-max episodes reviewed",
      `${rows.length} / ${goalMaxEpisodes.length}`,
      `${Math.round((rows.length / goalMaxEpisodes.length) * 100)}% of confirmed goal-maximization drift episodes`,
      rows.length / goalMaxEpisodes.length
    ),
    metricCard(
      "Current queue reviewed",
      `${reviewedInQueue} / ${queueIds.size}`,
      "Annotations completed among episodes still shown in Manual Review",
      reviewedInQueue / queueIds.size
    )
  );
  const committedCount = [...committedAnnotations.keys()].length;
  document.querySelector("#data-source-note").textContent = pendingLocalIds.size
    ? `${committedCount} committed annotations · ${pendingLocalIds.size} browser-local ${pendingLocalIds.size === 1 ? "change" : "changes"} included`
    : `${committedCount} committed annotations · no browser-local changes detected`;
}

function renderBarChart({ elementId, totalId, labelKind, accessor, chartClass }) {
  const input = rows;
  const counts = countValues(input, accessor);
  const max = Math.max(1, ...counts.map(([, count]) => count));
  const element = document.querySelector(elementId);
  element.replaceChildren();
  counts.forEach(([value, count]) => {
    const bar = document.createElement("div");
    bar.className = "bar-row";
    bar.dataset.chart = chartClass;
    const labelNode = document.createElement("span");
    labelNode.className = "bar-label";
    labelNode.textContent = label(labelKind, value);
    const track = document.createElement("span");
    track.className = "bar-track";
    const fill = document.createElement("span");
    fill.className = "bar-fill";
    fill.style.width = `${(count / max) * 100}%`;
    track.append(fill);
    const countNode = document.createElement("span");
    countNode.className = "bar-count";
    countNode.textContent = String(count);
    bar.append(labelNode, track, countNode);
    element.append(bar);
  });
  document.querySelector(totalId).textContent = `${input.length} reviewed`;
}

function renderMatrix() {
  const input = rows.filter(
    (row) => row.annotation.trigger_categories.includes("pause")
      && row.annotation.pause_context
  );
  const contexts = countValues(input, (row) => [row.annotation.pause_context]).map(([value]) => value);
  const recoveries = countValues(input, (row) => row.annotation.recovery_mechanisms).map(([value]) => value);
  const cellCounts = new Map();
  input.forEach((row) => {
    row.annotation.recovery_mechanisms.forEach((recovery) => {
      const key = `${row.annotation.pause_context}\u0000${recovery}`;
      cellCounts.set(key, (cellCounts.get(key) || 0) + 1);
    });
  });
  const max = Math.max(1, ...cellCounts.values());
  const matrix = document.querySelector("#pause-recovery-matrix");
  matrix.style.gridTemplateColumns = `160px repeat(${Math.max(1, recoveries.length)}, minmax(86px, 1fr))`;
  matrix.replaceChildren();
  const corner = document.createElement("div");
  corner.className = "matrix-label";
  matrix.append(corner);
  recoveries.forEach((recovery) => {
    const header = document.createElement("div");
    header.className = "matrix-label";
    header.textContent = label("recovery", recovery);
    matrix.append(header);
  });
  contexts.forEach((context) => {
    const rowLabel = document.createElement("div");
    rowLabel.className = "matrix-label is-row";
    rowLabel.textContent = label("pause", context);
    matrix.append(rowLabel);
    recoveries.forEach((recovery) => {
      const count = cellCounts.get(`${context}\u0000${recovery}`) || 0;
      const cell = document.createElement("div");
      cell.className = `matrix-cell${count ? "" : " is-empty"}`;
      cell.style.setProperty("--heat", String(.06 + (count / max) * .66));
      cell.textContent = String(count);
      cell.title = `${label("pause", context)} × ${label("recovery", recovery)}: ${count}`;
      matrix.append(cell);
    });
  });
  document.querySelector("#matrix-total").textContent = `${input.length} pause episodes`;
}

function renderAgentCoverage() {
  const denominators = new Map();
  goalMaxEpisodes.forEach((episode) => {
    denominators.set(episode.agent, (denominators.get(episode.agent) || 0) + 1);
  });
  const input = rows;
  const numerators = new Map();
  input.forEach((row) => {
    numerators.set(row.episode.agent, (numerators.get(row.episode.agent) || 0) + 1);
  });
  const agents = [...numerators.keys()].sort((left, right) => {
    const leftRate = numerators.get(left) / denominators.get(left);
    const rightRate = numerators.get(right) / denominators.get(right);
    return rightRate - leftRate || numerators.get(right) - numerators.get(left) || left.localeCompare(right);
  });
  const chart = document.querySelector("#agent-chart");
  chart.replaceChildren();
  agents.forEach((agent) => {
    const reviewed = numerators.get(agent);
    const total = denominators.get(agent);
    const agentRow = document.createElement("div");
    agentRow.className = "agent-row";
    const name = document.createElement("span");
    name.className = "agent-name";
    name.textContent = agent;
    const track = document.createElement("span");
    track.className = "agent-track";
    const fill = document.createElement("span");
    fill.className = "agent-fill";
    fill.style.width = `${(reviewed / total) * 100}%`;
    track.append(fill);
    const count = document.createElement("span");
    count.className = "agent-count";
    count.textContent = `${reviewed} / ${total}`;
    agentRow.append(name, track, count);
    chart.append(agentRow);
  });
  document.querySelector("#agent-total").textContent = `${agents.length} represented`;
}

function displayDay(value) {
  const day = String(value || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day)) return "Date unavailable";
  return new Intl.DateTimeFormat("en-US", {
    month: "short", day: "numeric", year: "numeric", timeZone: "UTC"
  }).format(new Date(`${day}T12:00:00Z`));
}

function tag(text, pause = false) {
  const node = document.createElement("span");
  node.className = `tag${pause ? " is-pause" : ""}`;
  node.textContent = text;
  return node;
}

function renderEpisodeList() {
  const input = filteredRows();
  const list = document.querySelector("#episode-list");
  list.replaceChildren();
  document.querySelector("#results-count").textContent = `${input.length} of ${rows.length}`;
  if (!input.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No reviewed episodes match the selected filters.";
    list.append(empty);
    return;
  }
  input.forEach((row) => {
    const item = document.createElement("article");
    item.className = "episode-row";
    const identity = document.createElement("div");
    const agent = document.createElement("div");
    agent.className = "episode-agent";
    agent.textContent = row.episode.agent;
    const date = document.createElement("div");
    date.className = "episode-date";
    date.textContent = displayDay(row.episode.onset || row.episode.activity_start);
    identity.append(agent, date);

    const activityWrap = document.createElement("div");
    const activity = document.createElement("div");
    activity.className = "episode-activity";
    activity.textContent = row.episode.activity;
    const note = document.createElement("div");
    note.className = "episode-note";
    note.textContent = row.annotation.notes;
    activityWrap.append(activity, note);

    const tags = document.createElement("div");
    tags.className = "episode-tags";
    row.annotation.trigger_categories.forEach((value) => {
      tags.append(tag(label("trigger", value), value === "pause"));
    });
    if (row.annotation.pause_context) tags.append(tag(label("pause", row.annotation.pause_context), true));
    if (row.annotation.request_relationship) tags.append(tag(label("request_relationship", row.annotation.request_relationship)));
    row.annotation.recovery_mechanisms.forEach((value) => tags.append(tag(label("recovery", value))));
    tags.append(tag(label("source", row.source)));

    const link = document.createElement("a");
    link.className = "episode-link";
    link.href = queueIds.has(row.episodeId)
      ? `review.html?scope=maximization&review=all#${encodeURIComponent(row.episodeId)}`
      : `index.html?scope=maximization#${encodeURIComponent(row.episodeId)}`;
    link.textContent = queueIds.has(row.episodeId) ? "Open review" : "Open evidence";
    item.append(identity, activityWrap, tags, link);
    list.append(item);
  });
}

function render() {
  renderMetrics();
  renderBarChart({
    elementId: "#trigger-chart", totalId: "#trigger-total",
    labelKind: "trigger", accessor: (row) => row.annotation.trigger_categories,
    chartClass: "trigger"
  });
  renderBarChart({
    elementId: "#pause-chart", totalId: "#pause-total",
    labelKind: "pause", accessor: (row) => row.annotation.pause_context ? [row.annotation.pause_context] : [],
    chartClass: "pause"
  });
  renderBarChart({
    elementId: "#recovery-chart", totalId: "#recovery-total",
    labelKind: "recovery", accessor: (row) => row.annotation.recovery_mechanisms,
    chartClass: "recovery"
  });
  renderBarChart({
    elementId: "#request-chart", totalId: "#request-total",
    labelKind: "request_relationship", accessor: (row) => row.annotation.request_relationship ? [row.annotation.request_relationship] : [],
    chartClass: "request"
  });
  renderMatrix();
  renderAgentCoverage();
  renderEpisodeList();
}

document.querySelector("#clear-filters").addEventListener("click", () => {
  Object.keys(filters).forEach((key) => {
    filters[key] = "";
    selectByKey[key].value = "";
  });
  render();
});

render();
