const REVIEW_KEY = "village-interview-point-review:v1";
const fresh = { cache: "no-store" };

const RULES = {
  before_onset: { n: "1", label: "Before first onset", purpose: "Validates the drift cause" },
  mid_longest: { n: "2", label: "Middle of the longest episode", purpose: "Its reasoning: what other options it considered" },
  mid_longest_any: { n: "2b", label: "Middle of its longest episode of any type", purpose: "Its reasoning: what other options it considered" },
  after_return: { n: "3", label: "After returning to drift", purpose: "Its reasoning: what kept it drifting after a nudge" },
  before_recovery: { n: "4", label: "Just before recovery", purpose: "Validates the correction cause" }
};
const RULE_ORDER = Object.keys(RULES);
const HORIZON_MS = Date.parse("2026-10-03T00:00:00Z");

const [pointsResponse, bundleResponse, annotationResponse, sourceResponse] = await Promise.all([
  fetch("./data/interview_points_v1.json", fresh),
  fetch("./data/second_audit_v2.json", fresh),
  fetch("./data/manual_review_annotations_v1.json", fresh),
  fetch("./data/source_records.json", fresh)
]);
if (!pointsResponse.ok || !bundleResponse.ok || !annotationResponse.ok) {
  document.querySelector("#main-content").innerHTML = `<div class="load-error"><strong>Interview points could not load.</strong><br>
    data/interview_points_v1.json, the audit bundle and the annotation dataset must be published together.</div>`;
  throw new Error("Could not load interview point data");
}
const selection = await pointsResponse.json();
const bundle = await bundleResponse.json();
const annotations = await annotationResponse.json();
const sourceRecords = sourceResponse.ok ? await sourceResponse.json() : {};

const taxonomy = annotations.trigger_taxonomy || {};
const categoryLabel = new Map((taxonomy.categories || []).map((c) => [c.id, c.label]));
const categoryOf = new Map(Object.entries(taxonomy.assignments || {}));
const episodeById = new Map(bundle.confirmed_episodes.map((e) => [e.episode_id, e]));
const episodesByAgent = new Map();
bundle.confirmed_episodes
  .filter((e) => e.period === "goal_maximization" && categoryOf.has(e.episode_id))
  .forEach((e) => {
    if (!episodesByAgent.has(e.agent)) episodesByAgent.set(e.agent, []);
    episodesByAgent.get(e.agent).push(e);
  });

// The agent's goal window: its earliest goal-maximization goal record to the end of the data.
const agentNameById = new Map((sourceRecords.agentRecords || []).map((a) => [a.id, a.name]));
const windowStart = new Map();
(sourceRecords.agentGoalRecords || []).forEach((g) => {
  const name = agentNameById.get(g.agent_id);
  const start = Date.parse(`${g.start_time}Z`);
  if (!name || !Number.isFinite(start) || start < Date.parse("2026-07-06T00:00:00Z")) return;
  windowStart.set(name, Math.min(windowStart.get(name) ?? Infinity, start));
});

function ms(value) {
  if (!value) return null;
  const text = String(value).trim().replace(" ", "T");
  const t = Date.parse(/[zZ]|[+-]\d\d:?\d\d$/.test(text) ? text : `${text}Z`);
  return Number.isFinite(t) ? t : null;
}

function episodeSpan(e) {
  const bouts = (e.drift_bouts || []).map(([a, b]) => [ms(a), ms(b)]).filter(([a, b]) => a != null && b != null);
  if (bouts.length) return [bouts[0][0], bouts.at(-1)[1]];
  const start = ms(e.onset) ?? ms(e.activity_start_observed_at);
  const end = ms(e.drift_end?.ended_at) ?? (start != null && e.duration_seconds != null ? start + Number(e.duration_seconds) * 1000 : null);
  return [start, end];
}

const dayFormat = new Intl.DateTimeFormat("en-US", { month: "short", day: "numeric", timeZone: "America/Los_Angeles" });

