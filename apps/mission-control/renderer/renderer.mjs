import {
  DESTINATIONS,
  assertOperatorView,
  createShellState,
  inspect,
  navigate,
  openSelectionOwner,
  shellPosture,
  withDefensiveState,
  withRoute,
} from "./shell-state.mjs";
import { buildDeepLink, parseDeepLink } from "./deep-link.mjs";
import { renderComponentCatalog } from "./component-catalog.mjs";
import {
  DENSITIES,
  THEMES,
  applyDisplaySettings,
  cycleSetting,
  loadDisplaySettings,
  saveDisplaySettings,
} from "./settings.mjs";
import { renderSchoolView } from "./school-view.mjs";
import {
  cacheOperatorView,
  defensiveBannerMarkup,
  defensiveState,
  defensiveStateForConnection,
  defensiveStateForError,
  loadCachedOperatorView,
} from "./defensive-state.mjs";
import {
  bindRovingNavigation,
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

function renderContext() {
  const shell = document.querySelector("#shell");
  if (!state) {
    shell.dataset.posture = defense.id;
    document.querySelector("#mode-badge").textContent = "INSPECTION";
    document.querySelector("#run-id").textContent = "No verified snapshot";
    document.querySelector("#generation-id").textContent = "Generation unavailable";
    document.querySelector("#freshness").textContent = defense.freshness;
    document.querySelector("#context-facts").innerHTML = "";
    return;
  }
  const { context } = state;
  shell.dataset.posture = shellPosture(context);
  document.querySelector("#mode-badge").textContent = context.mode;
  document.querySelector("#run-id").textContent = context.runId;
  document.querySelector("#run-id").title = context.runId;
  document.querySelector("#generation-id").textContent =
    `Generation ${context.generation} · manifest ${context.generationManifest}`;
  document.querySelector("#freshness").textContent = context.freshness;
  const facts = [
    ["Topology", context.topologyId],
    ["Factory", context.factoryRelease],
    ["Semantic", context.semanticRelease],
    ["Optimizer", context.optimizerStep],
    ["Lease", context.admissionLease],
    ["Frontier", context.correctionFrontier],
    ["Resources", context.resourceHealth],
    ["Coverage", context.coverage],
  ];
  document.querySelector("#context-facts").innerHTML = facts
    .map(([label, value]) => `<span><small>${label}</small><strong title="${value}">${value}</strong></span>`)
    .join("");
}

function renderDefensiveStatus() {
  const host = document.querySelector("#defensive-banner");
  host.dataset.state = defense.id;
  host.setAttribute("role", defense.role);
  host.hidden = defense.id === "live";
  host.innerHTML = defensiveBannerMarkup(defense);
  host.querySelector("[data-reconnect]")?.addEventListener("click", () => {
    establishSnapshot({ preserveRoute: true });
  });
}

function renderNavigation() {
  const nav = document.querySelector("#primary-nav");
  nav.setAttribute("aria-label", "Mission Control destinations");
  const active = state?.view ?? "mission-control";
  nav.innerHTML = DESTINATIONS.map(([id, label]) => {
    const blocked = !state || (id === "operate" && !state.mutationAvailable);
    const reason = id === "operate" && blocked
      ? " title=\"Operate is unavailable until a verified live command context is re-established.\""
      : "";
    return `<button type="button" data-view="${id}" data-focus-key="nav:${id}" aria-current="${active === id ? "page" : "false"}" ${blocked ? "disabled" : ""}${reason}>${label}</button>`;
  }).join("");
  nav.querySelectorAll("button:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => {
      state = navigate(state, button.dataset.view);
      render();
      document.querySelector("#view-title")?.focus?.({ preventScroll: true });
    });
  });
  bindRovingNavigation(nav);
}

function renderInspector() {
  const panel = document.querySelector("#inspector");
  const selected = state?.selected ?? null;
  const open = Boolean(state?.inspectorOpen);
  panel.setAttribute("aria-hidden", String(!open));
  panel.inert = !open;
  document.querySelector("#inspector-title").textContent = selected ? selected.id : "No selection";
  const exact = selected?.details
    ? Object.entries(selected.details).map(([label, value]) =>
      `<dt>${label}</dt><dd>${Array.isArray(value) ? value.join(", ") : value}</dd>`,
    ).join("")
    : "";
  document.querySelector("#inspector-details").innerHTML = selected
    ? `<dt>Object class</dt><dd>${selected.kind}</dd>
       <dt>Identity</dt><dd>${selected.id}</dd>
       <dt>Posture</dt><dd>${state.context.mode}</dd>
       <dt>Generation</dt><dd>${state.context.generation}</dd>
       <dt>Evidence</dt><dd>${defense.historical ? "Verified prior evidence · inspection only" : "Current verified fixture/reference"}</dd>${exact}`
    : "";
  document.querySelector("#open-owner").disabled = !selected;
}

