import { inspect } from "./shell-state.mjs";
import { renderComponentCatalog } from "./component-catalog.mjs";
import { loadAbiRow, loadAtlasOverview, loadSemanticIdentity, renderAtlasMarkup } from "./semantic-atlas.mjs";
import { renderSchoolView } from "./school/school-view.mjs";
import { renderNeuralView } from "./neural/neural-view.mjs";
import { renderEpisodesView } from "./episodes/episode-view.mjs";

export function createDomainViews({ onState, renderInspector, setHash }) {
let state;
let contextKey;
let contextEpoch = 0;
let selectionEpoch = 0;
const initialAtlasState = () => ({
  status: "idle",
  error: null,
  overview: null,
  selection: null,
  lens: "canonical",
  selectedBank: null,
});
let atlasState = initialAtlasState();
const currentSelection = (request) => request.context === contextEpoch && request.selection === selectionEpoch;
function renderAtlasDomain() {
  if (state.view !== "atlas") return;
  const host = document.querySelector("#domain-view");
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
    const request = { context: contextEpoch, selection: ++selectionEpoch };
    try {
      const selection = await loadSemanticIdentity(
        window.bamfMissionControl, state.context, semanticId,
      );
      if (!currentSelection(request)) return;
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      if (!currentSelection(request)) return;
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
    const request = { context: contextEpoch, selection: ++selectionEpoch };
    try {
      const selection = await loadAbiRow(window.bamfMissionControl, state.context, bank, row);
      if (!currentSelection(request)) return;
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      if (!currentSelection(request)) return;
      atlasState = { ...atlasState, status: "error",
        error: error?.code ?? error?.message ?? "ABI query failed" };
    }
    renderAtlasDomain();
  });
}

async function ensureAtlasOverview() {
  const requestEpoch = contextEpoch;
  if (state.view !== "atlas" || atlasState.status !== "idle") return;
  atlasState = { ...atlasState, status: "loading", error: null };
  renderAtlasDomain();
  try {
    const overview = await loadAtlasOverview(window.bamfMissionControl, state.context);
    if (requestEpoch !== contextEpoch) return;
    atlasState = { ...atlasState, status: "ready", overview };
  } catch (error) {
    if (requestEpoch !== contextEpoch) return;
    atlasState = { ...atlasState, status: "error",
      error: error?.code ?? error?.message ?? "Semantic Atlas unavailable" };
  }
  if (state.view === "atlas") renderAtlasDomain();
}

function renderCurrentView() {
  const domain = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const summary = document.querySelector("#view-summary");
  if (state.view === "school") {
    domain.hidden = false;
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
      onState(state);
      renderInspector();
      setHash();
    }, state.selected?.kind === "capability" ? state.selected.id : null);
    return;
  }
  if (state.view === "atlas") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Source-authoritative semantic identity and generation-scoped ABI state, with learned similarity isolated behind a separate lens.";
    renderAtlasDomain();
    return;
  }
  if (state.view === "model") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
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
      onState(state);
      renderInspector();
      setHash();
    });
    return;
  }
  if (state.view === "learning") {
    domain.hidden = false;
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
      onState(state);
      renderInspector();
      setHash();
    }, state.selected?.kind === "episode" ? state.selected.id : null);
    return;
  }
  domain.hidden = true;
  fixture.hidden = false;
  catalog.hidden = false;
  domain.innerHTML = "";
  summary.textContent = "Shell foundation ready for provider-neutral BAMF views.";
  catalog.innerHTML = renderComponentCatalog();
}

return { render(nextState) {
  const nextKey = JSON.stringify([nextState.context.runId, nextState.context.generation,
    nextState.context.mode, nextState.context.generationManifest, nextState.context.semanticRelease]);
  if (nextKey !== contextKey) {
    contextKey = nextKey;
    contextEpoch += 1;
    atlasState = initialAtlasState();
  }
  state = nextState;
  renderCurrentView();
  if (state.view === "atlas") void ensureAtlasOverview();
} };
}
