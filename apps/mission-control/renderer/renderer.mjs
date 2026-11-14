import { createFrameShell } from "./frames/frame-shell.mjs";
import {
  assertOperatorView,
  createShellState,
  inspect,
  navigate,
  openEvidence,
  openSelectionOwner,
  returnFromEvidence,
  selectObject,
  normalizeContext,
  withDefensiveState,
  withRoute,
} from "./shell-state.mjs";
import { buildDeepLink, parseDeepLink, routeFromState } from "./deep-link.mjs";
import {
  DENSITIES,
  THEMES,
  applyDisplaySettings,
  cycleSetting,
  loadDisplaySettings,
  saveDisplaySettings,
} from "./settings.mjs";
import {
  cacheOperatorView,
  defensiveState,
  defensiveStateForConnection,
  defensiveStateForError,
  loadCachedOperatorView,
} from "./foundation/defensive-state.mjs";
import {
  renderChrome,
  renderContext,
  renderNavigation,
  renderInspector,
  renderPaletteOptions,
} from "./foundation/renderer-ui.mjs";
import {
  focusToken,
  restoreFocus,
} from "./foundation/accessibility.mjs";
import { createHomeController } from "./home/home-controller.mjs";
import { createResourceController } from "./resources/resource-controller.mjs";
import { createCapabilityExplorer } from "./capability/app.mjs";
import { activateDomainViews } from "./foundation/domain-controller.mjs";
import { createInteractionController } from "./interactions/controller.mjs";
import { routeForObjectRef } from "./interactions/app-uri.mjs";
import { withHistoricalLens } from "./interactions/model.mjs";

const SNAPSHOT_REQUEST = Object.freeze({
  schemaVersion: "bamf.gui20.operator-view-query/v1",
  schema: "bilqis.bamf.mission-control.operator-view/v1",
});
let state = null;
let verifiedLiveContext = null;
let displaySettings;
let defense = defensiveState("loading");
let focusReturnToken = null;
let paletteReturnToken = null;
const homeController = createHomeController(window.bamfMissionControl);
const resourceController = createResourceController(window.bamfMissionControl);
const interactionController = createInteractionController({
  document,
  storage: window.localStorage,
  getState: () => state,
  onTimeLens: (generation) => { state = withHistoricalLens(state, generation); render(); },
  onCurrentLens: () => {
    if (!state || !verifiedLiveContext) {
      announce("No verified current context is available.");
      return;
    }
    state = withDefensiveState({ ...state, context: verifiedLiveContext }, defense);
    render();
  },
  canUseCurrent: () => Boolean(verifiedLiveContext),
  onOpenRef: (ref) => { state = withRoute(state, routeForObjectRef(ref)); render(); },
  announce,
});

const frameShell = createFrameShell({
  getState: () => state, setState: next => { state = next; }, getDefense: () => defense,
  render, onInspect: openInspector,
  refresh: () => { renderContext(state, defense); renderNavigation(state, navigateTo); renderInspector(state, defense); setHash(); },
});
const capabilityExplorer = createCapabilityExplorer({
  host: document.querySelector("#domain-view"),
  serviceQuery: request => window.bamfMissionControl.querySnapshot(request),
  changeLens: (lens, capabilityId) => {
    if (!state) return;
    state = {
      ...state,
      context: Object.freeze({
        ...state.context, ...lens,
        historicalPinned: lens.mode === "HISTORICAL",
        generationManifest: "UNKNOWN", topologyId: "UNKNOWN",
        factoryRelease: "UNKNOWN", semanticRelease: "UNKNOWN",
        coverage: "UNKNOWN", freshness: "UNKNOWN",
      }),
      selected: { kind: "capability", id: capabilityId },
      inspectorOpen: false,
      mutationAvailable: false,
    };
    render();
  },
  openObject: (selected) => {
    if (!state) return;
    state = { ...openSelectionOwner(inspect(state, selected)), inspectorOpen: false };
    render();
  },
  resolvePins: (meta) => {
    if (!state) return;
    state = {
      ...state,
      context: Object.freeze({
        ...state.context,
        generationManifest: meta.run.generation_manifest_sha256,
        topologyId: meta.run.topology_sha256,
        factoryRelease: meta.run.factory_release_sha256,
        semanticRelease: meta.run.semantic_release_sha256,
        coverage: meta.coverage,
      }),
    };
    renderContext(state, defense);
    setHash();
  },
});

