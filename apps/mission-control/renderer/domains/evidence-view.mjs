const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const PAGE_SIZE = 16;

export const SEARCH_KINDS = Object.freeze([
  ["context", "Current run / generation"],
  ["record", "Exact record ID"],
  ["run", "Run ID"],
  ["generation", "Generation"],
  ["checkpoint", "Checkpoint digest"],
  ["capability", "Capability ID"],
  ["episode", "Candidate / episode ID"],
  ["source", "Source / source revision"],
  ["semantic", "Semantic ID"],
  ["frame", "Frame ID"],
  ["memory", "Memory motif / slot identity"],
  ["correction", "Correction / requalification ID"],
  ["command", "Command operation ID"],
  ["reference", "Receipt / evidence reference"],
]);

const ui = {
  contextKey: null,
  status: "idle",
  criteria: { kind: "context", value: "" },
  page: null,
  records: [],
  links: [],
  selected: null,
  selectedLinks: null,
  raw: false,
  error: null,
};

function esc(value) {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#39;");
}

function request(overrides = {}) {
  return {
    schema: QUERY_SCHEMA, family: "record", mode: "current", run_id: null,
    record_id: null, schema_version: null, generation: null, frontier_id: null,
    as_of: null, reference: null, cursor: null, limit: PAGE_SIZE, ...overrides,
  };
}

function scoped(context, overrides = {}) {
  const historical = context.mode === "HISTORICAL";
  return request({
    mode: historical ? "historical" : "current",
    run_id: context.runId,
    generation: context.generation,
    ...overrides,
  });
}

export function buildEvidenceRequest(context, criteria = {}, cursor = null) {
  const kind = criteria.kind ?? "context";
  const value = String(criteria.value ?? "").trim();
  if (kind === "context") return scoped(context, { cursor });
  if (kind === "record") {
    return request({
      mode: context.mode === "HISTORICAL" ? "historical" : "current",
      record_id: value || null,
      generation: context.mode === "HISTORICAL" ? context.generation : null,
      run_id: context.mode === "HISTORICAL" ? context.runId : null,
      cursor,
    });
  }
  if (kind === "run") return request({ run_id: value || null, cursor });
  if (kind === "generation") {
    const generation = Number(value);
    return request({
      mode: "historical", run_id: context.runId,
      generation: Number.isSafeInteger(generation) && generation >= 0 ? generation : null,
      cursor,
    });
  }
  if (kind === "reference") {
    return scoped(context, { family: "reference", reference: value || null, cursor });
  }
  const exact = kind === "checkpoint" && value && !value.startsWith("checkpoint:")
    ? `checkpoint:${value}` : value;
  const crossContext = new Set(["source", "semantic", "command"]).has(kind);
  return crossContext
    ? request({ reference: exact || null, cursor })
    : scoped(context, { reference: exact || null, cursor });
}

export async function loadEvidencePage(api, context, criteria, cursor = null) {
  return api.query(buildEvidenceRequest(context, criteria, cursor));
}

export async function loadRecordById(api, context, recordId) {
  const page = await api.query(buildEvidenceRequest(
    context, { kind: "record", value: recordId }, null,
  ));
  return { page, record: page.records?.[0] ?? null };
}

export async function loadRecordLinks(api, record) {
  const meta = record?.meta ?? {};
  const run = meta.run ?? null;
  return api.query(request({
    family: "links",
    mode: run ? "historical" : "current",
    run_id: run?.run_id ?? null,
    record_id: meta.record_id ?? null,
    generation: run?.generation ?? null,
    as_of: run ? meta.as_of ?? null : null,
    limit: 32,
  }));
}

function pageState(page) {
  if (!page) return "NOT QUERIED";
  const suffix = page.truncated ? " · TRUNCATED" : "";
  return `${page.state} · ${page.coverage}${suffix}`;
}

function markerSummary(marker) {
  const meta = marker?.meta ?? {};
  const details = [
    ...(Array.isArray(marker?.missing_fields) ? marker.missing_fields : []),
    marker?.reason ?? null,
    marker?.resource ?? null,
    marker?.stale_record_id ?? null,
    Number.isSafeInteger(marker?.requested_as_of) ? `requested as-of ${marker.requested_as_of}` : null,
    Number.isSafeInteger(marker?.available_as_of) ? `available as-of ${marker.available_as_of}` : null,
  ].filter((value) => value !== null && value !== undefined);
  return `<article class="evidence-marker"><strong>${esc(marker?.schema_version ?? "DEGRADED EVIDENCE MARKER")}</strong>
    <code>${esc(meta.record_id ?? "marker:unidentified")}</code>
    <span>${details.length ? esc(details.join(" · ")) : "Exact degraded-state marker; no additional detail reported."}</span></article>`;
}

