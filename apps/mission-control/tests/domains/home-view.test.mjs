import test from "node:test";
import assert from "node:assert/strict";
import {
  HOME_FAMILIES,
  classifyLearning,
  homeStatus,
  projectionFromPages,
} from "../../renderer/home/home-model.mjs";
import { referenceHomeProjection } from "../../renderer/home/home-fixture.mjs";
import { renderHomeMarkup } from "../../renderer/home/home-view.mjs";
import { collectTestIds } from "../../renderer/foundation/test-hooks.mjs";

const context = Object.freeze({ runId: "fixture-run", generation: 7, mode: "LIVE" });

function emptyPage(family, state = "EMPTY") {
  return { accepted: true, family, mode: "current", state, coverage: "COMPLETE", records: [] };
}

function runPage({ generation = 0, optimizerStep = 0, stage = "UNKNOWN" } = {}) {
  return {
    accepted: true, family: "run", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: [{
      schema_version: "bilqis.bamf.mission-control.run-context/v1",
      meta: { run: { generation } },
      run_state: "ACCEPTED", optimizer_step: optimizerStep, stage,
    }],
  };
}

test("Home uses the governed five-state band and target overview regions", () => {
  const model = referenceHomeProjection();
  const markup = renderHomeMarkup(model);
  for (const id of ["running", "learning", "regression", "blocked", "invalidity"]) {
    assert.match(markup, new RegExp(`data-test-id="home-status-${id}"`));
  }
  assert.doesNotMatch(markup, /home-status-work/);
  for (const id of ["home-current-work", "home-attention", "home-pulse", "home-school", "home-health-details"]) {
    assert.match(markup, new RegExp(`data-test-id="${id}"`));
  }
  assert.match(markup, /Fixture evidence/);
  assert.match(markup, /School Snapshot/);
  assert.match(markup, /class="home-school-table-wrap"[^>]*tabindex="0"[^>]*data-test-id="home-school-scroll"/);
  assert.match(markup, /Recorded · not a live transaction/);
  assert.doesNotMatch(markup, /Observed · provisional/);
  assert.match(markup, /Accepted capability snapshot/);
  assert.equal(model.learningStatus, "REGRESSION");
});

test("Home renders durable milestone, release, materialization, gate, blocker, and drift notifications", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  const kinds = ["GRADUATION", "SEMANTIC_RELEASE", "GRAPH_MATERIALIZATION", "GATE_TRANSITION", "BLOCKER", "DRIFT"];
  pages.notification = {
    accepted: true, family: "notification", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: kinds.map((kind, index) => ({
      schema_version: "bilqis.bamf.mission-control.notification/v1",
      meta: { record_id: `notification:${index}`, observed_at: 1_799_100_000 + index, materialized_at: 1_799_100_000 + index },
      notification_id: `notification:${index}`,
      source_event_id: `event:${index}`,
      subject_ref: `subject:${index}`,
      kind,
      severity: ["BLOCKER", "DRIFT"].includes(kind) ? "WARNING" : "SUCCESS",
      state: "ACTIVE",
      created_at: 1_799_100_000 + index,
      evidence_ref: `evidence:${index}`,
      acknowledged_at: null,
      supersedes_notification_id: null,
    })),
  };
  const model = projectionFromPages(pages, context);
  const markup = renderHomeMarkup(model, { nowMs: 1_799_100_100_000, locale: "en-US" });
  assert.equal(model.notifications.length, kinds.length);
  assert.match(markup, /data-test-id="home-notifications"/);
  for (const kind of kinds) assert.match(markup, new RegExp(kind));
  assert.match(markup, /Evidence: evidence:0/);
});

test("Home health is collapsed detail and operator-significant work values remain complete", () => {
  const markup = renderHomeMarkup(referenceHomeProjection());
  assert.match(markup, /<details class="home-health" data-test-id="home-health-details">/);
  assert.doesNotMatch(markup, /home-metric-card|home-health-strip/);
  assert.match(markup, /paired-screen:source\+prereq/);
  assert.match(markup, /AWAITING_RECONCILIATION/);
});