// ---- review marks (per browser) ----
function loadReview() {
  try {
    return JSON.parse(localStorage.getItem(REVIEW_KEY) || "{}") || {};
  } catch {
    return {};
  }
}
const review = loadReview();
function saveReview() {
  try {
    localStorage.setItem(REVIEW_KEY, JSON.stringify(review));
  } catch {
    // storage unavailable (private window, blocked site data): marks last for this page view only
  }
}
const pointKey = (agent, p) => `${agent}::${p.rule}::${p.call_id}`;
const statusOf = (agent, p) => review[pointKey(agent, p)]?.status || "open";

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function renderRuleKey() {
  document.querySelector("#rule-key").replaceChildren(...RULE_ORDER.map((id) => {
    const r = RULES[id];
    const box = element("div");
    box.append(element("strong", "", `${r.n} · ${r.label}`), document.createTextNode(r.purpose));
    return box;
  }));
}

function renderStrip(agent, points, mainType) {
  const episodes = episodesByAgent.get(agent) || [];
  const spans = episodes.map(episodeSpan).filter(([a]) => a != null);
  const pointTimes = points.map((p) => ms(p.moment_utc)).filter((t) => t != null);
  const start = Math.min(windowStart.get(agent) ?? Infinity, ...spans.map(([a]) => a), ...pointTimes);
  const end = HORIZON_MS;
  const pos = (t) => `${Math.max(0, Math.min(100, ((t - start) / (end - start)) * 100))}%`;
  const strip = element("div", "ip-strip");
  const goalWindow = element("span", "ip-strip-window");
  goalWindow.style.left = "0%";
  goalWindow.style.width = "100%";
  strip.append(goalWindow);
  episodes.forEach((e) => {
    const [a, z] = episodeSpan(e);
    if (a == null) return;
    const bar = element("span", `ip-strip-ep${categoryOf.get(e.episode_id) === mainType ? " is-main" : ""}`);
    bar.style.left = pos(a);
    bar.style.width = `calc(${pos(z ?? a)} - ${pos(a)})`;
    bar.title = `${categoryLabel.get(categoryOf.get(e.episode_id)) || ""} · ${e.activity}`;
    strip.append(bar);
  });
  // Markers within ~3% of each other alternate between two heights so their labels don't overlap.
  let lastLeft = -Infinity;
  let raised = false;
  [...points].sort((l, r) => (ms(l.moment_utc) ?? 0) - (ms(r.moment_utc) ?? 0)).forEach((p) => {
    const t = ms(p.moment_utc);
    if (t == null) return;
    const left = ((t - start) / (end - start)) * 100;
    raised = left - lastLeft < 3 ? !raised : false;
    lastLeft = left;
    const mark = element("span", `ip-strip-mark${raised ? " is-raised" : ""}`);
    mark.style.left = pos(t);
    mark.title = `${RULES[p.rule]?.label || p.rule} · ${p.moment_pt}`;
    mark.append(element("b", "", RULES[p.rule]?.n || "?"), element("i"));
    strip.append(mark);
  });
  const axis = element("div", "ip-strip-axis");
  axis.append(element("span", "", dayFormat.format(start)), element("span", "", "Oct 2"));
  const wrap = element("div");
  wrap.append(strip, axis);
  return wrap;
}

function copyText(text, button) {
  const done = () => {
    const old = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => (button.textContent = old), 1200);
  };
  if (navigator.clipboard?.writeText) {
    navigator.clipboard.writeText(text).then(done, () => window.prompt("Copy:", text));
  } else {
    window.prompt("Copy:", text);
  }
}

function fact(term, value, className = "") {
  const dl = element("dl", "ip-fact");
  const dt = element("dt", "", term);
  const dd = element("dd", className);
  if (value instanceof Node) dd.append(value);
  else dd.textContent = value;
  dl.append(dt, dd);
  return dl;
}

