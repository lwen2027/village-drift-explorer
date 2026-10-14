const REVIEW_STORAGE_KEY = "village-drift-manual-review-ledger:v1";
const fresh = { cache: "no-store" };

const [bundleResponse, manifestResponse, annotationResponse, sourceResponse, categoryResponse, contactResponse] = await Promise.all([
  fetch("./data/second_audit_v2.json", fresh),
  fetch("./data/manual_review_wait_exclusions_v1.json", fresh),
  fetch("./data/manual_review_annotations_v1.json", fresh),
  fetch("./data/source_records.json", fresh),
  fetch("./data/goal_categories_v1.json", fresh),
  fetch("./data/human_contact_v1.json", fresh)
]);

if (!bundleResponse.ok || !manifestResponse.ok || !annotationResponse.ok || !sourceResponse.ok) {
  document.querySelector("#main-content").innerHTML = `
    <div class="load-error"><strong>Findings overview could not load.</strong><br>
    The audit bundle, review manifest, and annotation dataset must be published together.</div>`;
  throw new Error("Could not load review findings data");
}

const bundle = await bundleResponse.json();
const manifest = await manifestResponse.json();
const committedSeed = await annotationResponse.json();
const sourceRecords = await sourceResponse.json();
const triggerTaxonomy = committedSeed.trigger_taxonomy || {};
const triggerTaxonomyCategories = Array.isArray(triggerTaxonomy.categories)
  ? triggerTaxonomy.categories
  : [];
const triggerTaxonomyByEpisode = new Map(Object.entries(triggerTaxonomy.assignments || {}));
// Goal categories are optional; without them the atlas renders as one ungrouped list.
const goalCategories = categoryResponse.ok ? (await categoryResponse.json()).categories || [] : [];
// Operator corrections are optional too; each targeted correction becomes a marker on the agent's atlas row.
const humanContact = contactResponse.ok ? await contactResponse.json() : {};
const operatorCorrections = humanContact.operator_corrections || [];
// Agents contacted by outside (non-staff) humans on at least this many goal days are flagged as possibly biased.
const OUTSIDE_TARGETING_MIN_DAYS = 10;
const outsideTargetingByAgent = new Map(
  Object.entries(humanContact.agents || {})
    .map(([agent, record]) => [agent, record.outside_targeting])
    .filter(([, targeting]) => targeting && targeting.days >= OUTSIDE_TARGETING_MIN_DAYS)
);
const correctionsByAgent = new Map();
operatorCorrections.forEach((correction) => {
  correction.targets.forEach((agent) => {
    if (!correctionsByAgent.has(agent)) correctionsByAgent.set(agent, []);
    correctionsByAgent.get(agent).push(correction);
  });
});
// Heavily targeted agents carry an asterisk wherever their name is shown on this page.
function agentLabel(agent) {
  return outsideTargetingByAgent.has(agent) ? `${agent}*` : agent;
}
const goalCategoryByAgent = new Map(
  goalCategories.flatMap((category) => category.agents.map((agent) => [agent, category.id]))
);
const borderlineEpisodeIds = new Set(
  Object.entries(committedSeed.annotations || {})
    .filter(([, annotation]) => annotation?.drift_assessment === "borderline")
    .map(([episodeId]) => episodeId)
);
const goalMaxEpisodes = bundle.confirmed_episodes.filter(
  (episode) => episode.period === "goal_maximization"
    && !borderlineEpisodeIds.has(episode.episode_id)
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
    substack_message: "Substack message",
    agent_message_or_request: "Agent message/request",
    self_initiated_or_continuation: "Self-initiated/continuation",
    prior_goal_memory_carryover: "Prior-goal memory carryover",
    self_authored_memory_constraint: "Self-authored memory constraint",
    proxy_substitution: "Proxy substitution",
    operator_or_system_event: "Operator/system event"
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
    natural_end_or_timeout: "Natural end or timeout",
    not_corrected: "Not corrected"
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
  calendar_boundary_confusion: "Mistaken day or workday boundary",
  no_next_action: "Nothing left to do"
};

const externalTriggerCategoryIds = new Set([
  "agent_message_or_request",
  "gitlab_issue_or_comment",
  "substack_message",
  "user_email",
  "user_message"
]);

function annotationIsFullyResolved(annotation) {
  const clean = normalizeAnnotation(annotation);
  if (clean.provenance.verification_status === "needs_manual_verification") return false;
  if (!clean.trigger_categories.length || clean.trigger_categories.includes("unknown")) return false;
  if (!clean.request_relationship || ["unclear", "unknown"].includes(clean.request_relationship)) return false;
  if (!clean.recovery_mechanisms.length || clean.recovery_mechanisms.includes("unknown")) return false;
  if (clean.trigger_categories.includes("pause")
      && (!clean.pause_context || ["other_or_unknown", "unknown"].includes(clean.pause_context))) return false;
  if (clean.trigger_categories.some((trigger) => externalTriggerCategoryIds.has(trigger))
      && !clean.trigger_actor.trim()) return false;
  return true;
}

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
    drift_assessment: value?.drift_assessment === "borderline" ? "borderline" : "confirmed",
    trigger_categories: Array.isArray(value?.trigger_categories)
      ? [...new Set(value.trigger_categories.map(String))]
      : [],
    trigger_actor: String(value?.trigger_actor || ""),
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
    drift_assessment: Object.prototype.hasOwnProperty.call(local || {}, "drift_assessment")
      ? cleanLocal.drift_assessment
      : cleanCommitted.drift_assessment,
    trigger_categories: cleanLocal.trigger_categories.length
      ? cleanLocal.trigger_categories
      : cleanCommitted.trigger_categories,
    trigger_actor: cleanLocal.trigger_actor || cleanCommitted.trigger_actor,
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

function mergeSourceVerifiedAndLocal(committed, local) {
  const cleanCommitted = normalizeAnnotation(committed);
  const cleanLocal = normalizeAnnotation(local);
  const notes = !cleanLocal.notes || cleanLocal.notes === cleanCommitted.notes
    ? cleanCommitted.notes
    : !cleanCommitted.notes
      ? cleanLocal.notes
      : `${cleanCommitted.notes}\n\nPreserved browser review note:\n${cleanLocal.notes}`;
  const followUps = [];
  const seen = new Set();
  [...cleanCommitted.follow_ups, ...cleanLocal.follow_ups].forEach((item) => {
    const key = `${item?.type || ""}\u0000${String(item?.note || "").trim()}`;
    if (seen.has(key)) return;
    seen.add(key);
    followUps.push({ ...item });
  });
  return {
    ...cleanCommitted,
    notes,
    follow_ups: followUps,
    provenance: {
      ...cleanCommitted.provenance,
      preserved_browser_review_fields: Boolean(
        (cleanLocal.notes && cleanLocal.notes !== cleanCommitted.notes)
        || cleanLocal.follow_ups.length
      )
    }
  };
}

function annotationSemantic(annotation) {
  const clean = normalizeAnnotation(annotation);
  const semantic = {
    drift_assessment: clean.drift_assessment,
    trigger_categories: [...clean.trigger_categories].sort(),
    request_relationship: clean.request_relationship,
    pause_context: clean.pause_context,
    recovery_mechanisms: [...clean.recovery_mechanisms].sort(),
    notes: clean.notes,
    follow_ups: clean.follow_ups.map((item) => ({
      type: item?.type || "",
      note: String(item?.note || "")
    })),
    trigger_actor: clean.trigger_actor
  };
  if (clean.provenance.verification_status) {
    semantic.verification_status = clean.provenance.verification_status;
  }
  return JSON.stringify(semantic);
}

