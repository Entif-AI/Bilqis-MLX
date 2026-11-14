import { renderComponentCatalog } from "./component-catalog.mjs";
import {
  loadAbiRow,
  loadAtlasOverview,
  loadSemanticIdentity,
  renderAtlasMarkup,
} from "./domains/semantic-atlas.mjs";
import { renderSchoolView } from "./domains/school-view.mjs";
import { renderNeuralView } from "./domains/neural-view.mjs";
import { renderEpisodesView } from "./domains/episode-view.mjs";
import { renderTeacherView } from "./domains/teacher-view.mjs";

export function createViewController({ bridge, getState, inspectSelection }) {
  let atlasState = {
    status: "idle",
    error: null,
    overview: null,
    selection: null,
    lens: "canonical",
    selectedBank: null,
  };

  function renderAtlasDomain() {
    const state = getState();
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
      try {
        const selection = await loadSemanticIdentity(bridge, getState().context, semanticId);
        atlasState = { ...atlasState, status: "ready", selection };
      } catch (error) {
        atlasState = {
          ...atlasState,
          status: "error",
          error: error?.code ?? error?.message ?? "Semantic query failed",
        };
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
        const selection = await loadAbiRow(bridge, getState().context, bank, row);
        atlasState = { ...atlasState, status: "ready", selection };
      } catch (error) {
        atlasState = {
          ...atlasState,
          status: "error",
          error: error?.code ?? error?.message ?? "ABI query failed",
        };
      }
      renderAtlasDomain();
    });
  }

  async function ensureAtlasOverview() {
    if (getState().view !== "atlas" || atlasState.status !== "idle") return;
    atlasState = { ...atlasState, status: "loading", error: null };
    renderAtlasDomain();
    try {
      const overview = await loadAtlasOverview(bridge, getState().context);
      atlasState = { ...atlasState, status: "ready", overview };
    } catch (error) {
      atlasState = {
        ...atlasState,
        status: "error",
        error: error?.code ?? error?.message ?? "Semantic Atlas unavailable",
      };
    }
    if (getState().view === "atlas") renderAtlasDomain();
  }

  function renderCurrentView() {
    const state = getState();
    const domain = document.querySelector("#domain-view");
    const fixture = document.querySelector(".fixture-card");
    const catalog = document.querySelector("#visual-catalog");
    const summary = document.querySelector("#view-summary");
    if (state.view === "school") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
      renderSchoolView(domain, (id, row) => inspectSelection({
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
      renderNeuralView(domain, (id, kind) => inspectSelection({
        kind: "neural",
        id,
        details: {
          "Diagnostic class": kind,
          "Interpretation boundary": "Measured routing/runtime telemetry only",
        },
      }));
      return;
    }
    if (state.view === "learning") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Candidate proposal, work, assessment, retention and finalization reconstructed from bounded evidence.";
      renderEpisodesView(domain, (id, evidenceType) => inspectSelection({
        kind: "evidence",
        id,
        details: {
          "Evidence type": evidenceType,
          "Episode replay": "Read-only durable evidence reference",
        },
      }), state.selected?.kind === "episode" ? state.selected.id : null);
      return;
    }
    if (state.view === "teacher") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Teacher strategy population, measured outcomes, cost and fidelity observations without unsupported ranking.";
      renderTeacherView(domain, (id) => inspectSelection({
        kind: "strategy",
        id,
        details: {
          "Comparison posture": "Descriptive evidence only",
          "Policy mutation": "None",
        },
      }));
      return;
    }
    domain.hidden = true;
    fixture.hidden = false;
    catalog.hidden = false;
    domain.innerHTML = "";
    summary.textContent = "Shell foundation ready for provider-neutral BAMF views.";
    catalog.innerHTML = renderComponentCatalog();
  }

  return Object.freeze({ renderCurrentView, ensureAtlasOverview });
}