function renderPoint(agent, p) {
  const r = RULES[p.rule] || { n: "?", label: p.rule, purpose: "" };
  const status = statusOf(agent, p);
  const item = element("li", `ip-point${status === "ok" ? " is-ok" : status === "change" ? " is-change" : ""}`);
  const body = element("div", "ip-body");
  const head = element("div", "ip-head");
  head.append(element("strong", "", r.label), element("span", "ip-when", p.moment_pt));
  body.append(head, element("span", "ip-purpose", r.purpose));
  body.append(fact("Its action", p.call_action || "—", "ip-action"));
  body.append(fact("Why here", p.why + (p.flag ? ` ⚠ ${p.flag}` : "")));
  const episode = episodeById.get(p.episode_id);
  if (episode) {
    const [a, z] = episodeSpan(episode);
    const hours = (Number(episode.duration_seconds || 0) / 3600).toFixed(1);
    const range = a != null ? `${dayFormat.format(a)}${z != null && dayFormat.format(z) !== dayFormat.format(a) ? `–${dayFormat.format(z)}` : ""}` : "";
    body.append(fact("Episode", `${episode.activity} (${categoryLabel.get(p.category) || p.category}, ${hours} h, ${range})`));
    if (p.rule === "before_recovery" && episode.drift_end?.reason) body.append(fact("How it ended", episode.drift_end.reason));
  }
  const links = element("div", "ip-links");
  const copy = element("button", "ip-copy", "Copy village-exact command");
  copy.type = "button";
  copy.title = p.call_id;
  copy.addEventListener("click", () => copyText(`village-exact show ${p.call_id} --memory`, copy));
  const t = ms(p.moment_utc);
  const replay = element("a", "", "Village replay ↗");
  replay.href = `https://theaidigest.org/village?date=${String(p.moment_utc).slice(0, 10)}&time=${t}&agent=${encodeURIComponent(agent)}`;
  replay.target = "_blank";
  replay.rel = "noopener";
  const evidence = element("a", "", "Episode evidence ↗");
  evidence.href = `index.html?scope=maximization#${encodeURIComponent(p.episode_id)}`;
  evidence.target = "_blank";
  evidence.rel = "noopener";
  links.append(copy, replay, evidence);
  body.append(fact("Call", links));

  const reviewRow = element("div", "ip-review");
  const name = `review-${pointKey(agent, p)}`;
  [["open", "Not reviewed"], ["ok", "Looks right"], ["change", "Needs change"]].forEach(([value, label]) => {
    const option = element("label");
    const input = document.createElement("input");
    input.type = "radio";
    input.name = name;
    input.value = value;
    input.checked = status === value;
    input.addEventListener("change", () => {
      review[pointKey(agent, p)] = { ...(review[pointKey(agent, p)] || {}), status: value, updated_at: new Date().toISOString() };
      saveReview();
      render();
    });
    option.append(input, document.createTextNode(label));
    reviewRow.append(option);
  });
  const note = element("input", "ip-note");
  note.type = "text";
  note.placeholder = "Note (e.g. better moment, wrong episode)";
  note.value = review[pointKey(agent, p)]?.note || "";
  note.addEventListener("change", () => {
    review[pointKey(agent, p)] = { status: statusOf(agent, p), ...(review[pointKey(agent, p)] || {}), note: note.value, updated_at: new Date().toISOString() };
    saveReview();
  });
  reviewRow.append(note);
  body.append(reviewRow);

  item.append(element("span", "ip-num", r.n), body);
  return item;
}

function renderCard(a) {
  const card = element("article", "ip-card");
  const title = element("div", "ip-title");
  title.append(element("h3", "", a.agent));
  const badges = element("div", "ip-badges");
  const statuses = a.points.map((p) => statusOf(a.agent, p));
  const done = statuses.filter((s) => s !== "open").length;
  badges.append(element("span", "ip-badge", `${a.points.length} points`));
  const progress = element("span", `ip-badge${statuses.includes("change") ? " is-change" : done === a.points.length ? " is-done" : ""}`,
    statuses.includes("change") ? `${statuses.filter((s) => s === "change").length} to change` : `${done}/${a.points.length} reviewed`);
  badges.append(progress);
  title.append(badges);
  const sub = element("p", "ip-sub");
  sub.append(document.createTextNode(`${a.main_type_label} `),
    element("span", "", `· ${a.main_type_hours} h of ${a.total_hours} h drift · ${a.main_type_episodes} episode${a.main_type_episodes === 1 ? "" : "s"} of this type`));
  const head = element("div");
  head.append(title, sub);
  const list = element("ol", "ip-points");
  [...a.points]
    .sort((l, r) => RULE_ORDER.indexOf(l.rule) - RULE_ORDER.indexOf(r.rule))
    .forEach((p) => list.append(renderPoint(a.agent, p)));
  card.append(head, renderStrip(a.agent, a.points, a.main_type), list);
  return card;
}

