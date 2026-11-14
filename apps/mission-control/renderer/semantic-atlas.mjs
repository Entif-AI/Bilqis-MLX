export const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
export const QUERY_PAGE_SCHEMA = "bilqis.bamf.control-plane.query-page/v1";
export const CONCEPT_SCHEMA = "bilqis.bamf.mission-control.semantic-concept-snapshot/v1";
export const STATE_SCHEMA = "bilqis.bamf.mission-control.semantic-generation-state/v1";
export const BANK_SCHEMA = "bilqis.bamf.mission-control.semantic-bank-snapshot/v1";
export const HELD_SCHEMA = "bilqis.bamf.mission-control.semantic-held-mapping/v1";
export const SIMILARITY_SCHEMA = "bilqis.bamf.mission-control.semantic-similarity-snapshot/v1";
export const SUMMARY_SCHEMA = "bilqis.bamf.mission-control.semantic-atlas-snapshot/v1";

const PAGE_STATES = new Set([
  "PRESENT", "EMPTY", "MISSING", "UNAVAILABLE", "PARTIAL", "STALE", "DENIED", "UNKNOWN",
]);

function invalid(detail) {
  throw new TypeError(`MISSION_CONTROL_SEMANTIC_QUERY_INVALID:${detail}`);
}

export function conceptRecordId(semanticRelease, semanticId) {
  if (typeof semanticRelease !== "string" || !/^[0-9a-f]{64}$/.test(semanticRelease) ||
      typeof semanticId !== "string" || semanticId.length === 0 || semanticId.includes("\n")) {
    invalid("CONCEPT_ID");
  }
  return `semantic-concept:${semanticRelease}:${semanticId}`;
}

export function stateRecordId(context, bank, row) {
  if (!context || typeof context.runId !== "string" || !Number.isSafeInteger(context.generation) ||
      !Number.isSafeInteger(bank) || bank < 0 || !Number.isSafeInteger(row) || row < 0) {
    invalid("STATE_ID");
  }
  return `semantic-state:${context.runId}:${context.generation}:${bank}:${row}`;
}

export function queryRequest({
  family = "semantic", mode = "current", runId = null, recordId = null,
  schemaVersion = null, generation = null, frontierId = null, asOf = null,
  reference = null, cursor = null, limit = 32,
} = {}) {
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family,
    mode,
    run_id: runId,
    record_id: recordId,
    schema_version: schemaVersion,
    generation,
    frontier_id: frontierId,
    as_of: asOf,
    reference,
    cursor,
    limit,
  });
}

function generationSelector(context) {
  if (context.mode === "HISTORICAL") {
    return { mode: "historical", runId: context.runId, generation: context.generation };
  }
  return { mode: "current", runId: context.runId };
}

export function generationQuery(context, options = {}) {
  return queryRequest({ ...generationSelector(context), ...options });
}

export function sourceQuery(options = {}) {
  return queryRequest({ mode: "current", ...options });
}

export function assertQueryPage(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) invalid("PAGE");
  if (raw.accepted === false) {
    if (typeof raw.reason !== "string" || raw.reason.length === 0) invalid("ERROR");
    return raw;
  }
  if (raw.schema !== QUERY_PAGE_SCHEMA || raw.accepted !== true ||
      !PAGE_STATES.has(raw.state) || !Array.isArray(raw.records) ||
      !Array.isArray(raw.markers) || !Array.isArray(raw.links) ||
      !Number.isSafeInteger(raw.total_matches) || raw.total_matches < 0) {
    invalid("PAGE_SHAPE");
  }
  return raw;
}

async function ask(api, request) {
  if (!api || typeof api.query !== "function") invalid("QUERY_CAPABILITY");
  return assertQueryPage(await api.query(request));
}

function firstRecord(page, schema) {
  return page.accepted === true
    ? page.records.find((record) => record?.schema_version === schema) ?? null
    : null;
}

export async function loadAtlasOverview(api, context) {
  const [summary, banks, held, similarities] = await Promise.all([
    ask(api, generationQuery(context, { schemaVersion: SUMMARY_SCHEMA, limit: 1 })),
    ask(api, generationQuery(context, { schemaVersion: BANK_SCHEMA, limit: 32 })),
    ask(api, sourceQuery({ schemaVersion: HELD_SCHEMA, limit: 8 })),
    ask(api, generationQuery(context, { schemaVersion: SIMILARITY_SCHEMA, limit: 8 })),
  ]);
  return Object.freeze({ summary, banks, held, similarities });
}

async function learnedEdges(api, context, semanticId) {
  const references = await ask(api, generationQuery(context, {
    family: "reference", reference: semanticId, limit: 32,
  }));
  if (references.accepted !== true) return [];
  const recordIds = [...new Set(references.links
    .filter((link) => link.relation === "LEARNED_SIMILARITY_SOURCE" ||
      link.relation === "LEARNED_SIMILARITY_TARGET")
    .map((link) => link.source_record_id))];
  const pages = await Promise.all(recordIds.slice(0, 32).map((recordId) =>
    ask(api, generationQuery(context, { recordId, limit: 1 }))));
  return pages.map((page) => firstRecord(page, SIMILARITY_SCHEMA)).filter(Boolean);
}

