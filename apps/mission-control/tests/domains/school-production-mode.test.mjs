import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import {
  capabilityQuery,
  loadSchoolRows,
  schoolRowFromRecord,
} from "../../renderer/school/school-live.mjs";
import { factoryQuery, loadFactoryRows } from "../../renderer/school/factory-live.mjs";
import { renderFactoryCockpitView } from "../../renderer/school/factory-cockpit-view.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const rendererRoot = path.resolve(here, "../../renderer");

const datum = (value) => ({ state: "PRESENT", origin: "MEASURED", value, units: null });

function capability(id, generation = 7) {
  return {
    schema_version: "bilqis.bamf.mission-control.capability-snapshot/v1",
    meta: {
      record_id: "capability:" + id,
      run: { run_id: "run-7", generation },
      observed_at: 1_799_000_100 + generation,
      materialized_at: 1_799_000_110 + generation,
      source_refs: ["source:" + id],
      evidence_refs: [],
      receipt_refs: [],
    },
    capability_id: id,
    grade_id: "B",
    status: "ADMITTED",
    score_correct: datum(8),
    score_total: datum(12),
    debt: datum(4),
  };
}

function factoryRecord({ blocked = false, stale = false } = {}) {
  return {
    schema_version: "bilqis.bamf.mission-control.factory-cockpit-snapshot/v1",
    meta: { record_id: "factory-release:" + "a".repeat(64), run: null },
    subject_kind: "FACTORY_RELEASE",
    subject_sha256: "a".repeat(64),
    factory_release_sha256: "a".repeat(64),
    candidate_sha256: null,
    semantic_release_sha256: "b".repeat(64),
    lifecycle_state: "ADMITTED",
    delivery_status: blocked ? "BLOCKED" : "LAUNCH_QUALIFIED",
    currency_state: stale ? "STALE" : "CURRENT",
    admission_authority: "HUMAN_ONLY",
    grade_frontier: [{ grade_id: "B", capability_ids: ["B.AND", "B.OR"] }],
    capability_ids: ["B.AND", "B.OR"],
    dependency_edges: [["B.OR", "B.AND"]],
    blockers: blocked ? [{ owner_ref: "issue:#320", evidence_ref: "receipt:blocked", reason: "Topology qualification pending" }] : [],
    promoted_capability_ids: ["B.AND"],
    debt_capability_ids: ["B.OR"],
    receipt_refs: ["c".repeat(64)],
    qualification_receipt_sha256: "d".repeat(64),
    admission_receipt_sha256: "e".repeat(64),
    lineage: [{
      run_id: "run-7",
      checkpoint_lineage_id: "lineage-7",
      generation: 7,
      generation_manifest_sha256: "f".repeat(64),
      checkpoint_sha256: "1".repeat(64),
      checkpoint_receipt_sha256: "2".repeat(64),
      topology: {
        knowledge: "EXACT",
        view_schema_version: "bilqis.akasha.factory-topology-view/v1",
        topology_schema: "bilqis.mlx.model-topology/v2",
        topology_sha256: "3".repeat(64),
        architecture_id: "bamf-atlas-v2",
        layers: 12,
        query_heads: 16,
        kv_heads: 8,
        model_dimension: 768,
        feed_forward_dimension: 3072,
        context_length: 1024,
        compatibility_ref: null,
      },
    }],
  };
}

test("production capability projection preserves exact evidence and leaves unexposed School fields empty", () => {
  const row = schoolRowFromRecord(capability("B.AND"));
  assert.equal(row.id, "B.AND");
  assert.equal(row.now, 8);
  assert.equal(row.total, 12);
  assert.equal(row.debt, 4);
  assert.equal(row.observedAt, 1_799_000_107);
  assert.equal(row.materializedAt, 1_799_000_117);
  for (const field of ["was", "top", "pRet", "visits", "retainedSteps", "lastGain", "lastRegression", "strategy", "sourceState", "implementationState"]) {
    assert.equal(row[field], null, field);
  }
  assert.deepEqual(row.prerequisites, []);
  assert.deepEqual(row.sourceRefs, ["source:B.AND"]);
});

