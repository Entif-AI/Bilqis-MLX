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
import { renderSchoolView } from "./school-view.mjs";
import { renderNeuralView } from "./neural-view.mjs";
import { renderEpisodesView } from "./episode-view.mjs";

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

function renderCurrentView() {
  const domain = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const summary = document.querySelector("#view-summary");
  if (state.selected?.kind === "frame") modelSection = "frames";
  if (state.selected?.kind === "neural") modelSection = "neural";
  document.querySelector("#model-nav").hidden = state.view !== "model";
  document.querySelectorAll("[data-model-section]").forEach(button => {
    button.setAttribute("aria-pressed", String(button.dataset.modelSection === modelSection));
  });
  domain.hidden = state.view === "model" && modelSection === "frames";
  document.querySelector("#domain-context-note").hidden = !["school", "learning", "model"].includes(state.view) || domain.hidden;
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
  if (state.view === "model") {
    fixture.hidden = true;
    catalog.hidden = true;
    if (modelSection === "frames") {
      summary.textContent = "Frame Compiler Explorer · inspect exact packing receipts and causal visibility.";
      return;
    }
    summary.textContent = "Topology, attention health, depth routing and local refinement as measured telemetry only.";
    renderNeuralView(domain, (id, kind) => {
      state = inspect(state, {
        kind: "neural",
        id,
        details: {
          "Diagnostic class": kind,
          "Interpretation boundary": "Measured routing/runtime telemetry only",
        },
      });
      renderInspector();
      setHash();
    });
    return;
  }
  if (state.view === "learning") {
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Candidate proposal, work, assessment, retention and finalization reconstructed from bounded evidence.";
    renderEpisodesView(domain, (id, evidenceType) => {
      state = inspect(state, {
        kind: "evidence",
        id,
        details: {
          "Evidence type": evidenceType,
          "Episode replay": "Read-only durable evidence reference",
        },
      });
      renderInspector();
      setHash();
    }, state.selected?.kind === "episode" ? state.selected.id : null);
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
  renderFrameView();
  setHash();
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