function recordSummary(record, index) {
  const meta = record.meta ?? {};
  const run = meta.run ?? null;
  return `<button class="evidence-result" type="button" data-evidence-record="${index}">
    <strong>${esc(meta.record_id ?? "UNIDENTIFIED RECORD")}</strong>
    <span>${esc(record.schema_version ?? "SCHEMA UNKNOWN")}</span>
    <small>${esc(meta.authority ?? "AUTHORITY UNKNOWN")} · ${esc(meta.coverage ?? "COVERAGE UNKNOWN")}${run ? ` · gen ${esc(run.generation)}` : ""}</small>
  </button>`;
}

function linkSummary(link, index) {
  const target = link.target_record_id
    ? `<button type="button" data-evidence-target="${index}">Open exact record</button>`
    : `<span class="evidence-unresolved">EXTERNAL / NOT HYDRATED</span>`;
  return `<article class="evidence-link"><strong>${esc(link.relation)}</strong>
    <code>${esc(link.source_record_id)}</code><span>→</span><code>${esc(link.target_ref)}</code>${target}</article>`;
}

function refs(meta) {
  const groups = [
    ["SOURCE", meta?.source_refs ?? []],
    ["EVIDENCE", meta?.evidence_refs ?? []],
    ["RECEIPT", meta?.receipt_refs ?? []],
  ];
  return groups.map(([kind, values]) => values.map((value) =>
    `<button type="button" data-evidence-ref="${esc(value)}"><b>${kind}</b> ${esc(value)}</button>`,
  ).join("")).join("") || '<span class="evidence-unresolved">No provenance refs reported.</span>';
}

function readable(record, linksPage) {
  const meta = record.meta ?? {};
  const body = Object.entries(record).filter(([key]) => key !== "meta")
    .map(([key, value]) => `<dt>${esc(key)}</dt><dd><code>${esc(
      typeof value === "object" ? JSON.stringify(value) : value,
    )}</code></dd>`).join("");
  const verification = record.verification_state ?? record.verification_status ?? "NOT SEPARATELY REPORTED";
  return `<div class="evidence-readable">
    <dl><dt>Record ID</dt><dd>${esc(meta.record_id)}</dd><dt>Schema / version</dt><dd>${esc(record.schema_version)}</dd>
    <dt>Authority</dt><dd>${esc(meta.authority)}</dd><dt>Coverage</dt><dd>${esc(meta.coverage)}</dd>
    <dt>Verification</dt><dd>${esc(verification)}</dd><dt>Materialized</dt><dd>${esc(meta.materialized_at ?? "UNKNOWN")}</dd>
    <dt>Observed</dt><dd>${esc(meta.observed_at ?? "UNKNOWN")}</dd><dt>As of</dt><dd>${esc(meta.as_of ?? "UNKNOWN")}</dd>${body}</dl>
    <section><h4>Provenance chain</h4><div class="evidence-refs">${refs(meta)}</div></section>
    <section><h4>Exact links</h4><div class="evidence-links">${(linksPage?.links ?? []).map(linkSummary).join("") || '<span class="evidence-unresolved">No resolvable links reported.</span>'}</div></section>
  </div>`;
}