function render() {
  const sort = document.querySelector("#ip-sort").value;
  const type = document.querySelector("#ip-type").value;
  const rule = document.querySelector("#ip-rule").value;
  const status = document.querySelector("#ip-status").value;
  const query = document.querySelector("#ip-search").value.trim().toLowerCase();
  const reviewed = (a) => a.points.filter((p) => statusOf(a.agent, p) !== "open").length / a.points.length;
  const sorters = {
    hours: (l, r) => r.main_type_hours - l.main_type_hours,
    agent: (l, r) => l.agent.localeCompare(r.agent),
    points: (l, r) => r.points.length - l.points.length,
    review: (l, r) => reviewed(l) - reviewed(r)
  };
  const visible = selection.agents
    .filter((a) => !type || a.main_type === type)
    .filter((a) => !rule || a.points.some((p) => p.rule === rule))
    .filter((a) => {
      const s = a.points.map((p) => statusOf(a.agent, p));
      if (status === "open") return s.includes("open");
      if (status === "change") return s.includes("change");
      if (status === "done") return !s.includes("open");
      return true;
    })
    .filter((a) => !query || a.agent.toLowerCase().includes(query))
    .sort((l, r) => (sorters[sort] || sorters.hours)(l, r) || l.agent.localeCompare(r.agent));
  const list = document.querySelector("#ip-list");
  list.replaceChildren(...(visible.length ? visible.map(renderCard) : [element("p", "empty", "No agents match these filters.")]));
  const all = selection.agents.flatMap((a) => a.points.map((p) => statusOf(a.agent, p)));
  document.querySelector("#ip-meta").textContent =
    `${visible.length} of ${selection.agents.length} agents · ${all.length} points · ${all.filter((s) => s !== "open").length} reviewed`;
}

function initialize() {
  renderRuleKey();
  const types = [...new Map(selection.agents.map((a) => [a.main_type, a.main_type_label])).entries()].sort((l, r) => l[1].localeCompare(r[1]));
  const typeSelect = document.querySelector("#ip-type");
  types.forEach(([id, label]) => typeSelect.append(new Option(label, id)));
  const ruleSelect = document.querySelector("#ip-rule");
  RULE_ORDER.forEach((id) => {
    const n = selection.agents.filter((a) => a.points.some((p) => p.rule === id)).length;
    if (n) ruleSelect.append(new Option(`${RULES[id].n} · ${RULES[id].label} (${n})`, id));
  });
  ["#ip-sort", "#ip-type", "#ip-rule", "#ip-status"].forEach((id) => document.querySelector(id).addEventListener("change", render));
  document.querySelector("#ip-search").addEventListener("input", render);
  document.querySelector("#ip-export").addEventListener("click", () => {
    const rows = selection.agents.flatMap((a) => a.points.map((p) => ({
      agent: a.agent, rule: p.rule, call_id: p.call_id, episode_id: p.episode_id, moment_utc: p.moment_utc,
      status: statusOf(a.agent, p), note: review[pointKey(a.agent, p)]?.note || "",
      updated_at: review[pointKey(a.agent, p)]?.updated_at || null
    })));
    const blob = new Blob([JSON.stringify({ exported_at: new Date().toISOString(), points: rows }, null, 1)], { type: "application/json" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `interview-point-review-${new Date().toISOString().slice(0, 10)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
  });
  const excluded = selection.excluded || [];
  if (excluded.length) {
    const box = document.querySelector("#ip-excluded");
    box.hidden = false;
    box.append(element("strong", "", "Not interviewed (too little goal-max drift)"));
    const ul = element("ul");
    excluded.forEach((x) => ul.append(element("li", "", `${x.agent}: ${x.reason}`)));
    box.append(ul);
  }
  render();
}

initialize();