function setHash() {
  if (!state) return;
  const next = buildDeepLink(state);
  if (window.location.hash !== next) history.replaceState(null, "", next);
}

function announce(message) {
  const announcer = document.querySelector("#announcer");
  announcer.textContent = "";
  window.queueMicrotask(() => { announcer.textContent = message; });
}

function render() {
  frameShell.beforeRender();
  renderChrome(state, defense, displaySettings, {
    api: window.bamfMissionControl,
    onEvidenceSelect: selectEvidenceRecord,
    onEvidenceReturn: returnEvidenceOrigin,
    onReconnect: () => establishSnapshot({ preserveRoute: true }),
    onNavigate: navigateTo,
    onInspect: openInspector,
  });
  frameShell.afterRender();
  setHash();
  activateDomainViews({
    state, getState: () => state, defense, api: window.bamfMissionControl,
    homeController, resourceController, capabilityExplorer, onInspect: openInspector,
  });
  window.queueMicrotask(() => interactionController.render());
}

function selectEvidenceRecord(selected) {
  if (!state) return;
  state = selectObject(state, selected);
  renderInspector(state, defense);
  interactionController.render();
  setHash();
}

function returnEvidenceOrigin() {
  if (!state?.evidenceOrigin) return;
  state = returnFromEvidence(state);
  render();
  announce("Returned to the inspected evidence origin.");
}

function navigateTo(view) {
  state = navigate(state, view);
  document.querySelector("#command-palette")?.close?.();
  render();
  window.queueMicrotask(() => document.querySelector("#view-title")?.focus?.({ preventScroll: true }));
}

function openInspector(selected) {
  if (!state) return;
  focusReturnToken = focusToken(document.activeElement);
  state = inspect(state, selected);
  renderInspector(state, defense);
  interactionController.render();
  setHash();
  window.queueMicrotask(() => document.querySelector("#inspector-close")?.focus());
  announce(`Inspector opened for ${selected.id}`);
}

function closeInspector() {
  if (!state?.inspectorOpen) return;
  state = inspect(state, null);
  renderInspector(state, defense);
  interactionController.render();
  setHash();
  window.queueMicrotask(() => restoreFocus(document, focusReturnToken));
  announce("Inspector closed");
}

function openPalette() {
  const dialog = document.querySelector("#command-palette");
  paletteReturnToken = focusToken(document.activeElement);
  renderPaletteOptions(state, (view) => {
    navigateTo(view);
    window.queueMicrotask(() => document.querySelector("#main-content")?.focus());
  });
  if (!dialog.open) dialog.showModal();
  window.queueMicrotask(() => dialog.querySelector("button:not(:disabled)")?.focus());
}