export function renderEvidenceMarkup(state = ui) {
  const page = state.page;
  const selected = state.selected;
  const markers = (page?.markers ?? []).map(markerSummary).join("");
  const results = [
    ...state.records.map(recordSummary),
    ...state.links.map((link, index) => linkSummary(link, index)),
  ].join("");
  const selectedMarkup = !selected ? "" : `<section class="evidence-detail">
    <header><div><span class="eyebrow">Exact evidence item</span><h3>${esc(selected.meta?.record_id)}</h3></div>
      <button type="button" data-evidence-raw>${state.raw ? "Readable view" : "Raw structured payload"}</button></header>
    ${state.raw ? `<pre>${esc(JSON.stringify(selected, null, 2))}</pre>` : readable(selected, state.selectedLinks)}
  </section>`;
  return `<div class="evidence-view"><header class="evidence-heading"><div><span class="eyebrow">GUI16 · Evidence &amp; Receipts</span>
    <h2>Forensic provenance browser</h2></div><p>Literal CP03 records only. External payloads remain external unless the control plane exposes an exact record identity.</p></header>
    <form id="evidence-search-form" class="evidence-search"><label>Search by<select name="kind">${SEARCH_KINDS.map(([value, label]) =>
      `<option value="${value}"${state.criteria.kind === value ? " selected" : ""}>${label}</option>`).join("")}</select></label>
      <label>Exact identity<input name="value" value="${esc(state.criteria.value)}" autocomplete="off" /></label><button type="submit">Search</button></form>
    <div class="evidence-query-state" data-state="${esc(page?.state ?? state.status)}"><strong>${esc(pageState(page))}</strong>
      <span>${page ? `${esc(page.returned)} returned / ${esc(page.total_matches)} exact matches` : esc(state.error ?? "Ready")}</span></div>
    ${markers ? `<section class="evidence-markers" aria-label="Omissions and degraded evidence">${markers}</section>` : ""}
    <div class="evidence-results">${results || '<div class="evidence-empty">No evidence rows returned for this exact query.</div>'}</div>
    ${page?.next_cursor ? '<button type="button" data-evidence-more>Load next bounded page</button>' : ""}${selectedMarkup}</div>`;
}

async function search(container, api, context, criteria, cursor = null, append = false) {
  ui.status = "loading"; ui.error = null; ui.criteria = criteria;
  renderEvidenceView(container, api, context);
  try {
    const page = await loadEvidencePage(api, context, criteria, cursor);
    ui.page = page; ui.status = "ready";
    ui.records = append ? [...ui.records, ...(page.records ?? [])] : [...(page.records ?? [])];
    ui.links = append ? [...ui.links, ...(page.links ?? [])] : [...(page.links ?? [])];
    if (!append) { ui.selected = null; ui.selectedLinks = null; ui.raw = false; }
  } catch (error) {
    ui.status = "error"; ui.error = error?.code ?? error?.message ?? "Evidence query failed";
  }
  renderEvidenceView(container, api, context);
}

async function select(container, api, context, record) {
  ui.selected = record; ui.raw = false; ui.selectedLinks = null;
  renderEvidenceView(container, api, context);
  try { ui.selectedLinks = await loadRecordLinks(api, record); } catch (_error) { ui.selectedLinks = null; }
  renderEvidenceView(container, api, context);
}

function bind(container, api, context) {
  container.querySelector("#evidence-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void search(container, api, context, {
      kind: data.get("kind")?.toString() ?? "context",
      value: data.get("value")?.toString() ?? "",
    });
  });
  container.querySelectorAll("[data-evidence-record]").forEach((button) => button.addEventListener("click", () =>
    void select(container, api, context, ui.records[Number(button.dataset.evidenceRecord)])));
  container.querySelectorAll("[data-evidence-target]").forEach((button) => button.addEventListener("click", async () => {
    const link = ui.links[Number(button.dataset.evidenceTarget)] ?? ui.selectedLinks?.links?.[Number(button.dataset.evidenceTarget)];
    if (!link?.target_record_id) return;
    const found = await loadRecordById(api, context, link.target_record_id);
    if (found.record) void select(container, api, context, found.record);
  }));
  container.querySelectorAll("[data-evidence-ref]").forEach((button) => button.addEventListener("click", () =>
    void search(container, api, context, { kind: "reference", value: button.dataset.evidenceRef })));
  container.querySelector("[data-evidence-raw]")?.addEventListener("click", () => {
    ui.raw = !ui.raw; renderEvidenceView(container, api, context);
  });
  container.querySelector("[data-evidence-more]")?.addEventListener("click", () =>
    void search(container, api, context, ui.criteria, ui.page?.next_cursor ?? null, true));
}

export function renderEvidenceView(container, api, context, initialId = null) {
  const key = `${context.mode}:${context.runId}:${context.generation}`;
  if (ui.contextKey !== key) Object.assign(ui, {
    contextKey: key, status: "idle", criteria: { kind: initialId ? "record" : "context", value: initialId ?? "" },
    page: null, records: [], links: [], selected: null, selectedLinks: null, raw: false, error: null,
  });
  container.innerHTML = renderEvidenceMarkup(ui);
  bind(container, api, context);
  if (ui.status === "idle") void search(container, api, context, ui.criteria);
}
