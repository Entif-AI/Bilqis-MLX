import {
  HOME_FAMILIES,
  familyForEvent,
  isNotificationEvent,
  projectionFromPages,
  queryRequest,
} from "./home-model.mjs";
import { bindHomeInteractions, renderHomeMarkup } from "./home-view.mjs";

function acceptedIdentity(page) {
  const run = page?.records?.find((record) => record.schema_version?.endsWith(".run-context/v1"));
  const ref = run?.meta?.run;
  return ref ? JSON.stringify([ref.run_id, ref.generation, ref.generation_manifest_sha256]) : null;
}

export function createHomeController(api, {
  referenceProjection = null,
  schedule = (callback, delay) => { const timer = setTimeout(callback, delay); timer.unref?.(); return timer; },
  cancel = (timer) => clearTimeout(timer),
} = {}) {
  let pages = {}, model = null, context = null, historical = false;
  let renderTarget = null, inspectTarget = null, navigateTarget = null;
  let unsubscribe = null, teardown = null, timer = null, epoch = 0, queue = Promise.resolve();
  let disconnected = false, needsSnapshot = false, pending = new Map(), retryFamilies = new Set();
  let activationKey = null;

  function keyFor(nextContext, nextHistorical) {
    return JSON.stringify([
      nextContext?.runId ?? null,
      nextContext?.generation ?? null,
      nextContext?.mode ?? null,
      nextContext?.generationManifest ?? null,
      nextContext?.factoryRelease ?? null,
      nextContext?.semanticRelease ?? null,
      nextContext?.topologyId ?? null,
      nextContext?.fixture === true,
      nextHistorical,
    ]);
  }

  function render({ resetDetails = false } = {}) {
    if (!renderTarget || !model) return;
    const openIds = resetDetails ? [] : [...renderTarget.querySelectorAll("details[data-test-id][open]")]
      .map((item) => item.dataset.testId);
    renderTarget.hidden = false;
    renderTarget.innerHTML = renderHomeMarkup(model, { historical });
    for (const id of openIds) {
      const details = renderTarget.querySelector(`[data-test-id="${id}"]`);
      if (details) details.open = true;
    }
    bindHomeInteractions(renderTarget, inspectTarget ?? (() => {}), navigateTarget ?? (() => {}));
  }
  function project(fixtureFallback = true) {
    model = projectionFromPages(pages, context);
    if (fixtureFallback && referenceProjection && context?.fixture === true && context?.mode !== "HISTORICAL" &&
        HOME_FAMILIES.every((family) => pages[family]?.accepted !== true || pages[family]?.state === "EMPTY")) {
      const fixture = referenceProjection();
      model = { ...fixture, runtime: { ...fixture.runtime, running: context?.operatorActive ?? fixture.runtime.running } };
    }
    render();
  }
  function failed(current) {
    if (current !== epoch) return;
    disconnected = true;
    context = { ...context, transportDisconnected: true, operatorActive: null };
    project();
  }
  function enqueue(current, operation) {
    const result = queue.then(async () => {
      if (current !== epoch) return;
      try { await operation(); } catch (_error) { failed(current); }
    });
    queue = result;
    return result;
  }
  function unavailablePage(family, source) {
    return {
      accepted: false, family,
      mode: source?.mode === "HISTORICAL" ? "historical" : "current",
      state: "UNAVAILABLE", coverage: "UNKNOWN",
      records: [], markers: [], links: [], returned: 0,
      total_matches: 0, truncated: false, next_cursor: null,
    };
  }
  async function queryFamily(family, source) {
    const paginated = new Set(["run", "notification"]);
    if (!paginated.has(family)) return api.query(queryRequest(family, source));
    let cursor = null;
    let first = null;
    const records = [], markers = [], links = [];
    const seen = new Set();
    do {
      const page = await api.query(queryRequest(family, source, { cursor }));
      if (page?.accepted !== true) return page;
      first ??= page;
      records.push(...(page.records ?? []));
      markers.push(...(page.markers ?? []));
      links.push(...(page.links ?? []));
      const next = page.next_cursor ?? null;
      if (next === null) break;
      if (seen.has(next)) throw new Error("HOME_QUERY_CURSOR_LOOP");
      seen.add(next);
      cursor = next;
    } while (true);
    return {
      ...first, records, markers, links,
      returned: records.length, truncated: false, next_cursor: null,
    };
  }
  function transportRejected(page) {
    const reason = String(page?.reason ?? "");
    return page?.accepted === false &&
      /(NOT_CONNECTED|DISCONNECTED|BROKER_EXITED)/.test(reason);
  }
  async function safeQueryFamily(family, source) {
    return queryFamily(family, source);
  }
  async function loadFamily(family, current) {
    const page = await safeQueryFamily(family, context);
    if (current !== epoch) return null;
    if (transportRejected(page)) throw new Error("HOME_TRANSPORT_UNAVAILABLE");
    if (page?.accepted === true) retryFamilies.delete(family);
    else retryFamilies.add(family);
    pages = { ...pages, [family]: page };
    project();
    return page;
  }
  async function loadAll(current) {
    const source = context;
    const request = (family) => safeQueryFamily(family, source);
    const anchor = historical ? null : await request("run");
    if (current !== epoch) return;
    const families = historical ? HOME_FAMILIES : HOME_FAMILIES.filter((family) => family !== "run");
    const entries = await Promise.all(families.map(async (family) => [family, await request(family)]));
    if (current !== epoch) return;
    const frontier = historical ? null : await request("run");
    if (current !== epoch) return;
    const queried = [...entries.map(([, page]) => page), ...[anchor, frontier].filter(Boolean)];
    if (queried.some(transportRejected)) throw new Error("HOME_TRANSPORT_UNAVAILABLE");
    if (!historical && anchor?.accepted === true && frontier?.accepted === true &&
        acceptedIdentity(anchor) !== acceptedIdentity(frontier)) {
      needsSnapshot = true;
      return;
    }
    const run = frontier?.accepted === true ? frontier : anchor;
    const allEntries = historical ? entries : [...entries, ["run", run]];
    pages = Object.fromEntries(allEntries);
    retryFamilies = new Set(allEntries
      .filter(([, page]) => page?.accepted !== true)
      .map(([family]) => family));
    needsSnapshot = false;
    disconnected = false;
    context = { ...context, transportDisconnected: false };
    project(true);
  }
  async function refreshRun(current) {
    const page = await safeQueryFamily("run", context);
    if (current !== epoch) return;
    if (transportRejected(page)) throw new Error("HOME_TRANSPORT_UNAVAILABLE");
    if (page?.accepted !== true) {
      retryFamilies.add("run");
      pages = { ...pages, run: page };
      project(true);
      return;
    }
    retryFamilies.delete("run");
    if (needsSnapshot || acceptedIdentity(pages.run) !== acceptedIdentity(page)) return loadAll(current);
    pages = { ...pages, run: page };
    project(true);
  }
  async function refreshStatus(current) {
    if (historical || typeof api.status !== "function") return;
    const status = await api.status();
    if (current !== epoch) return;
    context = { ...context, operatorActive: typeof status?.learnerActive === "boolean" ? status.learnerActive : null };
    project();
  }
  function enqueueOnce(current, key, operation) {
    if (pending.has(key)) return pending.get(key);
    const tasks = pending;
    const result = enqueue(current, operation).finally(() => { if (tasks.get(key) === result) tasks.delete(key); });
    tasks.set(key, result);
    return result;
  }
  async function subscribe(current) {
    if (historical || typeof api.subscribeEvents !== "function") return;
    let stop;
    try { stop = await api.subscribeEvents((event) => enqueueOnce(current, event?.event_family ?? "unknown", async () => {
      if (event?.event_family === "operator.action.state") return refreshStatus(current);
      if (isNotificationEvent(event)) return loadAll(current);
      const family = familyForEvent(event);
      if (!family) return;
      if (event.event_family === "run.trainer.observed") return refreshRun(current);
      if (event.event_family?.startsWith("run.") || event.event_family?.startsWith("checkpoint.")) return loadAll(current);
      return loadFamily(family, current);
    })); } catch (_error) { return; }
    if (current !== epoch) { if (typeof stop === "function") await stop(); return; }
    unsubscribe = stop;
  }
  async function recover(current) {
    if (disconnected) {
      if (typeof api.connect === "function") await api.connect();
      if (current !== epoch) return;
      const stop = unsubscribe;
      unsubscribe = null;
      if (typeof stop === "function") await stop();
      if (current !== epoch) return;
      await subscribe(current);
      if (current !== epoch) return;
      await refreshStatus(current);
      await loadAll(current);
    } else {
      if (typeof unsubscribe !== "function") await subscribe(current);
      if (current !== epoch) return;
      await refreshStatus(current);
      if (current !== epoch) return;
      await refreshRun(current);
      if (current !== epoch) return;
      const families = new Set([...retryFamilies, "notification"]);
      families.delete("run");
      for (const family of families) {
        await loadFamily(family, current);
        if (current !== epoch) return;
      }
    }
  }
  function startTimer(current) {
    if (current !== epoch || historical) return;
    timer = schedule(async () => {
      timer = null;
      await enqueue(current, () => recover(current));
      startTimer(current);
    }, 2000);
  }

  async function stopSubscription() {
    while (typeof unsubscribe === "function") {
      if (teardown !== null) {
        try {
          await teardown;
        } catch {
          // The caller that owns the failed teardown reports it. A concurrent
          // lifecycle transition retries the still-owned subscription below.
        }
        continue;
      }
      const stop = unsubscribe;
      const pendingStop = Promise.resolve().then(() => stop());
      teardown = pendingStop;
      try {
        await pendingStop;
        if (unsubscribe === stop) unsubscribe = null;
        return;
      } finally {
        if (teardown === pendingStop) teardown = null;
      }
    }
  }

  async function activate(nextContext, { host, onInspect, onNavigate, defense } = {}) {
    const nextHistorical = Boolean(defense?.historical || nextContext?.mode === "HISTORICAL");
    const nextKey = keyFor(nextContext, nextHistorical);
    if (teardown !== null) {
      try {
        await teardown;
      } catch {
        // Re-evaluate the requested context after the owning caller observes
        // the teardown failure; stopSubscription() will retry if still needed.
      }
    }
    if (activationKey === nextKey) {
      renderTarget = host;
      inspectTarget = onInspect;
      navigateTarget = onNavigate;
      render();
      return queue;
    }
    const current = ++epoch;
    if (timer !== null) { cancel(timer); timer = null; }
    queue = Promise.resolve(); pending = new Map(); retryFamilies = new Set();
    renderTarget = host; inspectTarget = onInspect; navigateTarget = onNavigate;
    historical = nextHistorical;
    context = { ...nextContext, mode: historical ? "HISTORICAL" : nextContext?.mode }; pages = {}; disconnected = false; needsSnapshot = false;
    model = referenceProjection && nextContext?.fixture === true && !historical ? referenceProjection() : null;
    render({ resetDetails: true });
    await stopSubscription();
    if (current !== epoch) return;
    activationKey = nextKey;
    await enqueue(current, async () => {
      await subscribe(current);
      if (current !== epoch) return;
      await refreshStatus(current);
      if (current !== epoch) return;
      await loadAll(current);
    });
    startTimer(current);
  }
  async function deactivate() {
    ++epoch;
    activationKey = null;
    if (timer !== null) { cancel(timer); timer = null; }
    renderTarget = null; inspectTarget = null; navigateTarget = null;
    await stopSubscription();
  }
  return Object.freeze({ activate, deactivate, currentModel: () => model });
}
