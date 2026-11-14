import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  buildEvidenceRequest,
  loadEvidencePage,
  loadRecordById,
  loadRecordLinks,
  renderEvidenceMarkup,
} from "../renderer/domains/evidence-view.mjs";

const context = Object.freeze({ mode: "LIVE", runId: "run-7", generation: 7 });
const historical = Object.freeze({ mode: "HISTORICAL", runId: "run-7", generation: 6 });

function meta(recordId, generation = 7) {
  return {
    record_id: recordId,
    run: { run_id: "run-7", generation },
    materialized_at: 120,
    observed_at: 118,
    as_of: 118,
    coverage: "COMPLETE",
    authority: "MEASURED",
    source_refs: ["source:lesson:1"],
    evidence_refs: ["evidence:grader:1"],
    receipt_refs: ["receipt:source:1"],
  };
}

function page(request, { records = [], links = [], state = "PRESENT", coverage = "COMPLETE", next = null } = {}) {
  return {
    schema: "bilqis.bamf.control-plane.query-page/v1",
    query_id: "a".repeat(64), request, family: request.family, mode: request.mode,
    state, coverage, total_matches: records.length + links.length,
    returned: records.length + links.length, truncated: next !== null,
    next_cursor: next, records, markers: [], links, accepted: true,
  };
}

const capability = {
  schema_version: "bilqis.bamf.mission-control.capability-snapshot/v1",
  meta: meta("capability:and"), capability_id: "B.AND",
};
const episode = {
  schema_version: "bilqis.bamf.mission-control.learning-episode/v1",
  meta: meta("episode:and"), episode_id: "ep-1", capability_id: "B.AND",
};
const receipt = {
  schema_version: "bilqis.bamf.mission-control.operator-action-receipt/v2",
  meta: meta("cp05:operation-1:completed"), request_id: "req-1",
  operation_id: "operation-1", state: "COMPLETED", acknowledged_at: 120,
  target_ref: "run:run-7", postcondition_ref: "postcondition:1", error_ref: null,
};

test("current context search is exact run/generation and bounded", () => {
  const request = buildEvidenceRequest(context, { kind: "context", value: "" });
  assert.equal(request.family, "record");
  assert.equal(request.run_id, "run-7");
  assert.equal(request.generation, 7);
  assert.equal(request.limit, 16);
});

test("historical exact record never falls back to current", () => {
  const request = buildEvidenceRequest(historical, { kind: "record", value: "receipt:g6" });
  assert.equal(request.family, "record");
  assert.equal(request.mode, "historical");
  assert.equal(request.run_id, "run-7");
  assert.equal(request.generation, 6);
  assert.equal(request.record_id, "receipt:g6");
});

test("domain identity and command searches reuse the generic forensic record family", () => {
  const capabilityRequest = buildEvidenceRequest(context, { kind: "capability", value: "B.AND" });
  const commandRequest = buildEvidenceRequest(context, { kind: "command", value: "operation-1" });
  assert.equal(capabilityRequest.family, "record");
  assert.equal(capabilityRequest.reference, "B.AND");
  assert.equal(commandRequest.family, "record");
  assert.equal(commandRequest.reference, "operation-1");
});

test("capability to episode to evidence chain follows CP03 links without manual ID copying", async () => {
  const seen = [];
  const api = {
    async query(request) {
      seen.push(request);
      if (request.family === "record" && request.reference === "B.AND") {
        return page(request, { records: [capability] });
      }
      if (request.family === "links" && request.record_id === "capability:and") {
        return page(request, { links: [{
          relation: "EPISODE", source_record_id: "capability:and",
          target_ref: "episode:and", target_record_id: "episode:and",
        }] });
      }
      if (request.family === "record" && request.record_id === "episode:and") {
        return page(request, { records: [episode] });
      }
      if (request.family === "links" && request.record_id === "episode:and") {
        return page(request, { links: [{
          relation: "EVIDENCE", source_record_id: "episode:and",
          target_ref: "evidence:grader:1", target_record_id: null,
        }] });
      }
      throw new Error("unexpected query");
    },
  };
  const first = await loadEvidencePage(api, context, { kind: "capability", value: "B.AND" });
  const capabilityLinks = await loadRecordLinks(api, first.records[0]);
  const episodeId = capabilityLinks.links[0].target_record_id;
  const episodeResult = await loadRecordById(api, context, episodeId);
  const episodeLinks = await loadRecordLinks(api, episodeResult.record);
  assert.equal(episodeLinks.links[0].target_ref, "evidence:grader:1");
  assert.deepEqual(seen.map((item) => item.family), ["record", "links", "record", "links"]);
});

