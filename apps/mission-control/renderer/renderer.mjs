import { createDomainViews } from "./views/domain-views.mjs";
import {
  DESTINATIONS,
  createShellState,
  inspect,
  navigate,
  normalizeContext,
  openSelectionOwner,
  shellPosture,
  withRoute,
} from "./shell-state.mjs";
import { buildDeepLink, parseDeepLink } from "./deep-link.mjs";
import { mountFrameExplorer } from "./frames/frame-explorer.mjs";
import { escapeText as esc } from "./frames/frame-model.mjs";

import {
  DENSITIES,
  THEMES,
  applyDisplaySettings,
  cycleSetting,
  loadDisplaySettings,
  saveDisplaySettings,
} from "./settings.mjs";

const labels = new Map(DESTINATIONS);
const demoObjects = [
  ["capability", "B.AND"],
  ["episode", "episode-record:fixture:retained-44239"],
  ["semantic", "sem:logic.and"],
  ["frame", "frame:quad-fast"],
  ["memory", "motif:bool-composition"],
  ["checkpoint", "generation:44238"],
  ["evidence", "receipt:fixture-001"],
  ["correction", "correction:fixture-1"],
  ["warning", "resource:disk-reserve"],
];

let state;
let displaySettings;
let frameMount;
let frameRouteId;
let modelSection = "neural";
let frameReturnContext;


const domainViews = createDomainViews({
  getState: () => state, getModelSection: () => modelSection,
  onInspect: selected => { state = inspect(state, selected); renderInspector(); setHash(); },
});

function connectionFreshness(connectionState) {
  if (connectionState === "healthy") return "FRESH";
  if (connectionState === "stale") return "STALE";
  if ([
    "disconnected", "service-restarting", "incompatible-version", "unauthorized",
  ].includes(connectionState)) return "DISCONNECTED";
  return "UNKNOWN";
}

function setHash() {
  const next = buildDeepLink(state);
  if (window.location.hash !== next) history.replaceState(null, "", next);
}

function renderContext() {
  const { context } = state;
  document.querySelector("#shell").dataset.posture = shellPosture(context);
  document.querySelector("#mode-badge").textContent = context.mode;
  document.querySelector("#run-id").textContent = context.runId;
  document.querySelector("#generation-id").textContent =
    `Generation ${context.generation} · manifest ${context.generationManifest}`;
  document.querySelector("#freshness").textContent = context.freshness;
  document.querySelector("#run-selector").replaceChildren(new Option(context.runId, context.runId));
  document.querySelector("#generation-selector").replaceChildren(new Option(`${context.generation} · ${context.mode}`, String(context.generation)));
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
    .map(([label, value]) => `<span><small>${esc(label)}</small><strong>${esc(value)}</strong></span>`)
    .join("");
}

function renderNavigation() {
  const nav = document.querySelector("#primary-nav");
  nav.innerHTML = DESTINATIONS.map(([id, label]) =>
    `<button type="button" data-view="${id}" aria-current="${state.view === id ? "page" : "false"}">${label}</button>`,
  ).join("");
  nav.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state = navigate(state, button.dataset.view);
      render();
    });
  });
}

function renderInspector() {
  const panel = document.querySelector("#inspector");
  const selected = state.selected;
  panel.setAttribute("aria-hidden", String(!state.inspectorOpen));
  document.querySelector("#inspector-title").textContent = selected ? selected.id : "No selection";
  const exact = selected?.details
    ? Object.entries(selected.details).map(([label, value]) =>
      `<dt>${esc(label)}</dt><dd>${esc(Array.isArray(value) ? value.join(", ") : value)}</dd>`,
    ).join("")
    : "";
  document.querySelector("#inspector-details").innerHTML = selected
    ? `<dt>Object class</dt><dd>${esc(selected.kind)}</dd>
       <dt>Identity</dt><dd>${esc(selected.id)}</dd>
       <dt>Posture</dt><dd>${esc(state.context.mode)}</dd>
       <dt>Generation</dt><dd>${state.context.generation}</dd>
       <dt>Evidence</dt><dd>Fixture reference only</dd>${exact}`
    : "";
  document.querySelector("#open-owner").disabled = !selected;
}

function renderDemoActions() {
  const host = document.querySelector("#demo-actions");
  host.innerHTML = demoObjects
    .map(([kind, id]) => `<button type="button" data-kind="${kind}" data-id="${id}">Inspect ${kind}</button>`)
    .join("");
  host.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      state = inspect(state, { kind: button.dataset.kind, id: button.dataset.id });
      render();
    });
  });
}

function render() {
  if (state.selected?.kind === "frame") modelSection = "frames";
  if (state.selected?.kind === "neural") modelSection = "neural";
  renderFrameView();
  renderContext();
  renderNavigation();
  renderInspector();
  renderDemoActions();
  domainViews.render();
  document.querySelector("#view-title").textContent = labels.get(state.view);
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  setHash();
  if (state.view === "atlas") void domainViews.ensureAtlasOverview();
}

function renderFrameView() {
  const host = document.querySelector("#frame-explorer");
  const isFrameView = state.view === "model" && modelSection === "frames";
  host.hidden = !isFrameView;
  if (!isFrameView) {
    frameMount?.dispose(); frameMount = null; frameRouteId = null;
    if (frameReturnContext) {
      state = { ...state, context: frameReturnContext };
      frameReturnContext = null;
      renderContext(); renderInspector();
    }
    return;
  }
  const selectedId = state.selected?.kind === "frame" ? state.selected.id : null;
  if (frameMount && (!selectedId || frameRouteId === selectedId)) return;
  frameMount?.dispose();
  frameReturnContext ??= state.context;
  frameRouteId = selectedId;
  frameMount = mountFrameExplorer(host, {
    querySnapshot: request => window.bamfMissionControl.querySnapshot(request),
    context: state.context, selectedId,
    onContext: (operatorView, mode) => {
      state = { ...state, context: Object.freeze({ ...normalizeContext(operatorView),
        mode: mode === "historical" ? "HISTORICAL" : "LIVE", freshness: state.context.freshness }) };
      renderContext(); renderInspector();
    },
    onSelection: id => {
      frameRouteId = id || null;
      state = inspect(state, id ? { kind: "frame", id } : null);
      renderInspector(); setHash();
    },
  });
}

async function bootstrap() {
  const connection = await window.bamfMissionControl.connect();
  const operatorView = await window.bamfMissionControl.querySnapshot({
    schemaVersion: "bamf.gui20.operator-view-query/v1",
    schema: "bilqis.bamf.mission-control.operator-view/v1",
  });
  displaySettings = loadDisplaySettings(window.localStorage);
  applyDisplaySettings(document.documentElement, displaySettings);
  state = createShellState(operatorView, parseDeepLink(window.location.hash));
  state = {
    ...state,
    context: Object.freeze({
      ...state.context,
      freshness: connectionFreshness(connection.state),
    }),
  };
  document.querySelector("#inspector-close").addEventListener("click", () => {
    state = inspect(state, null);
    render();
  });
  document.querySelectorAll("[data-model-section]").forEach(button => {
    button.addEventListener("click", () => {
      modelSection = button.dataset.modelSection;
      state = inspect(state, null);
      render();
    });
  });
  document.querySelector("#open-owner").addEventListener("click", () => {
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
  window.addEventListener("hashchange", () => {
    const route = parseDeepLink(window.location.hash);
    state = withRoute(state, route);
    render();
  });
  render();
}

bootstrap();
