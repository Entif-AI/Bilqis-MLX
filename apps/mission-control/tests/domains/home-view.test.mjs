import test from "node:test";
import assert from "node:assert/strict";
import {
  HOME_FAMILIES,
  classifyLearning,
  familyForEvent,
  projectionFromPages,
  queryRequest,
  referenceHomeProjection,
} from "../../renderer/home/home-model.mjs";
import { createHomeController } from "../../renderer/home/home-controller.mjs";
import { renderHomeMarkup } from "../../renderer/home/home-view.mjs";

const context = Object.freeze({ runId: "fixture-run", generation: 7, mode: "LIVE" });

function emptyPage(family, state = "EMPTY") {
  return { accepted: true, family, mode: "current", state, coverage: "COMPLETE", records: [] };
}

function fakeHost() {
  return { hidden: false, innerHTML: "", querySelectorAll: () => [] };
}

test("GUI03 reference home answers the five operator questions in one dense view", () => {
  const model = referenceHomeProjection();
  const markup = renderHomeMarkup(model);
  for (const label of ["RUNNING", "LEARNING", "WORK", "REGRESSION", "INVALIDITY"]) {
    assert.match(markup, new RegExp(label));
  }
  for (const section of ["Learning", "Curriculum", "Runtime", "System", "Learning Pulse", "Current Work", "School Map", "Attention Required"]) {
    assert.match(markup, new RegExp(section));
  }
  assert.match(markup, /FIXTURE EVIDENCE/);
  assert.equal(model.learningStatus, "IMPROVING");
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

test("attention queue contains actionable conditions rather than ordinary healthy telemetry", () => {
  const model = referenceHomeProjection();
  assert.equal(model.attention.some((item) => /healthy|hard warnings.*0|memory pressure.*ok/i.test(`${item.label} ${item.detail}`)), false);
  assert.deepEqual(model.attention.map((item) => item.kind), ["stalled", "held", "recovery"]);
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
  assert.match(markup, /UNAVAILABLE/);
});

test("historical home queries bind the explicit prior generation", () => {
  const request = queryRequest("capability", { runId: "run-7", generation: 6, mode: "HISTORICAL" });
  assert.equal(request.mode, "historical");
  assert.equal(request.run_id, "run-7");
  assert.equal(request.generation, 6);
});

test("CP04 event families refresh only their owning CP03 family", () => {
  assert.equal(familyForEvent({ event_family: "candidate.retained" }), "episode");
  assert.equal(familyForEvent({ event_family: "capability.changed" }), "capability");
  assert.equal(familyForEvent({ event_family: "resource.health.sample" }), "resource");
  assert.equal(familyForEvent({ event_family: "warning.failure" }), null);
});

test("live home uses one family query per CP04 event rather than polling the full view", async () => {
  const calls = [];
  let listener = null;
  const api = {
    async query(request) {
      calls.push(request.family);
      return emptyPage(request.family);
    },
    subscribeEvents(next) {
      listener = next;
      return async () => { listener = null; };
    },
  };
  const controller = createHomeController(api);
  await controller.activate(context, { host: fakeHost(), onInspect: () => {}, defense: { historical: false } });
  assert.deepEqual(new Set(calls), new Set(HOME_FAMILIES));
  const baseline = calls.length;
  await listener({ event_family: "capability.changed" });
  assert.equal(calls.length, baseline + 1);
  assert.equal(calls.at(-1), "capability");
  await controller.deactivate();
});

test("historical home never opens a live CP04 subscription", async () => {
  let subscriptions = 0;
  const api = {
    async query(request) { return { ...emptyPage(request.family), mode: "historical" }; },
    subscribeEvents() { subscriptions += 1; return async () => {}; },
  };
  const controller = createHomeController(api);
  await controller.activate({ ...context, mode: "HISTORICAL" }, {
    host: fakeHost(), onInspect: () => {}, defense: { historical: true },
  });
  assert.equal(subscriptions, 0);
});