test("readable and raw views expose the same literal receipt values", () => {
  const base = {
    status: "ready", criteria: { kind: "record", value: receipt.meta.record_id },
    page: page(buildEvidenceRequest(context, { kind: "record", value: receipt.meta.record_id }), { records: [receipt] }),
    records: [receipt], links: [], selected: receipt, selectedLinks: null, error: null,
  };
  const readable = renderEvidenceMarkup({ ...base, raw: false });
  const raw = renderEvidenceMarkup({ ...base, raw: true });
  for (const literal of [receipt.meta.record_id, receipt.operation_id, receipt.postcondition_ref]) {
    assert.ok(readable.includes(literal));
    assert.ok(raw.includes(literal));
  }
  assert.ok(readable.includes("NOT SEPARATELY REPORTED"));
});

test("missing, denied, and conflicting evidence remain visibly distinct", () => {
  const request = buildEvidenceRequest(context, { kind: "reference", value: "receipt:x" });
  const missing = renderEvidenceMarkup({
    status: "ready", criteria: { kind: "reference", value: "receipt:x" },
    page: page(request, { state: "MISSING", coverage: "UNKNOWN" }), records: [], links: [],
    selected: null, selectedLinks: null, raw: false, error: null,
  });
  const denied = missing.replaceAll("MISSING", "DENIED");
  assert.ok(missing.includes("MISSING · UNKNOWN"));
  assert.ok(denied.includes("DENIED · UNKNOWN"));

  const conflict = renderEvidenceMarkup({
    status: "ready", criteria: { kind: "capability", value: "B.AND" },
    page: page(request, { records: [
      { ...capability, meta: meta("decision:accepted") },
      { ...capability, meta: meta("decision:rejected") },
    ] }),
    records: [
      { ...capability, meta: meta("decision:accepted") },
      { ...capability, meta: meta("decision:rejected") },
    ], links: [], selected: null, selectedLinks: null, raw: false, error: null,
  });
  assert.ok(conflict.includes("decision:accepted"));
  assert.ok(conflict.includes("decision:rejected"));
});

test("partial and stale marker detail exposes omissions instead of hiding them", () => {
  const request = buildEvidenceRequest(context, { kind: "context", value: "" });
  const partial = {
    schema_version: "bilqis.bamf.mission-control.partial/v1",
    meta: meta("partial:episode"),
    partial_record_id: "episode:and",
    missing_fields: ["grader_receipt", "source_revision"],
  };
  const markup = renderEvidenceMarkup({
    status: "ready", criteria: { kind: "context", value: "" },
    page: { ...page(request, { records: [episode], state: "PARTIAL", coverage: "PARTIAL" }), markers: [partial] },
    records: [episode], links: [], selected: null, selectedLinks: null, raw: false, error: null,
  });
  assert.ok(markup.includes("grader_receipt"));
  assert.ok(markup.includes("source_revision"));
  assert.ok(markup.includes("PARTIAL · PARTIAL"));
});

test("cursor pagination is passed back to CP03 unchanged", () => {
  const cursor = `cp03:${"1".repeat(64)}:${"2".repeat(64)}:16`;
  const request = buildEvidenceRequest(context, { kind: "context", value: "" }, cursor);
  assert.equal(request.cursor, cursor);
  assert.equal(request.limit, 16);
});

test("forensic renderer has no direct provider, filesystem, process, or network escape", () => {
  const here = path.dirname(fileURLToPath(import.meta.url));
  const source = fs.readFileSync(path.join(here, "../renderer/domains/evidence-view.mjs"), "utf8");
  for (const forbidden of ["require(", "node:fs", "process.", "electron", "fetch(", "XMLHttpRequest"]) {
    assert.equal(source.includes(forbidden), false, forbidden);
  }
});
