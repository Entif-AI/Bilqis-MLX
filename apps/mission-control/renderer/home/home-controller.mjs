import {
  HOME_FAMILIES,
  familyForEvent,
  projectionFromPages,
  queryRequest,
  referenceHomeProjection,
} from "./home-model.mjs";
import { bindHomeInteractions, renderHomeMarkup } from "./home-view.mjs";

function contextKey(context) {
  return context ? [context.runId, context.generation, context.mode].join(":") : "none";
}

export function createHomeController(api) {
  let key = null;
  let pages = {};
  let model = null;
  let loadPromise = null;
  let unsubscribe = null;
  let renderTarget = null;
  let inspectTarget = null;
  let context = null;
  let historical = false;
  let operatorActive = null;

  function projectionContext() {
    return { ...context, operatorActive };
  }

  async function refreshStatus() {
    if (historical || typeof api.status !== "function") {
      operatorActive = typeof context?.operatorActive === "boolean"
        ? context.operatorActive
        : null;
      return;
    }
    try {
      const status = await api.status();
      operatorActive = typeof status?.learnerActive === "boolean"
        ? status.learnerActive
        : null;
    } catch (_error) {
      operatorActive = null;
    }
  }

  function render() {
    if (!renderTarget || !model) return;
    renderTarget.hidden = false;
    renderTarget.innerHTML = renderHomeMarkup(model, { historical });
    bindHomeInteractions(renderTarget, inspectTarget ?? (() => {}));
  }

  async function loadFamily(family) {
    const request = queryRequest(family, context);
    const page = await api.query(request);
    await refreshStatus();
    pages = { ...pages, [family]: page };
    model = projectionFromPages(pages, projectionContext());
    render();
  }

  async function loadAll() {
    const entries = await Promise.all(HOME_FAMILIES.map(async (family) => {
      try {
        return [family, await api.query(queryRequest(family, context))];
      } catch (_error) {
        return [family, { accepted: false, state: "UNAVAILABLE", records: [] }];
      }
    }));
    await refreshStatus();
    pages = Object.fromEntries(entries);
    model = projectionFromPages(pages, projectionContext());
    if (context?.runId === "fixture-run" &&
        HOME_FAMILIES.every((family) => pages[family]?.accepted !== true || pages[family]?.state === "EMPTY")) {
      model = referenceHomeProjection();
    }
    render();
  }

  async function subscribe() {
    if (historical || typeof api.subscribeEvents !== "function") return;
    try {
      unsubscribe = api.subscribeEvents(async (event) => {
        const family = familyForEvent(event);
        if (!family || context?.mode === "HISTORICAL") return;
        try {
          await loadFamily(family);
        } catch (_error) {
          pages = { ...pages, [family]: { accepted: false, state: "UNAVAILABLE", records: [] } };
          model = projectionFromPages(pages, projectionContext());
          render();
        }
      });
    } catch (_error) {
      unsubscribe = null;
    }
  }

  async function activate(nextContext, { host, onInspect, defense } = {}) {
    renderTarget = host;
    inspectTarget = onInspect;
    context = nextContext;
    historical = Boolean(defense?.historical || nextContext?.mode === "HISTORICAL");
    operatorActive = typeof nextContext?.operatorActive === "boolean"
      ? nextContext.operatorActive
      : null;
    const nextKey = contextKey(nextContext) + `:${historical}`;
    if (key === nextKey) {
      render();
      return loadPromise;
    }
    key = nextKey;
    pages = {};
    model = nextContext?.runId === "fixture-run" ? referenceHomeProjection() : null;
    if (typeof unsubscribe === "function") {
      await unsubscribe();
      unsubscribe = null;
    }
    render();
    loadPromise = loadAll().then(subscribe);
    return loadPromise;
  }

  async function deactivate() {
    const stop = unsubscribe;
    unsubscribe = null;
    renderTarget = null;
    inspectTarget = null;
    key = null;
    if (typeof stop === "function") await stop();
  }

  function currentModel() {
    return model;
  }

  return Object.freeze({ activate, deactivate, currentModel });
}
