const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const RESOURCE_SCHEMA = "bilqis.bamf.mission-control.resource-sample/v1";
const PRESENT = "PRESENT";
const TRAINER_SCHEMAS = new Set([
  "bilqis.bamf.mission-control.trainer-observation/v1",
  "bilqis.bamf.mission-control.trainer-observation/v2",
  "bilqis.bamf.mission-control.trainer-observation/v3",
  "bilqis.bamf.mission-control.trainer-observation/v4",
  "bilqis.bamf.mission-control.trainer-observation/v5",
  "bilqis.bamf.mission-control.trainer-observation/v6",
  "bilqis.bamf.mission-control.trainer-observation/v7",
]);

function absent(units = null) {
  return Object.freeze({ state: "UNAVAILABLE", value: null, units, semantic: "UNAVAILABLE", origin: null });
}

function fromDatum(datum, semantic = null) {
  if (datum?.state !== PRESENT) return absent(datum?.units ?? null);
  return Object.freeze({
    state: PRESENT,
    value: datum.value,
    units: datum.units ?? null,
    semantic: semantic ?? datum.origin ?? "MEASURED",
    origin: datum.origin ?? null,
  });
}

function derived(value, units, semantic = "DERIVED") {
  return Number.isFinite(value)
    ? Object.freeze({ state: PRESENT, value, units, semantic, origin: "DERIVED" })
    : absent(units);
}

function observed(value, units) {
  return Number.isFinite(value)
    ? Object.freeze({ state: PRESENT, value, units, semantic: "OBSERVED", origin: "TRAINER_OBSERVATION" })
    : absent(units);
}

function pageRecords(page) {
  return page?.accepted === true && Array.isArray(page.records)
    ? page.records.filter((record) => record?.schema_version === RESOURCE_SCHEMA)
    : [];
}

export function resourceQuery(context, overrides = {}) {
  const historical = context?.mode === "HISTORICAL";
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family: "resource",
    mode: historical ? "historical" : "current",
    run_id: context?.runId ?? null,
    record_id: null,
    schema_version: RESOURCE_SCHEMA,
    generation: historical ? context?.generation ?? null : null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor: null,
    limit: 32,
    ...overrides,
  });
}

export function resourceRunQuery(context) {
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family: "run",
    mode: "current",
    run_id: context?.runId ?? null,
    record_id: null,
    schema_version: null,
    generation: null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor: null,
    limit: 32,
  });
}

export function historicalResourceQuery(context, generation) {
  if (!Number.isSafeInteger(generation) || generation < 0) {
    throw new TypeError("GUI15_HISTORICAL_GENERATION_REQUIRED");
  }
  return resourceQuery({ ...context, mode: "HISTORICAL", generation }, {
    mode: "historical",
    generation,
  });
}

function liveTimeline(records) {
  return Object.freeze(records.map((record) => Object.freeze({
    id: record.meta?.record_id ?? "resource:unknown",
    observedAt: record.meta?.observed_at ?? null,
    unifiedMemoryUsed: record.memory_used_bytes?.state === PRESENT ? record.memory_used_bytes.value : null,
    mlxAllocated: null,
    batchSize: null,
    sequenceDensity: null,
    acceptedStepsHour: record.step_rate_per_minute?.state === PRESENT
      ? record.step_rate_per_minute.value * 60 : null,
    expansionCount: null,
    episodeId: null,
    batchId: null,
    checkpointId: null,
    sourceWorkload: null,
    exactRefGroups: Object.freeze({
      source: Object.freeze([...(record.meta?.source_refs ?? [])]),
      evidence: Object.freeze([...(record.meta?.evidence_refs ?? [])]),
      receipt: Object.freeze([...(record.meta?.receipt_refs ?? [])]),
    }),
    exactRefs: Object.freeze([
      ...(record.meta?.source_refs ?? []),
      ...(record.meta?.evidence_refs ?? []),
      ...(record.meta?.receipt_refs ?? []),
    ]),
  })));
}

