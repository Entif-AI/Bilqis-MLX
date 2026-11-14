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

function renderCurrentView() {
  const domain = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const summary = document.querySelector("#view-summary");
  if (state.view === "school") {
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
    renderSchoolView(domain, (id, row) => {
      state = inspect(state, {
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
      renderInspector();
      setHash();
    }, state.selected?.kind === "capability" ? state.selected.id : null);
    return;
  }
  fixture.hidden = false;
  catalog.hidden = false;
  domain.innerHTML = "";
  summary.textContent = "Shell foundation ready for provider-neutral BAMF views.";
  catalog.innerHTML = renderComponentCatalog();
}

function render() {
  renderContext();
  renderNavigation();
  renderInspector();
  renderDemoActions();
  renderCurrentView();
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
