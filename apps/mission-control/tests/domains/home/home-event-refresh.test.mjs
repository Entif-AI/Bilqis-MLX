import assert from "node:assert/strict";
import test from "node:test";
import { createHomeController } from "../../../renderer/home/home-controller.mjs";
import { context, host, observation, runPage } from "./home-observed-fixtures.mjs";

const empty = () => ({ accepted: true, state: "EMPTY", coverage: "COMPLETE", records: [] });
const rejected = (index) => ({
  schema_version: "bilqis.bamf.mission-control.candidate-decision/v1",
  outcome: "REJECTED", capability_id: "A.IDENTITY", reason_code: "NO_GAIN",
  meta: { record_id: "decision:" + index, observed_at: 1000 + index },
});
const episode = (count) => ({
  ...empty(), state: "PRESENT",
  records: Array.from({ length: count }, (_, index) => rejected(index)),
});

function harness(query) {
  let listener, stopped = 0, subscriptions = 0;
  const calls = [];
  const controller = createHomeController({
    async query(request) { calls.push(request.family); return query(request); },
    subscribeEvents(next) {
      subscriptions++;
      listener = next;
      return () => { stopped++; };
    },
  }, { schedule: () => 1, cancel: () => {} });
  return { controller, calls, activate: () => controller.activate(context, { host: host() }),
    event: (value) => listener(value), counts: () => ({ subscriptions, stopped }) };
}

test("event bursts refresh the same family once without losing any history", async () => {
  let count = 1;
  const h = harness(({ family }) => family === "run" ? runPage() :
    family === "episode" ? episode(count) : empty());
  await h.activate();
  h.calls.length = 0;
  count = 3;
  await Promise.all([h.event({ event_family: "lesson.visit.completed" }),
    h.event({ event_family: "candidate.rejected" }),
    h.event({ event_family: "run.state.changed" }),
    h.event({ event_family: "checkpoint.committed" })]);
  assert.deepEqual(h.calls, ["episode", "run"]);
  assert.equal(h.controller.currentModel().runtime.rejectedCandidates, 3);
  await h.controller.deactivate();
});

test("a rejection arriving during a pending episode query gets a follow-up refresh", async () => {
  let count = 1, release, reading;
  const inFlight = new Promise((resolve) => { reading = resolve; });
  const h = harness(async ({ family }) => {
    if (family === "run") return runPage();
    if (family !== "episode") return empty();
    const page = episode(count);
    if (count === 2) await new Promise((resolve) => { release = resolve; reading(); });
    return page;
  });
  await h.activate();
  h.calls.length = 0;
  count = 2;
  const first = h.event({ event_family: "candidate.rejected" });
  await inFlight;
  count = 3;
  const second = h.event({ event_family: "candidate.rejected" });
  release();
  await Promise.all([first, second]);
  assert.deepEqual(h.calls, ["episode", "run", "episode", "run"]);
  assert.equal(h.controller.currentModel().runtime.rejectedCandidates, 3);
  await h.controller.deactivate();
});

test("a scoped event cannot install successor data behind the prior accepted identity", async () => {
  let generation = 0, advance = false;
  const h = harness(({ family }) => {
    if (family === "run") return runPage(observation(), generation);
    if (family === "episode") {
      if (advance) generation = 1;
      return episode(generation + 1);
    }
    return empty();
  });
  await h.activate();
  h.calls.length = 0;
  advance = true;
  await h.event({ event_family: "candidate.rejected" });
  assert.equal(h.controller.currentModel().observed.acceptedGeneration, 1);
  assert.equal(h.controller.currentModel().runtime.rejectedCandidates, 2);
  assert.ok(h.calls.includes("school"));
  await h.controller.deactivate();
});

test("stream termination resubscribes and reconciles missed same-generation decisions", async () => {
  let count = 1;
  const h = harness(({ family }) => family === "run" ? runPage() :
    family === "episode" ? episode(count) : empty());
  await h.activate();
  count = 4;
  await h.event({ schemaVersion: "bamf.gui20.event-stream-state/v1", state: "DISCONNECTED" });
  assert.deepEqual(h.counts(), { subscriptions: 2, stopped: 1 });
  assert.equal(h.controller.currentModel().observed.acceptedGeneration, 0);
  assert.equal(h.controller.currentModel().runtime.rejectedCandidates, 4);
  await h.controller.deactivate();
});