export function resourceProfileFromPage(page, context, runPage = null) {
  const records = pageRecords(page);
  const latest = records.at(-1) ?? null;
  const observation = context?.mode === "HISTORICAL" ? null : (runPage?.accepted === true && Array.isArray(runPage.records)
    ? runPage.records.filter((record) =>
      TRAINER_SCHEMAS.has(record?.schema_version) && record.posture === "OBSERVED" &&
      record.meta?.run?.run_id === context?.runId)
      .sort((a, b) => ((b.meta?.observed_at ?? 0) - (a.meta?.observed_at ?? 0)) ||
        ((b.revision ?? 0) - (a.revision ?? 0))).at(0) ?? null
    : null);
  const stepPerMinute = latest?.step_rate_per_minute?.state === PRESENT
    ? latest.step_rate_per_minute.value : null;
  const aggregate = Object.freeze({
    unifiedMemoryUsed: fromDatum(latest?.memory_used_bytes),
    unifiedMemoryBudget: fromDatum(latest?.memory_budget_bytes, "BUDGET_VALUE"),
    forecastMemoryPeak: absent("bytes"),
    peakRss: observed(observation?.peak_rss_bytes, "bytes"),
    mlxAllocatedMemory: absent("bytes"),
    mlxCacheMemory: absent("bytes"),
    cpuUtilization: absent("percent"),
    preparationWorkers: absent("workers"),
    diskFree: observed(observation?.disk_free_bytes, "bytes"),
    diskUsed: fromDatum(latest?.disk_used_bytes),
    diskReserve: absent("bytes"),
    candidateSnapshotFootprint: absent("bytes"),
    acceptedStepsHour: derived(stepPerMinute === null ? null : stepPerMinute * 60, "steps/hour"),
    sequenceDensity: absent("fraction"),
    frameDensity: absent("fraction"),
    batchSize: absent("examples"),
    actualLengthP50: absent("positions"),
    actualLengthP95: absent("positions"),
    actualLengthMax: absent("positions"),
    preparationCompileMs: absent("ms"),
    mlxWallMs: absent("ms"),
    monetaryCost: absent("USD"),
  });
  return Object.freeze({
    provenance: "LIVE_QUERY",
    pageState: observation && (page?.accepted !== true || page.state === "EMPTY")
      ? "PARTIAL" : page?.accepted === true ? page.state : "UNAVAILABLE",
    generation: context?.generation ?? latest?.meta?.run?.generation ?? null,
    window: observation ? "resource + observed trainer data" : "accepted CP03 resource page",
    aggregate,
    memoryDecomposition: Object.freeze([
      "model-parameters", "optimizer-state", "gradients", "engram", "activations",
      "candidate-snapshot", "caches", "frame-sidecars", "other",
    ].map((id) => Object.freeze({ id, label: id.replaceAll("-", " "), value: null, state: "UNAVAILABLE" }))),
    timeline: liveTimeline(records),
    throughputInterpretation: "RESOURCE_FACT_ONLY",
  });
}

export function decomposition(profile) {
  const measured = profile.memoryDecomposition.filter((item) => item.state === PRESENT && Number.isFinite(item.value));
  const allocated = measured.reduce((sum, item) => sum + item.value, 0);
  const datum = profile.aggregate.unifiedMemoryUsed;
  const aggregate = datum?.state === PRESENT && Number.isFinite(datum.value) ? datum.value : null;
  const remainder = aggregate === null ? null : aggregate - allocated;
  const complete = aggregate !== null && remainder === 0 && measured.length === profile.memoryDecomposition.length;
  const reconciliationState = aggregate === null ? "UNAVAILABLE" : complete ? "COMPLETE" : "PARTIAL";
  return Object.freeze({ allocated, aggregate, remainder, complete, reconciliationState });
}

export function resourceComparison(before, after) {
  const keys = [
    "unifiedMemoryUsed", "mlxAllocatedMemory", "mlxCacheMemory", "diskFree",
    "acceptedStepsHour", "sequenceDensity", "frameDensity", "batchSize",
    "preparationCompileMs", "mlxWallMs",
  ];
  return Object.freeze(keys.map((key) => {
    const left = before?.aggregate?.[key];
    const right = after?.aggregate?.[key];
    const comparable = left?.state === PRESENT && right?.state === PRESENT &&
      Number.isFinite(left.value) && Number.isFinite(right.value) && left.units === right.units;
    return Object.freeze({ key, before: left ?? absent(), after: right ?? absent(), delta: comparable ? right.value - left.value : null });
  }));
}