test("serious attention leads the operational row while healthy attention stays secondary", () => {
  const fixture = referenceHomeProjection();
  const fixtureMarkup = renderHomeMarkup(fixture);
  assert.equal(homeStatus(fixture).attentionPriority, "primary");
  assert.ok(fixtureMarkup.indexOf('data-test-id="home-attention"') < fixtureMarkup.indexOf('data-test-id="home-current-work"'));
  const healthy = { ...fixture, pulse: Object.freeze([]), attention: Object.freeze([]), learningStatus: "IMPROVING" };
  const healthyMarkup = renderHomeMarkup(healthy);
  assert.equal(homeStatus(healthy).attentionPriority, "secondary");
  assert.ok(healthyMarkup.indexOf('data-test-id="home-current-work"') < healthyMarkup.indexOf('data-test-id="home-attention"'));
});

test("Home markup exposes unique stable home test hooks", () => {
  const ids = collectTestIds(renderHomeMarkup(referenceHomeProjection()));
  assert.equal(new Set(ids).size, ids.length);
  assert.ok(ids.length > 20);
  assert.ok(ids.every((id) => id.startsWith("home-")));
});

test("ten retained no-growth events remain throughput and never become learned success", () => {
  assert.equal(classifyLearning({ retained: 10, freshRetainedImprovements: 0 }), "THROUGHPUT_ONLY");
  const markup = renderHomeMarkup({ ...referenceHomeProjection(), learningStatus: "THROUGHPUT_ONLY" });
  assert.match(markup, /Throughput is present, but no fresh retained improvement is evidenced/);
  assert.doesNotMatch(markup, /Fresh retained improvement is evidenced/);
});

test("fresh retained improvement is distinct and exact regression event retains drill-through identity", () => {
  const model = referenceHomeProjection();
  assert.equal(classifyLearning({ retained: 1, freshRetainedImprovements: 1 }), "IMPROVING");
  const regression = model.pulse.find((event) => event.kind === "regress");
  assert.deepEqual(regression.target, { kind: "capability", id: "A.PARENT" });
  const gain = model.pulse.find((event) => event.kind === "gain");
  assert.equal(gain.target.kind, "episode");
  assert.match(gain.target.id, /^episode-record:/);
});

test("Home projection preserves exact source-backed observation times for current work and attention", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.episode = {
    accepted: true, family: "episode", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: [{
      schema_version: "bilqis.bamf.mission-control.learning-episode/v1",
      meta: { record_id: "episode:active", observed_at: 1_799_000_100, materialized_at: 1_799_000_105 },
      capability_id: "B.AND", state: "OPTIMIZING",
    }],
  };
  pages.correction = {
    accepted: true, family: "correction", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: [{
      schema_version: "bilqis.bamf.mission-control.correction/v1",
      meta: { record_id: "correction:1", observed_at: 1_799_000_200, materialized_at: 1_799_000_205 },
      state: "REQUALIFICATION_REQUIRED",
    }],
  };
  const model = projectionFromPages(pages, context);
  assert.equal(model.currentWork.observedAt, 1_799_000_100);
  assert.equal(model.currentWork.materializedAt, 1_799_000_105);
  assert.equal(model.attention[0].observedAt, 1_799_000_200);
  assert.equal(model.attention[0].materializedAt, 1_799_000_205);
});

test("Home pulse keeps observed and materialized time identities separate", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.episode = {
    accepted: true, family: "episode", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: [{
      schema_version: "bilqis.bamf.mission-control.candidate-decision/v1",
      meta: { record_id: "decision:1", observed_at: null, materialized_at: 1_799_000_305 },
      capability_id: "B.AND", outcome: "ACCEPTED", reason_code: "RETAINED",
    }],
  };
  const model = projectionFromPages(pages, context);
  assert.equal(model.pulse[0].observedAt, null);
  assert.equal(model.pulse[0].materializedAt, 1_799_000_305);
});

