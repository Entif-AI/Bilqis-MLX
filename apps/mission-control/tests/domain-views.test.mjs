import test from "node:test";
import assert from "node:assert/strict";
import { createDomainViews } from "../renderer/domain-views.mjs";

test("late Atlas responses cannot overwrite another destination or generation", async () => {
  const original = { document: globalThis.document, window: globalThis.window, FormData: globalThis.FormData };
  try {
    for (const destination of ["resources", "new-generation"]) {
      for (const formId of ["#atlas-search-form", "#atlas-abi-form"]) {
        const handlers = new Map();
        const pending = [];
        const host = { innerHTML: "", hidden: false,
          querySelectorAll: () => [],
          querySelector: (id) => ({ addEventListener: (_event, handler) => handlers.set(id, handler) }),
        };
        const elements = new Map([["#domain-view", host], [".fixture-card", {}],
          ["#visual-catalog", {}], ["#view-summary", {}]]);
        globalThis.document = { querySelector: (id) => elements.get(id) };
        globalThis.window = { bamfMissionControl: { query: () => new Promise((resolve) => pending.push(resolve)) } };
        globalThis.FormData = class { get(key) { return ({ semanticId: "a".repeat(64), bank: "0", row: "0" })[key]; } };
        const views = createDomainViews({ onState() {}, renderInspector() {}, setHash() {} });
        const state = { view: "atlas", context: { runId: "run", generation: 1, mode: "HISTORICAL" } };
        views.render(state);
        const search = handlers.get(formId)({ preventDefault() {}, currentTarget: {} });
        const oldRequests = [...pending];
        views.render(destination === "resources" ? { ...state, view: "resources" }
          : { ...state, context: { ...state.context, generation: 2 } });
        const currentMarkup = host.innerHTML;
        oldRequests.forEach((resolve) => resolve({ schema: "bamf.gui07.query-error/v1", accepted: false, reason: "old response" }));
        await search;
        await Promise.resolve();
        assert.equal(host.innerHTML, currentMarkup, `${formId}: ${destination}`);
      }
    }
  } finally {
    Object.assign(globalThis, original);
  }
});
