const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const FACTORY_SCHEMA = "bilqis.bamf.mission-control.factory-cockpit-snapshot/v1";
const PAGE_LIMIT = 32;
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

export { FACTORY_SCHEMA };
