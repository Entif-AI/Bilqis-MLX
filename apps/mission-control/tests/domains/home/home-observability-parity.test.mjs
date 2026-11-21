import assert from "node:assert/strict";
import test from "node:test";
import { projectionFromPages } from "../../../renderer/home/home-model.mjs";
import { renderHomeMarkup } from "../../../renderer/home/home-view.mjs";
import { context, observation, runPage } from "./home-observed-fixtures.mjs";

test("producer-present observation facts survive the Home projection boundary", () => {
  const row = observation({
    schema_version: "bilqis.bamf.mission-control.trainer-observation/v7",
    elapsed_ms: 64_000,
    peak_rss_bytes: 64 * 1048576,
    disk_free_bytes: 120 * 1073741824,
    visit_evidence: {
      state: "PARTIAL",
      grade_id: "B",
      capability_id: "B.AND",
      teacher_policy_key: "policy:contrast",
      selected_option_id: "source:truth-table",
      target: { state: "MEASURED", before: 7, after: 9, total: 12, delta: 2 },
      protected_scope_state: "PARTIAL",
      protected: [{
        capability_id: "A.IDENTITY", state: "MEASURED",
        before: 12, after: 12, total: 12, delta: 0,
      }],
      decision: "RETAIN",
      reason: "TARGET_GAIN_WITH_PROTECTION",
    },
  });
  const model = projectionFromPages({ run: runPage(row) }, context);
  const html = renderHomeMarkup(model, { nowMs: 1_300_000, locale: "en-US" });

  assert.equal(model.runtime.elapsed, "1 minute and 4 seconds");
  assert.equal(model.system.peakMemory, "64.0 MiB");
  assert.equal(model.system.diskFree, "120.0 GiB");
  assert.equal(model.currentWork.strategy, "policy:contrast");
  assert.equal(model.currentWork.targetAssessment, "7/12 -> 9/12 (+2)");
  assert.equal(model.currentWork.protectedAssessment, "PARTIAL · 1 measured");
  assert.match(html, /Teacher policy<\/dt><dd>policy:contrast/);
  assert.match(html, /Teaching option<\/dt><dd>source:truth-table/);
  assert.match(html, /Target assessment<\/dt><dd>7\/12 -&gt; 9\/12 \(\+2\)/);
  assert.match(html, /Decision<\/dt><dd>RETAIN/);
  assert.match(html, /Decision reason<\/dt><dd>TARGET_GAIN_WITH_PROTECTION/);
  assert.doesNotMatch(html, /Peak memory<\/dt><dd>Unavailable/);
});

test("sparse current planning preserves recent accepted learning evidence without relabeling it current", () => {
  const health = {
    grade_id: "A", capability_id: "A.IDENTITY", state: "MEASURED",
    latest: { correct: 11, total: 12 }, best: { correct: 11, total: 12 },
    gain_from_first: 2, fixed_screen_errors: 1,
    distance_to_mastery_state: "MEASURED", distance_to_mastery: 1,
    protected_regression_state: "NOT_MEASURED", regressed_protected_capabilities: [],
    prior_certified_surface_ids: [], qualification_state: "NOT_MEASURED",
    certified_surface_regression_state: "NOT_MEASURED", warnings: [],
    recent_checkpoints: [
      { checkpoint_sha256: "1".repeat(64), optimizer_step: 8, correct: 9, total: 12 },
      { checkpoint_sha256: "2".repeat(64), optimizer_step: 9, correct: 11, total: 12 },
    ],
  };
  const previous = observation({
    observation_id: "previous-health", revision: 8,
    schema_version: "bilqis.bamf.mission-control.trainer-observation/v5",
    phase: "COMPLETED", outcome: "ACCEPTED", connection_state: "FINISHED",
    learning_health: health,
    meta: { run: { run_id: "trainer-run", generation: 0 }, observed_at: 1200 },
  });
  const current = observation({
    observation_id: "current-planning", revision: 2,
    schema_version: "bilqis.bamf.mission-control.trainer-observation/v7",
    phase: "SELECTING", outcome: "RUNNING", learning_health: null,
    candidate_step: null, candidate_horizon: null, candidate_steps: [],
    meta: { run: { run_id: "trainer-run", generation: 0 }, observed_at: 1300 },
  });
  const page = runPage(current);
  page.records.push(previous);
  const model = projectionFromPages({ run: page }, context);
  const html = renderHomeMarkup(model, { nowMs: 1_300_000, locale: "en-US" });

  assert.equal(model.observed.current.observation_id, "current-planning");
  assert.equal(model.observed.latestLearningEvidence.observation_id, "previous-health");
  assert.equal(model.learningStatus, "IMPROVING");
  assert.match(html, /Recent accepted learning health/);
  assert.match(html, /A\.IDENTITY/);
  assert.match(html, /11 \/ 12/);
  assert.match(html, /Observed phase<\/dt><dd>SELECTING/);
});
