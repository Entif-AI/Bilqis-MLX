const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const CAPABILITY_SCHEMA = "bilqis.bamf.mission-control.capability-snapshot/v1";
const DOSSIER_SCHEMA = "bilqis.bamf.mission-control.capability-dossier/v1";
const PAGE_LIMIT = 32;
const MAX_PAGES = 128;

function value(datum) {
  return datum?.state === "PRESENT" ? datum.value : null;
}

function dossierValue(record, name) {
  for (const entry of record?.entries ?? []) {
    for (const item of entry?.values ?? []) {
      if (item?.name === name) return value(item.value);
    }
  }
  return null;
}

export function capabilityQuery(context, cursor = null, schemaVersion = CAPABILITY_SCHEMA) {
  const historical = context?.mode === "HISTORICAL";
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family: "capability",
    mode: historical ? "historical" : "current",
    run_id: context?.runId ?? null,
    record_id: null,
    schema_version: schemaVersion,
    generation: historical ? context?.generation ?? null : null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor,
    limit: PAGE_LIMIT,
  });
}

export function schoolRowFromRecord(record, dossier = null, dossierState = "UNAVAILABLE") {
  if (record?.schema_version !== CAPABILITY_SCHEMA) return null;
  const gap = dossier ? "DOSSIER_FIELD_MISSING"
    : dossierState === "EMPTY" ? "DOSSIER_MISSING" : "DOSSIER_UNAVAILABLE";
  const was = dossierValue(dossier, "was");
  const top = value(dossier?.top);
  const visits = dossierValue(dossier, "visits");
  const retainedSteps = dossierValue(dossier, "retained_steps");
  const strategy = dossierValue(dossier, "strategy");
  const prerequisiteCount = dossierValue(dossier, "prerequisite_count");
  const prerequisites = (dossier?.entries ?? [])
    .filter((entry) => entry.kind === "prerequisite" && entry.related_kind === "capability")
    .map((entry) => entry.related_id);
  const prerequisitesKnown = Number.isInteger(prerequisiteCount) && prerequisiteCount === prerequisites.length;
  return Object.freeze({
    id: record.capability_id,
    grade: record.grade_id,
    family: null,
    prerequisites: Object.freeze(prerequisitesKnown ? prerequisites : []),
    was,
    top,
    now: value(record.score_correct),
    total: value(record.score_total),
    growth: null,
    debt: value(record.debt),
    pRet: null,
    visits,
    retainedSteps,
    lastGain: null,
    lastRegression: null,
    strategy,
    sourceFamilies: Object.freeze((dossier?.entries ?? [])
      .filter((entry) => entry.kind === 'observed-source-family')
      .map((entry) => entry.related_id)),
    sourceState: value(dossier?.source_state),
    implementationState: null,
    lifecycleState: record.status,
    qualificationState: record.status,
    staleDebt: false,
    recentGain: false,
    observedDebt: value(record.debt) !== null,
    schedulingSemantics: null,
    observedAt: record.meta?.observed_at ?? null,
    materializedAt: record.meta?.materialized_at ?? null,
    recordId: record.meta?.record_id ?? record.capability_id,
    sourceRefs: Object.freeze([...(record.meta?.source_refs ?? [])]),
    evidenceRefs: Object.freeze([...(record.meta?.evidence_refs ?? [])]),
    receiptRefs: Object.freeze([...(record.meta?.receipt_refs ?? [])]),
    absenceReasons: Object.freeze({
      prerequisites: prerequisitesKnown ? null : "PREREQUISITE_PROJECTION_UNAVAILABLE",
      was: was === null ? gap : null,
      top: top === null ? gap : null,
      growth: "GROWTH_NOT_MEASURED",
      pRet: "PRET_NOT_MEASURED",
      visits: visits === null ? gap : null,
      retainedSteps: retainedSteps === null ? gap : null,
      lastGain: "HISTORY_EVENT_SUMMARY_NOT_PROJECTED",
      lastRegression: "HISTORY_EVENT_SUMMARY_NOT_PROJECTED",
      strategy: strategy === null ? gap : null,
      sourceFamilies: "SOURCE_FAMILY_PROJECTION_UNAVAILABLE",
      sourceState: value(dossier?.source_state) === null ? "SOURCE_STATE_PROJECTION_UNAVAILABLE" : null,
      implementationState: "IMPLEMENTATION_STATE_PROJECTION_UNAVAILABLE",
    }),
  });
}

async function loadSchema(api, context, schemaVersion) {
  const records = [];
  let cursor = null;
  let state = "EMPTY";
  let coverage = "UNKNOWN";
  for (let pageIndex = 0; pageIndex < MAX_PAGES; pageIndex += 1) {
    const page = await api.query(capabilityQuery(context, cursor, schemaVersion));
    if (page?.accepted !== true) {
      return { state: page?.state ?? "UNAVAILABLE", coverage: page?.coverage ?? "UNKNOWN", records: [] };
    }
    state = page.state;
    coverage = page.coverage;
    records.push(...(page.records ?? []));
    cursor = page.next_cursor ?? null;
    if (cursor === null) return { state, coverage, records };
  }
  throw new RangeError("SCHOOL_CAPABILITY_QUERY_PAGE_LIMIT");
}

export async function loadSchoolRows(api, context) {
  if (!api || typeof api.query !== "function") {
    return Object.freeze({ state: "UNAVAILABLE", coverage: "UNKNOWN", rows: Object.freeze([]), reason: "CONTROL_PLANE_QUERY_UNAVAILABLE" });
  }
  const snapshots = await loadSchema(api, context, CAPABILITY_SCHEMA);
  if (!snapshots.records.length && snapshots.state !== "EMPTY") {
    return Object.freeze({ state: snapshots.state, coverage: snapshots.coverage, rows: Object.freeze([]), reason: "CAPABILITY_QUERY_REJECTED" });
  }
  const dossiers = await loadSchema(api, context, DOSSIER_SCHEMA);
  const byCapability = new Map(
    dossiers.records.filter((record) => record?.schema_version === DOSSIER_SCHEMA)
      .map((record) => [record.capability_id, record]),
  );
  const rows = snapshots.records.map((record) => schoolRowFromRecord(
    record, byCapability.get(record.capability_id) ?? null, dossiers.state,
  )).filter(Boolean);
  return Object.freeze({ state: snapshots.state, coverage: snapshots.coverage, rows: Object.freeze(rows), reason: null });
}
