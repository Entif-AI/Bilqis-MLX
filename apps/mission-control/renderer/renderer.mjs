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
  loadAbiRow,
  loadAtlasOverview,
  loadSemanticIdentity,
  renderAtlasMarkup,
} from "./semantic-atlas.mjs";
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
let atlasState = {
  status: "idle",
  error: null,
  overview: null,
  selection: null,
  lens: "canonical",
  selectedBank: null,
};

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

function renderAtlasDomain() {
  const host = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const atlasVisible = state.view === "atlas";
  host.hidden = !atlasVisible;
  fixture.hidden = atlasVisible;
  catalog.hidden = atlasVisible;
  document.querySelector("#view-summary").textContent = atlasVisible
    ? "Source-authoritative semantic identity and generation-scoped ABI state, with learned similarity isolated behind a separate lens."
    : "Shell foundation ready for provider-neutral BAMF views.";
  if (!atlasVisible) return;

  host.innerHTML = renderAtlasMarkup({ ...atlasState, context: state.context });
  host.querySelectorAll("[data-atlas-lens]").forEach((button) => {
    button.addEventListener("click", () => {
      atlasState = { ...atlasState, lens: button.dataset.atlasLens };
      renderAtlasDomain();
    });
  });
  host.querySelectorAll("[data-atlas-bank]").forEach((button) => {
    button.addEventListener("click", () => {
      atlasState = { ...atlasState, selectedBank: Number(button.dataset.atlasBank) };
      renderAtlasDomain();
    });
  });
  host.querySelector("#atlas-search-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const semanticId = new FormData(event.currentTarget).get("semanticId")?.toString().trim();
    if (!semanticId) return;
    atlasState = { ...atlasState, status: "loading", error: null };
    renderAtlasDomain();
    try {
      const selection = await loadSemanticIdentity(
        window.bamfMissionControl, state.context, semanticId,
      );
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      atlasState = { ...atlasState, status: "error",
        error: error?.code ?? error?.message ?? "Semantic query failed" };
    }
    renderAtlasDomain();
  });
  host.querySelector("#atlas-abi-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const bank = Number(form.get("bank"));
    const row = Number(form.get("row"));
    if (!Number.isSafeInteger(bank) || bank < 0 || !Number.isSafeInteger(row) || row < 0) return;
    atlasState = { ...atlasState, status: "loading", error: null, selectedBank: bank };
    renderAtlasDomain();
    try {
      const selection = await loadAbiRow(window.bamfMissionControl, state.context, bank, row);
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      atlasState = { ...atlasState, status: "error",
        error: error?.code ?? error?.message ?? "ABI query failed" };
    }
    renderAtlasDomain();
  });
}

async function ensureAtlasOverview() {
  if (state.view !== "atlas" || atlasState.status !== "idle") return;
  atlasState = { ...atlasState, status: "loading", error: null };
  renderAtlasDomain();
  try {
    const overview = await loadAtlasOverview(window.bamfMissionControl, state.context);
    atlasState = { ...atlasState, status: "ready", overview };
  } catch (error) {
    atlasState = { ...atlasState, status: "error",
      error: error?.code ?? error?.message ?? "Semantic Atlas unavailable" };
  }
  if (state.view === "atlas") renderAtlasDomain();
}

function render() {
  renderContext();
  renderNavigation();
  renderInspector();
  renderDemoActions();
  document.querySelector("#visual-catalog").innerHTML = renderComponentCatalog();
  document.querySelector("#view-title").textContent = labels.get(state.view);
  renderAtlasDomain();
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  setHash();
  if (state.view === "atlas") void ensureAtlasOverview();
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
