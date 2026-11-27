const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";

export const GENERATION_MANIFEST_SCHEMA =
  "bilqis.bamf.mission-control.generation-manifest/v1";
export const GENERATION_MANIFEST_SCHEMA_V2 =
  "bilqis.bamf.mission-control.generation-manifest/v2";
export const CANDIDATE_DECISION_SCHEMA =
  "bilqis.bamf.mission-control.candidate-decision/v1";

function baseQuery(context, family) {
  return {
    schema: QUERY_SCHEMA,
    family,
    mode: context?.mode === "HISTORICAL" ? "historical" : "current",
    run_id: context?.runId ?? null,
    record_id: null,
    schema_version: null,
    generation: context?.generation ?? null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor: null,
    limit: 32,
  };
}

export function buildGenerationQuery(context) {
  return baseQuery(context, "generation");
}

export function buildRejectedQuery(context) {
  return baseQuery(context, "episode");
}

export function assertQueryPage(value) {
  if (value?.accepted === true) return value;
  throw new Error(value?.reason ?? "LINEAGE_QUERY_REJECTED");
}

export function selectGenerationRecord(page, context) {
  const records = (page?.records ?? []).filter(record =>
    [GENERATION_MANIFEST_SCHEMA, GENERATION_MANIFEST_SCHEMA_V2].includes(record?.schema_version) &&
    record?.meta?.run?.run_id === context?.runId &&
    record?.meta?.run?.generation === context?.generation
  );
  if (records.length > 1) throw new Error("LINEAGE_GENERATION_IDENTITY_AMBIGUOUS");
  return records[0] ?? null;
}

export function rejectedDecisions(page) {
  return (page?.records ?? []).filter(record =>
    record?.schema_version === CANDIDATE_DECISION_SCHEMA &&
    record?.outcome === "REJECTED"
  );
}
