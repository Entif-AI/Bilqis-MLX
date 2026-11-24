const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const FACTORY_SCHEMA = "bilqis.bamf.mission-control.factory-cockpit-snapshot/v1";
const PAGE_LIMIT = 32;
const GENERATION_SCHEMA = "bilqis.bamf.mission-control.generation-manifest/v2";
const MAX_PAGES = 128;

export function factoryQuery(cursor = null) {
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family: "factory",
    mode: "current",
    run_id: null,
    record_id: null,
    schema_version: FACTORY_SCHEMA,
    generation: null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor,
    limit: PAGE_LIMIT,
  });
}

export async function loadFactoryRows(api) {
  if (!api || typeof api.query !== "function") {
    return Object.freeze({ state: "UNAVAILABLE", coverage: "UNKNOWN", rows: Object.freeze([]) });
  }
  const rows = [];
  let cursor = null;
  let state = "EMPTY";
  let coverage = "UNKNOWN";
  for (let pageIndex = 0; pageIndex < MAX_PAGES; pageIndex += 1) {
    const page = await api.query(factoryQuery(cursor));
    if (page?.accepted !== true) {
      return Object.freeze({
        state: page?.state ?? "UNAVAILABLE",
        coverage: page?.coverage ?? "UNKNOWN",
        rows: Object.freeze([]),
      });
    }
    state = page.state;
    coverage = page.coverage;
    for (const record of page.records ?? []) {
      if (record?.schema_version === FACTORY_SCHEMA) rows.push(Object.freeze(record));
    }
    cursor = page.next_cursor ?? null;
    if (cursor === null) {
      return Object.freeze({ state, coverage, rows: Object.freeze(rows) });
    }
  }
  throw new RangeError("SCHOOL_FACTORY_QUERY_PAGE_LIMIT");
}

export async function loadFactoryLineagePage(api, record, cursor = null) {
  const run = record.lineage?.at(-1)?.run_id;
  const release = record.factory_release_sha256;
  if (!api || !run || !release) {
    return { state: "UNAVAILABLE", rows: [], nextCursor: null, total: null };
  }
  const page = await api.query({
    ...factoryQuery(cursor), family: "generation", schema_version: GENERATION_SCHEMA,
    run_id: run, reference: "factory-release:" + release,
  });
  if (page?.accepted !== true) {
    return { state: page?.state ?? "UNAVAILABLE", rows: [], nextCursor: null, total: null };
  }
  return {
    state: page.state, coverage: page.coverage, rows: page.records ?? [],
    nextCursor: page.next_cursor ?? null, total: page.total_matches,
  };
}

export { FACTORY_SCHEMA };
