import {
  historicalResourceQuery,
  referenceResourceState,
  resourceProfileFromPage,
  resourceQuery,
} from "./resource-model.mjs";
import {
  historicalResourceFixture,
} from "./resource-fixture.mjs";
import {
  bindResourceInteractions,
  renderResourceMarkup,
} from "./resource-view.mjs";

function contextKey(context) {
  return context ? [context.runId, context.generation, context.mode].join(":") : "none";
}

export function createResourceController(api) {
  let key = null;
  let context = null;
  let state = null;
  let host = null;
  let inspect = null;
  let historical = false;
  let unsubscribe = null;
  let loadPromise = null;

  function render() {
    if (!host) return;
    host.hidden = false;
    host.innerHTML = renderResourceMarkup(state, { historical });
    host.__resourceState = state;
    bindResourceInteractions(host, { onInspect: inspect, onCompare: loadComparison });
  }

  async function loadCurrent() {
    try {
      const page = await api.query(resourceQuery(context));
      if (context?.runId === "fixture-run" && historical &&
          context.generation === historicalResourceFixture().generation) {
        state = Object.freeze({
          current: historicalResourceFixture(),
          comparison: state?.comparison ?? null,
          comparisonState: state?.comparisonState ?? "EMPTY",
        });
      } else if (context?.runId === "fixture-run" && !historical &&
          (page?.accepted !== true || page?.state === "EMPTY")) {
        state = referenceResourceState();
      } else {
        state = Object.freeze({
          current: resourceProfileFromPage(page, context),
          comparison: state?.comparison ?? null,
          comparisonState: state?.comparisonState ?? "EMPTY",
        });
      }
    } catch (_error) {
      if (context?.runId === "fixture-run" && historical &&
          context.generation === historicalResourceFixture().generation) {
        state = Object.freeze({
          current: historicalResourceFixture(),
          comparison: null,
          comparisonState: "EMPTY",
        });
      } else if (context?.runId === "fixture-run" && !historical) state = referenceResourceState();
      else state = Object.freeze({ current: null, comparison: null, currentState: "UNAVAILABLE", comparisonState: "EMPTY" });
    }
    render();
  }

  async function loadComparison(generation) {
    if (!context) return;
    if (context.runId === "fixture-run" && generation === historicalResourceFixture().generation) {
      state = Object.freeze({ ...state, comparison: historicalResourceFixture(), comparisonState: "PRESENT" });
      render();
      return;
    }
    state = Object.freeze({ ...state, comparison: null, comparisonState: "LOADING" });
    render();
    try {
      const page = await api.query(historicalResourceQuery(context, generation));
      const profile = resourceProfileFromPage(page, { ...context, mode: "HISTORICAL", generation });
      state = Object.freeze({ ...state, comparison: profile, comparisonState: page?.accepted === true ? page.state : "UNAVAILABLE" });
    } catch (_error) {
      state = Object.freeze({ ...state, comparison: null, comparisonState: "UNAVAILABLE" });
    }
    render();
  }

  async function subscribe() {
    if (historical || typeof api.subscribeEvents !== "function") return;
    try {
      unsubscribe = api.subscribeEvents(async (event) => {
        if (!String(event?.event_family ?? "").startsWith("resource.")) return;
        await loadCurrent();
      });
    } catch (_error) {
      unsubscribe = null;
    }
  }

  async function activate(nextContext, { target, onInspect, defense } = {}) {
    host = target;
    inspect = onInspect;
    context = nextContext;
    historical = Boolean(defense?.historical || nextContext?.mode === "HISTORICAL");
    const nextKey = `${contextKey(nextContext)}:${historical}`;
    if (key === nextKey) {
      render();
      return loadPromise;
    }
    key = nextKey;
    const stop = unsubscribe;
    unsubscribe = null;
    if (typeof stop === "function") await stop();
    state = nextContext?.runId === "fixture-run" && !historical ? referenceResourceState() : null;
    render();
    loadPromise = loadCurrent().then(subscribe);
    return loadPromise;
  }

  async function deactivate() {
    const stop = unsubscribe;
    unsubscribe = null;
    host = null;
    inspect = null;
    key = null;
    if (typeof stop === "function") await stop();
  }

  function currentState() {
    return state;
  }

  return Object.freeze({ activate, deactivate, currentState, loadComparison });
}
