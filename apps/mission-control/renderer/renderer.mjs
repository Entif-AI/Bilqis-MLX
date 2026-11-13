import {
  DESTINATIONS,
  createShellState,
  inspect,
  navigate,
  openSelectionOwner,
  shellPosture,
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

const labels = new Map(DESTINATIONS);
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

let state;
let displaySettings;

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
    `Generation ${context.generation} · checkpoint ${context.checkpoint}`;
  document.querySelector("#freshness").textContent = context.freshness;
  const facts = [
    ["Topology", context.topologyId],
    ["Factory", context.factoryRelease],
    ["Semantic", context.semanticRelease],
    ["Optimizer", context.optimizerStep],
    ["Lease", context.admissionLease],
    ["Frontier", context.correctionFrontier],
    ["Resources", context.resourceHealth],
  ];
  document.querySelector("#context-facts").innerHTML = facts
    .map(([label, value]) => `<span><small>${label}</small><strong>${value}</strong></span>`)
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
    ? `<dt>Object class</dt><dd>${selected.kind}</dd>
       <dt>Identity</dt><dd>${selected.id}</dd>
       <dt>Posture</dt><dd>${state.context.mode}</dd>
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
  document.querySelector("#visual-catalog").innerHTML = renderComponentCatalog();
  document.querySelector("#view-title").textContent = labels.get(state.view);
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  setHash();
}

async function bootstrap() {
  await window.bamfMissionControl.connect();
  const bootstrapState = await window.bamfMissionControl.querySnapshot({
    schemaVersion: "bamf.gui01.bootstrap-query.fixture/v1",
    objectRef: "shell-bootstrap",
  });
  displaySettings = loadDisplaySettings(window.localStorage);
  applyDisplaySettings(document.documentElement, displaySettings);
  state = createShellState(bootstrapState.context, parseDeepLink(window.location.hash));
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
    state = createShellState(state.context, route);
    render();
  });
  render();
}

bootstrap();
