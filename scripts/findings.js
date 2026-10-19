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
const triggerTaxonomyLabels = new Map(triggerTaxonomyCategories.map((category) => [category.id, category.label]));
// Goal categories are optional; without them the atlas renders as one ungrouped list.
const goalCategories = categoryResponse.ok ? (await categoryResponse.json()).categories || [] : [];
// Operator corrections are optional too; each targeted correction becomes a marker on the agent's atlas row.
const humanContact = contactResponse.ok ? await contactResponse.json() : {};
// Self-authored rule tags (unreviewed keyword pass) are optional.
const rulesResponse = await fetch("./data/self_authored_rules_v1.json", fresh);
const selfAuthoredRules = rulesResponse.ok ? await rulesResponse.json() : {};
// Reviewed on-goal highlights per agent (optional).
const highlightsResponse = await fetch("./data/on_goal_highlights_v1.json", fresh);
const onGoalHighlights = highlightsResponse.ok ? await highlightsResponse.json() : {};
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
    not_corrected: "Not corrected",
    still_drifting_at_end_of_data: "Still drifting at end of data",
    continued_in_later_record: "Continued in a later record",
    switched_to_another_drift: "Switched to another drift"
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

// Drift hours for ranking. Bout-measured episodes use their bout sum; start-and-end-only
// spans are clipped to weekday Village hours (9 AM–5 PM PT, 16:00–24:00 UTC) and flagged as estimates.
const VILLAGE_DAY_UTC_START_HOUR = 16;
function driftHoursFor(episode) {
  const seconds = Number(episode.duration_seconds);
  if (!Number.isFinite(seconds) || seconds <= 0) return { hours: 0, estimated: false };
  if (episodeBouts(episode).length) return { hours: seconds / 3600, estimated: false };
  const startMs = episodeOnsetMs(episode);
  if (startMs == null) return { hours: 0, estimated: false };
  const endMs = startMs + seconds * 1000;
  let clipped = 0;
  for (let dayMs = Math.floor(startMs / DAY_MS) * DAY_MS; dayMs < endMs; dayMs += DAY_MS) {
    const weekday = new Date(dayMs).getUTCDay();
    if (weekday === 0 || weekday === 6) continue;
    const windowStart = dayMs + VILLAGE_DAY_UTC_START_HOUR * 3600000;
    clipped += Math.max(0, Math.min(endMs, dayMs + DAY_MS) - Math.max(startMs, windowStart));
  }
  return { hours: clipped / 3600000, estimated: clipped / 1000 < seconds - 1 };
}

function measureText(value, mode) {
  if (mode !== "hours") return String(value);
  if (value > 0 && value < .05) return "<0.1 h";
  return value >= 10 ? `${Math.round(value).toLocaleString()} h` : `${value.toFixed(1)} h`;
}

