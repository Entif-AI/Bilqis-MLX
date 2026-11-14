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
import { renderComponentCatalog } from "./component-catalog.mjs";
import { mountFrameExplorer } from "./frame-explorer.mjs";
import { escapeText as esc } from "./frame-model.mjs";
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
  ["episode", "candidate-44238-7"],
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
  document.querySelector("#inspector-details").innerHTML = selected
    ? `<dt>Object class</dt><dd>${esc(selected.kind)}</dd>
       <dt>Identity</dt><dd>${esc(selected.id)}</dd>
       <dt>Posture</dt><dd>${esc(state.context.mode)}</dd>
       <dt>Generation</dt><dd>${state.context.generation}</dd>
       <dt>Evidence</dt><dd>Fixture reference only</dd>`
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
  renderContext();
  renderNavigation();
  renderInspector();
  renderDemoActions();
  if (state.view !== "model") document.querySelector("#visual-catalog").innerHTML = renderComponentCatalog();
  document.querySelector("#view-title").textContent = labels.get(state.view);
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  renderFrameView();
  setHash();
}

function renderFrameView() {
  const host = document.querySelector("#frame-explorer");
  const isFrameView = state.view === "model";
  host.hidden = !isFrameView;
  document.querySelector(".fixture-card").hidden = isFrameView;
  document.querySelector("#visual-catalog").hidden = isFrameView;
  document.querySelector("#view-summary").textContent = isFrameView
    ? "Frame Compiler Explorer · inspect exact packing receipts and causal visibility."
    : "Shell foundation ready for provider-neutral BAMF views.";
  if (!isFrameView) {
    frameMount?.dispose(); frameMount = null; frameRouteId = null;
    return;
  }
  const selectedId = state.selected?.kind === "frame" ? state.selected.id : null;
  if (frameMount && (!selectedId || frameRouteId === selectedId)) return;
  frameMount?.dispose();
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