test("Home pulse keeps the newest cumulative decisions when current pages are newest-first", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.episode = {
    accepted: true, family: "episode", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: Array.from({ length: 12 }, (_, index) => ({
      schema_version: "bilqis.bamf.mission-control.candidate-decision/v1",
      meta: {
        record_id: `decision:${12 - index}`,
        observed_at: 1_799_000_400 - index,
        materialized_at: 1_799_000_500 - index,
      },
      capability_id: `A.CAP.${12 - index}`,
      outcome: "ACCEPTED",
      reason_code: "RETAINED",
    })),
  };
  const model = projectionFromPages(pages, context);
  assert.equal(model.pulse.length, 8);
  assert.deepEqual(model.pulse.map((event) => event.capabilityId), [
    "A.CAP.12", "A.CAP.11", "A.CAP.10", "A.CAP.9",
    "A.CAP.8", "A.CAP.7", "A.CAP.6", "A.CAP.5",
  ]);
});

test("Home fixtures never relabel generation coordinates as wall-clock time", () => {
  const model = referenceHomeProjection();
  assert.equal(model.pulse.every((event) => event.observedAt === null && event.materializedAt === null), true);
  const markup = renderHomeMarkup(model);
  assert.match(markup, /home-pulse-time-0[^>]*>Time unavailable<\/span>/);
  assert.doesNotMatch(markup, /data-source-unix-seconds="4423[5-9]"/);
});

test("Home consumes shared contextual-help and temporal primitives without collapsing materialization time", () => {
  const fixture = referenceHomeProjection();
  const model = {
    ...fixture,
    currentWork: Object.freeze({ ...fixture.currentWork, observedAt: 1_799_000_100, materializedAt: 1_799_000_105 }),
    attention: Object.freeze([{ ...fixture.attention[0], observedAt: 1_799_000_200, materializedAt: 1_799_000_205 }]),
    pulse: Object.freeze([{ ...fixture.pulse[0], observedAt: 1_799_000_300, materializedAt: 1_799_000_305 }]),
  };
  const markup = renderHomeMarkup(model, { nowMs: 1_799_000_400_000, locale: "en-US" });
  for (const id of ["status", "current", "attention", "pulse", "school", "health"]) {
    assert.match(markup, new RegExp(`data-test-id="home-help-${id}-trigger"`));
  }
  assert.match(markup, /data-source-unix-seconds="1799000100"/);
  assert.match(markup, /data-source-unix-seconds="1799000200"/);
  assert.match(markup, /data-source-unix-seconds="1799000300"/);
  assert.match(markup, />5 minutes ago</);
  assert.doesNotMatch(markup, /data-source-unix-seconds="1799000105"/);
  assert.doesNotMatch(markup, /data-source-unix-seconds="1799000205"/);
  assert.doesNotMatch(markup, /data-source-unix-seconds="1799000305"/);
});

test("Home does not repeat the shell-owned Model Forensics destination heading", () => {
  const markup = renderHomeMarkup(referenceHomeProjection());
  assert.doesNotMatch(markup, /<h1\b/i);
  assert.doesNotMatch(markup, />\s*Model Forensics\s*</i);
});

test("attention queue contains actionable conditions rather than ordinary healthy telemetry", () => {
  const model = referenceHomeProjection();
  assert.deepEqual(model.attention.map((item) => item.kind), ["stalled", "held", "recovery"]);
  assert.equal(model.attention.some((item) => item.label !== undefined || item.detail !== undefined), false);
});