function annotationFingerprint(
  annotation,
  includeTriggerActor = true,
  includeDriftAssessment = true
) {
  const clean = normalizeAnnotation(annotation);
  const semantic = {
    trigger_categories: [...clean.trigger_categories].sort(),
    request_relationship: clean.request_relationship,
    recovery_mechanisms: [...clean.recovery_mechanisms].sort(),
    notes: clean.notes,
    follow_ups: clean.follow_ups.map((item) => ({
      type: item?.type || "",
      note: String(item?.note || "")
    })),
    pause_context: clean.pause_context
  };
  if (includeDriftAssessment) semantic.drift_assessment = clean.drift_assessment;
  if (includeTriggerActor) semantic.trigger_actor = clean.trigger_actor;
  if (clean.provenance.verification_status) {
    semantic.verification_status = clean.provenance.verification_status;
  }
  const serialized = JSON.stringify(semantic);
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

function browserHashIsResolved(episodeId, localHash) {
  if (!localHash) return false;
  const latest = committedSeed?.resolved_browser_hashes?.[episodeId];
  const history = committedSeed?.resolved_browser_hash_history?.[episodeId] || [];
  return localHash === latest || history.includes(localHash);
}

function archivedRevisionIsResolved(episodeId, local, committed) {
  if (!local || !committed) return false;
  const localHash = annotationFingerprint(local);
  return (committedSeed?.annotation_history?.[episodeId] || []).some((revision) => {
    const archived = revision?.annotation;
    if (!archived) return false;
    if (annotationFingerprint(archived) === localHash) return true;
    if (annotationFingerprint(
      mergeSourceVerifiedAndLocal(committed, archived)
    ) === localHash) return true;
    return annotationFingerprint(
      mergeCommittedAndLocal(committed, archived)
    ) === localHash;
  });
}
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
  const preActorLocalHash = local ? annotationFingerprint(local, false) : null;
  const preAssessmentLocalHash = local
    ? annotationFingerprint(local, true, false)
    : null;
  const committedHash = committed ? annotationFingerprint(committed) : null;
  const sourceVerifiedUpgrade = (
    committed?.provenance?.verification_status === "raw_source_verified"
    && local?.provenance?.verification_status !== "raw_source_verified"
    && (Date.parse(committed?.updated_at || "") || 0)
      >= (Date.parse(local?.updated_at || "") || 0)
  );

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
  if (
    browserHashIsResolved(episodeId, localHash)
    || archivedRevisionIsResolved(episodeId, local, committed)
  ) {
    mergedAnnotations.set(episodeId, normalizeAnnotation(committed));
    return;
  }
  if (
    sourceVerifiedUpgrade
  ) {
    mergedAnnotations.set(
      episodeId,
      mergeSourceVerifiedAndLocal(committed, local)
    );
    const mergedHash = annotationFingerprint(mergedAnnotations.get(episodeId));
    if (mergedHash !== committedHash) pendingLocalIds.add(episodeId);
    return;
  }
  if (
    localHash === committedHash
    || localHash === baselineHash
    || preActorLocalHash === baselineHash
    || preAssessmentLocalHash === baselineHash
  ) {
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

const annotatedRows = [...mergedAnnotations.entries()]
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

const rows = annotatedRows.filter((row) => annotationIsFullyResolved(row.annotation));

const reviewedEpisodeIds = new Set(rows.map((row) => row.episodeId));
const DAY_MS = 24 * 60 * 60 * 1000;

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

const goalMaxDays = bundle.stage1_daily_verdicts
  .filter((row) => row.period === "goal_maximization" && row.day)
  .map((row) => row.day)
  .sort();
const analysisHorizonMs = timestampMs(goalMaxDays.at(-1), "end");
const agentNameById = new Map(
  (sourceRecords.agentRecords || []).map((agent) => [agent.id, agent.name])
);

// A goal reworded mid-assignment appears as back-to-back records with the same
// short name; treat those as one goal period that keeps the latest wording.
function mergeRewordedGoals(periods) {
  const merged = [];
  [...periods].sort((left, right) =>
    left.agent.localeCompare(right.agent) || left.startMs - right.startMs
  ).forEach((period) => {
    const previous = merged.at(-1);
    if (previous && previous.agent === period.agent
        && previous.shortGoal === period.shortGoal
        && Math.abs(period.startMs - previous.endMs) < 60 * 1000) {
      previous.priorGoals.push(previous.goal);
      previous.goal = period.goal;
      previous.endMs = period.endMs;
      return;
    }
    merged.push(period);
  });
  return merged;
}

const goalPeriods = mergeRewordedGoals((sourceRecords.agentGoalRecords || [])
  .map((goal) => ({
    id: goal.id,
    agent: agentNameById.get(goal.agent_id) || "Unknown agent",
    goal: goal.name,
    priorGoals: [],
    shortGoal: goal.short_name || goal.name,
    startMs: timestampMs(goal.start_time),
    endMs: Math.min(timestampMs(goal.end_time) ?? analysisHorizonMs, analysisHorizonMs),
    episodes: [],
    synthetic: false
  }))
  .filter((goal) => goal.startMs != null && goal.startMs < goal.endMs));

const periodsByAgent = new Map();
goalPeriods.forEach((period) => {
  if (!periodsByAgent.has(period.agent)) periodsByAgent.set(period.agent, []);
  periodsByAgent.get(period.agent).push(period);
});
periodsByAgent.forEach((periods) => periods.sort((left, right) => left.startMs - right.startMs));

function normalizedGoalText(value) {
  return String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

const syntheticPeriods = new Map();
function goalPeriodForEpisode(episode) {
  const onsetMs = episodeOnsetMs(episode);
  const candidates = periodsByAgent.get(episode.agent) || [];
  const assigned = normalizedGoalText(episode.assigned_goal);
  const nameMatches = candidates.filter((period) =>
    [period.goal, ...(period.priorGoals || [])].some((name) => {
      const goal = normalizedGoalText(name);
      return assigned === goal || assigned.includes(goal) || goal.includes(assigned);
    })
  );
  if (nameMatches.length) {
    return [...nameMatches].sort((left, right) =>
      Math.abs(left.startMs - onsetMs) - Math.abs(right.startMs - onsetMs)
    )[0];
  }
  const temporal = candidates.filter((period) => onsetMs >= period.startMs && onsetMs <= period.endMs);
  if (temporal.length) return temporal.at(-1);

  const key = `${episode.agent}\u0000${episode.assigned_goal}`;
  if (!syntheticPeriods.has(key)) {
    syntheticPeriods.set(key, {
      id: `synthetic-${episode.agent}-${episode.assigned_goal}`,
      agent: episode.agent,
      goal: episode.assigned_goal,
      shortGoal: episode.assigned_goal,
      startMs: onsetMs,
      endMs: analysisHorizonMs,
      episodes: [],
      synthetic: true
    });
  }
  const synthetic = syntheticPeriods.get(key);
  synthetic.startMs = Math.min(synthetic.startMs, onsetMs);
  return synthetic;
}

goalMaxEpisodes.forEach((episode) => {
  const period = goalPeriodForEpisode(episode);
  period.episodes.push(episode);
  episode.goalPeriodId = period.id;
});

syntheticPeriods.forEach((period) => {
  const nextStart = (periodsByAgent.get(period.agent) || [])
    .map((candidate) => candidate.startMs)
    .filter((startMs) => startMs > period.startMs)
    .sort((left, right) => left - right)[0];
  if (nextStart) period.endMs = nextStart;
  goalPeriods.push(period);
});

// Episodes validated as a set of drift bouts are measured by their bouts, not one onset-anchored span.
function episodeBouts(episode) {
  return (episode.drift_bouts || [])
    .map(([start, end]) => ({ startMs: timestampMs(start), endMs: timestampMs(end), episode }))
    .filter((bout) => bout.startMs != null && bout.endMs != null && bout.endMs >= bout.startMs);
}

function episodeIntervals(episode) {
  const bouts = episodeBouts(episode);
  if (bouts.length) return bouts;
  const interval = validatedInterval(episode);
  return interval ? [interval] : [];
}

function validatedInterval(episode) {
  const bouts = episodeBouts(episode);
  if (bouts.length) {
    return { startMs: bouts[0].startMs, endMs: bouts.at(-1).endMs, episode };
  }
  const startMs = episodeOnsetMs(episode);
  const durationSeconds = Number(episode.duration_seconds);
  if (startMs == null || episode.duration_seconds == null || !Number.isFinite(durationSeconds) || durationSeconds < 0) {
    return null;
  }
  return { startMs, endMs: startMs + durationSeconds * 1000, episode };
}

function mergedIntervals(intervals, floorMs = -Infinity, ceilingMs = Infinity) {
  const sorted = intervals
    .map((interval) => ({
      ...interval,
      startMs: Math.max(floorMs, interval.startMs),
      endMs: Math.min(ceilingMs, interval.endMs)
    }))
    .filter((interval) => interval.endMs >= interval.startMs)
    .sort((left, right) => left.startMs - right.startMs || left.endMs - right.endMs);
  const merged = [];
  sorted.forEach((interval) => {
    const prior = merged.at(-1);
    if (prior && interval.startMs <= prior.endMs) {
      prior.endMs = Math.max(prior.endMs, interval.endMs);
      prior.episodes.push(interval.episode);
    } else {
      merged.push({ startMs: interval.startMs, endMs: interval.endMs, episodes: [interval.episode] });
    }
  });
  return merged;
}

goalPeriods.forEach((period) => {
  period.durationMs = Math.max(1, period.endMs - period.startMs);
  period.episodes.sort((left, right) => episodeOnsetMs(left) - episodeOnsetMs(right));
  period.exactIntervals = period.episodes.flatMap(episodeIntervals);
  period.mergedIntervals = mergedIntervals(period.exactIntervals, period.startMs, period.endMs);
  period.validatedMs = period.mergedIntervals.reduce(
    (total, interval) => total + Math.max(0, interval.endMs - interval.startMs), 0
  );
  period.burdenShare = period.validatedMs / period.durationMs;
  period.unknownDurationCount = period.episodes.filter((episode) => !validatedInterval(episode)).length;
  const firstOnset = period.episodes.length ? episodeOnsetMs(period.episodes[0]) : null;
  period.firstPosition = firstOnset == null
    ? Infinity
    : Math.max(0, Math.min(1, (firstOnset - period.startMs) / period.durationMs));
});

const filters = {
  agent: "",
  trigger: "",
  pause: "",
  request: "",
  recovery: "",
  source: ""
};
let episodeListLimit = 40;

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
  if (kind === "agent") return agentLabel(value);
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
    episodeListLimit = 40;
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
  // Borderline episodes are left out of the goal-max rows but stay in the review queue.
  const reviewedInQueue = [...queueIds].filter((episodeId) => {
    const annotation = mergedAnnotations.get(episodeId)
      || committedSeed.annotations?.[episodeId];
    return annotation && annotationIsFullyResolved(annotation);
  }).length;
  const grid = document.querySelector("#metric-grid");
  grid.replaceChildren(
    metricCard(
      "Goal-max episodes fully reviewed",
      `${rows.length} / ${goalMaxEpisodes.length}`,
      `${Math.round((rows.length / goalMaxEpisodes.length) * 100)}% of confirmed goal-maximization drift episodes`,
      rows.length / goalMaxEpisodes.length
    ),
    metricCard(
      "Current queue fully reviewed",
      `${reviewedInQueue} / ${queueIds.size}`,
      "Annotations completed among episodes still shown in Manual Review",
      reviewedInQueue / queueIds.size
    )
  );
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

function formatDuration(seconds) {
  if (!Number.isFinite(seconds)) return "Duration unresolved";
  if (seconds < 60) return `${Math.round(seconds)} sec`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${(seconds / 3600).toFixed(seconds < 10800 ? 1 : 0)} hr`;
  return `${(seconds / 86400).toFixed(seconds < 259200 ? 1 : 0)} days`;
}

function shortText(value, length = 35) {
  const text = String(value || "");
  return text.length > length ? `${text.slice(0, length - 1)}…` : text;
}

const SVG_NS = "http://www.w3.org/2000/svg";
function svgElement(name, attributes = {}, textValue = null) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => element.setAttribute(key, String(value)));
  if (textValue != null) element.textContent = textValue;
  return element;
}

function svgTitle(parent, textValue) {
  parent.append(svgElement("title", {}, textValue));
}

function goalAtlasGroups(periods) {
  if (!goalCategories.length) return [{ category: null, periods }];
  const groups = goalCategories.map((category) => ({
    category,
    periods: periods.filter((period) => goalCategoryByAgent.get(period.agent) === category.id)
  }));
  const uncategorized = periods.filter((period) => !goalCategoryByAgent.has(period.agent));
  if (uncategorized.length) {
    groups.push({ category: { id: "other", label: "Other goals", note: "Not yet assigned to a goal category." }, periods: uncategorized });
  }
  return groups.filter((group) => group.periods.length);
}

function goalAtlasGroupHeading({ category, periods }) {
  const heading = document.createElement("div");
  heading.className = "goal-atlas-group";
  const title = document.createElement("div");
  title.className = "goal-atlas-group-title";
  title.textContent = category.label;
  const stats = document.createElement("span");
  stats.className = "goal-atlas-group-stats";
  const medianEpisodes = median(periods.map((period) => period.episodes.length));
  const medianShare = median(periods.map((period) => period.burdenShare));
  stats.textContent = `${periods.length} goal period${periods.length === 1 ? "" : "s"} · median ${Number.isInteger(medianEpisodes) ? medianEpisodes : medianEpisodes.toFixed(1)} ep · median ${(medianShare * 100).toFixed(1)}% validated drift`;
  title.append(stats);
  const note = document.createElement("div");
  note.className = "goal-atlas-group-note";
  note.textContent = category.note;
  heading.append(title, note);
  return heading;
}

// The atlas clips overflowing names, so tooltips are drawn in a fixed layer outside it.
const floatingTip = document.createElement("div");
floatingTip.className = "floating-tip";
floatingTip.setAttribute("role", "tooltip");
floatingTip.hidden = true;
document.body.append(floatingTip);

function showFloatingTip(event) {
  const target = event.target.closest?.("[data-tip]");
  if (!target) return;
  floatingTip.textContent = target.dataset.tip;
  floatingTip.hidden = false;
  const rect = target.getBoundingClientRect();
  const tipRect = floatingTip.getBoundingClientRect();
  const left = Math.min(window.innerWidth - tipRect.width - 8, Math.max(8, rect.left));
  const top = rect.bottom + 6 + tipRect.height > window.innerHeight ? rect.top - tipRect.height - 6 : rect.bottom + 6;
  floatingTip.style.left = `${left}px`;
  floatingTip.style.top = `${top}px`;
}

function hideFloatingTip(event) {
  if (event.target.closest?.("[data-tip]")) floatingTip.hidden = true;
}

document.addEventListener("mouseover", showFloatingTip);
document.addEventListener("focusin", showFloatingTip);
document.addEventListener("mouseout", hideFloatingTip);
document.addEventListener("focusout", hideFloatingTip);
document.addEventListener("scroll", () => { floatingTip.hidden = true; }, true);

function renderGoalAtlas() {
  const sortMode = document.querySelector("#goal-atlas-sort").value;
  const sorted = [...goalPeriods].sort((left, right) => {
    if (sortMode === "agent") return left.agent.localeCompare(right.agent);
    if (sortMode === "episodes") return right.episodes.length - left.episodes.length || left.agent.localeCompare(right.agent);
    if (sortMode === "first") return left.firstPosition - right.firstPosition || left.agent.localeCompare(right.agent);
    return right.burdenShare - left.burdenShare || right.episodes.length - left.episodes.length;
  });
  const atlas = document.querySelector("#goal-atlas");
  atlas.replaceChildren();
  goalAtlasGroups(sorted).forEach((group) => {
    if (group.category) atlas.append(goalAtlasGroupHeading(group));
    group.periods.forEach((period) => {
      const row = document.createElement("div");
      row.className = "goal-strip-row";
      const identity = document.createElement("div");
      identity.className = "goal-strip-name";
      const agent = document.createElement("div");
      agent.className = "goal-strip-agent";
      agent.textContent = agentLabel(period.agent);
      const targeting = outsideTargetingByAgent.get(period.agent);
      if (targeting) {
        const people = Object.entries(targeting.by_person || {})
          .sort((left, right) => right[1].contacts - left[1].contacts)
          .slice(0, 3)
          .map(([person]) => person);
        const badge = document.createElement("span");
        badge.className = "goal-strip-targeted";
        badge.textContent = "targeted";
        badge.tabIndex = 0;
        badge.dataset.tip = `Targeted by outside (non-staff) humans: ${targeting.contacts} contacts on ${targeting.days} days (${people.join(", ")}); `
          + `${targeting.led_to_episodes} drift episode${targeting.led_to_episodes === 1 ? "" : "s"} triggered by outside humans. Results for this agent may be biased.`;
        badge.setAttribute("aria-label", badge.dataset.tip);
        agent.append(" ", badge);
      }
      const goal = document.createElement("div");
      goal.className = "goal-strip-goal";
      goal.textContent = period.shortGoal;
      goal.title = period.priorGoals?.length
        ? `${period.goal}\nEarlier wording: ${period.priorGoals.join(" / ")}`
        : period.goal;
      identity.append(agent, goal);
      const track = document.createElement("div");
      track.className = "goal-strip-track";
      period.episodes.forEach((episode) => {
        const onsetMs = episodeOnsetMs(episode);
        if (onsetMs == null) return;
        const reviewed = reviewedEpisodeIds.has(episode.episode_id);
        const totalSeconds = episode.duration_seconds == null ? NaN : Number(episode.duration_seconds);
        // Bout totals are drift time, so show hours rather than calendar days.
        const totalText = Number.isFinite(totalSeconds) && totalSeconds >= 86400
          ? `${Math.round(totalSeconds / 3600)} hr`
          : formatDuration(totalSeconds);
        const activityText = shortText(episode.activity, 90);
        const reviewedText = reviewed ? " · human reviewed" : "";
        const bouts = episodeBouts(episode);
        const intervals = bouts.length
          ? bouts
          : [validatedInterval(episode) || { startMs: onsetMs, endMs: null }];
        const position = (ms) => Math.max(0, Math.min(100, ((Math.max(period.startMs, Math.min(period.endMs, ms)) - period.startMs) / period.durationMs) * 100));
        if (bouts.length > 1) {
          // A faint line ties together the bouts that belong to one episode.
          const span = document.createElement("span");
          span.className = "goal-strip-span";
          span.style.left = `${position(bouts[0].startMs)}%`;
          span.style.width = `${Math.max(.25, position(bouts.at(-1).endMs) - position(bouts[0].startMs))}%`;
          span.dataset.tip = `${activityText} · ${bouts.length} drift bouts · ${totalText} total${reviewedText}`;
          track.append(span);
        }
        intervals.forEach((interval, index) => {
          const left = position(interval.startMs);
          const segment = document.createElement("span");
          segment.className = `goal-strip-segment${interval.endMs == null ? " is-unknown" : ""}${reviewed ? " is-reviewed" : ""}`;
          segment.style.left = `${left}%`;
          if (interval.endMs != null) {
            segment.style.width = `${Math.max(.25, position(interval.endMs) - left)}%`;
          }
          segment.dataset.tip = bouts.length > 1
            ? `${activityText} · bout ${index + 1} of ${bouts.length}, ${displayDay(new Date(interval.startMs).toISOString())}: ${formatDuration((interval.endMs - interval.startMs) / 1000)} (episode total ${totalText})${reviewedText}`
            : `${activityText} · ${totalText}${reviewedText}`;
          track.append(segment);
        });
      });
      (correctionsByAgent.get(period.agent) || []).forEach((correction) => {
        const correctionMs = timestampMs(correction.timestamp);
        if (correctionMs == null || correctionMs < period.startMs || correctionMs > period.endMs) return;
        const marker = document.createElement("span");
        marker.className = "goal-strip-correction";
        marker.style.left = `${((correctionMs - period.startMs) / period.durationMs) * 100}%`;
        marker.dataset.tip = `Operator correction · ${displayDay(correction.timestamp)} · ${correction.summary}`;
        track.append(marker);
      });
      const count = document.createElement("div");
      count.className = "goal-strip-count";
      count.textContent = `${period.episodes.length} ep`;
      row.append(identity, track, count);
      atlas.append(row);
    });
  });
  const known = goalMaxEpisodes.filter((episode) => episode.duration_seconds != null).length;
  document.querySelector("#goal-atlas-note").textContent = `${goalPeriods.length} goal periods · ${goalMaxEpisodes.length} confirmed episodes · ${known} with validated duration · ${goalMaxEpisodes.length - known} onset-only duration records.`;
}

function addCartesianFrame(svg, { left, right, top, bottom, xTicks, yTicks, xScale, yScale, xLabel, yLabel }) {
  xTicks.forEach(({ value, label: tickLabel }) => {
    const x = xScale(value);
    svg.append(svgElement("line", { x1: x, x2: x, y1: top, y2: bottom, class: "svg-grid" }));
    svg.append(svgElement("text", { x, y: bottom + 18, "text-anchor": "middle", class: "svg-label" }, tickLabel));
  });
  yTicks.forEach(({ value, label: tickLabel }) => {
    const y = yScale(value);
    svg.append(svgElement("line", { x1: left, x2: right, y1: y, y2: y, class: "svg-grid" }));
    svg.append(svgElement("text", { x: left - 8, y: y + 3, "text-anchor": "end", class: "svg-label" }, tickLabel));
  });
  svg.append(svgElement("line", { x1: left, x2: right, y1: bottom, y2: bottom, class: "svg-axis" }));
  svg.append(svgElement("line", { x1: left, x2: left, y1: top, y2: bottom, class: "svg-axis" }));
  svg.append(svgElement("text", { x: (left + right) / 2, y: bottom + 40, "text-anchor": "middle", class: "svg-title" }, xLabel));
  const yTitle = svgElement("text", { x: 14, y: (top + bottom) / 2, "text-anchor": "middle", class: "svg-title", transform: `rotate(-90 14 ${(top + bottom) / 2})` }, yLabel);
  svg.append(yTitle);
}

const burdenColors = ["#3f7082", "#ae5037", "#a77b2c", "#466f61", "#74578f", "#bd6f3b", "#657a3d", "#8a5961", "#5b6f9e", "#8d734e"];
const burdenSelectionsByMode = new Map();

function dominantMechanism(period) {
  const counts = new Map();
  period.episodes.forEach((episode) => {
    const mechanism = episode.mechanism_shape || "unknown";
    counts.set(mechanism, (counts.get(mechanism) || 0) + 1);
  });
  return [...counts.entries()]
    .sort((left, right) => right[1] - left[1] || mechanismLabel(left[0]).localeCompare(mechanismLabel(right[0])))[0]?.[0] || "unknown";
}

function burdenGrouping(period, mode) {
  if (mode === "model_family") {
    const family = modelFamily(period.agent);
    return { key: family, label: family };
  }
  if (mode === "mechanism") {
    const mechanism = dominantMechanism(period);
    return { key: mechanism, label: mechanismLabel(mechanism) };
  }
  const categoryId = goalCategoryByAgent.get(period.agent) || "other";
  const category = goalCategories.find((candidate) => candidate.id === categoryId);
  return { key: categoryId, label: category?.label || "Other goals" };
}

function orderedBurdenGroups(plotted, mode) {
  const present = new Map(plotted.map((period) => {
    const grouping = burdenGrouping(period, mode);
    return [grouping.key, grouping];
  }));
  if (mode === "goal_type") {
    const ordered = goalCategories.filter((category) => present.has(category.id)).map((category) => present.get(category.id));
    if (present.has("other")) ordered.push(present.get("other"));
    return ordered;
  }
  return [...present.values()].sort((left, right) => left.label.localeCompare(right.label));
}

function burdenSelection(mode, groups) {
  if (!burdenSelectionsByMode.has(mode)) {
    burdenSelectionsByMode.set(mode, new Set(groups.map((group) => group.key)));
  }
  return burdenSelectionsByMode.get(mode);
}

function renderBurdenLegend(groups, colorByKey, selectedKeys, groupCounts) {
  const legend = document.querySelector("#burden-legend");
  legend.replaceChildren();
  groups.forEach((group) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "legend-item burden-filter-chip";
    item.setAttribute("aria-pressed", String(selectedKeys.has(group.key)));
    item.title = `${selectedKeys.has(group.key) ? "Exclude" : "Include"} ${group.label}`;
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch is-circle";
    swatch.style.background = colorByKey.get(group.key);
    item.append(swatch, document.createTextNode(`${group.label} · ${groupCounts.get(group.key) || 0}`));
    item.addEventListener("click", () => {
      if (selectedKeys.has(group.key)) selectedKeys.delete(group.key);
      else selectedKeys.add(group.key);
      renderBurdenScatter();
    });
    legend.append(item);
  });
}

function renderBurdenScatter() {
  const plotted = goalPeriods.filter((period) => period.episodes.length);
  const mode = document.querySelector("#burden-color-mode").value;
  const groups = orderedBurdenGroups(plotted, mode);
  const colorByKey = new Map(groups.map((group, index) => [group.key, burdenColors[index % burdenColors.length]]));
  const selectedKeys = burdenSelection(mode, groups);
  const groupCounts = new Map(groups.map((group) => [group.key, 0]));
  plotted.forEach((period) => {
    const key = burdenGrouping(period, mode).key;
    groupCounts.set(key, (groupCounts.get(key) || 0) + 1);
  });
  const showContext = document.querySelector("#burden-show-context").checked;
  const svg = document.querySelector("#burden-scatter");
  svg.replaceChildren();
  const left = 58, right = 620, top = 20, bottom = 305;
  const xMax = Math.max(5, ...plotted.map((period) => period.episodes.length));
  const rawYMax = Math.max(.01, ...plotted.map((period) => period.burdenShare));
  const yMax = Math.ceil(rawYMax * 20) / 20;
  const xScale = (value) => left + (value / xMax) * (right - left);
  const yScale = (value) => bottom - (value / yMax) * (bottom - top);
  const xTicks = Array.from({ length: 6 }, (_, index) => ({
    value: (xMax * index) / 5,
    label: String(Math.round((xMax * index) / 5))
  }));
  const yTicks = Array.from({ length: 6 }, (_, index) => ({
    value: (yMax * index) / 5,
    label: `${Math.round(((yMax * index) / 5) * 100)}%`
  }));
  addCartesianFrame(svg, { left, right, top, bottom, xTicks, yTicks, xScale, yScale, xLabel: "Confirmed episodes", yLabel: "Validated drift share" });
  const orderedPoints = [...plotted].sort((leftPeriod, rightPeriod) => {
    const leftSelected = selectedKeys.has(burdenGrouping(leftPeriod, mode).key);
    const rightSelected = selectedKeys.has(burdenGrouping(rightPeriod, mode).key);
    return Number(leftSelected) - Number(rightSelected);
  });
  orderedPoints.forEach((period) => {
    const grouping = burdenGrouping(period, mode);
    const selected = selectedKeys.has(grouping.key);
    if (!selected && !showContext) return;
    const point = svgElement("circle", {
      cx: xScale(period.episodes.length),
      cy: yScale(period.burdenShare),
      r: selected ? 6 : 4.5,
      fill: selected ? (colorByKey.get(grouping.key) || "#8d8678") : "#aaa294",
      stroke: selected && period.unknownDurationCount ? "#ae5037" : "#fbf8f0",
      "stroke-width": selected && period.unknownDurationCount ? 2.5 : 1.5,
      opacity: selected ? .9 : .13
    });
    svgTitle(point, `${selected ? "" : "Excluded · "}${agentLabel(period.agent)} — ${period.goal}\n${grouping.label}\n${period.episodes.length} episodes; ${(period.burdenShare * 100).toFixed(2)}% validated drift share; ${period.unknownDurationCount} unresolved durations`);
    svg.append(point);
  });
  renderBurdenLegend(groups, colorByKey, selectedKeys, groupCounts);
  const selectedCount = plotted.filter((period) => selectedKeys.has(burdenGrouping(period, mode).key)).length;
  document.querySelector("#burden-meta").textContent = `${selectedCount} of ${plotted.length} goal periods`;
  document.querySelector("#burden-select-all").disabled = selectedKeys.size === groups.length;
  document.querySelector("#burden-clear").disabled = selectedKeys.size === 0;
}

function renderDurationDistribution() {
  const known = goalMaxEpisodes
    .filter((episode) => episode.duration_seconds != null)
    .map((episode) => Number(episode.duration_seconds))
    .filter((duration) => Number.isFinite(duration) && duration >= 0)
    .sort((left, right) => left - right);
  const bins = [
    { label: "< 5 min", min: 0, max: 300 },
    { label: "5–30 min", min: 300, max: 1800 },
    { label: "30m–2h", min: 1800, max: 7200 },
    { label: "2–8 hr", min: 7200, max: 28800 },
    { label: "8–24 hr", min: 28800, max: 86400 },
    { label: "1–3 days", min: 86400, max: 259200 },
    { label: "3+ days", min: 259200, max: Infinity }
  ].map((bin) => ({ ...bin, count: known.filter((value) => value >= bin.min && value < bin.max).length }));
  const maxCount = Math.max(1, ...bins.map((bin) => bin.count));
  const container = document.querySelector("#duration-bars");
  container.replaceChildren();
  bins.forEach((bin) => {
    const row = document.createElement("div");
    row.className = "duration-row";
    const labelNode = document.createElement("span");
    labelNode.textContent = bin.label;
    const track = document.createElement("span");
    track.className = "duration-track";
    const fill = document.createElement("span");
    fill.className = "duration-fill";
    fill.style.width = `${(bin.count / maxCount) * 100}%`;
    track.append(fill);
    const count = document.createElement("span");
    count.className = "duration-count";
    count.textContent = `${bin.count} (${known.length ? Math.round((bin.count / known.length) * 100) : 0}%)`;
    row.append(labelNode, track, count);
    container.append(row);
  });
  const unknown = goalMaxEpisodes.length - known.length;
  document.querySelector("#duration-meta").textContent = `${known.length} episodes with validated duration`;
  document.querySelector("#duration-note").textContent = `${unknown} of ${goalMaxEpisodes.length} confirmed episodes have unresolved numeric duration and are excluded from this chart. Percentages use the ${known.length} episodes with validated duration.`;
}

function renderFirstDriftTiming() {
  const positions = goalPeriods.flatMap((period) => {
    const first = period.episodes.map(episodeOnsetMs).filter(Number.isFinite).sort((left, right) => left - right)[0];
    if (first == null || !Number.isFinite(period.durationMs) || period.durationMs <= 0) return [];
    return [{ period, position: Math.max(0, Math.min(1, (first - period.startMs) / period.durationMs)) }];
  });
  const boundaries = [0, .01, .02, .05, .1, .2, .4, .6, .8, 1];
  const bins = boundaries.slice(0, -1).map((start, index) => ({
    start,
    end: boundaries[index + 1],
    label: `${start * 100}–${boundaries[index + 1] * 100}%`,
    periods: []
  }));
  positions.forEach((entry) => {
    const bin = bins.find((candidate, index) =>
      entry.position >= candidate.start && (entry.position < candidate.end || index === bins.length - 1)
    );
    if (bin) bin.periods.push(entry.period);
  });
  const container = document.querySelector("#first-drift-bars");
  container.replaceChildren();
  bins.forEach((bin) => {
    const share = positions.length ? bin.periods.length / positions.length : 0;
    const row = document.createElement("div");
    row.className = "first-drift-row";
    row.title = bin.periods.length ? bin.periods.map((period) => agentLabel(period.agent)).join(", ") : "No goal periods";
    const label = document.createElement("span");
    label.textContent = bin.label;
    const track = document.createElement("div");
    track.className = "first-drift-track";
    const fill = document.createElement("span");
    fill.className = "first-drift-fill";
    fill.style.width = `${share * 100}%`;
    track.append(fill);
    const count = document.createElement("span");
    count.className = "first-drift-count";
    count.textContent = `${bin.periods.length} (${Math.round(share * 100)}%)`;
    row.append(label, track, count);
    container.append(row);
  });
  const missing = goalPeriods.filter((period) => period.episodes.length).length - positions.length;
  document.querySelector("#first-drift-meta").textContent = `${positions.length} drift-positive goal periods`;
  document.querySelector("#first-drift-note").textContent = `Bins are intentionally narrower near assignment and bars show counts, not density per percentage point. Percentages use all ${positions.length} drift-positive goal periods.${missing ? ` ${missing} period${missing === 1 ? "" : "s"} lacked a usable onset.` : ""}`;
}

function renderCumulativeGoal(periodId) {
  const period = goalPeriods.find((candidate) => candidate.id === periodId);
  if (!period) return;
  const svg = document.querySelector("#cumulative-chart");
  svg.replaceChildren();
  const left = 58, right = 620, top = 25, bottom = 290;
  const maxShare = Math.max(.01, period.burdenShare * 1.15);
  const xScale = (value) => left + value * (right - left);
  const yScale = (value) => bottom - (value / maxShare) * (bottom - top);
  addCartesianFrame(svg, {
    left, right, top, bottom,
    xTicks: [0, .25, .5, .75, 1].map((value) => ({ value, label: `${value * 100}%` })),
    yTicks: [0, .25, .5, .75, 1].map((fraction) => ({ value: maxShare * fraction, label: `${(maxShare * fraction * 100).toFixed(1)}%` })),
    xScale, yScale, xLabel: "Position in goal window", yLabel: "Cumulative validated drift"
  });
  let cumulative = 0;
  const points = [[xScale(0), yScale(0)]];
  period.mergedIntervals.forEach((interval) => {
    const startPosition = Math.max(0, Math.min(1, (interval.startMs - period.startMs) / period.durationMs));
    const endPosition = Math.max(0, Math.min(1, (interval.endMs - period.startMs) / period.durationMs));
    points.push([xScale(startPosition), yScale(cumulative)]);
    cumulative += Math.max(0, interval.endMs - interval.startMs) / period.durationMs;
    points.push([xScale(endPosition), yScale(cumulative)]);
  });
  points.push([xScale(1), yScale(cumulative)]);
  svg.append(svgElement("polyline", { points: points.map((point) => point.join(",")).join(" "), fill: "none", stroke: "#ae5037", "stroke-width": 3 }));
  period.episodes.filter((episode) => !validatedInterval(episode)).forEach((episode) => {
    const onset = episodeOnsetMs(episode);
    const position = Math.max(0, Math.min(1, (onset - period.startMs) / period.durationMs));
    const marker = svgElement("rect", { x: xScale(position) - 3.5, y: bottom - 3.5, width: 7, height: 7, fill: "#a77b2c", transform: `rotate(45 ${xScale(position)} ${bottom})` });
    svgTitle(marker, episode.activity);
    svg.append(marker);
  });
  document.querySelector("#cumulative-note").textContent = `${agentLabel(period.agent)} · ${period.episodes.length} episodes · ${(period.burdenShare * 100).toFixed(2)}% minimum validated drift share · ${period.unknownDurationCount} unresolved durations shown as diamonds.`;
}

function initializeCumulativeChart() {
  const select = document.querySelector("#cumulative-goal-select");
  const periods = goalPeriods.filter((period) => period.episodes.length).sort((left, right) => right.burdenShare - left.burdenShare || right.episodes.length - left.episodes.length);
  select.replaceChildren();
  periods.forEach((period) => {
    const option = document.createElement("option");
    option.value = period.id;
    option.textContent = `${agentLabel(period.agent)} — ${shortText(period.shortGoal, 34)}`;
    select.append(option);
  });
  select.addEventListener("change", () => renderCumulativeGoal(select.value));
  if (periods.length) {
    select.value = periods[0].id;
    renderCumulativeGoal(periods[0].id);
  }
}

function primaryManualTriggerAndContext(annotation) {
  const triggers = annotation.trigger_categories || [];
  if (triggers.includes("pause") && annotation.pause_context) {
    return { trigger: "pause", context: `pause:${annotation.pause_context}` };
  }
  const requestTrigger = triggers.find((trigger) => externalTriggerCategoryIds.has(trigger));
  if (requestTrigger && annotation.request_relationship) {
    return { trigger: requestTrigger, context: `request:${annotation.request_relationship}` };
  }
  return { trigger: triggers[0] || "unknown", context: "none" };
}

function renderAnnotationFlow() {
  function contextLabel(value) {
    if (value === "none") return "No secondary context";
    const [kind, category] = value.split(":", 2);
    if (kind === "pause") return `Pause · ${label("pause", category)}`;
    if (kind === "request") return `Request · ${label("request_relationship", category)}`;
    return value.replaceAll("_", " ");
  }
  const flowRows = rows.map((row) => ({
    ...primaryManualTriggerAndContext(row.annotation),
    recovery: row.annotation.recovery_mechanisms[0] || "unknown"
  }));
  const stages = [
    { key: "trigger", x: 175, label: (value) => label("trigger", value) },
    { key: "context", x: 580, label: contextLabel },
    { key: "recovery", x: 965, label: (value) => label("recovery", value) }
  ];
  const chartTop = 40, chartHeight = 540, nodeWidth = 14, gap = 9;
  const countsByStage = stages.map((stage) => countValues(flowRows, (row) => [row[stage.key]]));
  const total = Math.max(1, flowRows.length);
  const scale = Math.min(...countsByStage.map((counts) => (chartHeight - Math.max(0, counts.length - 1) * gap) / total));
  const nodeMaps = stages.map(() => new Map());
  countsByStage.forEach((counts, stageIndex) => {
    const used = counts.reduce((sum, [, count]) => sum + count * scale, 0) + Math.max(0, counts.length - 1) * gap;
    let y = chartTop + (chartHeight - used) / 2;
    counts.forEach(([value, count]) => {
      nodeMaps[stageIndex].set(value, { value, count, x: stages[stageIndex].x, y, height: count * scale });
      y += count * scale + gap;
    });
  });

  const svg = document.querySelector("#annotation-flow");
  svg.replaceChildren();
  const linkColors = ["#ae5037", "#3f7082"];
  for (let stageIndex = 0; stageIndex < 2; stageIndex += 1) {
    const leftStage = stages[stageIndex];
    const rightStage = stages[stageIndex + 1];
    const links = new Map();
    flowRows.forEach((row) => {
      const key = `${row[leftStage.key]}\u0000${row[rightStage.key]}`;
      links.set(key, (links.get(key) || 0) + 1);
    });
    const sourceOffsets = new Map();
    const targetOffsets = new Map();
    [...links.entries()]
      .map(([key, count]) => {
        const [source, target] = key.split("\u0000");
        return { source, target, count };
      })
      .sort((left, right) =>
        nodeMaps[stageIndex].get(left.source).y - nodeMaps[stageIndex].get(right.source).y
        || nodeMaps[stageIndex + 1].get(left.target).y - nodeMaps[stageIndex + 1].get(right.target).y
      )
      .forEach((link) => {
        const sourceNode = nodeMaps[stageIndex].get(link.source);
        const targetNode = nodeMaps[stageIndex + 1].get(link.target);
        const width = Math.max(1, link.count * scale);
        const sourceOffset = sourceOffsets.get(link.source) || 0;
        const targetOffset = targetOffsets.get(link.target) || 0;
        const x1 = sourceNode.x + nodeWidth;
        const x2 = targetNode.x;
        const y1 = sourceNode.y + sourceOffset + width / 2;
        const y2 = targetNode.y + targetOffset + width / 2;
        const path = svgElement("path", {
          d: `M ${x1} ${y1} C ${(x1 + x2) / 2} ${y1}, ${(x1 + x2) / 2} ${y2}, ${x2} ${y2}`,
          fill: "none",
          stroke: linkColors[stageIndex],
          "stroke-width": width,
          opacity: .18
        });
        svgTitle(path, `${stages[stageIndex].label(link.source)} → ${stages[stageIndex + 1].label(link.target)}: ${link.count}`);
        svg.append(path);
        sourceOffsets.set(link.source, sourceOffset + width);
        targetOffsets.set(link.target, targetOffset + width);
      });
  }
  stages.forEach((stage, stageIndex) => {
    const heading = ["Trigger", "Trigger context", "Recovery"][stageIndex];
    svg.append(svgElement("text", { x: stage.x + nodeWidth / 2, y: 18, "text-anchor": "middle", class: "svg-title" }, heading));
    nodeMaps[stageIndex].forEach((node) => {
      const rect = svgElement("rect", { x: node.x, y: node.y, width: nodeWidth, height: Math.max(1, node.height), rx: 4, fill: stageIndex === 1 ? "#3f7082" : stageIndex === 0 ? "#ae5037" : "#466f61" });
      svgTitle(rect, `${stage.label(node.value)}: ${node.count}`);
      svg.append(rect);
      const anchor = stageIndex === 0 ? "end" : "start";
      const textX = stageIndex === 0 ? node.x - 8 : node.x + nodeWidth + 8;
      const labelLength = stageIndex === 1 ? 38 : 28;
      svg.append(svgElement("text", { x: textX, y: node.y + Math.max(9, node.height / 2 + 3), "text-anchor": anchor, class: "svg-label" }, `${shortText(stage.label(node.value), labelLength)} · ${node.count}`));
    });
  });
  document.querySelector("#flow-meta").textContent = `${flowRows.length} reviewed episodes`;
}

function initializeExplorations() {
  renderGoalAtlas();
  document.querySelector("#goal-atlas-sort").addEventListener("change", renderGoalAtlas);
  renderBurdenScatter();
  document.querySelector("#burden-color-mode").addEventListener("change", renderBurdenScatter);
  document.querySelector("#burden-select-all").addEventListener("click", () => {
    const mode = document.querySelector("#burden-color-mode").value;
    const groups = orderedBurdenGroups(goalPeriods.filter((period) => period.episodes.length), mode);
    burdenSelectionsByMode.set(mode, new Set(groups.map((group) => group.key)));
    renderBurdenScatter();
  });
  document.querySelector("#burden-clear").addEventListener("click", () => {
    burdenSelectionsByMode.set(document.querySelector("#burden-color-mode").value, new Set());
    renderBurdenScatter();
  });
  document.querySelector("#burden-show-context").addEventListener("change", renderBurdenScatter);
  renderDurationDistribution();
  renderFirstDriftTiming();
  initializeCumulativeChart();
  renderAnnotationFlow();
}

function localDateKey(milliseconds) {
  const date = new Date(milliseconds);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

const VILLAGE_TIME_ZONE = "America/Los_Angeles";
const VILLAGE_ACTIVE_START_HOUR = 9;
const VILLAGE_ACTIVE_END_HOUR = 17;
const villageClock = new Intl.DateTimeFormat("en-CA", {
  timeZone: VILLAGE_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  hourCycle: "h23"
});

function villageDateAndHour(milliseconds) {
  const parts = Object.fromEntries(
    villageClock.formatToParts(new Date(milliseconds))
      .filter((part) => part.type !== "literal")
      .map((part) => [part.type, part.value])
  );
  return {
    date: `${parts.year}-${parts.month}-${parts.day}`,
    hour: Number(parts.hour)
  };
}

function villageHourLabel(hour) {
  if (hour === 12) return "12 PM";
  if (hour > 12) return `${hour - 12} PM`;
  return `${hour} AM`;
}

function renderDriftWeather() {
  const dates = [...new Set(goalMaxDays)];
  const activeDateSet = new Set(dates);
  const cells = new Map();
  function cellFor(date, hour) {
    const key = `${date}\u0000${hour}`;
    if (!cells.has(key)) cells.set(key, { exact: 0, unresolved: 0 });
    return cells.get(key);
  }
  goalMaxEpisodes.forEach((episode) => {
    const intervals = episodeIntervals(episode);
    if (!intervals.length) {
      const onset = episodeOnsetMs(episode);
      if (onset != null) {
        const { date, hour } = villageDateAndHour(onset);
        if (activeDateSet.has(date) && hour >= VILLAGE_ACTIVE_START_HOUR && hour < VILLAGE_ACTIVE_END_HOUR) {
          cellFor(date, hour).unresolved += 1;
        }
      }
      return;
    }
    const buckets = new Set();
    intervals.forEach((interval) => {
      const firstBucket = Math.floor(interval.startMs / 3600000) * 3600000;
      for (let bucket = firstBucket; bucket <= interval.endMs; bucket += 3600000) {
        const overlap = Math.min(interval.endMs, bucket + 3600000) - Math.max(interval.startMs, bucket);
        if (overlap <= 0 && interval.endMs !== interval.startMs) continue;
        buckets.add(bucket);
      }
    });
    buckets.forEach((bucket) => {
      const midpoint = bucket + 1800000;
      const { date, hour } = villageDateAndHour(midpoint);
      if (!activeDateSet.has(date) || hour < VILLAGE_ACTIVE_START_HOUR || hour >= VILLAGE_ACTIVE_END_HOUR) return;
      cellFor(date, hour).exact += 1;
    });
  });

  const maxExact = Math.max(1, ...cells.values().map((cell) => cell.exact));
  const svg = document.querySelector("#weather-chart");
  svg.replaceChildren();
  const left = 54, right = 1100, top = 30, bottom = 288;
  const cellWidth = (right - left) / dates.length;
  const activeHours = VILLAGE_ACTIVE_END_HOUR - VILLAGE_ACTIVE_START_HOUR;
  const cellHeight = (bottom - top) / activeHours;
  dates.forEach((date, dateIndex) => {
    for (let hour = VILLAGE_ACTIVE_START_HOUR; hour < VILLAGE_ACTIVE_END_HOUR; hour += 1) {
      const cell = cells.get(`${date}\u0000${hour}`) || { exact: 0, unresolved: 0 };
      const opacity = cell.exact ? .08 + .84 * (cell.exact / maxExact) : .025;
      const rect = svgElement("rect", {
        x: left + dateIndex * cellWidth,
        y: top + (hour - VILLAGE_ACTIVE_START_HOUR) * cellHeight,
        width: Math.max(.8, cellWidth - .5),
        height: Math.max(.8, cellHeight - .5),
        rx: 1,
        fill: `rgba(174, 80, 55, ${opacity})`
      });
      svgTitle(rect, `${date} ${villageHourLabel(hour)} PT · ${cell.exact} validated concurrent drift · ${cell.unresolved} unresolved-duration onsets`);
      svg.append(rect);
      if (cell.unresolved) {
        svg.append(svgElement("circle", {
          cx: left + (dateIndex + .5) * cellWidth,
          cy: top + (hour - VILLAGE_ACTIVE_START_HOUR + .5) * cellHeight,
          r: Math.min(3.2, 1.3 + Math.log2(cell.unresolved + 1)),
          fill: "#a77b2c"
        }));
      }
    }
    if (dateIndex % 7 === 0) {
      svg.append(svgElement("text", {
        x: left + (dateIndex + .5) * cellWidth,
        y: bottom + 16,
        "text-anchor": "end",
        class: "svg-label",
        transform: `rotate(-45 ${left + (dateIndex + .5) * cellWidth} ${bottom + 16})`
      }, date.slice(5)));
    }
  });
  [9, 11, 13, 15, 17].forEach((hour) => {
    svg.append(svgElement("text", { x: left - 8, y: top + (hour - VILLAGE_ACTIVE_START_HOUR) * cellHeight + 3, "text-anchor": "end", class: "svg-label" }, villageHourLabel(hour)));
  });
  svg.append(svgElement("text", { x: (left + right) / 2, y: 334, "text-anchor": "middle", class: "svg-title" }, "Village run date (Pacific Time)"));
  document.querySelector("#weather-meta").textContent = `${dates.length} Village days · 9 AM–5 PM PT`;
}

function median(values) {
  if (!values.length) return null;
  const sorted = [...values].sort((left, right) => left - right);
  const middle = Math.floor(sorted.length / 2);
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
}

function modelFamily(agent) {
  const name = String(agent || "");
  if (/^Claude\b|\(Claude Code\)/.test(name)) return "Claude (Anthropic)";
  if (/^GPT-|^o\d/.test(name)) return "GPT and o-series (OpenAI)";
  if (/^Gemini\b/.test(name)) return "Gemini (Google)";
  if (/^Grok\b/.test(name)) return "Grok (xAI)";
  if (/^DeepSeek\b/.test(name)) return "DeepSeek";
  if (/^Kimi\b/.test(name)) return "Kimi (Moonshot AI)";
  if (/^GLM\b/.test(name)) return "GLM (Zhipu AI)";
  if (/^Muse\b/.test(name)) return "Muse Spark (Meta)";
  return "Other";
}

function renderAgentFingerprints() {
  const periodsByName = new Map();
  goalPeriods.forEach((period) => {
    if (!periodsByName.has(period.agent)) periodsByName.set(period.agent, []);
    periodsByName.get(period.agent).push(period);
  });
  const profiles = [...periodsByName.entries()].map(([agent, periods]) => {
    const episodes = periods.flatMap((period) => period.episodes);
    const totalMs = periods.reduce((sum, period) => sum + period.durationMs, 0);
    const validatedMs = periods.reduce((sum, period) => sum + period.validatedMs, 0);
    const driftPositive = periods.filter((period) => period.episodes.length);
    const activeDays = new Set(episodes.map((episode) => localDateKey(episodeOnsetMs(episode))));
    const knownDurations = episodes.filter((episode) => episode.duration_seconds != null).map((episode) => Number(episode.duration_seconds));
    return {
      agent,
      episodeCount: episodes.length,
      raw: [
        episodes.length / Math.max(1, totalMs / DAY_MS) * 30,
        validatedMs / Math.max(1, totalMs),
        driftPositive.length ? driftPositive.reduce((sum, period) => sum + (1 - period.firstPosition), 0) / driftPositive.length : 0,
        activeDays.size / Math.max(1, totalMs / DAY_MS),
        knownDurations.length ? knownDurations.filter((seconds) => seconds >= 28800).length / knownDurations.length : 0,
        episodes.length ? episodes.filter((episode) => episode.duration_seconds == null).length / episodes.length : 0
      ]
    };
  }).filter((profile) => profile.episodeCount).sort((left, right) => right.episodeCount - left.episodeCount);
  const definitions = [
    ["Frequency", "episodes / 30 days"],
    ["Burden", "validated drift share"],
    ["Early onset", "earlier first drift"],
    ["Day spread", "share of goal days with drift"],
    ["Long-form", "validated episodes ≥8 hours"],
    ["Unresolved", "duration-unresolved share"]
  ];
  const maxima = definitions.map((_, index) => Math.max(.0001, ...profiles.map((profile) => profile.raw[index])));
  const container = document.querySelector("#fingerprint-grid");
  container.replaceChildren();
  const families = new Map();
  profiles.forEach((profile) => {
    const family = modelFamily(profile.agent);
    if (!families.has(family)) families.set(family, []);
    families.get(family).push(profile);
  });
  const familyEntries = [...families.entries()].sort((left, right) =>
    (left[0] === "Other" ? 1 : 0) - (right[0] === "Other" ? 1 : 0)
    || right[1].reduce((sum, profile) => sum + profile.episodeCount, 0) - left[1].reduce((sum, profile) => sum + profile.episodeCount, 0)
    || left[0].localeCompare(right[0]));
  const grids = new Map(familyEntries.map(([family, members]) => {
    const section = document.createElement("section");
    section.className = "fingerprint-family";
    const heading = document.createElement("h4");
    heading.className = "fingerprint-family-heading";
    heading.textContent = family;
    const count = document.createElement("span");
    const episodeTotal = members.reduce((sum, profile) => sum + profile.episodeCount, 0);
    count.textContent = `${members.length} ${members.length === 1 ? "agent" : "agents"} · ${episodeTotal} episodes`;
    heading.append(count);
    const grid = document.createElement("div");
    grid.className = "fingerprint-grid";
    section.append(heading, grid);
    container.append(section);
    return [family, grid];
  }));
  familyEntries.flatMap(([, members]) => members).forEach((profile) => {
    const card = document.createElement("article");
    card.className = "fingerprint-card";
    const name = document.createElement("div");
    name.className = "fingerprint-agent";
    name.textContent = agentLabel(profile.agent);
    const meta = document.createElement("div");
    meta.className = "fingerprint-meta";
    meta.textContent = `${profile.episodeCount} confirmed episodes`;
    const svg = svgElement("svg", { viewBox: "0 0 180 170", class: "fingerprint-svg", role: "img", "aria-label": `${profile.agent} drift fingerprint` });
    const centerX = 90, centerY = 82, radius = 58;
    const pointAt = (index, fraction) => {
      const angle = -Math.PI / 2 + (index / definitions.length) * Math.PI * 2;
      return [centerX + Math.cos(angle) * radius * fraction, centerY + Math.sin(angle) * radius * fraction];
    };
    [.33, .66, 1].forEach((ring) => {
      svg.append(svgElement("polygon", { points: definitions.map((_, index) => pointAt(index, ring).join(",")).join(" "), fill: "none", stroke: "#cfc1a6", "stroke-width": 1 }));
    });
    definitions.forEach((definition, index) => {
      const end = pointAt(index, 1);
      svg.append(svgElement("line", { x1: centerX, y1: centerY, x2: end[0], y2: end[1], stroke: "#d8ccb4", "stroke-width": 1 }));
      const textPoint = pointAt(index, 1.2);
      svg.append(svgElement("text", { x: textPoint[0], y: textPoint[1] + 3, "text-anchor": "middle", class: "svg-label" }, definition[0].split(" ").map((part) => part[0]).join("")));
    });
    const normalized = profile.raw.map((value, index) => Math.min(1, value / maxima[index]));
    const polygon = svgElement("polygon", { points: normalized.map((value, index) => pointAt(index, value).join(",")).join(" "), fill: "rgba(70,111,97,.25)", stroke: "#466f61", "stroke-width": 2 });
    svgTitle(polygon, definitions.map((definition, index) => `${definition[0]}: ${profile.raw[index] < .1 ? profile.raw[index].toFixed(3) : profile.raw[index].toFixed(2)}`).join("\n"));
    svg.append(polygon);
    card.append(name, meta, svg);
    grids.get(modelFamily(profile.agent)).append(card);
  });
  const legend = document.querySelector("#fingerprint-legend");
  legend.replaceChildren(...definitions.map(([labelText, copy]) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    item.textContent = `${labelText.split(" ").map((part) => part[0]).join("")} = ${copy}`;
    return item;
  }));
  document.querySelector("#fingerprint-meta").textContent = `${profiles.length} drift-positive agents in ${families.size} model families · axes normalized to observed maxima`;
}

const influenceSourceGroups = [
  { id: "self", label: "Self / internal", color: "#ae5037" },
  { id: "agent", label: "Village agent", color: "#3f7082" },
  { id: "human", label: "Human / external", color: "#a77b2c" },
  { id: "system", label: "Operator / system", color: "#74578f" }
];
const influenceColorByGroup = new Map(influenceSourceGroups.map((group) => [group.id, group.color]));

function influenceGroupFor(row) {
  const trigger = primaryManualTriggerAndContext(row.annotation).trigger;
  if (trigger === "agent_message_or_request") return "agent";
  if (["user_email", "user_message", "gitlab_issue_or_comment", "substack_message"].includes(trigger)) return "human";
  if (trigger === "operator_or_system_event") return "system";
  return "self";
}

function sourceActorFor(row) {
  const actor = String(row.annotation.trigger_actor || "").trim();
  if (actor) return actor;
  const trigger = primaryManualTriggerAndContext(row.annotation).trigger;
  const channelActors = {
    pause: "Self-directed pause",
    user_email: "Unidentified human email",
    user_message: "Unidentified human message",
    gitlab_issue_or_comment: "Unidentified GitLab request",
    substack_message: "Unidentified Substack message",
    agent_message_or_request: "Unidentified agent request",
    self_initiated_or_continuation: "Self-initiated",
    prior_goal_memory_carryover: "Prior-goal memory",
    self_authored_memory_constraint: "Self-authored memory constraint",
    proxy_substitution: "Proxy substitution",
    operator_or_system_event: "Operator/system",
    unknown: "Unknown source"
  };
  return channelActors[trigger] || label("trigger", trigger);
}

function appendInfluenceBar(container, { labelText, count, maxCount, segments, title }) {
  const row = document.createElement("div");
  row.className = "influence-bar-row";
  row.title = title || `${labelText}: ${count} reviewed episodes`;
  const labelNode = document.createElement("span");
  labelNode.className = "influence-bar-label";
  labelNode.textContent = labelText;
  const track = document.createElement("span");
  track.className = "influence-bar-track";
  segments.forEach(({ group, count: segmentCount }) => {
    if (!segmentCount) return;
    const fill = document.createElement("span");
    fill.className = "influence-bar-fill";
    fill.style.width = `${(segmentCount / maxCount) * 100}%`;
    fill.style.background = influenceColorByGroup.get(group) || "#8d8678";
    fill.title = `${influenceSourceGroups.find((candidate) => candidate.id === group)?.label || group}: ${segmentCount}`;
    track.append(fill);
  });
  const countNode = document.createElement("span");
  countNode.className = "influence-bar-count";
  countNode.textContent = String(count);
  row.append(labelNode, track, countNode);
  container.append(row);
}

function renderInfluenceBars() {
  const sourceCounts = new Map();
  const sourceGroup = new Map();
  const targetCounts = new Map();
  rows.forEach((row) => {
    const source = sourceActorFor(row);
    const target = row.episode.agent;
    const group = influenceGroupFor(row);
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + 1);
    if (!sourceGroup.has(source)) sourceGroup.set(source, group);
    if (!targetCounts.has(target)) targetCounts.set(target, new Map());
    const targetGroups = targetCounts.get(target);
    targetGroups.set(group, (targetGroups.get(group) || 0) + 1);
  });

  const sources = [...sourceCounts.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0]));
  const sourceList = document.querySelector("#trigger-source-bars");
  sourceList.replaceChildren();
  const maxSourceCount = Math.max(1, ...sources.map(([, count]) => count));
  sources.forEach(([source, count]) => appendInfluenceBar(sourceList, {
    labelText: agentLabel(source),
    count,
    maxCount: maxSourceCount,
    segments: [{ group: sourceGroup.get(source), count }]
  }));

  const targets = [...targetCounts.entries()].map(([agent, groups]) => ({
    agent,
    groups,
    count: [...groups.values()].reduce((sum, count) => sum + count, 0)
  })).sort((left, right) => right.count - left.count || left.agent.localeCompare(right.agent));
  const targetList = document.querySelector("#affected-agent-bars");
  targetList.replaceChildren();
  const maxTargetCount = Math.max(1, ...targets.map((target) => target.count));
  targets.forEach((target) => appendInfluenceBar(targetList, {
    labelText: agentLabel(target.agent),
    count: target.count,
    maxCount: maxTargetCount,
    segments: influenceSourceGroups.map((group) => ({ group: group.id, count: target.groups.get(group.id) || 0 })),
    title: `${agentLabel(target.agent)}: ${target.count} reviewed episodes\n${influenceSourceGroups.map((group) => `${group.label}: ${target.groups.get(group.id) || 0}`).join("\n")}`
  }));

  const legend = document.querySelector("#influence-legend");
  legend.replaceChildren(...influenceSourceGroups.map((group) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = group.color;
    item.append(swatch, document.createTextNode(group.label));
    return item;
  }));
  document.querySelector("#influence-meta").textContent = `${rows.length} reviewed episodes · ${sources.length} trigger sources · ${targets.length} affected agents`;
}

function isObservedRecovery(annotation) {
  return annotation.recovery_mechanisms.some((value) => !["not_corrected", "unknown"].includes(value));
}

function renderResilienceScorecards() {
  const reviewedByAgent = new Map();
  rows.forEach((row) => {
    if (!reviewedByAgent.has(row.episode.agent)) reviewedByAgent.set(row.episode.agent, []);
    reviewedByAgent.get(row.episode.agent).push(row);
  });
  const scorecards = [...reviewedByAgent.entries()].map(([agent, agentRows]) => {
    const recovered = agentRows.filter((row) => isObservedRecovery(row.annotation)).length;
    const selfCorrected = agentRows.filter((row) => row.annotation.recovery_mechanisms.includes("self_correction")).length;
    return { agent, reviewed: agentRows.length, recovered, selfCorrected };
  });
  const rate = (score, numerator) => numerator(score) / score.reviewed;
  const compareAgent = (left, right) => agentLabel(left.agent).localeCompare(agentLabel(right.agent));
  const sortMode = document.querySelector("#resilience-sort").value;
  const comparators = {
    recovery_rate: (left, right) => rate(right, (score) => score.recovered) - rate(left, (score) => score.recovered)
      || rate(right, (score) => score.selfCorrected) - rate(left, (score) => score.selfCorrected)
      || right.reviewed - left.reviewed
      || compareAgent(left, right),
    self_rate: (left, right) => rate(right, (score) => score.selfCorrected) - rate(left, (score) => score.selfCorrected)
      || right.selfCorrected - left.selfCorrected
      || rate(right, (score) => score.recovered) - rate(left, (score) => score.recovered)
      || compareAgent(left, right),
    self_count: (left, right) => right.selfCorrected - left.selfCorrected
      || rate(right, (score) => score.selfCorrected) - rate(left, (score) => score.selfCorrected)
      || right.reviewed - left.reviewed
      || compareAgent(left, right),
    pressure: (left, right) => right.reviewed - left.reviewed
      || rate(right, (score) => score.recovered) - rate(left, (score) => score.recovered)
      || compareAgent(left, right),
    agent: compareAgent
  };
  scorecards.sort(comparators[sortMode] || comparators.recovery_rate);
  const list = document.querySelector("#resilience-list");
  list.replaceChildren();
  scorecards.forEach((score, index) => {
    const row = document.createElement("div");
    row.className = "score-row";
    const rank = document.createElement("div");
    rank.className = "score-rank";
    rank.textContent = `#${index + 1}`;
    const agent = document.createElement("div");
    agent.className = "score-agent";
    agent.textContent = agentLabel(score.agent);
    const reviewed = document.createElement("div");
    reviewed.className = "score-value";
    reviewed.textContent = String(score.reviewed);
    const recoveryRate = score.recovered / score.reviewed;
    const selfRate = score.selfCorrected / score.reviewed;
    const track = document.createElement("div");
    track.className = "score-track";
    track.title = `${score.recovered} of ${score.reviewed} episodes recovered; ${score.selfCorrected} self-corrected`;
    const selfFill = document.createElement("span");
    selfFill.className = "score-fill is-self";
    selfFill.style.width = `${selfRate * 100}%`;
    const otherFill = document.createElement("span");
    otherFill.className = "score-fill";
    otherFill.style.width = `${Math.max(0, recoveryRate - selfRate) * 100}%`;
    track.append(selfFill, otherFill);
    const summary = document.createElement("div");
    summary.className = "score-summary";
    summary.textContent = `${Math.round(recoveryRate * 100)}% recovered · ${score.selfCorrected}/${score.recovered} self-corrected`;
    row.append(rank, agent, reviewed, track, summary);
    list.append(row);
  });
  document.querySelector("#resilience-meta").textContent = `${scorecards.length} agents · ${rows.length} reviewed episodes`;
}

function mechanismLabel(value) {
  const labels = {
    non_pursuit: "Non-pursuit",
    activity_changed: "Activity changed",
    relationship_changed: "Relationship changed",
    assignment_changed: "Assignment changed"
  };
  return labels[value] || String(value || "Unknown").replaceAll("_", " ");
}

const taxonomyRecoveryColors = {
  self_correction: "#466f61",
  finished_activity: "#81a27b",
  automatic_nudge: "#d19a5b",
  operator_nudge: "#b96043",
  operator_message: "#984b38",
  peer_feedback: "#3f7082",
  custom_peer_agent_message: "#5c8ca0",
  external_user_intervention: "#74578f",
  checking_email: "#667f9b",
  custom_scheduled_checkpoint_reached: "#a77b2c",
  end_of_day: "#8c7d68",
  natural_end_or_timeout: "#9c927f",
  not_corrected: "#c8c0ae",
  unknown: "#ded8ca"
};

function taxonomyRecoveryColor(recovery, index) {
  return taxonomyRecoveryColors[recovery]
    || burdenColors[index % burdenColors.length];
}

function renderTriggerTaxonomy() {
  const categoryById = new Map(triggerTaxonomyCategories.map((category) => [category.id, category]));
  const taxonomyRows = rows.map((row) => ({
    ...row,
    taxonomyId: triggerTaxonomyByEpisode.get(row.episodeId),
    primaryRecovery: row.annotation.recovery_mechanisms[0] || "unknown"
  }));
  const unassigned = taxonomyRows.filter((row) => !categoryById.has(row.taxonomyId));
  if (unassigned.length) {
    throw new Error(`Missing trigger-taxonomy assignments for ${unassigned.map((row) => row.episodeId).join(", ")}`);
  }

  const globalRecoveryCounts = new Map();
  taxonomyRows.forEach((row) => {
    globalRecoveryCounts.set(row.primaryRecovery, (globalRecoveryCounts.get(row.primaryRecovery) || 0) + 1);
  });
  const recoveryOrder = [...globalRecoveryCounts.entries()]
    .sort((left, right) => right[1] - left[1] || label("recovery", left[0]).localeCompare(label("recovery", right[0])))
    .map(([recovery]) => recovery);
  const recoveryColors = new Map(recoveryOrder.map((recovery, index) => [
    recovery,
    taxonomyRecoveryColor(recovery, index)
  ]));

  const rowsByCategory = new Map(triggerTaxonomyCategories.map((category) => [category.id, []]));
  taxonomyRows.forEach((row) => rowsByCategory.get(row.taxonomyId).push(row));
  const visibleCategories = triggerTaxonomyCategories.filter((category) => rowsByCategory.get(category.id).length);
  const maxCount = Math.max(1, ...visibleCategories.map((category) => rowsByCategory.get(category.id).length));
  const families = [];
  visibleCategories.forEach((category) => {
    let family = families.find((item) => item.name === category.family);
    if (!family) {
      family = { name: category.family, categories: [] };
      families.push(family);
    }
    family.categories.push(category);
  });

  const legend = document.querySelector("#taxonomy-legend");
  legend.replaceChildren(...recoveryOrder.map((recovery) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = recoveryColors.get(recovery);
    item.append(swatch, document.createTextNode(label("recovery", recovery)));
    return item;
  }));

  const chart = document.querySelector("#taxonomy-chart");
  chart.replaceChildren();
  families.forEach((family) => {
    const familySection = document.createElement("section");
    familySection.className = "taxonomy-family";
    const familyHeading = document.createElement("div");
    familyHeading.className = "taxonomy-family-heading";
    const familyName = document.createElement("h4");
    familyName.textContent = family.name;
    const familyTotal = document.createElement("span");
    const familyCount = family.categories.reduce(
      (total, category) => total + rowsByCategory.get(category.id).length,
      0
    );
    familyTotal.textContent = `${familyCount} episodes`;
    familyHeading.append(familyName, familyTotal);
    familySection.append(familyHeading);

    family.categories.forEach((category) => {
      const categoryRows = rowsByCategory.get(category.id);
      const recoveryCounts = new Map();
      categoryRows.forEach((row) => {
        recoveryCounts.set(row.primaryRecovery, (recoveryCounts.get(row.primaryRecovery) || 0) + 1);
      });
      const categoryRow = document.createElement("div");
      categoryRow.className = "taxonomy-row";
      const copy = document.createElement("div");
      const categoryLabel = document.createElement("div");
      categoryLabel.className = "taxonomy-label";
      categoryLabel.textContent = category.label;
      const description = document.createElement("div");
      description.className = "taxonomy-description";
      description.textContent = category.description;
      copy.append(categoryLabel, description);
      const track = document.createElement("div");
      track.className = "taxonomy-track";
      recoveryOrder.forEach((recovery) => {
        const count = recoveryCounts.get(recovery) || 0;
        if (!count) return;
        const segment = document.createElement("span");
        segment.className = "taxonomy-segment";
        segment.style.width = `${(count / maxCount) * 100}%`;
        segment.style.background = recoveryColors.get(recovery);
        segment.title = `${category.label} → ${label("recovery", recovery)}: ${count}`;
        track.append(segment);
      });
      const count = document.createElement("div");
      count.className = "taxonomy-count";
      count.textContent = String(categoryRows.length);
      categoryRow.append(copy, track, count);
      familySection.append(categoryRow);
    });
    chart.append(familySection);
  });

  const multiRecoveryCount = taxonomyRows.filter((row) => row.annotation.recovery_mechanisms.length > 1).length;
  document.querySelector("#taxonomy-total").textContent = `${visibleCategories.length} categories · ${taxonomyRows.length} episodes`;
  document.querySelector("#taxonomy-note").textContent = `Bar lengths show episode counts relative to the largest category; colors show the primary recorded correction mechanism. ${multiRecoveryCount} episodes also retain a secondary recovery label in their annotation.`;
}

