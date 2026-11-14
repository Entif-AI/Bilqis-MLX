import { createDomainViews } from "./domain-views.mjs";
import { createCapabilityExplorer } from "./capability/app.mjs";
import { escapeHtml } from "./capability/model.mjs";
import {
  DESTINATIONS,
  createShellState,
  inspect,
  navigate,
  openSelectionOwner,
  shellPosture,
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

const labels = new Map(DESTINATIONS);
const demoObjects = [
  ["capability", "B.AND"],
  ["episode", "episode-record:fixture:retained-44239"],
  ["semantic", "sem:logic.and"],
  ["memory", "motif:bool-composition"],
  ["checkpoint", "generation:44238"],
  ["evidence", "receipt:fixture-001"],
  ["correction", "correction:fixture-1"],
  ["warning", "resource:disk-reserve"],
];

let state;
let displaySettings;
let explorer;
let domains;


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
  document.querySelector("#shell").dataset.view = state.view;
  document.querySelector("#shell").dataset.posture = shellPosture(context);
  document.querySelector("#mode-badge").textContent = context.mode;
  document.querySelector("#run-id").textContent = context.runId;
  document.querySelector("#generation-id").textContent =
    `Generation ${context.generation} · manifest ${context.generationManifest}`;
  document.querySelector("#freshness").textContent = context.freshness;
  const runSelector = document.querySelector("#run-selector");
  runSelector.replaceChildren(new Option(context.runId, context.runId));
  runSelector.disabled = true;
  const generationSelector = document.querySelector("#generation-selector");
  const generations = context.fixture ? [1, 2, 3] : [context.generation];
  generationSelector.replaceChildren(...generations.map((g) => new Option(
    `${g} · ${g === context.generation ? context.mode : "HISTORICAL"}`, g, false, g === context.generation)));
  generationSelector.disabled = !context.fixture;
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
    .map(([label, value]) => `<span><small>${label}</small><strong>${escapeHtml(value)}</strong></span>`)
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
  panel.hidden = !state.inspectorOpen;
  panel.setAttribute("aria-hidden", String(!state.inspectorOpen));
  document.querySelector("#inspector-title").textContent = selected ? selected.id : "No selection";
  const exact = selected?.details
    ? Object.entries(selected.details).map(([label, value]) =>
      `<dt>${escapeHtml(label)}</dt><dd>${escapeHtml(Array.isArray(value) ? value.join(", ") : value)}</dd>`,
    ).join("")
    : "";
  document.querySelector("#inspector-details").innerHTML = selected
    ? `<dt>Object class</dt><dd>${escapeHtml(selected.kind)}</dd>
       <dt>Identity</dt><dd>${escapeHtml(selected.id)}</dd>
       <dt>Posture</dt><dd>${state.context.mode}</dd>
       <dt>Generation</dt><dd>${state.context.generation}</dd>
       <dt>Evidence</dt><dd>Open owning view for exact records</dd>${exact}`

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
  document.querySelector("#inspector").hidden = !state.inspectorOpen;
  renderDemoActions();
  const dossierView = state.view === "capability";
  document.querySelector("#capability-explorer").hidden = !dossierView;
  document.querySelector("#domain-view").hidden = dossierView;
  if (dossierView) {
    document.querySelector(".fixture-card").hidden = true;
    document.querySelector("#visual-catalog").hidden = true;
    document.querySelector("#view-summary").textContent = "Measured chronology, source support, and literal evidence. No inferred causes.";
    explorer?.update(state);
  } else {
    explorer?.hide();
    domains?.render(state);
  }

  document.querySelector("#view-title").textContent = labels.get(state.view);
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  setHash();
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
  document.querySelector("#generation-selector").addEventListener("change", (event) => {
    state = { ...state, context: Object.freeze({ ...state.context,
      generation: Number(event.target.value), mode: "HISTORICAL", generationManifest: "UNKNOWN",
      topologyId: "UNKNOWN", factoryRelease: "UNKNOWN", semanticRelease: "UNKNOWN", coverage: "UNKNOWN" }) };
    render();
  });
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
  domains = createDomainViews({ onState: (next) => { state = next; }, renderInspector, setHash });
  explorer = createCapabilityExplorer({
    host: document.querySelector("#capability-explorer"),
    serviceQuery: (query) => window.bamfMissionControl.querySnapshot(query),
    changeLens: (lens, capabilityId) => {
      state = { ...state, context: Object.freeze({ ...state.context, ...lens,
        generationManifest: "UNKNOWN", topologyId: "UNKNOWN", factoryRelease: "UNKNOWN",
        semanticRelease: "UNKNOWN", freshness: "UNKNOWN", coverage: "UNKNOWN" }),
        selected: { kind: "capability", id: capabilityId }, inspectorOpen: false };
      render();
    },
    openObject: (selected) => {
      state = openSelectionOwner(inspect(state, selected));
      state.inspectorOpen = false;
      render();
    },
    resolvePins: (meta) => {
      state = { ...state, context: Object.freeze({ ...state.context,
        generationManifest: meta.run.generation_manifest_sha256, topologyId: meta.run.topology_sha256,
        factoryRelease: meta.run.factory_release_sha256, semanticRelease: meta.run.semantic_release_sha256,
        coverage: meta.coverage }) };
      renderContext();
    },
  });
  render();
}

bootstrap();