async function heldForIdentity(api, semanticId) {
  const references = await ask(api, sourceQuery({
    family: "reference", reference: semanticId, limit: 32,
  }));
  if (references.accepted !== true) return null;
  const held = references.links.find((link) => link.relation === "HELD_SEMANTIC_IDENTITY");
  if (!held) return null;
  const page = await ask(api, sourceQuery({ recordId: held.source_record_id, limit: 1 }));
  return firstRecord(page, HELD_SCHEMA);
}

export async function loadSemanticIdentity(api, context, semanticId) {
  const conceptPage = await ask(api, sourceQuery({
    recordId: conceptRecordId(context.semanticRelease, semanticId), limit: 1,
  }));
  const concept = firstRecord(conceptPage, CONCEPT_SCHEMA);
  if (!concept) {
    return Object.freeze({ semanticId, concept: null, state: null,
      held: await heldForIdentity(api, semanticId), similarities: [] });
  }
  const statePage = await ask(api, generationQuery(context, {
    recordId: stateRecordId(context, concept.abi_bank, concept.abi_row), limit: 1,
  }));
  const state = firstRecord(statePage, STATE_SCHEMA);
  const similarities = await learnedEdges(api, context, semanticId);
  return Object.freeze({ semanticId, concept, state, held: null, similarities });
}

export async function loadAbiRow(api, context, bank, row) {
  const statePage = await ask(api, generationQuery(context, {
    recordId: stateRecordId(context, bank, row), limit: 1,
  }));
  const state = firstRecord(statePage, STATE_SCHEMA);
  if (!state) return Object.freeze({ bank, row, state: null, concept: null, similarities: [] });
  const conceptPage = state.concept_record_id
    ? await ask(api, sourceQuery({ recordId: state.concept_record_id, limit: 1 }))
    : null;
  const concept = conceptPage ? firstRecord(conceptPage, CONCEPT_SCHEMA) : null;
  const similarities = await learnedEdges(api, context, state.semantic_id);
  return Object.freeze({ bank, row, state, concept, similarities });
}

export function lensEdges(selection, lens) {
  if (!selection) return [];
  if (lens === "learned") {
    return (selection.similarities ?? []).map((record) => {
      if (record.canonical_equivalence !== false) {
        invalid("SIMILARITY_CANONICAL_EQUIVALENCE");
      }
      return Object.freeze({
        kind: "learned",
        source: record.source_semantic_id,
        target: record.target_semantic_id,
        relation: `similarity · ${record.similarity?.value ?? "unknown"}`,
        canonicalEquivalence: record.canonical_equivalence,
        basis: record.basis_ref,
      });
    });
  }
  return (selection.concept?.relations ?? []).map((relation) => Object.freeze({
    kind: "canonical",
    source: selection.concept.semantic_id,
    target: relation.target_semantic_id,
    relation: relation.predicate,
  }));
}