function openInspector(selected) {
  if (!state) return;
  focusReturnToken = focusToken(document.activeElement);
  state = inspect(state, selected);
  renderInspector();
  setHash();
  window.queueMicrotask(() => document.querySelector("#inspector-close")?.focus());
  announce(`Inspector opened for ${selected.id}`);
}

function closeInspector() {
  if (!state?.inspectorOpen) return;
  state = inspect(state, null);
  renderInspector();
  setHash();
  window.queueMicrotask(() => restoreFocus(document, focusReturnToken));
  announce("Inspector closed");
}

function renderDemoActions() {
  const host = document.querySelector("#demo-actions");
  if (!state) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = demoObjects
    .map(([kind, id]) => `<button type="button" data-kind="${kind}" data-id="${id}" data-focus-key="demo:${kind}:${id}">Inspect ${kind}</button>`)
    .join("");
  host.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      openInspector({ kind: button.dataset.kind, id: button.dataset.id });
    });
  });
}

function renderCurrentView() {
  const domain = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const summary = document.querySelector("#view-summary");
  if (!state) {
    fixture.hidden = true;
    catalog.hidden = false;
    domain.innerHTML = "";
    summary.textContent = defense.description;
    catalog.innerHTML = renderComponentCatalog();
    return;
  }
  if (state.view === "school") {
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
    renderSchoolView(domain, (id, row) => {
      openInspector({
        kind: "capability",
        id,
        details: {
          "WAS/TOP/NOW/ALL": row.was + "/" + row.top + "/" + row.now + "/" + row.total,
          Debt: row.debt,
          "P(RET)": row.pRet ?? "NOT MEASURED",
          Prerequisites: row.prerequisites.length ? row.prerequisites : ["none"],
          "Source state": row.sourceState,
          "Implementation state": row.implementationState,
          "Qualification state": row.qualificationState,
        },
      });
    }, state.selected?.kind === "capability" ? state.selected.id : null);
    return;
  }
  fixture.hidden = false;
  catalog.hidden = false;
  domain.innerHTML = "";
  summary.textContent = defense.historical
    ? "Inspection-only evidence retained while the live command context is unavailable."
    : "Shell foundation ready for provider-neutral BAMF views.";
  catalog.innerHTML = renderComponentCatalog();
}

function renderPaletteOptions() {
  const host = document.querySelector("#palette-options");
  host.innerHTML = DESTINATIONS.map(([id, label]) => {
    const blocked = !state || (id === "operate" && !state.mutationAvailable);
    return `<button type="button" data-view="${id}" data-focus-key="palette:${id}" ${blocked ? "disabled" : ""}>${label}${id === "operate" && blocked ? " · unavailable offline" : ""}</button>`;
  }).join("");
  host.querySelectorAll("button:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => {
      state = navigate(state, button.dataset.view);
      document.querySelector("#command-palette").close();
      render();
      window.queueMicrotask(() => document.querySelector("#main-content")?.focus());
    });
  });
  bindRovingNavigation(host);
}

function openPalette() {
  const dialog = document.querySelector("#command-palette");
  paletteReturnToken = focusToken(document.activeElement);
  renderPaletteOptions();
  if (!dialog.open) dialog.showModal();
  window.queueMicrotask(() => dialog.querySelector("button:not(:disabled)")?.focus());
}

function render() {
  renderContext();
  renderDefensiveStatus();
  renderNavigation();
  renderInspector();
  renderDemoActions();
  renderCurrentView();
  document.querySelector("#view-title").textContent = labels.get(state?.view ?? "mission-control");
  document.querySelector("#view-title").setAttribute("tabindex", "-1");
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  document.querySelector("#theme-trigger").setAttribute("aria-label", `Change theme. Current theme ${displaySettings.theme}`);
  document.querySelector("#density-trigger").setAttribute("aria-label", `Change information density. Current density ${displaySettings.density}`);
  setHash();
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
