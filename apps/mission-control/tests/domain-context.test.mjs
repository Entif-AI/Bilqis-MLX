import test from "node:test";
import assert from "node:assert/strict";
import { createAtlasRequestGuard, createDomainViews } from "../renderer/views/domain-views.mjs";

test("late Atlas completion cannot publish after navigation or a context change", async () => {
  for (const destination of ["model", "school"]) {
    let state = { view: "atlas", context: {} };
    const guard = createAtlasRequestGuard(() => state);
    let resolve; let published = false;
    const pending = new Promise(done => { resolve = done; });
    const current = guard.begin();
    const completion = pending.then(() => { if (current()) published = true; });
    state = { ...state, view: destination }; guard.invalidate();
    resolve(); await completion;
    assert.equal(published, false);
    state = { ...state, view: "atlas" };
    assert.equal(current(), false, "returning to Atlas does not revive old work");
  }
  let state = { view: "atlas", context: {} };
  const guard = createAtlasRequestGuard(() => state);
  const oldContext = guard.begin();
  state = { ...state, context: {} };
  assert.equal(oldContext(), false);
});

test("a newer Atlas request supersedes an older request in the same context", () => {
  const state = { view: "atlas", context: {} };
  const guard = createAtlasRequestGuard(() => state);
  const old = guard.begin(); const current = guard.begin();
  assert.equal(old(), false);
  assert.equal(current(), true);
});

function mountOwner(t) {
  const previous = { document: globalThis.document, window: globalThis.window, FormData: globalThis.FormData };
  t.after(() => Object.assign(globalThis, previous));
  const forms = Object.fromEntries(["#atlas-search-form", "#atlas-abi-form"].map(key => [key, {
    handlers: {}, values: { semanticId: "fixture:semantic", bank: "0", row: "1" },
    addEventListener(event, callback) { this.handlers[event] = callback; },
  }]));
  const element = () => ({ innerHTML: "", hidden: false, textContent: "",
    querySelectorAll: () => [], querySelector: key => forms[key] ?? null });
  const nodes = new Map(["#domain-view", ".fixture-card", "#visual-catalog", "#view-summary", "#model-nav", "#domain-context-note"].map(key => [key, element()]));
  globalThis.document = { querySelector: key => nodes.get(key), querySelectorAll: () => [] };
  globalThis.FormData = class { constructor(form) { this.form = form; } get(key) { return this.form.values[key]; } };
  let resolve; let calls = 0;
  const pending = new Promise(done => { resolve = done; });
  globalThis.window = { bamfMissionControl: { query: () => { calls += 1; return pending; } } };
  let state = { view: "atlas", selected: null, context: { runId: "fixture-run", generation: 7, mode: "LIVE", semanticRelease: "1".repeat(64) } };
  const owner = createDomainViews({ getState: () => state, onInspect() {}, getModelSection: () => "frames" });
  owner.render();
  return { owner, host: nodes.get("#domain-view"), forms,
    navigate(view) { state = { ...state, view }; owner.render(); },
    changeContext() { state = { ...state, context: { ...state.context, generation: 6 } }; owner.render(); },
    finish() { resolve({ schema: "bamf.gui07.query-error/v1", accepted: false, reason: "delayed fixture" }); },
    calls: () => calls,
  };
}

test("real Atlas overview/search/ABI handlers cannot repaint Frames or School after navigation", async t => {
  for (const operation of ["overview", "search", "abi"]) {
    for (const destination of ["model", "school"]) {
      await t.test(`${operation} -> ${destination}`, async t => {
        const fixture = mountOwner(t);
        const form = fixture.forms[operation === "search" ? "#atlas-search-form" : "#atlas-abi-form"];
        const completion = operation === "overview" ? fixture.owner.ensureAtlasOverview()
          : form.handlers.submit({ preventDefault() {}, currentTarget: form });
        assert.match(fixture.host.innerHTML, /Loading semantic/);
        fixture.navigate(destination);
        if (destination === "model") assert.equal(fixture.host.hidden, true);
        const destinationMarkup = fixture.host.innerHTML;
        fixture.finish(); await completion;
        assert.equal(fixture.host.innerHTML, destinationMarkup);
        const calls = fixture.calls();
        fixture.navigate("atlas"); await fixture.owner.ensureAtlasOverview();
        assert.ok(fixture.calls() > calls, "a discarded unfinished load can be retried");
      });
    }
  }
});

test("real Atlas handlers keep the newest request's outcome", async t => {
  const fixture = mountOwner(t);
  const requests = [];
  globalThis.window.bamfMissionControl.query = () => new Promise((_resolve, reject) => requests.push(reject));
  const search = fixture.forms["#atlas-search-form"];
  const abi = fixture.forms["#atlas-abi-form"];
  const older = search.handlers.submit({ preventDefault() {}, currentTarget: search });
  const newer = abi.handlers.submit({ preventDefault() {}, currentTarget: abi });
  requests[1](new Error("newest request outcome")); await newer;
  requests[0](new Error("obsolete request outcome")); await older;
  assert.match(fixture.host.innerHTML, /newest request outcome/);
  assert.doesNotMatch(fixture.host.innerHTML, /obsolete request outcome/);
});

test("real Atlas completion cannot publish a result from the prior context", async t => {
  const fixture = mountOwner(t);
  const completion = fixture.owner.ensureAtlasOverview();
  fixture.changeContext();
  const markup = fixture.host.innerHTML;
  fixture.finish(); await completion;
  assert.equal(fixture.host.innerHTML, markup);
});