function initializeExperimentalLenses() {
  renderDriftWeather();
  renderAgentFingerprints();
  renderInfluenceBars();
  renderResilienceScorecards();
  document.querySelector("#resilience-sort").addEventListener("change", renderResilienceScorecards);
  renderTriggerTaxonomy();
}

function renderEpisodeList() {
  const input = filteredRows().sort((left, right) => {
    const leftFollowUps = left.annotation.follow_ups.length;
    const rightFollowUps = right.annotation.follow_ups.length;
    if (leftFollowUps !== rightFollowUps) return rightFollowUps - leftFollowUps;
    const leftTime = left.episode.onset || left.episode.activity_start || "";
    const rightTime = right.episode.onset || right.episode.activity_start || "";
    return rightTime.localeCompare(leftTime);
  });
  const list = document.querySelector("#episode-list");
  list.replaceChildren();
  const followUpCount = input.filter((row) => row.annotation.follow_ups.length).length;
  const visible = input.slice(0, episodeListLimit);
  document.querySelector("#results-count").textContent = `Showing ${Math.min(visible.length, input.length)} of ${input.length}${followUpCount ? ` · ${followUpCount} with follow-ups first` : ""}`;
  const showMore = document.querySelector("#show-more");
  showMore.hidden = visible.length >= input.length;
  showMore.textContent = `Show ${Math.min(40, input.length - visible.length)} more`;
  if (!input.length) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.textContent = "No reviewed episodes match the selected filters.";
    list.append(empty);
    return;
  }
  visible.forEach((row) => {
    const item = document.createElement("article");
    item.className = `episode-row${row.annotation.follow_ups.length ? " has-follow-up" : ""}`;
    const identity = document.createElement("div");
    const agent = document.createElement("div");
    agent.className = "episode-agent";
    agent.textContent = agentLabel(row.episode.agent);
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
    if (row.annotation.follow_ups.length) {
      const followUps = document.createElement("div");
      followUps.className = "episode-followups";
      row.annotation.follow_ups.forEach((followUp) => {
        const chip = document.createElement("div");
        chip.className = "follow-up-chip";
        const type = document.createElement("strong");
        type.textContent = followUp.type === "replay_scenario"
          ? "Replay scenario"
          : followUp.type === "iteration_idea"
            ? "Iteration idea"
            : "Follow-up";
        chip.append(type, document.createTextNode(` · ${followUp.note || "No note supplied"}`));
        followUps.append(chip);
      });
      activityWrap.append(followUps);
    }

    const tags = document.createElement("div");
    tags.className = "episode-tags";
    row.annotation.trigger_categories.forEach((value) => {
      tags.append(tag(label("trigger", value), value === "pause"));
    });
    if (row.annotation.trigger_actor) tags.append(tag(`Actor: ${row.annotation.trigger_actor}`));
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
  renderEpisodeList();
}

document.querySelector("#clear-filters").addEventListener("click", () => {
  Object.keys(filters).forEach((key) => {
    filters[key] = "";
    selectByKey[key].value = "";
  });
  episodeListLimit = 40;
  render();
});

document.querySelector("#show-more").addEventListener("click", () => {
  episodeListLimit += 40;
  renderEpisodeList();
});

initializeExplorations();
initializeExperimentalLenses();
render();