async function establishSnapshot({ preserveRoute = false } = {}) {
  const modelSection = state?.modelSection;
  frameShell.reset();
  if (state) state = { ...state, mutationAvailable: false };
  const route = preserveRoute && state
    ? routeFromState(state)
    : parseDeepLink(window.location.hash);
  defense = defensiveState("loading", {
    snapshotAvailable: Boolean(state),
    snapshotSource: state ? "previous" : "none",
  });
  render();

  let connection = null;
  let connectError = null;
  try {
    connection = await window.bamfMissionControl.connect();
  } catch (error) {
    connectError = error;
  }

  let operatorView = null;
  let snapshotSource = "none";
  let snapshotError = null;
  if (connection !== null) {
    try {
      operatorView = await window.bamfMissionControl.querySnapshot(SNAPSHOT_REQUEST);
      assertOperatorView(operatorView);
      snapshotSource = "service";
      cacheOperatorView(window.localStorage, operatorView);
    } catch (error) {
      snapshotError = error;
      operatorView = null;
    }
  }

  if (operatorView === null) {
    const cached = loadCachedOperatorView(window.localStorage);
    if (cached !== null) {
      try {
        assertOperatorView(cached.operatorView);
        operatorView = cached.operatorView;
        snapshotSource = "cache";
      } catch (error) {
        snapshotError ??= error;
      }
    }
  }

  if (operatorView === null) {
    defense = defensiveStateForError(snapshotError ?? connectError, {
      snapshotAvailable: false,
      snapshotSource: "none",
    });
    state = null;
    render();
    announce(`${defense.label}. No verified snapshot is available.`);
    return;
  }

  const options = { snapshotAvailable: true, snapshotSource };
  defense = snapshotError || connectError
    ? defensiveStateForError(snapshotError ?? connectError, options)
    : defensiveStateForConnection(connection?.state, options);
  if (snapshotSource === "cache" && defense.id === "live") {
    defense = defensiveState("stale", options);
  }
  verifiedLiveContext = snapshotSource === "service" && defense.id === "live"
    ? normalizeContext(operatorView)
    : null;
  state = { ...withDefensiveState(createShellState(operatorView, route), defense), modelSection };
  render();
  announce(`${defense.label}. ${defense.historical ? "Inspection-only evidence is shown." : "Live context established."}`);
}

function bindStaticInteractions() {
  document.querySelector("#inspector-close").addEventListener("click", closeInspector);
  document.querySelector("#open-owner").addEventListener("click", () => {
    if (!state) return;
    state = openSelectionOwner(state);
    render();
  });
  document.querySelector("#open-evidence").addEventListener("click", () => {
    if (!state?.selected) return;
    state = openEvidence(state);
    render();
  });
  document.querySelector("#theme-trigger").addEventListener("click", () => {
    displaySettings = { ...displaySettings, theme: cycleSetting(displaySettings.theme, THEMES) };
    saveDisplaySettings(window.localStorage, displaySettings);
    applyDisplaySettings(document.documentElement, displaySettings);
    render();
  });
  document.querySelector("#density-trigger").addEventListener("click", () => {
    displaySettings = { ...displaySettings, density: cycleSetting(displaySettings.density, DENSITIES) };
    saveDisplaySettings(window.localStorage, displaySettings);
    applyDisplaySettings(document.documentElement, displaySettings);
    render();
  });
  document.querySelector("#palette-trigger").addEventListener("click", openPalette);
  document.querySelector("#palette-close").addEventListener("click", () => {
    document.querySelector("#command-palette").close();
  });
  document.querySelector("#command-palette").addEventListener("close", () => {
    window.queueMicrotask(() => restoreFocus(document, paletteReturnToken));
  });
  document.querySelector("#generation-selector").addEventListener("change", (event) => {
    if (!state) return;
    const generation = Number(event.currentTarget.value);
    if (!Number.isSafeInteger(generation) || generation < 0) return;
    state = withHistoricalLens(state, generation);
    render();
  });
  window.addEventListener("hashchange", () => {
    if (!state) return;
    const route = parseDeepLink(window.location.hash);
    state = withRoute(state, route);
    render();
  });
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
      event.preventDefault();
      openPalette();
      return;
    }
    if (event.key === "Escape" && state?.inspectorOpen && !document.querySelector("#command-palette").open) {
      event.preventDefault();
      closeInspector();
    }
  });
  interactionController.bindStatic();
}

async function bootstrap() {
  displaySettings = loadDisplaySettings(window.localStorage);
  applyDisplaySettings(document.documentElement, displaySettings);
  bindStaticInteractions();
  render();
  await establishSnapshot();
}

bootstrap();
