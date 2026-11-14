import { DESTINATIONS, shellPosture } from "./shell-state.mjs";
import { renderComponentCatalog } from "./component-catalog.mjs";
import { renderSchoolView } from "./school-view.mjs";
import { renderNeuralView } from "./neural-view.mjs";
import { defensiveBannerMarkup } from "./defensive-state.mjs";
import { bindRovingNavigation } from "./accessibility.mjs";

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

export function renderContext(state, defense) {
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
    ["Topology", context.topologyId], ["Factory", context.factoryRelease],
    ["Semantic", context.semanticRelease], ["Optimizer", context.optimizerStep],
    ["Lease", context.admissionLease], ["Frontier", context.correctionFrontier],
    ["Resources", context.resourceHealth], ["Coverage", context.coverage],
  ];
  document.querySelector("#context-facts").innerHTML = facts
    .map(([label, value]) => `<span><small>${label}</small><strong title="${value}">${value}</strong></span>`)
    .join("");
}

export function renderDefensiveStatus(defense, onReconnect) {
  const host = document.querySelector("#defensive-banner");
  host.dataset.state = defense.id;
  host.setAttribute("role", defense.role);
  host.hidden = defense.id === "live";
  host.innerHTML = defensiveBannerMarkup(defense);
  host.querySelector("[data-reconnect]")?.addEventListener("click", onReconnect);
}

export function renderNavigation(state, onNavigate) {
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
    button.addEventListener("click", () => onNavigate(button.dataset.view));
  });
  bindRovingNavigation(nav);
}

export function renderInspector(state, defense) {
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

export function renderDemoActions(state, onInspect) {
  const host = document.querySelector("#demo-actions");
  if (!state) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = demoObjects
    .map(([kind, id]) => `<button type="button" data-kind="${kind}" data-id="${id}" data-focus-key="demo:${kind}:${id}">Inspect ${kind}</button>`)
    .join("");
  host.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => onInspect({
      kind: button.dataset.kind,
      id: button.dataset.id,
    }));
  });
}

export function renderCurrentView(state, defense, onInspect) {
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
    renderSchoolView(domain, (id, row) => onInspect({
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
    }), state.selected?.kind === "capability" ? state.selected.id : null);
    return;
  }
  if (state.view === "model") {
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Topology, attention health, depth routing and local refinement as measured telemetry only.";
    renderNeuralView(domain, (id, kind) => onInspect({
      kind: "neural",
      id,
      details: {
        "Diagnostic class": kind,
        "Interpretation boundary": "Measured routing/runtime telemetry only",
      },
    }));
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

export function renderPaletteOptions(state, onNavigate) {
  const host = document.querySelector("#palette-options");
  host.innerHTML = DESTINATIONS.map(([id, label]) => {
    const blocked = !state || (id === "operate" && !state.mutationAvailable);
    return `<button type="button" data-view="${id}" data-focus-key="palette:${id}" ${blocked ? "disabled" : ""}>${label}${id === "operate" && blocked ? " · unavailable offline" : ""}</button>`;
  }).join("");
  host.querySelectorAll("button:not(:disabled)").forEach((button) => {
    button.addEventListener("click", () => onNavigate(button.dataset.view));
  });
  bindRovingNavigation(host);
}

export function renderChrome(state, defense, displaySettings, handlers) {
  renderContext(state, defense);
  renderDefensiveStatus(defense, handlers.onReconnect);
  renderNavigation(state, handlers.onNavigate);
  renderInspector(state, defense);
  renderDemoActions(state, handlers.onInspect);
  renderCurrentView(state, defense, handlers.onInspect);
  document.querySelector("#view-title").textContent = labels.get(state?.view ?? "mission-control");
  document.querySelector("#view-title").setAttribute("tabindex", "-1");
  document.querySelector("#theme-trigger").textContent = "Theme · " + displaySettings.theme;
  document.querySelector("#density-trigger").textContent = "Density · " + displaySettings.density;
  document.querySelector("#theme-trigger").setAttribute("aria-label", `Change theme. Current theme ${displaySettings.theme}`);
  document.querySelector("#density-trigger").setAttribute("aria-label", `Change information density. Current density ${displaySettings.density}`);
}