function hoursEstimateNote(inputRows) {
  const estimated = inputRows.filter((row) => driftHoursFor(row.episode).estimated);
  if (!estimated.length) return "";
  const hours = estimated.reduce((sum, row) => sum + driftHoursFor(row.episode).hours, 0);
  return `${estimated.length} start-and-end-only episodes (${measureText(hours, "hours")}) are clipped to weekday 9 AM–5 PM PT and are estimates.`;
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

// Village working hours: 9 AM–5 PM Pacific on weekdays the Village ran. Drift burden is measured
// against these hours rather than the 24/7 calendar, so goal periods are comparable however they fall.
const workingWindows = (() => {
  const pacificHour = new Intl.DateTimeFormat("en-US", { timeZone: "America/Los_Angeles", hour: "numeric", hourCycle: "h23" });
  const dates = [...new Set(goalMaxDays)].filter((date) => {
    const weekday = new Date(`${date}T12:00:00Z`).getUTCDay();
    return weekday >= 1 && weekday <= 5;
  });
  return dates.map((date) => {
    const noonUtc = Date.parse(`${date}T12:00:00Z`);
    const offsetHours = 12 - Number(pacificHour.format(new Date(noonUtc)));
    const startMs = Date.parse(`${date}T00:00:00Z`) + (9 + offsetHours) * 3600000;
    return { date, startMs, endMs: startMs + 8 * 3600000 };
  });
})();

function workingOverlapMs(startMs, endMs) {
  return workingWindows.reduce((total, window) =>
    total + Math.max(0, Math.min(endMs, window.endMs) - Math.max(startMs, window.startMs)), 0);
}

goalPeriods.forEach((period) => {
  period.durationMs = Math.max(1, period.endMs - period.startMs);
  period.workingMs = Math.max(1, workingOverlapMs(period.startMs, period.endMs));
  period.episodes.sort((left, right) => episodeOnsetMs(left) - episodeOnsetMs(right));
  period.exactIntervals = period.episodes.flatMap(episodeIntervals);
  period.mergedIntervals = mergedIntervals(period.exactIntervals, period.startMs, period.endMs);
  period.validatedMs = period.mergedIntervals.reduce(
    (total, interval) => total + Math.max(0, interval.endMs - interval.startMs), 0
  );
  period.validatedWorkingMs = period.mergedIntervals.reduce(
    (total, interval) => total + workingOverlapMs(interval.startMs, interval.endMs), 0
  );
  period.burdenShare = period.validatedWorkingMs / period.workingMs;
  period.unknownDurationCount = period.episodes.filter((episode) => !validatedInterval(episode)).length;
  const firstOnset = period.episodes.length ? episodeOnsetMs(period.episodes[0]) : null;
  period.firstPosition = firstOnset == null
    ? Infinity
    : Math.max(0, Math.min(1, (firstOnset - period.startMs) / period.durationMs));
});

const filters = {
  agent: "",
  trigger: "",
  taxonomy: "",
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
  taxonomy: document.querySelector("#taxonomy-filter"),
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
  if (kind === "taxonomy") return triggerTaxonomyLabels.get(value) || value;
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
fillSelect("taxonomy", uniqueValues((row) => [triggerTaxonomyByEpisode.get(row.episodeId)]), "taxonomy", "All taxonomy categories");
fillSelect("pause", uniqueValues((row) => [row.annotation.pause_context]), "pause", "All pause contexts");
fillSelect("request", uniqueValues((row) => [row.annotation.request_relationship]), "request_relationship", "All request relationships");
fillSelect("recovery", uniqueValues((row) => row.annotation.recovery_mechanisms), "recovery", "All recovery mechanisms");
fillSelect("source", uniqueValues((row) => [row.source]), "source", "All review sources");

function rowMatches(row) {
  return (!filters.agent || row.episode.agent === filters.agent)
    && (!filters.trigger || row.annotation.trigger_categories.includes(filters.trigger))
    && (!filters.taxonomy || triggerTaxonomyByEpisode.get(row.episodeId) === filters.taxonomy)
    && (!filters.pause || row.annotation.pause_context === filters.pause)
    && (!filters.request || row.annotation.request_relationship === filters.request)
    && (!filters.recovery || row.annotation.recovery_mechanisms.includes(filters.recovery))
    && (!filters.source || row.source === filters.source);
}

function filteredRows() {
  return rows.filter(rowMatches);
}

function countValues(inputRows, accessor, weight = () => 1) {
  const counts = new Map();
  inputRows.forEach((row) => {
    accessor(row).filter(Boolean).forEach((value) => {
      counts.set(value, (counts.get(value) || 0) + weight(row));
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
  // Report the same non-borderline queue that Manual Review actually renders.
  const visibleQueueIds = [...queueIds].filter((episodeId) => episodeById.has(episodeId));
  const reviewedInQueue = visibleQueueIds.filter((episodeId) => {
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
      `${reviewedInQueue} / ${visibleQueueIds.length}`,
      "Annotations completed among episodes still shown in Manual Review",
      reviewedInQueue / visibleQueueIds.length
    )
  );
}

// "episodes" counts how often a pattern leads to drift; "hours" sums how much drift it caused.
let breakdownMeasure = "episodes";
let influenceMeasure = "episodes";
const rowWeight = (mode) => (row) => (mode === "hours" ? driftHoursFor(row.episode).hours : 1);

function renderBarChart({ elementId, totalId, labelKind, accessor, chartClass }) {
  const input = rows;
  const counts = countValues(input, accessor, rowWeight(breakdownMeasure));
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
    countNode.textContent = measureText(count, breakdownMeasure);
    bar.append(labelNode, track, countNode);
    element.append(bar);
  });
  const totalHours = input.reduce((sum, row) => sum + driftHoursFor(row.episode).hours, 0);
  document.querySelector(totalId).textContent = breakdownMeasure === "hours"
    ? `${input.length} reviewed · ${measureText(totalHours, "hours")}`
    : `${input.length} reviewed`;
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
  stats.textContent = `${periods.length} goal period${periods.length === 1 ? "" : "s"} · median ${Number.isInteger(medianEpisodes) ? medianEpisodes : medianEpisodes.toFixed(1)} ep · median ${(medianShare * 100).toFixed(1)}% of working hours drifting`;
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

function goalAtlasAxis(startMs, endMs, axisPosition) {
  const row = document.createElement("div");
  row.className = "goal-strip-row goal-strip-axis";
  const track = document.createElement("div");
  track.className = "goal-strip-axis-track";
  const tick = (ms, text) => {
    const label = document.createElement("span");
    label.className = "goal-strip-axis-tick";
    label.style.left = `${axisPosition(ms)}%`;
    label.textContent = text;
    track.append(label);
  };
  const month = new Intl.DateTimeFormat("en-US", { month: "short", timeZone: "UTC" });
  const start = new Date(startMs);
  tick(startMs, new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "UTC" }).format(start));
  for (let date = new Date(Date.UTC(start.getUTCFullYear(), start.getUTCMonth() + 1, 1)); date.getTime() < endMs; date.setUTCMonth(date.getUTCMonth() + 1)) {
    // Skip a month label that would collide with the start label.
    if (axisPosition(date.getTime()) - axisPosition(startMs) > 4) tick(date.getTime(), month.format(date));
  }
  row.append(document.createElement("div"), track, document.createElement("div"));
  return row;
}

const expandedAtlasPeriods = new Set();
const reviewRowByEpisode = new Map(rows.map((row) => [row.episodeId, row]));

function atlasEpisodeTiming(episode, onsetMs = episodeOnsetMs(episode)) {
  const totalSeconds = episode.duration_seconds == null ? NaN : Number(episode.duration_seconds);
  // Bout totals are drift time, so show hours rather than calendar days.
  const totalText = Number.isFinite(totalSeconds) && totalSeconds >= 86400
    ? `${Math.round(totalSeconds / 3600)} hr`
    : formatDuration(totalSeconds);
  const bouts = episodeBouts(episode);
  const interval = bouts.length
    ? { startMs: bouts[0].startMs, endMs: bouts.at(-1).endMs }
    : validatedInterval(episode) || { startMs: onsetMs, endMs: null };
  // A bout that runs to the 5 PM PT close ends at 00:00 UTC, which belongs to the day before.
  const startDay = displayDay(new Date(interval.startMs).toISOString());
  const endDay = interval.endMs == null ? startDay : displayDay(new Date(Math.max(interval.startMs, interval.endMs - 1000)).toISOString());
  const timing = { interval, totalText, detailText: totalText, rangeText: endDay === startDay ? startDay : `${startDay} – ${endDay}`, unbroken: false, days: null };
  if (interval.endMs == null) return timing;
  // Without bouts, a span that crosses a session boundary cannot be split by day.
  if (!bouts.length && endDay !== startDay) {
    timing.unbroken = true;
    timing.detailText = `${totalText} · start and end only, no daily breakdown`;
    return timing;
  }
  // A short episode without bouts is one bout of drift on its day.
  timing.days = boutDays(bouts.length ? bouts : [interval]);
  if (bouts.length) {
    timing.detailText = `${totalText} drift on ${timing.days.size} ${timing.days.size === 1 ? "day" : "days"}`;
  }
  return timing;
}

function episodeLinkFor(episodeId) {
  const link = document.createElement("a");
  link.className = "episode-link";
  link.href = queueIds.has(episodeId)
    ? `review.html?scope=maximization&review=all#${encodeURIComponent(episodeId)}`
    : `index.html?scope=maximization#${encodeURIComponent(episodeId)}`;
  link.textContent = queueIds.has(episodeId) ? "Open review" : "Open evidence";
  // Open in a new tab so the findings page keeps its expanded cards and scroll position.
  link.target = "_blank";
  link.rel = "noopener";
  return link;
}

const driftEndLabels = {
  ongoing_at_evidence_end: "Still drifting when the evidence ends",
  returned_to_goal: "Returned to goal",
  activity_ended: "Activity ended"
};

function goalAtlasEpisodePanel(period, track) {
  const panel = document.createElement("div");
  panel.className = "goal-strip-detail";
  const list = document.createElement("ol");
  list.className = "atlas-episode-list";
  period.episodes.forEach((episode) => {
    const review = reviewRowByEpisode.get(episode.episode_id);
    const timing = atlasEpisodeTiming(episode);
    const item = document.createElement("li");
    item.className = "atlas-episode";
    item.dataset.episodeId = episode.episode_id;

    const when = document.createElement("div");
    when.className = "atlas-episode-when";
    const range = document.createElement("strong");
    range.textContent = timing.rangeText;
    const detail = document.createElement("span");
    detail.textContent = timing.detailText;
    when.append(range, detail);

    const what = document.createElement("div");
    const activity = document.createElement("div");
    activity.className = "atlas-episode-activity";
    activity.textContent = episode.activity;
    what.append(activity);
    const end = episode.drift_end || {};
    if (end.status || end.reason) {
      const ending = document.createElement("div");
      ending.className = "atlas-episode-end";
      const status = document.createElement("strong");
      status.textContent = driftEndLabels[end.status] || "End";
      ending.append(status);
      if (end.reason) ending.append(` · ${end.reason}`);
      what.append(ending);
    }

    const facts = document.createElement("dl");
    facts.className = "atlas-episode-facts";
    const fact = (term, value) => {
      if (!value) return;
      const dt = document.createElement("dt");
      dt.textContent = term;
      const dd = document.createElement("dd");
      dd.textContent = value;
      facts.append(dt, dd);
    };
    if (review) {
      const annotation = review.annotation;
      const official = triggerTaxonomyLabels.get(triggerTaxonomyByEpisode.get(episode.episode_id));
      fact("Trigger", [official || annotation.trigger_categories.map((value) => label("trigger", value)).join(", "), annotation.trigger_actor].filter(Boolean).join(" · "));
      fact("Request", annotation.request_relationship && label("request_relationship", annotation.request_relationship));
      fact("Pause", annotation.pause_context && label("pause", annotation.pause_context));
      fact("Recovery", annotation.recovery_mechanisms.map((value) => label("recovery", value)).join(", "));
    } else {
      fact("Review", "Not yet fully reviewed");
    }

    item.append(when, what, facts, episodeLinkFor(episode.episode_id));
    // Hovering an episode points at its bar in the row above.
    const bar = track.querySelector(`[data-episode-id="${CSS.escape(episode.episode_id)}"]`);
    item.addEventListener("mouseenter", () => bar?.classList.add("is-highlighted"));
    item.addEventListener("mouseleave", () => bar?.classList.remove("is-highlighted"));
    list.append(item);
  });
  panel.append(list);
  return panel;
}

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
  // Every row shares one calendar axis, so agents onboarded later show shorter goal windows.
  const axisStartMs = Math.min(...goalPeriods.map((period) => period.startMs));
  const axisEndMs = Math.max(...goalPeriods.map((period) => period.endMs));
  const axisPosition = (ms) => ((ms - axisStartMs) / Math.max(1, axisEndMs - axisStartMs)) * 100;
  atlas.append(goalAtlasAxis(axisStartMs, axisEndMs, axisPosition));
  goalAtlasGroups(sorted).forEach((group) => {
    if (group.category) atlas.append(goalAtlasGroupHeading(group));
    group.periods.forEach((period) => {
      const row = document.createElement("div");
      row.className = "goal-strip-row is-expandable";
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
      const goalWindow = document.createElement("span");
      goalWindow.className = "goal-strip-window";
      goalWindow.style.left = `${axisPosition(period.startMs)}%`;
      goalWindow.style.width = `${axisPosition(period.endMs) - axisPosition(period.startMs)}%`;
      goalWindow.dataset.tip = `Goal window · ${displayDay(new Date(period.startMs).toISOString())} – ${displayDay(new Date(period.endMs - 1000).toISOString())}`;
      track.append(goalWindow);
      period.episodes.forEach((episode) => {
        const onsetMs = episodeOnsetMs(episode);
        if (onsetMs == null) return;
        const reviewed = reviewedEpisodeIds.has(episode.episode_id);
        const timing = atlasEpisodeTiming(episode, onsetMs);
        const { interval } = timing;
        const position = (ms) => axisPosition(Math.max(period.startMs, Math.min(period.endMs, ms)));
        const left = position(interval.startMs);
        const bar = document.createElement("span");
        bar.className = `goal-strip-segment${interval.endMs == null ? " is-unknown" : ""}${reviewed ? " is-reviewed" : ""}${timing.unbroken ? " is-unbroken" : ""}`;
        bar.dataset.episodeId = episode.episode_id;
        bar.style.left = `${left}%`;
        if (interval.endMs != null) {
          bar.style.width = `${Math.max(.25, position(interval.endMs) - left)}%`;
          if (timing.days) bar.style.background = boutDayGradient(timing.days, interval);
        }
        bar.dataset.tip = `${shortText(episode.activity, 90)} · ${timing.rangeText} · ${timing.detailText}${reviewed ? " · human reviewed" : ""}`;
        track.append(bar);
      });
      (correctionsByAgent.get(period.agent) || []).forEach((correction) => {
        const correctionMs = timestampMs(correction.timestamp);
        if (correctionMs == null || correctionMs < period.startMs || correctionMs > period.endMs) return;
        const marker = document.createElement("span");
        marker.className = "goal-strip-correction";
        marker.style.left = `${axisPosition(correctionMs)}%`;
        marker.dataset.tip = `Operator correction · ${displayDay(correction.timestamp)} · ${correction.summary}`;
        track.append(marker);
      });
      const count = document.createElement("button");
      count.type = "button";
      count.className = "goal-strip-count goal-strip-toggle";
      count.textContent = `${period.episodes.length} ep`;
      count.setAttribute("aria-label", `${period.episodes.length} confirmed episodes for ${agentLabel(period.agent)}; show details`);
      row.append(identity, track, count);
      atlas.append(row);
      const setExpanded = (expanded) => {
        count.setAttribute("aria-expanded", String(expanded));
        row.classList.toggle("is-expanded", expanded);
        if (expanded) {
          expandedAtlasPeriods.add(period.id);
          if (!row.nextElementSibling?.classList.contains("goal-strip-detail")) row.after(goalAtlasEpisodePanel(period, track));
        } else {
          expandedAtlasPeriods.delete(period.id);
          if (row.nextElementSibling?.classList.contains("goal-strip-detail")) row.nextElementSibling.remove();
        }
      };
      setExpanded(expandedAtlasPeriods.has(period.id) && period.episodes.length > 0);
      if (!period.episodes.length) count.disabled = true;
      row.addEventListener("click", (event) => {
        if (!period.episodes.length) return;
        const bar = event.target.closest(".goal-strip-segment");
        // Clicking a bar opens the row and points at that episode instead of collapsing it.
        if (bar) {
          setExpanded(true);
          const item = row.nextElementSibling.querySelector(`[data-episode-id="${CSS.escape(bar.dataset.episodeId)}"]`);
          item?.scrollIntoView({ block: "nearest", behavior: "smooth" });
          item?.classList.add("is-highlighted");
          setTimeout(() => item?.classList.remove("is-highlighted"), 1600);
          return;
        }
        setExpanded(!row.classList.contains("is-expanded"));
      });
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
  addCartesianFrame(svg, { left, right, top, bottom, xTicks, yTicks, xScale, yScale, xLabel: "Confirmed episodes", yLabel: "Share of working hours drifting" });
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
    svgTitle(point, `${selected ? "" : "Excluded · "}${agentLabel(period.agent)} — ${period.goal}\n${grouping.label}\n${period.episodes.length} episodes; ${(period.burdenShare * 100).toFixed(1)}% of working hours spent drifting; ${period.unknownDurationCount} unresolved durations`);
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
  document.querySelector("#duration-meta").textContent = `${known.length} episodes with measured drift time`;
  document.querySelector("#duration-note").textContent = `${unknown} of ${goalMaxEpisodes.length} confirmed episodes have unresolved numeric drift time and are excluded. For bout-based episodes, the value is the sum of validated drift bouts—not the onset-to-end envelope. Percentages use the ${known.length} episodes with measured drift time.`;
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
    xScale, yScale, xLabel: "Position in goal window", yLabel: "Cumulative share of working hours"
  });
  let cumulative = 0;
  const points = [[xScale(0), yScale(0)]];
  period.mergedIntervals.forEach((interval) => {
    const startPosition = Math.max(0, Math.min(1, (interval.startMs - period.startMs) / period.durationMs));
    const endPosition = Math.max(0, Math.min(1, (interval.endMs - period.startMs) / period.durationMs));
    points.push([xScale(startPosition), yScale(cumulative)]);
    cumulative += workingOverlapMs(interval.startMs, interval.endMs) / period.workingMs;
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
  document.querySelector("#cumulative-note").textContent = `${agentLabel(period.agent)} · ${period.episodes.length} episodes · ${(period.burdenShare * 100).toFixed(1)}% of working hours spent drifting · ${period.unknownDurationCount} unresolved durations shown as diamonds.`;
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
  const mode = document.querySelector("#flow-measure").value;
  const weight = rowWeight(mode);
  const flowRows = rows.map((row) => ({
    ...primaryManualTriggerAndContext(row.annotation),
    recovery: row.annotation.recovery_mechanisms[0] || "unknown",
    weight: weight(row)
  })).filter((row) => row.weight > 0);
  const stages = [
    { key: "trigger", x: 175, label: (value) => label("trigger", value) },
    { key: "context", x: 580, label: contextLabel },
    { key: "recovery", x: 965, label: (value) => label("recovery", value) }
  ];
  const chartTop = 40, chartHeight = 540, nodeWidth = 14, gap = 9;
  // Order each column in groups so related nodes sit together and bands cross less:
  // triggers (pauses, outside requests, self-originated, operator/system), contexts (pause, request, none),
  // and endings (no outside input, after outside input, not a recovery).
  const SELF_ENDINGS = new Set(["self_correction", "finished_activity", "end_of_day"]);
  const groupOf = [
    (value) => (value === "pause" ? 0 : externalTriggerCategoryIds.has(value) ? 1 : value === "operator_or_system_event" ? 3 : 2),
    (value) => (value.startsWith("pause:") ? 0 : value.startsWith("request:") ? 1 : 2),
    (value) => (SELF_ENDINGS.has(value) ? 0 : NON_RECOVERY_ENDINGS.has(value) ? 2 : 1)
  ];
  const countsByStage = stages.map((stage, stageIndex) => countValues(flowRows, (row) => [row[stage.key]], (row) => row.weight)
    .sort((left, right) => groupOf[stageIndex](left[0]) - groupOf[stageIndex](right[0]) || right[1] - left[1]));
  const total = Math.max(.0001, flowRows.reduce((sum, row) => sum + row.weight, 0));
  const scale = Math.min(...countsByStage.map((counts) => (chartHeight - Math.max(0, counts.length - 1) * gap - 3 * 14) / total));
  const nodeMaps = stages.map(() => new Map());
  const groupGap = 14;
  countsByStage.forEach((counts, stageIndex) => {
    const groupBreaks = counts.filter((entry, index) => index && groupOf[stageIndex](entry[0]) !== groupOf[stageIndex](counts[index - 1][0])).length;
    const used = counts.reduce((sum, [, count]) => sum + count * scale, 0) + Math.max(0, counts.length - 1) * gap + groupBreaks * groupGap;
    let y = chartTop + (chartHeight - used) / 2;
    counts.forEach(([value, count], index) => {
      if (index && groupOf[stageIndex](value) !== groupOf[stageIndex](counts[index - 1][0])) y += groupGap;
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
      links.set(key, (links.get(key) || 0) + row.weight);
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
        const width = Math.max(mode === "hours" ? .5 : 1, link.count * scale);
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
        svgTitle(path, `${stages[stageIndex].label(link.source)} → ${stages[stageIndex + 1].label(link.target)}: ${measureText(link.count, mode)}`);
        svg.append(path);
        sourceOffsets.set(link.source, sourceOffset + width);
        targetOffsets.set(link.target, targetOffset + width);
      });
  }
  stages.forEach((stage, stageIndex) => {
    const heading = ["Trigger", "Trigger context", "Recovery"][stageIndex];
    svg.append(svgElement("text", { x: stage.x + nodeWidth / 2, y: 18, "text-anchor": "middle", class: "svg-title" }, heading));
    // Tiny nodes (common in hours mode) would stack their labels; keep at least 11px between them.
    let lastLabelY = -Infinity;
    nodeMaps[stageIndex].forEach((node) => {
      const rect = svgElement("rect", { x: node.x, y: node.y, width: nodeWidth, height: Math.max(1, node.height), rx: 4, fill: stageIndex === 1 ? "#3f7082" : stageIndex === 0 ? "#ae5037" : "#466f61" });
      svgTitle(rect, `${stage.label(node.value)}: ${measureText(node.count, mode)}`);
      svg.append(rect);
      const anchor = stageIndex === 0 ? "end" : "start";
      const textX = stageIndex === 0 ? node.x - 8 : node.x + nodeWidth + 8;
      const labelLength = stageIndex === 1 ? 38 : 28;
      const labelY = Math.max(node.y + Math.max(9, node.height / 2 + 3), lastLabelY + 11);
      lastLabelY = labelY;
      svg.append(svgElement("text", { x: textX, y: labelY, "text-anchor": anchor, class: "svg-label" }, `${shortText(stage.label(node.value), labelLength)} · ${measureText(node.count, mode)}`));
    });
  });
  document.querySelector("#flow-meta").textContent = mode === "hours"
    ? `${rows.length} reviewed episodes · ${measureText(total, mode)}`
    : `${rows.length} reviewed episodes`;
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
  document.querySelector("#flow-measure").addEventListener("change", renderAnnotationFlow);
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

// Bouts never cross a UTC day, which brackets one Village session.
function boutDays(bouts) {
  const days = new Map();
  bouts.forEach((bout) => {
    const date = new Date(bout.startMs).toISOString().slice(0, 10);
    days.set(date, (days.get(date) || 0) + (bout.endMs - bout.startMs) / 1000);
  });
  return days;
}

const SESSION_SECONDS = (VILLAGE_ACTIVE_END_HOUR - VILLAGE_ACTIVE_START_HOUR) * 3600;

// Shade each whole day of the episode by its share of a full session spent
// drifting, so drift that carries over from one session to the next reads as
// one continuous bar rather than daily stripes.
function boutDayGradient(days, interval) {
  const span = Math.max(1, interval.endMs - interval.startMs);
  const at = (ms) => `${(((Math.min(interval.endMs, Math.max(interval.startMs, ms)) - interval.startMs) / span) * 100).toFixed(3)}%`;
  const firstDayMs = Math.floor(interval.startMs / DAY_MS) * DAY_MS;
  const tiles = [];
  for (let dayMs = firstDayMs; dayMs < interval.endMs; dayMs += DAY_MS) {
    const weekday = new Date(dayMs).getUTCDay();
    const seconds = days.get(new Date(dayMs).toISOString().slice(0, 10));
    tiles.push({ dayMs, share: seconds ? Math.min(1, seconds / SESSION_SECONDS) : 0, weekend: weekday === 0 || weekday === 6 });
  }
  // Weekends have no session, so they inherit the lighter of the neighbouring weekdays.
  tiles.forEach((tile, index) => {
    if (!tile.weekend) return;
    const before = tiles.slice(0, index).reverse().find((other) => !other.weekend);
    const after = tiles.slice(index + 1).find((other) => !other.weekend);
    tile.share = before && after ? Math.min(before.share, after.share) : 0;
  });
  const stops = tiles.flatMap((tile) => {
    const color = `color-mix(in srgb, var(--rust) ${tile.share ? Math.round(30 + 70 * tile.share) : 14}%, transparent)`;
    return [`${color} ${at(tile.dayMs)}`, `${color} ${at(tile.dayMs + DAY_MS)}`];
  });
  return `linear-gradient(90deg, ${stops.join(", ")})`;
}

function villageHourLabel(hour) {
  if (hour === 12) return "12 PM";
  if (hour > 12) return `${hour - 12} PM`;
  return `${hour} AM`;
}

function renderDriftWeather() {
  // Village run days only: weekday dates. Saturday-dated logs are Friday evening's spill-over past midnight UTC.
  const isWeekday = (date) => {
    const weekday = new Date(`${date}T12:00:00Z`).getUTCDay();
    return weekday >= 1 && weekday <= 5;
  };
  const dates = [...new Set(goalMaxDays)].filter(isWeekday);
  const activeDateSet = new Set(dates);
  // Agents in a goal-maximization period on each day: the denominator for each cell's share.
  const activeAgentsByDate = new Map();
  bundle.stage1_daily_verdicts.forEach((row) => {
    if (row.period !== "goal_maximization" || !activeDateSet.has(row.day) || !row.agent) return;
    if (!activeAgentsByDate.has(row.day)) activeAgentsByDate.set(row.day, new Set());
    activeAgentsByDate.get(row.day).add(row.agent);
  });
  const cells = new Map();
  function cellFor(date, hour) {
    const key = `${date}\u0000${hour}`;
    if (!cells.has(key)) cells.set(key, { agents: new Set(), unresolved: 0 });
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
      const { date, hour } = villageDateAndHour(bucket + 1800000);
      if (!activeDateSet.has(date) || hour < VILLAGE_ACTIVE_START_HOUR || hour >= VILLAGE_ACTIVE_END_HOUR) return;
      cellFor(date, hour).agents.add(episode.agent);
    });
  });
  // Each cell's shade is the share of that day's active agents drifting in that hour.
  cells.forEach((cell, key) => {
    const date = key.split("\u0000")[0];
    cell.exact = cell.agents.size;
    cell.active = activeAgentsByDate.get(date)?.size || 0;
    cell.share = cell.active ? cell.exact / cell.active : 0;
  });

  const maxShare = Math.max(.01, ...[...cells.values()].map((cell) => cell.share));
  const svg = document.querySelector("#weather-chart");
  svg.replaceChildren();
  const left = 54, right = 1100, top = 30, bottom = 288;
  const cellWidth = (right - left) / dates.length;
  const activeHours = VILLAGE_ACTIVE_END_HOUR - VILLAGE_ACTIVE_START_HOUR;
  const cellHeight = (bottom - top) / activeHours;
  dates.forEach((date, dateIndex) => {
    for (let hour = VILLAGE_ACTIVE_START_HOUR; hour < VILLAGE_ACTIVE_END_HOUR; hour += 1) {
      const cell = cells.get(`${date}\u0000${hour}`) || { exact: 0, unresolved: 0, share: 0, active: activeAgentsByDate.get(date)?.size || 0 };
      const opacity = cell.exact ? .08 + .84 * (cell.share / maxShare) : .025;
      const rect = svgElement("rect", {
        x: left + dateIndex * cellWidth,
        y: top + (hour - VILLAGE_ACTIVE_START_HOUR) * cellHeight,
        width: Math.max(.8, cellWidth - .5),
        height: Math.max(.8, cellHeight - .5),
        rx: 1,
        fill: `rgba(174, 80, 55, ${opacity})`
      });
      svgTitle(rect, `${date} ${villageHourLabel(hour)} PT · ${cell.exact} of ${cell.active} active agents drifting (${Math.round(cell.share * 100)}%)${cell.unresolved ? ` · ${cell.unresolved} unresolved-duration onsets` : ""}`);
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

// Release order within a model family: public release dates for models that predate the Village,
// otherwise the day the model joined the Village (which follows its release closely).
const AGENT_RELEASE_DATES = {
  "Claude 3 Opus": "2024-03-04", "GPT-4o": "2024-05-13", "Claude 3.5 Sonnet": "2024-06-20",
  "o1": "2024-12-05", "Claude 3.7 Sonnet": "2025-02-24", "GPT-4.1": "2025-04-14", "o3": "2025-04-16",
  "Gemini 2.5 Pro": "2025-04-24", "o4-mini": "2025-05-22", "Claude Opus 4": "2025-05-23",
  "Claude Opus 4.1": "2025-08-18", "Grok 4": "2025-08-18", "GPT-5": "2025-08-18",
  "Claude Sonnet 4.5": "2025-09-30", "Claude Haiku 4.5": "2025-10-22", "GPT-5.1": "2025-11-14",
  "Gemini 3 Pro": "2025-11-19", "Claude Opus 4.5": "2025-11-25", "Opus 4.5 (Claude Code)": "2025-11-25",
  "DeepSeek-V3.2": "2025-12-04", "GPT-5.2": "2025-12-12", "Claude Opus 4.6": "2026-02-06",
  "Claude Sonnet 4.6": "2026-02-18", "Gemini 3.1 Pro": "2026-03-09", "GPT-5.4": "2026-03-16",
  "Claude Opus 4.7": "2026-04-17", "Kimi K2.6": "2026-04-22", "GPT-5.5": "2026-04-27",
  "Gemini 3.5 Flash": "2026-05-20", "Claude Opus 4.8": "2026-05-28", "Claude Fable 5": "2026-06-09",
  "Claude Sonnet 5": "2026-06-30", "DeepSeek-V4-Pro": "2026-07-02", "GLM-5.2": "2026-07-03",
  "GPT-5.6 Sol": "2026-07-09", "GPT-5.6 Terra": "2026-07-09", "GPT-5.6 Luna": "2026-07-09",
  "Grok 4.5": "2026-07-10", "Kimi K3": "2026-07-17", "Claude Opus 5": "2026-07-24",
  "GLM-5.3 Flash": "2026-08-28", "Claude Fable 5.1": "2026-09-01", "Muse Spark 1.3": "2026-09-03",
  "Gemini 3.8 Flash": "2026-09-03", "GPT-6 Astra": "2026-09-04", "GPT-6 Sol": "2026-09-22",
  "GPT-6 Luna": "2026-09-22", "Claude Opus 5.5": "2026-09-22", "Claude Sonnet 5.5": "2026-09-28",
  "GPT-6.1 Sol": "2026-09-29"
};

// Share of an agent's reviewed drift hours in episodes that ended in an observed recovery.
function recoveredHourShare(episodes) {
  let reviewed = 0;
  let recovered = 0;
  episodes.forEach((episode) => {
    const review = reviewRowByEpisode.get(episode.episode_id);
    if (!review) return;
    const { hours } = driftHoursFor(episode);
    reviewed += hours;
    if (isObservedRecovery(review.annotation)) recovered += hours;
  });
  return reviewed ? recovered / reviewed : 0;
}

// Share of an agent's reviewed drift hours in waiting episodes (pause trigger or a waiting taxonomy category).
function waitHourShare(episodes) {
  let reviewed = 0;
  let waiting = 0;
  episodes.forEach((episode) => {
    const review = reviewRowByEpisode.get(episode.episode_id);
    if (!review) return;
    const { hours } = driftHoursFor(episode);
    const taxonomy = triggerTaxonomyByEpisode.get(episode.episode_id) || "";
    reviewed += hours;
    if (review.annotation.trigger_categories.includes("pause") || taxonomy.startsWith("pause")
        || taxonomy === "memory_reinforced_waiting") waiting += hours;
  });
  return reviewed ? waiting / reviewed : 0;
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
    const validatedMs = periods.reduce((sum, period) => sum + period.validatedWorkingMs, 0);
    const workingMs = periods.reduce((sum, period) => sum + period.workingMs, 0);
    const driftPositive = periods.filter((period) => period.episodes.length);
    const knownDurations = episodes.filter((episode) => episode.duration_seconds != null).map((episode) => Number(episode.duration_seconds));
    return {
      agent,
      episodeCount: episodes.length,
      raw: [
        episodes.length / Math.max(1, totalMs / DAY_MS) * 30,
        validatedMs / Math.max(1, workingMs),
        driftPositive.length ? driftPositive.reduce((sum, period) => sum + (1 - period.firstPosition), 0) / driftPositive.length : 0,
        waitHourShare(episodes),
        knownDurations.length ? knownDurations.filter((seconds) => seconds >= 28800).length / knownDurations.length : 0,
        recoveredHourShare(episodes)
      ]
    };
  }).filter((profile) => profile.episodeCount).sort((left, right) => right.episodeCount - left.episodeCount);
  const definitions = [
    ["Frequency", "episodes / 30 days"],
    ["Burden", "share of working hours spent drifting"],
    ["Early onset", "earlier first drift"],
    ["Wait", "share of reviewed drift hours spent pausing or waiting"],
    ["Long-form", "validated episodes ≥8 hours"],
    ["Recovery", "share of reviewed drift hours that ended in a recovery"]
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
  // Within a family, earlier releases come first; agents without a known date go last.
  families.forEach((members) => members.sort((left, right) =>
    (AGENT_RELEASE_DATES[left.agent] || "9999").localeCompare(AGENT_RELEASE_DATES[right.agent] || "9999")
    || left.agent.localeCompare(right.agent)));
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
  row.title = title || `${labelText}: ${measureText(count, influenceMeasure)}${influenceMeasure === "hours" ? " of drift" : " reviewed episodes"}`;
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
    fill.title = `${influenceSourceGroups.find((candidate) => candidate.id === group)?.label || group}: ${measureText(segmentCount, influenceMeasure)}`;
    track.append(fill);
  });
  const countNode = document.createElement("span");
  countNode.className = "influence-bar-count";
  countNode.textContent = measureText(count, influenceMeasure);
  row.append(labelNode, track, countNode);
  container.append(row);
}

function renderInfluenceBars() {
  const sourceCounts = new Map();
  const sourceGroup = new Map();
  const targetCounts = new Map();
  const weight = rowWeight(influenceMeasure);
  rows.forEach((row) => {
    const source = sourceActorFor(row);
    const target = row.episode.agent;
    const group = influenceGroupFor(row);
    sourceCounts.set(source, (sourceCounts.get(source) || 0) + weight(row));
    if (!sourceGroup.has(source)) sourceGroup.set(source, group);
    if (!targetCounts.has(target)) targetCounts.set(target, new Map());
    const targetGroups = targetCounts.get(target);
    targetGroups.set(group, (targetGroups.get(group) || 0) + weight(row));
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
    title: `${agentLabel(target.agent)}: ${measureText(target.count, influenceMeasure)}${influenceMeasure === "hours" ? " of drift" : " reviewed episodes"}\n${influenceSourceGroups.map((group) => `${group.label}: ${measureText(target.groups.get(group.id) || 0, influenceMeasure)}`).join("\n")}`
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
  const hoursMode = influenceMeasure === "hours";
  document.querySelector("#trigger-source-rank").textContent = hoursMode ? "Ranked by drift hours" : "Ranked by reviewed episodes";
  document.querySelector("#affected-agent-rank").textContent = hoursMode ? "Stacked drift hours" : "Stacked episode counts";
  document.querySelector("#influence-estimate-note").textContent = hoursMode ? hoursEstimateNote(rows) : "";
}

// Endings that are not a return to the goal: the drift persisted, carried on, or gave way to another drift.
const NON_RECOVERY_ENDINGS = new Set([
  "not_corrected", "unknown", "still_drifting_at_end_of_data", "continued_in_later_record", "switched_to_another_drift"
]);

function isObservedRecovery(annotation) {
  return annotation.recovery_mechanisms.some((value) => !NON_RECOVERY_ENDINGS.has(value));
}

function renderResilienceScorecards() {
  const reviewedByAgent = new Map();
  rows.forEach((row) => {
    if (!reviewedByAgent.has(row.episode.agent)) reviewedByAgent.set(row.episode.agent, []);
    reviewedByAgent.get(row.episode.agent).push(row);
  });
  const mode = document.querySelector("#resilience-measure").value;
  const weight = rowWeight(mode);
  const total = (input) => input.reduce((sum, row) => sum + weight(row), 0);
  const scorecards = [...reviewedByAgent.entries()].map(([agent, agentRows]) => {
    const recovered = total(agentRows.filter((row) => isObservedRecovery(row.annotation)));
    const selfCorrected = total(agentRows.filter((row) => row.annotation.recovery_mechanisms.includes("self_correction")));
    return { agent, reviewed: total(agentRows), recovered, selfCorrected };
  }).filter((score) => score.reviewed > 0);
  const minimumReviewed = mode === "hours" ? 5 : 5;
  scorecards.forEach((score) => {
    score.rateEligible = score.reviewed >= minimumReviewed;
  });
  const rate = (score, numerator) => numerator(score) / score.reviewed;
  const compareAgent = (left, right) => agentLabel(left.agent).localeCompare(agentLabel(right.agent));
  const sortMode = document.querySelector("#resilience-sort").value;
  const rateSort = sortMode === "recovery_rate" || sortMode === "self_rate";
  const eligibleFirst = (left, right) => Number(right.rateEligible) - Number(left.rateEligible);
  const comparators = {
    recovery_rate: (left, right) => eligibleFirst(left, right)
      || rate(right, (score) => score.recovered) - rate(left, (score) => score.recovered)
      || rate(right, (score) => score.selfCorrected) - rate(left, (score) => score.selfCorrected)
      || right.reviewed - left.reviewed
      || compareAgent(left, right),
    self_rate: (left, right) => eligibleFirst(left, right)
      || rate(right, (score) => score.selfCorrected) - rate(left, (score) => score.selfCorrected)
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
  let eligibleRank = 0;
  scorecards.forEach((score, index) => {
    const row = document.createElement("div");
    row.className = "score-row";
    if (rateSort && !score.rateEligible) row.classList.add("is-small-sample");
    const rank = document.createElement("div");
    rank.className = "score-rank";
    if (!rateSort || score.rateEligible) eligibleRank += 1;
    rank.textContent = rateSort && !score.rateEligible ? "—" : `#${rateSort ? eligibleRank : index + 1}`;
    const agent = document.createElement("div");
    agent.className = "score-agent";
    agent.textContent = agentLabel(score.agent);
    const reviewed = document.createElement("div");
    reviewed.className = "score-value";
    reviewed.textContent = measureText(score.reviewed, mode);
    const recoveryRate = score.recovered / score.reviewed;
    const selfRate = score.selfCorrected / score.reviewed;
    const track = document.createElement("div");
    track.className = "score-track";
    track.title = mode === "hours"
      ? `${measureText(score.recovered, mode)} of ${measureText(score.reviewed, mode)} of drift ended in a recovery; ${measureText(score.selfCorrected, mode)} self-corrected`
      : `${score.recovered} of ${score.reviewed} episodes recovered; ${score.selfCorrected} self-corrected`;
    const selfFill = document.createElement("span");
    selfFill.className = "score-fill is-self";
    selfFill.style.width = `${selfRate * 100}%`;
    const otherFill = document.createElement("span");
    otherFill.className = "score-fill";
    otherFill.style.width = `${Math.max(0, recoveryRate - selfRate) * 100}%`;
    track.append(selfFill, otherFill);
    const summary = document.createElement("div");
    summary.className = "score-summary";
    const summaryText = mode === "hours"
      ? `${Math.round(recoveryRate * 100)}% of hours recovered · ${Math.round(selfRate * 100)}% self-corrected`
      : `${Math.round(recoveryRate * 100)}% recovered · ${score.selfCorrected}/${score.recovered} self-corrected`;
    summary.textContent = `${rateSort && !score.rateEligible ? "Small sample · " : ""}${summaryText}`;
    row.append(rank, agent, reviewed, track, summary);
    list.append(row);
  });
  document.querySelector("#resilience-reviewed-heading").textContent = mode === "hours" ? "Reviewed drift hours" : "Reviewed episodes";
  document.querySelector("#resilience-self-count-option").textContent = mode === "hours" ? "Most self-corrected drift hours" : "Most self-corrected episodes";
  document.querySelector("#resilience-meta").textContent = `${scorecards.length} agents · ${rows.length} reviewed episodes`;
  const thresholdNote = rateSort
    ? ` Rate rankings require at least ${mode === "hours" ? "5 reviewed drift hours" : "5 reviewed episodes"}; smaller samples remain visible but unranked.`
    : "";
  document.querySelector("#resilience-note").textContent = (mode === "hours"
    ? `Every bar represents 100% of that agent’s reviewed drift hours; colored segments show the share of those hours in episodes that ended in an observed recovery. ${hoursEstimateNote(rows)}`.trim()
    : "Every bar represents 100% of that agent’s fully reviewed episodes. Episode count indicates distraction pressure; colored segments show the subset with an observed recovery.") + thresholdNote;
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

  const mode = document.querySelector("#taxonomy-measure").value;
  const weight = rowWeight(mode);
  const weightOf = (input) => input.reduce((sum, row) => sum + weight(row), 0);
  const rowsByCategory = new Map(triggerTaxonomyCategories.map((category) => [category.id, []]));
  taxonomyRows.forEach((row) => rowsByCategory.get(row.taxonomyId).push(row));
  const visibleCategories = triggerTaxonomyCategories.filter((category) => rowsByCategory.get(category.id).length);
  const families = [];
  visibleCategories.forEach((category) => {
    let family = families.find((item) => item.name === category.family);
    if (!family) {
      family = { name: category.family, categories: [] };
      families.push(family);
    }
    family.categories.push(category);
  });

  const key = document.querySelector("#taxonomy-key");
  const keyLabel = document.createElement("span");
  keyLabel.textContent = "Within-category share";
  const zero = document.createElement("span");
  zero.textContent = "0%";
  const gradient = document.createElement("span");
  gradient.className = "taxonomy-key-gradient";
  const full = document.createElement("span");
  full.textContent = "100%";
  key.replaceChildren(keyLabel, zero, gradient, full);

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
      (total, category) => total + weightOf(rowsByCategory.get(category.id)),
      0
    );
    familyTotal.textContent = mode === "hours" ? `${measureText(familyCount, mode)} of drift` : `${familyCount} episodes`;
    familyHeading.append(familyName, familyTotal);
    familySection.append(familyHeading);

    const gridWrap = document.createElement("div");
    gridWrap.className = "taxonomy-grid-wrap";
    const heatmap = document.createElement("div");
    heatmap.className = "taxonomy-heatmap";
    heatmap.style.gridTemplateColumns = `minmax(260px, 1.8fr) repeat(${recoveryOrder.length}, minmax(58px, .55fr)) 52px`;
    const categoryHeader = document.createElement("div");
    categoryHeader.className = "taxonomy-column-label is-category";
    categoryHeader.textContent = "Trigger category";
    heatmap.append(categoryHeader);
    recoveryOrder.forEach((recovery) => {
      const header = document.createElement("div");
      header.className = "taxonomy-column-label";
      header.textContent = label("recovery", recovery);
      heatmap.append(header);
    });
    const totalHeader = document.createElement("div");
    totalHeader.className = "taxonomy-column-label";
    totalHeader.textContent = "Total";
    heatmap.append(totalHeader);

    family.categories.forEach((category) => {
      const categoryRows = rowsByCategory.get(category.id);
      const recoveryCounts = new Map();
      const categoryTotal = weightOf(categoryRows);
      categoryRows.forEach((row) => {
        recoveryCounts.set(row.primaryRecovery, (recoveryCounts.get(row.primaryRecovery) || 0) + weight(row));
      });
      const copy = document.createElement("div");
      copy.className = "taxonomy-category-cell";
      const categoryLabel = document.createElement("div");
      categoryLabel.className = "taxonomy-label";
      categoryLabel.textContent = category.label;
      const description = document.createElement("div");
      description.className = "taxonomy-description";
      description.textContent = category.description;
      copy.append(categoryLabel, description);
      heatmap.append(copy);
      recoveryOrder.forEach((recovery) => {
        const count = recoveryCounts.get(recovery) || 0;
        const share = categoryTotal ? count / categoryTotal : 0;
        const cell = document.createElement("div");
        cell.className = `taxonomy-cell${count ? "" : " is-zero"}${share >= .62 ? " is-strong" : ""}`;
        cell.style.setProperty("--heat", count ? (.08 + share * .78).toFixed(3) : "0.025");
        cell.title = `${category.label} → ${label("recovery", recovery)}: ${measureText(count, mode)} of ${measureText(categoryTotal, mode)} (${Math.round(share * 100)}%)`;
        const value = document.createElement("strong");
        value.textContent = count ? measureText(count, mode) : "—";
        cell.append(value);
        if (count) {
          const percentage = document.createElement("span");
          percentage.textContent = `${Math.round(share * 100)}%`;
          cell.append(percentage);
        }
        heatmap.append(cell);
      });
      const count = document.createElement("div");
      count.className = "taxonomy-total-cell";
      count.textContent = measureText(categoryTotal, mode);
      heatmap.append(count);
    });
    gridWrap.append(heatmap);
    familySection.append(gridWrap);
    chart.append(familySection);
  });

  const multiRecoveryCount = taxonomyRows.filter((row) => row.annotation.recovery_mechanisms.length > 1).length;
  document.querySelector("#taxonomy-total").textContent = `${visibleCategories.length} categories · ${taxonomyRows.length} episodes`;
  const unit = mode === "hours" ? "drift hours" : "episode count";
  document.querySelector("#taxonomy-note").textContent = `Cell shading represents the share within each trigger category; every populated cell shows its ${unit} and percentage, and the final column gives the category total. ${multiRecoveryCount} episodes also retain a secondary recovery label in their annotation. ${mode === "hours" ? hoursEstimateNote(taxonomyRows) : ""}`.trim();
}

// ---------------------------------------------------------------------------
// Drift dynamics: every chart compares how often (episodes) with how much (drift hours).
// ---------------------------------------------------------------------------
const OUTSIDE_TRIGGERS = new Set(["agent_message_or_request", "gitlab_issue_or_comment", "user_email", "user_message", "substack_message", "operator_or_system_event"]);
const ORIGIN_GROUPS = [
  { id: "outside", label: "Outside input (peer, human or operator)", color: "#3f7082" },
  { id: "pause", label: "Pause", color: "#a77b2c" },
  { id: "self", label: "Self-originated (proxy, own rule, own initiative)", color: "#ae5037" }
];
const ORIGIN_BY_ID = new Map(ORIGIN_GROUPS.map((group) => [group.id, group]));

function triggerOriginFor(annotation) {
  const triggers = new Set(annotation.trigger_categories || []);
  if ([...triggers].some((trigger) => OUTSIDE_TRIGGERS.has(trigger))) return "outside";
  return triggers.has("pause") ? "pause" : "self";
}

function hoursOf(row) {
  return driftHoursFor(row.episode).hours;
}

function percentText(value) {
  return `${Math.round(value * 100)}%`;
}

// One row per category: a bar for its share of episodes and a bar for its share of drift hours.
// Shares default to the sum over items; pass totals when rows overlap (e.g. cumulative time windows).
function renderPairedBars(container, items, { showCounts = true, totalEpisodes = null, totalHours = null } = {}) {
  container.replaceChildren();
  totalEpisodes = totalEpisodes || items.reduce((sum, item) => sum + item.episodes, 0) || 1;
  totalHours = totalHours || items.reduce((sum, item) => sum + item.hours, 0) || 1;
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "pair-row";
    const name = document.createElement("span");
    name.className = "pair-label";
    name.textContent = item.label;
    const bars = document.createElement("span");
    bars.className = "pair-bars";
    [["episodes", item.episodes / totalEpisodes, `${item.episodes} ${item.episodes === 1 ? "episode" : "episodes"}`], ["hours", item.hours / totalHours, measureText(item.hours, "hours")]]
      .forEach(([kind, share, value]) => {
        const line = document.createElement("span");
        line.className = `pair-line is-${kind}`;
        const track = document.createElement("span");
        track.className = "pair-track";
        const fill = document.createElement("span");
        fill.className = "pair-fill";
        fill.style.width = `${share * 100}%`;
        if (item.color) fill.style.background = item.color;
        track.append(fill);
        const text = document.createElement("span");
        text.className = "pair-value";
        text.textContent = showCounts ? `${percentText(share)} · ${value}` : percentText(share);
        line.append(track, text);
        bars.append(line);
      });
    row.append(name, bars);
    row.title = `${item.label}: ${item.episodes} episodes (${percentText(item.episodes / totalEpisodes)}) · ${measureText(item.hours, "hours")} (${percentText(item.hours / totalHours)})`;
    container.append(row);
  });
}

function pairedLegend() {
  return '<span class="legend-item"><span class="legend-swatch pair-swatch is-episodes"></span>Share of episodes (how often)</span>'
    + '<span class="legend-item"><span class="legend-swatch pair-swatch is-hours"></span>Share of drift hours (how much)</span>';
}

function renderTriggerOrigin() {
  const totals = new Map(ORIGIN_GROUPS.map((group) => [group.id, { ...group, episodes: 0, hours: 0 }]));
  const byAgent = new Map();
  rows.forEach((row) => {
    const origin = triggerOriginFor(row.annotation);
    const hours = hoursOf(row);
    const total = totals.get(origin);
    total.episodes += 1;
    total.hours += hours;
    if (!byAgent.has(row.episode.agent)) byAgent.set(row.episode.agent, new Map(ORIGIN_GROUPS.map((group) => [group.id, { episodes: 0, hours: 0 }])));
    const cell = byAgent.get(row.episode.agent).get(origin);
    cell.episodes += 1;
    cell.hours += hours;
  });
  renderPairedBars(document.querySelector("#origin-pairs"), [...totals.values()]);
  document.querySelector("#origin-legend").innerHTML = pairedLegend();

  const mode = document.querySelector("#origin-measure").value;
  const key = mode === "hours" ? "hours" : "episodes";
  const list = document.querySelector("#origin-agents");
  list.replaceChildren();
  const agents = [...byAgent.entries()]
    .map(([agent, groups]) => ({ agent, groups, total: [...groups.values()].reduce((sum, cell) => sum + cell[key], 0) }))
    .filter((entry) => entry.total > 0)
    .sort((left, right) => right.total - left.total || left.agent.localeCompare(right.agent));
  agents.forEach((entry) => {
    const row = document.createElement("div");
    row.className = "origin-row";
    const name = document.createElement("span");
    name.className = "influence-bar-label";
    name.textContent = agentLabel(entry.agent);
    const track = document.createElement("span");
    track.className = "origin-track";
    ORIGIN_GROUPS.forEach((group) => {
      const share = entry.groups.get(group.id)[key] / entry.total;
      if (!share) return;
      const fill = document.createElement("span");
      fill.style.width = `${share * 100}%`;
      fill.style.background = group.color;
      fill.title = `${group.label}: ${measureText(entry.groups.get(group.id)[key], mode)} (${percentText(share)})`;
      track.append(fill);
    });
    const value = document.createElement("span");
    value.className = "influence-bar-count";
    value.textContent = measureText(entry.total, mode);
    row.append(name, track, value);
    list.append(row);
  });
  document.querySelector("#origin-agent-legend").replaceChildren(...ORIGIN_GROUPS.map((group) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = group.color;
    item.append(swatch, document.createTextNode(group.label));
    return item;
  }));
  document.querySelector("#origin-meta").textContent = `${rows.length} reviewed episodes`;
}

const WAIT_VERDICT_LABELS = {
  goal_tied: "Goal-tied wait",
  pretextual: "Pretextual wait (own rule or exemption)",
  unrelated: "Unrelated wait",
  mixed: "Mixed"
};

function renderJustifications() {
  const verdicts = new Map(Object.keys(WAIT_VERDICT_LABELS).map((id) => [id, { label: WAIT_VERDICT_LABELS[id], episodes: 0, hours: 0 }]));
  goalMaxEpisodes.forEach((episode) => {
    const review = episode.wait_review;
    if (!review || !verdicts.has(review.verdict)) return;
    const entry = verdicts.get(review.verdict);
    entry.episodes += 1;
    entry.hours += driftHoursFor(episode).hours;
  });
  renderPairedBars(document.querySelector("#verdict-pairs"), [...verdicts.values()].filter((entry) => entry.episodes));
  const ruleLabels = selfAuthoredRules.rules || {};
  const rules = new Map(Object.entries(ruleLabels).map(([id, ruleLabel]) => [id, { label: ruleLabel, episodes: 0, hours: 0 }]));
  const byEpisode = new Map(goalMaxEpisodes.map((episode) => [episode.episode_id, episode]));
  Object.entries(selfAuthoredRules.episodes || {}).forEach(([episodeId, tags]) => {
    const episode = byEpisode.get(episodeId);
    if (!episode) return;
    tags.forEach((tag) => {
      const entry = rules.get(tag.rule);
      if (!entry) return;
      entry.episodes += 1;
      entry.hours += driftHoursFor(episode).hours;
    });
  });
  renderPairedBars(document.querySelector("#rule-pairs"), [...rules.values()].filter((entry) => entry.episodes)
    .sort((left, right) => right.hours - left.hours));
  document.querySelector("#justification-legend").innerHTML = pairedLegend();
  const reviewed = [...verdicts.values()].reduce((sum, entry) => sum + entry.episodes, 0);
  const tagged = Object.keys(selfAuthoredRules.episodes || {}).length;
  document.querySelector("#justification-meta").textContent = `${reviewed} reviewed waits · ${tagged} episodes citing a rule`;
}

function renderRecoveryCurves() {
  const durations = goalMaxEpisodes.map((episode) => driftHoursFor(episode).hours).filter((hours) => hours > 0).sort((left, right) => left - right);
  const totalHours = durations.reduce((sum, hours) => sum + hours, 0);
  const svg = document.querySelector("#recovery-curve");
  svg.replaceChildren();
  const left = 62, right = 620, top = 24, bottom = 272;
  const minLog = Math.log10(1 / 60), maxLog = Math.log10(Math.max(2, durations.at(-1)));
  const xScale = (hours) => left + (Math.log10(Math.max(1 / 60, hours)) - minLog) / (maxLog - minLog) * (right - left);
  const yScale = (share) => bottom - share * (bottom - top);
  const ticks = [[1 / 60, "1 min"], [10 / 60, "10 min"], [1, "1 h"], [8, "8 h"], [40, "40 h"], [200, "200 h"]].filter(([hours]) => hours <= 10 ** maxLog);
  addCartesianFrame(svg, {
    left, right, top, bottom,
    xTicks: ticks.map(([value, tickLabel]) => ({ value, label: tickLabel })),
    yTicks: [0, .25, .5, .75, 1].map((value) => ({ value, label: `${value * 100}%` })),
    xScale, yScale, xLabel: "Measured drift time (log scale)", yLabel: "Share above threshold"
  });
  const episodePoints = [], hourPoints = [];
  let remainingHours = totalHours;
  durations.forEach((hours, index) => {
    const x = xScale(hours);
    episodePoints.push([x, yScale((durations.length - index) / durations.length)], [x, yScale((durations.length - index - 1) / durations.length)]);
    hourPoints.push([x, yScale(remainingHours / totalHours)]);
    remainingHours -= hours;
    hourPoints.push([x, yScale(remainingHours / totalHours)]);
  });
  [[episodePoints, "#3f7082", "Episodes"], [hourPoints, "#ae5037", "Drift hours"]].forEach(([points, color, name]) => {
    const line = svgElement("polyline", { points: [[left, yScale(1)], ...points].map((point) => point.join(",")).join(" "), fill: "none", stroke: color, "stroke-width": 2.5 });
    svgTitle(line, name);
    svg.append(line);
  });
  const median = durations[Math.floor(durations.length / 2)];
  let cumulative = 0, weightedMedian = 0;
  for (const hours of durations) {
    cumulative += hours;
    if (cumulative >= totalHours / 2) { weightedMedian = hours; break; }
  }
  const recovered = rows.filter((row) => isObservedRecovery(row.annotation));
  const recoveredHours = recovered.reduce((sum, row) => sum + hoursOf(row), 0);
  const reviewedHours = rows.reduce((sum, row) => sum + hoursOf(row), 0);
  document.querySelector("#recovery-curve-note").textContent =
    `The median episode contains ${measureText(median, "hours")} of measured drift, but half of all measured drift time sits in episodes with ${measureText(weightedMedian, "hours")} or more. `
    + `${percentText(recovered.length / rows.length)} of reviewed episodes ended in an observed recovery, covering ${percentText(recoveredHours / reviewedHours)} of reviewed drift hours.`;
  document.querySelector("#recovery-curve-legend").innerHTML =
    '<span class="legend-item"><span class="legend-swatch" style="background:#3f7082"></span>Share of episodes above x measured drift time</span>'
    + '<span class="legend-item"><span class="legend-swatch" style="background:#ae5037"></span>Share of measured drift time in episodes above x</span>';
  document.querySelector("#recovery-curve-meta").textContent = `${durations.length} episodes · ${measureText(totalHours, "hours")}`;
}

function renderNudgeResponse() {
  const nudged = [];
  goalMaxEpisodes.forEach((episode) => {
    const nudges = (episode.operator_nudges_within_evidence || []).filter((nudge) => timestampMs(nudge.timestamp) != null);
    if (!nudges.length) return;
    const end = episode.drift_end || {};
    const endMs = timestampMs(end.ended_at);
    const first = Math.min(...nudges.map((nudge) => timestampMs(nudge.timestamp)));
    nudged.push({
      episode,
      hours: driftHoursFor(episode).hours,
      corrected: nudges.some((nudge) => nudge.outcome === "corrected"),
      minutesToEnd: endMs == null ? null : Math.max(0, (endMs - first) / 60000)
    });
  });
  const windows = [[15, "Ended within 15 min of the first nudge"], [60, "Ended within 1 hour"], [240, "Ended within 4 hours"]];
  const totalEpisodes = nudged.length || 1;
  const totalHours = nudged.reduce((sum, item) => sum + item.hours, 0) || 1;
  const items = [
    { label: "Reviewer judged the nudge corrected the drift", filter: (item) => item.corrected },
    ...windows.map(([minutes, windowLabel]) => ({ label: windowLabel, filter: (item) => item.minutesToEnd != null && item.minutesToEnd <= minutes })),
    { label: "Still drifting when the evidence ends", filter: (item) => item.minutesToEnd == null }
  ];
  // Each share is out of all nudged episodes / drift hours, so the rows overlap and don't sum to 100%.
  renderPairedBars(document.querySelector("#nudge-pairs"), items.map((item) => {
    const matched = nudged.filter(item.filter);
    return { label: item.label, episodes: matched.length, hours: matched.reduce((sum, entry) => sum + entry.hours, 0) };
  }), { totalEpisodes, totalHours });
  document.querySelector("#nudge-legend").innerHTML = pairedLegend();
  document.querySelector("#nudge-meta").textContent = `${nudged.length} episodes with a nudge inside them · ${measureText(totalHours, "hours")}`;
}

function sourceAgentFor(actor) {
  const text = String(actor || "");
  const agents = [...new Set(goalMaxEpisodes.map((episode) => episode.agent))].sort((left, right) => right.length - left.length);
  const named = agents.find((agent) => text.startsWith(agent));
  if (named) return named;
  if (/multiple|peers/i.test(text)) return "Multiple agents";
  return "Outside humans";
}

// Outside-request episodes as (source, target, episode count, drift hours) tallies under the given key functions.
function pullTallies(sourceKey, targetKey) {
  const tallies = new Map();
  rows.forEach((row) => {
    if (triggerOriginFor(row.annotation) !== "outside" || !row.annotation.trigger_actor) return;
    const source = sourceKey(sourceAgentFor(row.annotation.trigger_actor));
    const target = targetKey(row.episode.agent);
    const key = `${source}\u0000${target}`;
    if (!tallies.has(key)) tallies.set(key, { source, target, episodes: 0, hours: 0 });
    const tally = tallies.get(key);
    tally.episodes += 1;
    tally.hours += hoursOf(row);
  });
  return [...tallies.values()];
}

// Heatmap of tallies. Axes are ordered by episode counts in both modes, so they stay put when toggling.
function renderPullMatrix(table, tallies, mode, { maxSources = 14, maxTargets = 16, corner, labelFor = (name) => name }) {
  const totals = (field) => {
    const map = new Map();
    tallies.forEach((tally) => map.set(tally[field], (map.get(tally[field]) || 0) + tally.episodes));
    return [...map.entries()].sort((left, right) => right[1] - left[1] || left[0].localeCompare(right[0])).map(([name]) => name);
  };
  const sources = totals("source").slice(0, maxSources);
  const targets = totals("target").slice(0, maxTargets);
  const value = (tally) => (mode === "hours" ? tally.hours : tally.episodes);
  const cells = new Map(tallies.map((tally) => [`${tally.source}\u0000${tally.target}`, value(tally)]));
  const max = Math.max(.0001, ...cells.values());
  table.replaceChildren();
  table.style.gridTemplateColumns = `minmax(150px, 1.4fr) repeat(${targets.length}, minmax(34px, 1fr))`;
  const cornerNode = document.createElement("div");
  cornerNode.className = "pull-head is-corner";
  cornerNode.textContent = corner;
  table.append(cornerNode);
  targets.forEach((target) => {
    const head = document.createElement("div");
    head.className = "pull-head";
    head.textContent = labelFor(target);
    head.title = labelFor(target);
    table.append(head);
  });
  sources.forEach((source) => {
    const name = document.createElement("div");
    name.className = "pull-source";
    name.textContent = labelFor(source);
    table.append(name);
    targets.forEach((target) => {
      const cellValue = cells.get(`${source}\u0000${target}`) || 0;
      const cell = document.createElement("div");
      cell.className = `pull-cell${cellValue ? "" : " is-zero"}`;
      cell.style.setProperty("--heat", cellValue ? (.12 + .8 * cellValue / max).toFixed(3) : "0");
      cell.textContent = cellValue ? (mode === "hours" ? (cellValue >= 10 ? Math.round(cellValue) : cellValue.toFixed(1)) : String(cellValue)) : "";
      cell.title = `${labelFor(source)} → ${labelFor(target)}: ${measureText(cellValue, mode)}${mode === "hours" ? " of drift" : " episodes"}`;
      table.append(cell);
    });
  });
  return { sources, targets };
}

const pullLabel = (name) => (name === "Outside humans" || name === "Multiple agents" ? name : agentLabel(name));

function renderWhoPullsWhom() {
  const mode = document.querySelector("#pull-measure").value;
  const { sources, targets } = renderPullMatrix(document.querySelector("#pull-matrix"), pullTallies((name) => name, (name) => name), mode,
    { corner: "Source ↓ / drifting agent →", labelFor: pullLabel });
  document.querySelector("#pull-meta").textContent = `${sources.length} sources · ${targets.length} drifting agents shown`;
}

function renderFamilyPulls() {
  const mode = document.querySelector("#family-pull-measure").value;
  const family = (name) => (name === "Outside humans" || name === "Multiple agents" ? name : modelFamily(name));
  const tallies = pullTallies(family, family);
  const { sources, targets } = renderPullMatrix(document.querySelector("#family-pull-matrix"), tallies, mode,
    { corner: "Source family ↓ / drifting family →", maxSources: 12, maxTargets: 10 });
  const agentPairs = tallies.filter((tally) => tally.source !== "Outside humans" && tally.source !== "Multiple agents");
  const same = agentPairs.filter((tally) => tally.source === tally.target);
  const sum = (items, field) => items.reduce((total, tally) => total + tally[field], 0);
  document.querySelector("#family-pull-note").textContent =
    `Among agent-to-agent pulls, ${percentText(sum(same, "episodes") / Math.max(1, sum(agentPairs, "episodes")))} of episodes and `
    + `${percentText(sum(same, "hours") / Math.max(.0001, sum(agentPairs, "hours")))} of drift hours stay within one model family. `
    + "Families differ in how many agents they have in the Village, so compare rows with their totals in mind.";
  document.querySelector("#family-pull-meta").textContent = `${sources.length} source groups · ${targets.length} families`;
}

function renderReciprocity() {
  const tallies = pullTallies((name) => name, (name) => name)
    .filter((tally) => tally.source !== "Outside humans" && tally.source !== "Multiple agents" && tally.source !== tally.target);
  const byPair = new Map(tallies.map((tally) => [`${tally.source}\u0000${tally.target}`, tally]));
  const seen = new Set();
  const mutual = [];
  const oneWay = [];
  tallies.forEach((tally) => {
    const pairKey = [tally.source, tally.target].sort().join("\u0000");
    if (seen.has(pairKey)) return;
    seen.add(pairKey);
    const back = byPair.get(`${tally.target}\u0000${tally.source}`);
    if (back) mutual.push([tally, back]);
    else oneWay.push(tally);
  });
  const cellText = (tally) => (tally ? `${tally.episodes} ep · ${measureText(tally.hours, "hours")}` : "—");
  const table = document.querySelector("#reciprocity-table");
  table.replaceChildren();
  const header = document.createElement("div");
  header.className = "reciprocity-row is-head";
  ["Pair", "A pulls B", "B pulls A"].forEach((text) => {
    const cell = document.createElement("span");
    cell.textContent = text;
    header.append(cell);
  });
  table.append(header);
  const addRow = (first, second, kind) => {
    const row = document.createElement("div");
    row.className = `reciprocity-row is-${kind}`;
    const pair = document.createElement("span");
    pair.textContent = `${agentLabel(first.source)} ↔ ${agentLabel(first.target)}`;
    const forward = document.createElement("span");
    forward.textContent = cellText(first);
    const backward = document.createElement("span");
    backward.textContent = cellText(second);
    row.append(pair, forward, backward);
    table.append(row);
  };
  mutual.sort((left, right) => (right[0].episodes + right[1].episodes) - (left[0].episodes + left[1].episodes))
    .forEach(([first, second]) => addRow(first, second, "mutual"));
  oneWay.sort((left, right) => right.episodes - left.episodes || right.hours - left.hours).slice(0, 8)
    .forEach((tally) => addRow(tally, null, "one-way"));
  const pairs = mutual.length + oneWay.length;
  const mutualEpisodes = mutual.reduce((sum, [first, second]) => sum + first.episodes + second.episodes, 0);
  const mutualHours = mutual.reduce((sum, [first, second]) => sum + first.hours + second.hours, 0);
  const totalEpisodes = tallies.reduce((sum, tally) => sum + tally.episodes, 0);
  const totalHours = tallies.reduce((sum, tally) => sum + tally.hours, 0);
  document.querySelector("#reciprocity-note").textContent =
    `${mutual.length} of ${pairs} agent pairs pull each other in both directions. Those mutual pairs account for `
    + `${percentText(mutualEpisodes / Math.max(1, totalEpisodes))} of agent-to-agent drift episodes and ${percentText(mutualHours / Math.max(.0001, totalHours))} of its drift hours. `
    + "Mutual pairs are listed first, then the largest one-way pulls.";
  document.querySelector("#reciprocity-meta").textContent = `${pairs} agent pairs`;
}

// ---------------------------------------------------------------------------
// Goal-window cards: one card per goal period with its aggregate numbers and every episode.
// ---------------------------------------------------------------------------
// Working time and drift for one period use the same source-grounded denominator
// as the atlas and burden scatter: the exact overlap of the assignment interval
// with active Village weekdays from 9 AM–5 PM Pacific.
// Village run days (weekdays with goal-maximization activity): the shared x-axis for card sparklines.
const villageRunDays = [...new Set(goalMaxDays)].filter((day) => {
  const weekday = new Date(`${day}T12:00:00Z`).getUTCDay();
  return weekday >= 1 && weekday <= 5;
}).sort();

function periodWorkingStats(period) {
  const periodWindows = workingWindows.map((window) => ({
    ...window,
    availableStartMs: Math.max(window.startMs, period.startMs),
    availableEndMs: Math.min(window.endMs, period.endMs)
  })).filter((window) => window.availableEndMs > window.availableStartMs);
  const merged = mergedIntervals(
    period.episodes.flatMap(episodeIntervals),
    period.startMs,
    period.endMs
  );
  const dailyShares = periodWindows.map((window) => {
    const availableMs = window.availableEndMs - window.availableStartMs;
    const driftMs = merged.reduce((sum, interval) => sum + Math.max(
      0,
      Math.min(interval.endMs, window.availableEndMs)
        - Math.max(interval.startMs, window.availableStartMs)
    ), 0);
    return { day: window.date, share: Math.min(1, driftMs / availableMs) };
  });
  return {
    workingHours: period.workingMs / 3600000,
    driftWorkingHours: period.validatedWorkingMs / 3600000,
    workDays: periodWindows.length,
    dailyShares
  };
}

// Window-level drift shape from daily drift shares, split into thirds: is drift high at the start, and at the end?
// "High" means at least half of the window's peak third. Descriptive only; the thirds are shown alongside.
const DRIFT_SHAPES = [
  { id: "sustained", label: "Sustained throughout", note: "high at the start and at the end" },
  { id: "rises", label: "Rises over the window", note: "low at the start, high by the end" },
  { id: "burst", label: "Mid-window burst", note: "low at both ends, peaking in the middle" },
  { id: "recovers", label: "Drifts, then recovers", note: "high at the start, low by the end" },
  { id: "minimal", label: "Minimal drift", note: "under 5% of working time" },
  { id: "short", label: "Too short to classify", note: "fewer than 10 working days" }
];
const DRIFT_SHAPE_BY_ID = new Map(DRIFT_SHAPES.map((shape) => [shape.id, shape]));

function driftShapeFor(dailyShares) {
  const shares = dailyShares.map((entry) => entry.share);
  if (shares.length < 10) return { id: "short", thirds: null };
  const mean = (values) => (values.length ? values.reduce((sum, value) => sum + value, 0) / values.length : 0);
  const n = shares.length;
  const thirds = [0, 1, 2].map((index) => mean(shares.slice(Math.floor(index * n / 3), Math.floor((index + 1) * n / 3))));
  if (mean(shares) < .05) return { id: "minimal", thirds };
  const half = Math.max(...thirds) / 2;
  const highStart = thirds[0] >= half;
  const highEnd = thirds[2] >= half;
  const id = highStart && highEnd ? "sustained" : highEnd ? "rises" : highStart ? "recovers" : "burst";
  return { id, thirds };
}

function topEntries(map, limit = 3) {
  return [...map.entries()].sort((left, right) => right[1].episodes - left[1].episodes || right[1].hours - left[1].hours).slice(0, limit);
}

function tally(map, key, hours) {
  if (!map.has(key)) map.set(key, { episodes: 0, hours: 0 });
  const entry = map.get(key);
  entry.episodes += 1;
  entry.hours += hours;
}

function goalWindowCardData(period) {
  const working = periodWorkingStats(period);
  const episodes = [...period.episodes].sort((left, right) => episodeOnsetMs(left) - episodeOnsetMs(right));
  const hoursOfEpisode = (episode) => driftHoursFor(episode).hours;
  const totalHours = episodes.reduce((sum, episode) => sum + hoursOfEpisode(episode), 0);
  const reviewed = episodes.map((episode) => ({ episode, review: reviewRowByEpisode.get(episode.episode_id) })).filter((item) => item.review);
  const origins = new Map(ORIGIN_GROUPS.map((group) => [group.id, { episodes: 0, hours: 0 }]));
  const taxonomy = new Map();
  const actors = new Map();
  const endings = new Map();
  let recoveredEpisodes = 0, recoveredHours = 0, reviewedHours = 0;
  reviewed.forEach(({ episode, review }) => {
    const hours = hoursOfEpisode(episode);
    reviewedHours += hours;
    const origin = origins.get(triggerOriginFor(review.annotation));
    origin.episodes += 1;
    origin.hours += hours;
    const category = triggerTaxonomyByEpisode.get(episode.episode_id);
    if (category) tally(taxonomy, triggerTaxonomyLabels.get(category) || category, hours);
    if (review.annotation.trigger_actor) tally(actors, pullLabel(sourceAgentFor(review.annotation.trigger_actor)) === "Outside humans" ? review.annotation.trigger_actor : pullLabel(sourceAgentFor(review.annotation.trigger_actor)), hours);
    tally(endings, label("recovery", review.annotation.recovery_mechanisms[0] || "unknown"), hours);
    if (isObservedRecovery(review.annotation)) {
      recoveredEpisodes += 1;
      recoveredHours += hours;
    }
  });
  // Episodes this agent's own requests started in other agents.
  const pulled = new Map();
  rows.forEach((row) => {
    if (row.episode.agent === period.agent || !row.annotation.trigger_actor) return;
    if (sourceAgentFor(row.annotation.trigger_actor) !== period.agent) return;
    const onsetMs = episodeOnsetMs(row.episode);
    if (onsetMs == null || onsetMs < period.startMs || onsetMs > period.endMs) return;
    tally(pulled, agentLabel(row.episode.agent), hoursOfEpisode(row.episode));
  });
  const verdicts = new Map();
  episodes.forEach((episode) => {
    if (episode.wait_review) tally(verdicts, WAIT_VERDICT_LABELS[episode.wait_review.verdict] || episode.wait_review.verdict, hoursOfEpisode(episode));
  });
  const rules = new Map();
  episodes.forEach((episode) => {
    (selfAuthoredRules.episodes?.[episode.episode_id] || []).forEach((tag) => {
      const ruleLabel = (selfAuthoredRules.rules || {})[tag.rule] || tag.rule;
      if (!rules.has(ruleLabel) || tag.first_seen < rules.get(ruleLabel).first_seen) rules.set(ruleLabel, tag);
    });
  });
  const nudges = episodes.flatMap((episode) => episode.operator_nudges_within_evidence || []);
  const corrections = (correctionsByAgent.get(period.agent) || []).filter((correction) => {
    const ms = timestampMs(correction.timestamp);
    return ms != null && ms >= period.startMs && ms <= period.endMs;
  });
  const firstOnset = episodes.length ? episodeOnsetMs(episodes[0]) : null;
  const longest = episodes.reduce((best, episode) => (hoursOfEpisode(episode) > (best ? hoursOfEpisode(best) : -1) ? episode : best), null);
  return {
    shape: driftShapeFor(working.dailyShares),
    period, working, episodes, totalHours, reviewed, origins, taxonomy, actors, endings, pulled, verdicts, rules, nudges, corrections,
    recoveredEpisodes, recoveredHours, reviewedHours,
    share: working.workingHours ? working.driftWorkingHours / working.workingHours : 0,
    firstDriftDays: firstOnset == null ? null : (firstOnset - period.startMs) / DAY_MS,
    longest,
    stillDrifting: episodes.filter((episode) => (episode.drift_end || {}).status === "ongoing_at_evidence_end").length,
    targeting: outsideTargetingByAgent.get(period.agent) || (humanContact.agents?.[period.agent] || {}).outside_targeting || null
  };
}

function cardElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function cardListBlock(title, entries, formatter) {
  const block = cardElement("div", "gw-block");
  block.append(cardElement("h5", null, title));
  if (!entries.length) {
    block.append(cardElement("p", "gw-empty", "None"));
    return block;
  }
  const list = cardElement("ul");
  entries.forEach((entry) => list.append(cardElement("li", null, formatter(entry))));
  block.append(list);
  return block;
}

const pairText = ([name, value]) => `${name} · ${value.episodes} ep · ${measureText(value.hours, "hours")}`;

function renderGoalWindowCard(data) {
  const { period } = data;
  const card = cardElement("article", "gw-card");
  card.dataset.agent = period.agent;

  const head = cardElement("header", "gw-head");
  const title = cardElement("div", "gw-title");
  title.append(cardElement("h4", null, agentLabel(period.agent)));
  const badges = cardElement("div", "gw-badges");
  const category = goalCategories.find((item) => item.id === goalCategoryByAgent.get(period.agent));
  if (category) badges.append(cardElement("span", "gw-badge", category.label));
  if (outsideTargetingByAgent.has(period.agent)) badges.append(cardElement("span", "gw-badge is-targeted", "Targeted"));
  const shape = DRIFT_SHAPE_BY_ID.get(data.shape.id);
  const shapeBadge = cardElement("span", `gw-badge gw-shape is-${shape.id}`,
    data.shape.thirds && shape.id !== "minimal" ? `${shape.label} · ${data.shape.thirds.map((value) => Math.round(value * 100)).join(" / ")}%` : shape.label);
  shapeBadge.title = `${shape.label}: ${shape.note}.${data.shape.thirds ? ` Drift share of working time in each third of the window: ${data.shape.thirds.map((value) => percentText(value)).join(", ")}.` : ""}`;
  badges.prepend(shapeBadge);
  title.append(badges);
  head.append(title);
  head.append(cardElement("p", "gw-goal", period.goal));
  const endText = new Date(Math.min(period.endMs, analysisHorizonMs)).toISOString();
  head.append(cardElement("p", "gw-dates", `${displayDay(new Date(period.startMs).toISOString())} – ${displayDay(endText)} · ${data.working.workDays} working days`));
  card.append(head);

  const stats = cardElement("div", "gw-stats");
  [
    [String(data.episodes.length), "episodes"],
    [measureText(data.totalHours, "hours"), "drift"],
    [percentText(data.share), "of working time"],
    [data.firstDriftDays == null ? "—" : `${Math.max(0, data.firstDriftDays).toFixed(1)} d`, "to first drift"],
    [data.longest ? measureText(driftHoursFor(data.longest).hours, "hours") : "—", "longest episode"],
    [data.reviewed.length ? `${percentText(data.recoveredEpisodes / data.reviewed.length)} / ${percentText(data.reviewedHours ? data.recoveredHours / data.reviewedHours : 0)}` : "—", "recovered (episodes / hours)"]
  ].forEach(([value, caption]) => {
    const stat = cardElement("div", "gw-stat");
    stat.append(cardElement("strong", null, value), cardElement("span", null, caption));
    stats.append(stat);
  });
  card.append(stats);

  if (data.working.dailyShares.length) {
    // Bars of daily drift share on a calendar shared by every card (one fixed-width slot per Village run day),
    // so bar widths match across cards and later joiners start further right.
    const slots = villageRunDays.length;
    const slotOf = new Map(villageRunDays.map((day, index) => [day, index]));
    const entries = data.working.dailyShares
      .map((entry) => ({ ...entry, index: slotOf.get(entry.day) }))
      .filter((entry) => entry.index != null)
      .sort((left, right) => left.index - right.index);
    const spark = cardElement("div", "gw-spark");
    spark.setAttribute("role", "img");
    spark.setAttribute("aria-label", "Daily share of the working day spent drifting, on the shared Village calendar");
    if (entries.length) {
      const span = cardElement("span", "gw-spark-window");
      span.style.left = `${(entries[0].index / slots) * 100}%`;
      span.style.width = `${((entries.at(-1).index - entries[0].index + 1) / slots) * 100}%`;
      spark.append(span);
    }
    entries.forEach((entry) => {
      const bar = cardElement("span", entry.share ? "gw-spark-bar" : "gw-spark-bar is-zero");
      bar.style.left = `${(entry.index / slots) * 100}%`;
      bar.style.width = `${100 / slots}%`;
      bar.style.height = `${Math.max(entry.share ? 6 : 2, entry.share * 100)}%`;
      bar.title = `${displayDay(entry.day)}: ${percentText(entry.share)} of the working day`;
      spark.append(bar);
    });
    // Dashed dividers mark where each third of the agent's own window begins (the shape label uses these thirds).
    if (entries.length >= 3) {
      [1, 2].forEach((third) => {
        const divider = cardElement("i");
        divider.style.left = `${(entries[Math.floor(third * entries.length / 3)].index / slots) * 100}%`;
        spark.append(divider);
      });
    }
    const axis = cardElement("div", "gw-spark-axis");
    axis.append(cardElement("span", null, displayDay(villageRunDays[0])), cardElement("span", null, displayDay(villageRunDays.at(-1))));
    card.append(spark, axis);
  }

  if (data.reviewed.length) {
    const origin = cardElement("div", "gw-origin");
    origin.append(cardElement("h5", null, "What started the drift"));
    const totalEpisodes = data.reviewed.length;
    const totalHours = data.reviewedHours || 1;
    [["episodes", "Episodes", totalEpisodes], ["hours", "Hours", totalHours]].forEach(([key, caption, total]) => {
      const line = cardElement("div", "gw-origin-line");
      line.append(cardElement("span", "gw-origin-label", caption));
      const track = cardElement("span", "gw-origin-track");
      ORIGIN_GROUPS.forEach((group) => {
        const value = data.origins.get(group.id)[key];
        if (!value) return;
        const fill = cardElement("span");
        fill.style.width = `${(value / total) * 100}%`;
        fill.style.background = group.color;
        fill.title = `${group.label}: ${key === "hours" ? measureText(value, "hours") : value} (${percentText(value / total)})`;
        track.append(fill);
      });
      line.append(track);
      origin.append(line);
    });
    card.append(origin);
  }

  const grid = cardElement("div", "gw-grid");
  grid.append(
    cardListBlock("Top trigger categories", topEntries(data.taxonomy), pairText),
    cardListBlock("Pulled off goal by", topEntries(data.actors), pairText),
    cardListBlock("Pulled others off goal", topEntries(data.pulled), pairText),
    cardListBlock("How episodes ended", topEntries(data.endings, 4), pairText),
    cardListBlock("Wait reviews", topEntries(data.verdicts, 4), pairText),
    cardListBlock("Self-authored rules cited", [...data.rules.entries()].sort((left, right) => left[1].first_seen.localeCompare(right[1].first_seen)),
      ([ruleLabel, tag]) => `${ruleLabel} · first ${displayDay(tag.first_seen)}: “${shortText(tag.excerpt, 110)}”`)
  );
  const human = cardElement("div", "gw-block");
  human.append(cardElement("h5", null, "People and nudges"));
  const humanList = cardElement("ul");
  const targeting = data.targeting;
  humanList.append(cardElement("li", null, `Outside-human contacts: ${targeting ? `${number(targeting.contacts)} over ${targeting.days} days` : "none recorded"}`));
  humanList.append(cardElement("li", null, `Operator corrections: ${data.corrections.length}${data.corrections.length ? ` (latest: ${shortText(data.corrections.at(-1).summary, 80)})` : ""}`));
  const corrected = data.nudges.filter((nudge) => nudge.outcome === "corrected").length;
  humanList.append(cardElement("li", null, `Nudges inside episodes: ${data.nudges.length}${data.nudges.length ? ` (${corrected} corrected the drift)` : ""}`));
  if (data.stillDrifting) humanList.append(cardElement("li", null, `Still drifting when the data ends: ${data.stillDrifting} episode${data.stillDrifting === 1 ? "" : "s"}`));
  human.append(humanList);
  grid.append(human);
  card.append(grid);

  // Reviewed on-goal highlights: what the agent actually did toward its goal, with replay links.
  const highlightRecord = onGoalHighlights.agents?.[period.agent];
  const highlights = (highlightRecord?.highlights || []).filter((item) => {
    const ms = timestampMs(item.ts);
    return ms != null && ms >= period.startMs - DAY_MS && ms <= period.endMs + DAY_MS;
  });
  if (highlights.length || highlightRecord?.summary) {
    const block = cardElement("div", "gw-highlights");
    block.append(cardElement("h5", null, "On-goal highlights"));
    if (highlightRecord.summary) block.append(cardElement("p", "gw-highlight-summary", highlightRecord.summary));
    const list = cardElement("ul");
    highlights.forEach((item) => {
      const entry = cardElement("li");
      const when = cardElement("span", "gw-highlight-when", displayDay(item.ts));
      const type = cardElement("span", "gw-highlight-type", (onGoalHighlights.types || {})[item.type] || item.type);
      const text = cardElement("span", "gw-highlight-text", item.description || item.text || "");
      if (item.excerpt) text.title = `“${item.excerpt}”`;
      const link = document.createElement("a");
      link.className = "gw-highlight-replay";
      const ms = timestampMs(item.ts);
      link.href = `https://theaidigest.org/village?date=${String(item.ts).slice(0, 10)}&time=${ms}&agent=${encodeURIComponent(period.agent)}`;
      link.target = "_blank";
      link.rel = "noopener";
      link.textContent = "Replay";
      entry.append(when, type, text, link);
      list.append(entry);
    });
    block.append(list);
    card.append(block);
  }

  if (data.episodes.length) {
    const details = cardElement("details", "gw-episodes");
    details.append(cardElement("summary", null, `All ${data.episodes.length} episodes`));
    const list = cardElement("ol");
    data.episodes.forEach((episode) => {
      const review = reviewRowByEpisode.get(episode.episode_id);
      const item = cardElement("li");
      const when = cardElement("span", "gw-ep-when", atlasEpisodeTiming(episode).rangeText);
      const hours = cardElement("span", "gw-ep-hours", measureText(driftHoursFor(episode).hours, "hours"));
      const origin = review ? ORIGIN_BY_ID.get(triggerOriginFor(review.annotation)) : null;
      const originNode = cardElement("span", "gw-ep-origin", origin ? origin.label.split(" (")[0] : "Not reviewed");
      if (origin) originNode.style.color = origin.color;
      const ending = cardElement("span", "gw-ep-end", review ? label("recovery", review.annotation.recovery_mechanisms[0] || "unknown") : driftEndLabels[(episode.drift_end || {}).status] || "");
      const activity = cardElement("span", "gw-ep-activity", episode.activity);
      item.append(when, hours, originNode, ending, activity, episodeLinkFor(episode.episode_id));
      list.append(item);
    });
    details.append(list);
    card.append(details);
  }
  return card;
}

const number = (value) => new Intl.NumberFormat("en-US").format(value);
let goalWindowCards = null;

function renderGoalWindowCards() {
  if (!goalWindowCards) goalWindowCards = goalPeriods.map(goalWindowCardData);
  const sortMode = document.querySelector("#gw-sort").value;
  const category = document.querySelector("#gw-category").value;
  const shapeFilter = document.querySelector("#gw-shape").value;
  const query = document.querySelector("#gw-search").value.trim().toLowerCase();
  const sorters = {
    share: (left, right) => right.share - left.share,
    hours: (left, right) => right.totalHours - left.totalHours,
    episodes: (left, right) => right.episodes.length - left.episodes.length,
    release: (left, right) => (AGENT_RELEASE_DATES[left.period.agent] || "9999").localeCompare(AGENT_RELEASE_DATES[right.period.agent] || "9999"),
    agent: (left, right) => left.period.agent.localeCompare(right.period.agent),
    shape: (left, right) => DRIFT_SHAPES.findIndex((shape) => shape.id === left.shape.id) - DRIFT_SHAPES.findIndex((shape) => shape.id === right.shape.id)
      || right.share - left.share
  };
  const visible = goalWindowCards
    .filter((data) => !category || goalCategoryByAgent.get(data.period.agent) === category)
    .filter((data) => !shapeFilter || data.shape.id === shapeFilter)
    .filter((data) => !query || `${data.period.agent} ${data.period.goal}`.toLowerCase().includes(query))
    .sort((left, right) => (sorters[sortMode] || sorters.share)(left, right) || left.period.agent.localeCompare(right.period.agent));
  const container = document.querySelector("#goal-window-cards");
  container.replaceChildren(...visible.map(renderGoalWindowCard));
  document.querySelector("#gw-meta").textContent = `${visible.length} of ${goalWindowCards.length} goal windows`;
}

function initializeGoalWindowCards() {
  const select = document.querySelector("#gw-category");
  goalCategories.forEach((category) => {
    const option = document.createElement("option");
    option.value = category.id;
    option.textContent = category.label;
    select.append(option);
  });
  // Legend for the origin colors used in each card's "What started the drift" bars and episode list.
  document.querySelector("#gw-legend").replaceChildren(...ORIGIN_GROUPS.map((group) => {
    const item = document.createElement("span");
    item.className = "legend-item";
    const swatch = document.createElement("span");
    swatch.className = "legend-swatch";
    swatch.style.background = group.color;
    item.append(swatch, document.createTextNode(group.label));
    return item;
  }));
  const shapeSelect = document.querySelector("#gw-shape");
  DRIFT_SHAPES.forEach((shape) => {
    const option = document.createElement("option");
    option.value = shape.id;
    option.textContent = shape.label;
    shapeSelect.append(option);
  });
  ["#gw-sort", "#gw-category", "#gw-shape"].forEach((id) => document.querySelector(id).addEventListener("change", renderGoalWindowCards));
  document.querySelector("#gw-search").addEventListener("input", renderGoalWindowCards);
  renderGoalWindowCards();
}

function initializeDriftDynamics() {
  renderTriggerOrigin();
  document.querySelector("#origin-measure").addEventListener("change", renderTriggerOrigin);
  renderJustifications();
  renderRecoveryCurves();
  renderNudgeResponse();
  renderWhoPullsWhom();
  document.querySelector("#pull-measure").addEventListener("change", renderWhoPullsWhom);
  renderFamilyPulls();
  document.querySelector("#family-pull-measure").addEventListener("change", renderFamilyPulls);
  renderReciprocity();
}

function initializeExperimentalLenses() {
  renderDriftWeather();
  renderAgentFingerprints();
  renderInfluenceBars();
  renderResilienceScorecards();
  document.querySelector("#resilience-sort").addEventListener("change", renderResilienceScorecards);
  document.querySelector("#resilience-measure").addEventListener("change", renderResilienceScorecards);
  renderTriggerTaxonomy();
  document.querySelector("#taxonomy-measure").addEventListener("change", renderTriggerTaxonomy);
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

    item.append(identity, activityWrap, tags, episodeLinkFor(row.episodeId));
    list.append(item);
  });
}

function render() {
  renderMetrics();
  renderBarChart({
    elementId: "#official-trigger-chart", totalId: "#official-trigger-total",
    labelKind: "taxonomy", accessor: (row) => [triggerTaxonomyByEpisode.get(row.episodeId)],
    chartClass: "taxonomy"
  });
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

document.querySelector("#influence-measure").addEventListener("change", (event) => {
  influenceMeasure = event.target.value;
  renderInfluenceBars();
});
document.querySelector("#breakdown-measure").addEventListener("change", (event) => {
  breakdownMeasure = event.target.value;
  document.querySelector("#breakdown-estimate-note").textContent = breakdownMeasure === "hours" ? hoursEstimateNote(rows) : "";
  render();
});

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

// Collapsible page sections. Each top-level section gets a toggle in its heading; the choice is remembered per section.
const SECTION_COLLAPSE_KEY = "village-drift-findings-collapsed-sections:v1";
function initializeCollapsibleSections() {
  let collapsed;
  try {
    collapsed = new Set(JSON.parse(localStorage.getItem(SECTION_COLLAPSE_KEY) || "[]"));
  } catch {
    collapsed = new Set();
  }
  const save = () => {
    try { localStorage.setItem(SECTION_COLLAPSE_KEY, JSON.stringify([...collapsed])); } catch { /* storage unavailable */ }
  };
  document.querySelectorAll("main section[aria-labelledby]").forEach((section) => {
    const heading = section.querySelector(":scope > .exploration-heading, :scope > .section-heading, :scope > .coverage-heading, :scope > .results-heading");
    if (!heading) return;
    const id = section.getAttribute("aria-labelledby");
    const title = document.getElementById(id)?.textContent || "section";
    const button = document.createElement("button");
    button.type = "button";
    button.className = "section-toggle";
    const apply = (isCollapsed) => {
      section.classList.toggle("is-collapsed", isCollapsed);
      button.setAttribute("aria-expanded", String(!isCollapsed));
      button.textContent = isCollapsed ? "Show" : "Hide";
      button.setAttribute("aria-label", `${isCollapsed ? "Show" : "Hide"} ${title}`);
    };
    button.addEventListener("click", () => {
      const isCollapsed = !section.classList.contains("is-collapsed");
      if (isCollapsed) collapsed.add(id); else collapsed.delete(id);
      save();
      apply(isCollapsed);
    });
    heading.classList.add("has-section-toggle");
    heading.append(button);
    apply(collapsed.has(id));
  });
}

initializeExplorations();
initializeExperimentalLenses();
initializeDriftDynamics();
initializeGoalWindowCards();
initializeCollapsibleSections();
render();
