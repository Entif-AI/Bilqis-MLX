import {
  assertOperatorView,
  createShellState,
  inspect,
  navigate,
  openSelectionOwner,
  withDefensiveState,
  withRoute,
} from "./shell-state.mjs";
import { buildDeepLink, parseDeepLink } from "./deep-link.mjs";
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
} from "./defensive-state.mjs";
import {
  renderChrome,
  renderInspector,
  renderPaletteOptions,
} from "./renderer-ui.mjs";
import {
  focusToken,
  restoreFocus,
} from "./accessibility.mjs";

const labels = new Map(DESTINATIONS);
const SNAPSHOT_REQUEST = Object.freeze({
  schemaVersion: "bamf.gui20.operator-view-query/v1",
  schema: "bilqis.bamf.mission-control.operator-view/v1",
});
const demoObjects = [
  ["capability", "B.AND"],
  ["episode", "candidate-44238-7"],
  ["semantic", "sem:logic.and"],
  ["memory", "motif:bool-composition"],
  ["checkpoint", "generation:44238"],
  ["evidence", "receipt:fixture-001"],
  ["correction", "correction:fixture-1"],
  ["warning", "resource:disk-reserve"],
];

let state = null;
let displaySettings;
let defense = defensiveState("loading");
let focusReturnToken = null;
let paletteReturnToken = null;

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
  renderChrome(state, defense, displaySettings, {
    onReconnect: () => establishSnapshot({ preserveRoute: true }),
    onNavigate: navigateTo,
    onInspect: openInspector,
  });
  setHash();
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
  setHash();
  window.queueMicrotask(() => document.querySelector("#inspector-close")?.focus());
  announce(`Inspector opened for ${selected.id}`);
}

function closeInspector() {
  if (!state?.inspectorOpen) return;
  state = inspect(state, null);
  renderInspector(state, defense);
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
  const route = preserveRoute && state
    ? { view: state.view, selected: state.selected }
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
  state = withDefensiveState(createShellState(operatorView, route), defense);
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
}

async function bootstrap() {
  displaySettings = loadDisplaySettings(window.localStorage);
  applyDisplaySettings(document.documentElement, displaySettings);
  bindStaticInteractions();
  render();
  await establishSnapshot();
}

bootstrap();