test("stale and partial query states remain explicit instead of becoming healthy zeroes", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.capability = emptyPage("capability", "STALE");
  pages.resource = emptyPage("resource", "PARTIAL");
  const model = projectionFromPages(pages, context);
  assert.equal(model.state.capability, "STALE");
  assert.equal(model.state.resource, "PARTIAL");
  assert.equal(model.learning.latestSchoolScore, null);
  assert.equal(model.system.memoryPressure, null);
  const markup = renderHomeMarkup(model);
  assert.match(markup, /data-state="STALE"/);
  assert.match(markup, /data-state="PARTIAL"/);
  assert.match(markup, /Unavailable/);
});

test("RUNNING reflects the live learner-active handshake instead of mere run-record presence", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  const stopped = projectionFromPages(pages, { ...context, operatorActive: false });
  const running = projectionFromPages(pages, { ...context, operatorActive: true });
  assert.equal(homeStatus(stopped).running, false);
  assert.equal(homeStatus(running).running, true);
  assert.match(renderHomeMarkup(stopped), /<dt>Running<\/dt><dd>No<\/dd>/);
  assert.match(renderHomeMarkup(running), /<dt>Running<\/dt><dd>Yes<\/dd>/);
});

test("accepted generation zero renders a setup state instead of a wall of unavailable metrics", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.run = runPage();
  const model = projectionFromPages(pages, { ...context, runId: "aspirant", generation: 0, operatorActive: false });
  const markup = renderHomeMarkup(model);
  assert.equal(model.startup.state, "GENERATION_ZERO_READY");
  assert.match(markup, /Generation 0 is accepted and ready/);
  assert.match(markup, /Optimizer step<\/dt><dd>0/);
  assert.match(markup, /Trainer<\/dt><dd>Stopped/);
  assert.match(markup, /No training events yet/);
  assert.match(markup, /data-test-id="home-startup-operate"/);
  assert.doesNotMatch(markup, /Unavailable/);
  assert.doesNotMatch(markup, /Latest school score|Whole-school growth|Peak memory/);
});

test("active notifications remain visible during otherwise-empty generation-zero startup", () => {
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  pages.run = runPage();
  pages.notification = {
    accepted: true, family: "notification", mode: "current", state: "PRESENT", coverage: "COMPLETE",
    records: [{
      schema_version: "bilqis.bamf.mission-control.notification/v1",
      notification_id: "notification:startup", source_event_id: "event:startup",
      subject_ref: "grade:B", kind: "BLOCKER", severity: "BLOCKER", state: "ACTIVE",
      created_at: 1_799_100_000, evidence_ref: "receipt:startup",
      acknowledged_at: null, supersedes_notification_id: null,
      meta: { record_id: "notification:startup", materialized_at: 1_799_100_000 },
    }],
  };
  const model = projectionFromPages(
    pages, { ...context, runId: "aspirant", generation: 0, operatorActive: false });
  const markup = renderHomeMarkup(model);
  assert.equal(model.startup, null);
  assert.match(markup, /data-test-id="home-notifications"/);
  assert.match(markup, /BLOCKER/);
  assert.match(markup, /data-home-target-kind="reference"/);
});


test("missing evidence does not become measured zero or healthy status", () => {
  const model = projectionFromPages({ run: runPage({ generation: 7 }) }, context);
  assert.equal(model.runtime.retainedCandidates, null);
  assert.equal(model.runtime.rejectedCandidates, null);
  assert.equal(model.system.correctionDebt, null);
  assert.equal(model.curriculum.qualifiedCapabilities, null);
  assert.equal(model.learningStatus, "UNKNOWN");
  assert.equal(homeStatus(model).regression, null);
  assert.equal(homeStatus(model).blocked, null);
  assert.equal(homeStatus(model).invalidity, null);
  const pages = Object.fromEntries(HOME_FAMILIES.map((family) => [family, emptyPage(family)]));
  const empty = projectionFromPages(pages, context);
  assert.equal(empty.runtime.retainedCandidates, 0);
  assert.equal(empty.system.correctionDebt, 0);
  assert.equal(empty.curriculum.qualifiedCapabilities, 0);
});
