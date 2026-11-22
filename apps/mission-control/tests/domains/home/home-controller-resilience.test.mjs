import assert from "node:assert/strict";
import test from "node:test";

import { createHomeController } from "../../../renderer/home/home-controller.mjs";
import { observation } from "./home-observed-fixtures.mjs";

function emptyPage(family) {
  return {
    accepted: true, family, mode: "current", state: "EMPTY",
    coverage: "COMPLETE", records: [],
  };
}

function fakeHost() {
  return { hidden: false, innerHTML: "", querySelectorAll: () => [] };
}

test("one unavailable family cannot blind paginated live run evidence", async () => {
  const context = Object.freeze({
    runId: "trainer-run", generation: 21, mode: "LIVE", operatorActive: true,
  });
  const liveObservation = observation({
    schema_version: "bilqis.bamf.mission-control.trainer-observation/v7",
    observation_id: "live-parent",
    revision: 7,
    phase: "TRAINING",
    capability_id: "A.PARENT",
    visit_evidence: {
      state: "PARTIAL",
      capability_id: "A.PARENT",
      teacher_policy_key: "db43f0c78c41",
      selected_option_id: "A.PARENT",
      target: { state: "NOT_MEASURED" },
      protected_scope_state: "UNKNOWN",
      protected: [],
    },
    meta: {
      run: {
        run_id: "trainer-run",
        generation: 21,
        generation_manifest_sha256: "manifest-21",
      },
      observed_at: 1_795_323_120,
    },
  });
  const calls = [];
  const api = {
    async status() { return { learnerActive: true }; },
    async query(request) {
      calls.push([request.family, request.cursor ?? null]);
      if (request.family === "semantic") {
        return {
          accepted: false, family: "semantic", mode: "current",
          reason: "CONTROL_PLANE_QUERY_RESPONSE_TOO_LARGE",
        };
      }
      if (request.family === "episode") {
        if (request.limit !== 8) {
          return {
            accepted: false, family: "episode", mode: "current",
            reason: "CONTROL_PLANE_QUERY_RESPONSE_TOO_LARGE",
          };
        }
        return {
          accepted: true, family: "episode", mode: "current", state: "PARTIAL",
          coverage: "PARTIAL", records: [], markers: [], links: [],
          next_cursor: request.cursor === null ? "episode-page-2" : null,
          truncated: request.cursor === null,
        };
      }
      if (request.family !== "run") return emptyPage(request.family);
      if (request.cursor === null) {
        return {
          accepted: true, family: "run", mode: "current", state: "PARTIAL",
          coverage: "PARTIAL",
          records: [{
            schema_version: "bilqis.bamf.mission-control.run-context/v1",
            meta: {
              record_id: "run-context:trainer-run:21",
              run: {
                run_id: "trainer-run",
                generation: 21,
                generation_manifest_sha256: "manifest-21",
              },
            },
            run_state: "ACCEPTED",
            optimizer_step: 138,
            stage: "FOUNDATION",
          }],
          markers: [], links: [], next_cursor: "run-page-2", truncated: true,
        };
      }
      return {
        accepted: true, family: "run", mode: "current", state: "PRESENT",
        coverage: "PARTIAL", records: [liveObservation],
        markers: [], links: [], next_cursor: null, truncated: false,
      };
    },
    subscribeEvents() { return async () => {}; },
  };
  const controller = createHomeController(api, {
    schedule: () => 1,
    cancel: () => {},
  });
  await controller.activate(context, {
    host: fakeHost(),
    onInspect: () => {},
    defense: { historical: false },
  });

  const model = controller.currentModel();
  assert.equal(model.observed.current.capability_id, "A.PARENT");
  assert.equal(model.currentWork.capabilityId, "A.PARENT");
  assert.equal(model.currentWork.strategy, "db43f0c78c41");
  assert.ok(calls.some(([family, cursor]) =>
    family === "run" && cursor === "run-page-2"));
  assert.ok(calls.some(([family, cursor]) =>
    family === "episode" && cursor === "episode-page-2"));
  await controller.deactivate();
});