test("production School query binds exact current or historical context and paginates without fixture fallback", async () => {
  const live = capabilityQuery({ runId: "run-7", generation: 7, mode: "LIVE" });
  assert.equal(live.mode, "current");
  assert.equal(live.run_id, "run-7");
  assert.equal(live.generation, null);

  const historical = capabilityQuery({ runId: "run-7", generation: 6, mode: "HISTORICAL" });
  assert.equal(historical.mode, "historical");
  assert.equal(historical.generation, 6);

  const requests = [];
  const api = {
    async query(request) {
      requests.push(request);
      const second = request.cursor === "next";
      return {
        accepted: true,
        state: "PRESENT",
        coverage: "COMPLETE",
        records: [capability(second ? "B.OR" : "B.AND")],
        next_cursor: second ? null : "next",
      };
    },
  };
  const result = await loadSchoolRows(api, { runId: "run-7", generation: 7, mode: "LIVE" });
  assert.deepEqual(result.rows.map((row) => row.id), ["B.AND", "B.OR"]);
  assert.equal(requests.length, 2);
  assert.equal(requests[1].cursor, "next");

  const rejected = await loadSchoolRows({
    async query() {
      return { accepted: false, state: "DENIED", coverage: "UNKNOWN", records: [] };
    },
  }, { runId: "run-7", generation: 7, mode: "LIVE" });
  assert.equal(rejected.state, "DENIED");
  assert.deepEqual(rejected.rows, []);
});

test("Factory query is intentionally global while lineage remains run-bound evidence", async () => {
  const request = factoryQuery();
  assert.equal(request.family, "factory");
  assert.equal(request.mode, "current");
  assert.equal(request.run_id, null);
  assert.equal(request.generation, null);

  const requests = [];
  const result = await loadFactoryRows({ async query(query) {
    requests.push(query);
    return { accepted: true, state: "PRESENT", coverage: "COMPLETE", records: [factoryRecord()], next_cursor: null };
  }});
  assert.equal(result.rows.length, 1);
  assert.equal(result.rows[0].lineage[0].run_id, "run-7");
  assert.equal(requests.length, 1);
});

test("Factory cockpit renders blocked stale evidence, exact topology, and no mutation controls", () => {
  const host = { innerHTML: "", querySelectorAll: () => [] };
  renderFactoryCockpitView(host, {
    rows: [factoryRecord({ blocked: true, stale: true })],
    state: "PRESENT",
    coverage: "COMPLETE",
  });
  assert.match(host.innerHTML, /BLOCKED/);
  assert.match(host.innerHTML, /STALE/);
  assert.match(host.innerHTML, /issue:#320/);
  assert.match(host.innerHTML, /bamf-atlas-v2/);
  assert.match(host.innerHTML, /12L/);
  assert.match(host.innerHTML, /human-only/);
  assert.doesNotMatch(host.innerHTML, /data-(?:admit|promote|stage|mutate)/);
});

test("production School modules have no static fixture import", () => {
  const schoolView = fs.readFileSync(path.join(rendererRoot, "school", "school-view.mjs"), "utf8");
  const schoolController = fs.readFileSync(path.join(rendererRoot, "school", "school-domain-controller.mjs"), "utf8");
  const currentView = fs.readFileSync(path.join(rendererRoot, "foundation", "current-view.mjs"), "utf8");
  assert.doesNotMatch(schoolView, /from\s+["'][^"']*fixture/);
  assert.doesNotMatch(schoolController, /from\s+["'][^"']*fixture/);
  assert.doesNotMatch(currentView, /school-fixture|curriculum-atlas-fixture/);
  assert.match(schoolController, /await import\("\.\/school-fixture\.mjs"\)/);
  assert.match(schoolController, /await import\("\.\/curriculum-atlas-view\.mjs"\)/);
});

test("package exposes the reviewed explicit fixture launch command", () => {
  const packageJson = JSON.parse(fs.readFileSync(path.resolve(rendererRoot, "../../../package.json"), "utf8"));
  assert.equal(packageJson.scripts.bamf, "electron apps/mission-control/main.cjs");
  assert.equal(packageJson.scripts["bamf:fixtures"], "electron apps/mission-control/main.cjs --mission-control-fixtures");
});