export function summarizeOverview(overview) {
  const summary = firstRecord(overview?.summary ?? {}, SUMMARY_SCHEMA);
  const banks = overview?.banks?.accepted === true ? overview.banks.records : [];
  return Object.freeze({
    active: summary?.active_concepts?.value ?? null,
    eligible: summary?.source_eligible?.value ?? null,
    held: overview?.held?.accepted === true ? overview.held.total_matches : null,
    similarityEdges: overview?.similarities?.accepted === true
      ? overview.similarities.total_matches : null,
    banks,
  });
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

function statusClass(value) {
  return String(value ?? "unknown").toLowerCase().replace(/[^a-z0-9_-]+/g, "-");
}

export function renderAtlasMarkup({ status, error, overview, selection, lens = "canonical",
  selectedBank = null } = {}) {
  if (status === "loading") return `<div class="atlas-empty">Loading semantic Atlas…</div>`;
  if (status === "error") return `<div class="atlas-empty atlas-error">${esc(error)}</div>`;
  const aggregate = overview ? summarizeOverview(overview) : null;
  const banks = aggregate?.banks ?? [];
  const heldRows = overview?.held?.accepted === true ? overview.held.records : [];
  const edges = lensEdges(selection, lens);
  const concept = selection?.concept;
  const generationState = selection?.state;
  const held = selection?.held;
  return `
    <div class="atlas-toolbar" role="toolbar" aria-label="Semantic authority lens">
      <button type="button" data-atlas-lens="canonical" aria-pressed="${lens === "canonical"}">Canonical authority</button>
      <button type="button" data-atlas-lens="learned" aria-pressed="${lens === "learned"}">Learned similarity</button>
      <span class="authority-warning">Similarity never creates canonical equivalence.</span>
    </div>
    <div class="atlas-stats">
      <span><small>Active</small><strong>${esc(aggregate?.active ?? "unknown")}</strong></span>
      <span><small>Source eligible</small><strong>${esc(aggregate?.eligible ?? "unknown")}</strong></span>
      <span><small>Held</small><strong>${esc(aggregate?.held ?? "unknown")}</strong></span>
      <span><small>Learned edges</small><strong>${esc(aggregate?.similarityEdges ?? "unavailable")}</strong></span>
    </div>
    <div class="atlas-layout">
      <section class="atlas-panel">
        <div class="atlas-panel-heading"><div><span class="eyebrow">ABI bank map</span><h2>Aggregate → bank → row</h2></div></div>
        <div class="atlas-banks">${banks.length ? banks.map((bank) => `
          <button type="button" class="atlas-bank ${selectedBank === bank.bank ? "is-selected" : ""}" data-atlas-bank="${bank.bank}">
            <strong>Bank ${bank.bank}</strong><span>${bank.active_rows} active · ${bank.masked_rows} reserved/masked</span>
            <small>${bank.recently_exercised_rows} exercised · ${bank.requalification_affected_rows} requal affected</small>
          </button>`).join("") : `<p class="atlas-muted">No bank snapshot available for this generation.</p>`}</div>
        <form id="atlas-abi-form" class="atlas-form">
          <label>Bank <input name="bank" inputmode="numeric" value="${esc(selectedBank ?? 0)}" required /></label>
          <label>Row <input name="row" inputmode="numeric" placeholder="0" required /></label>
          <button type="submit">Resolve ABI row</button>
        </form>
      </section>
      <section class="atlas-panel">
        <div class="atlas-panel-heading"><div><span class="eyebrow">Canonical identity</span><h2>Exact source-backed lookup</h2></div></div>
        <form id="atlas-search-form" class="atlas-form atlas-search">
          <label>Semantic identity <input name="semanticId" placeholder="https://…/id/sense/…" required /></label>
          <button type="submit">Inspect exact identity</button>
        </form>
        <div class="held-preview"><strong>Held source mappings</strong>
          ${heldRows.length ? `<ul>${heldRows.map((row) => `<li><code>${esc(row.key)}</code> · ${esc(row.reason_code)}</li>`).join("")}</ul>` : `<p class="atlas-muted">No held mappings returned.</p>`}
        </div>
      </section>
    </div>
    <section class="atlas-panel atlas-inspection">
      <div class="atlas-panel-heading"><div><span class="eyebrow">Identity inspector</span><h2>${esc(concept?.semantic_id ?? held?.semantic_id ?? selection?.state?.semantic_id ?? "No selection")}</h2></div>
        ${concept ? `<span class="atlas-kind">${esc(concept.kind)}</span>` : ""}</div>
      ${held ? `<div class="atlas-held"><strong>HELD · ${esc(held.reason_code)}</strong><span>${esc(held.teaching_reason)}</span><small>${esc(held.domain)} / ${esc(held.table)} / ${esc(held.key)}</small></div>` : ""}
      ${concept ? `<dl class="atlas-details">
        <dt>Source revision</dt><dd><code>${esc(concept.atlas_release_sha256)}</code></dd>
        <dt>Source loci</dt><dd>${concept.source_loci.map(esc).join("<br>") || "none"}</dd>
        <dt>ABI address</dt><dd>${concept.abi_index} · bank ${concept.abi_bank} · row ${concept.abi_row}</dd>
        <dt>Generation state</dt><dd><span class="atlas-state state-${statusClass(generationState?.admission_state)}">${esc(generationState?.admission_state ?? "not materialized")}</span></dd>
        <dt>New / exercised / requal</dt><dd>${generationState ? `${generationState.newly_admitted} / ${generationState.recently_exercised} / ${generationState.requalification_affected}` : "unknown"}</dd>
        <dt>Capabilities</dt><dd>${concept.capability_ids.map(esc).join("<br>") || "none declared"}</dd>
        <dt>Frames</dt><dd>${concept.frame_schema_refs.map(esc).join("<br>") || "none declared"}</dd>
      </dl>` : !held ? `<p class="atlas-muted">Search an exact semantic identity or resolve a bank/row.</p>` : ""}
      <div class="atlas-edges"><strong>${lens === "canonical" ? "Canonical relationships" : "Learned similarity neighborhood"}</strong>
        ${edges.length ? `<ul>${edges.map((edge) => `<li data-edge-kind="${edge.kind}"><code>${esc(edge.relation)}</code> → ${esc(edge.target)}${edge.kind === "learned" ? ` <small>${esc(edge.basis)} · canonical equivalence: ${esc(edge.canonicalEquivalence)}</small>` : ""}</li>`).join("")}</ul>` : `<p class="atlas-muted">No ${lens === "canonical" ? "canonical relationships" : "learned similarity edges"} returned.</p>`}
      </div>
    </section>`;
}
