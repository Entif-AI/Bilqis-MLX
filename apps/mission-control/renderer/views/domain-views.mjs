import { renderComponentCatalog } from "../component-catalog.mjs";
import { renderSchoolView } from "../school-view.mjs";
import { renderNeuralView } from "../neural-view.mjs";
import { renderEpisodesView } from "../episode-view.mjs";
import {
  loadAbiRow,
  loadAtlasOverview,
  loadSemanticIdentity,
  renderAtlasMarkup,
} from "../semantic-atlas.mjs";

export function createAtlasRequestGuard(getState) {
  let epoch = 0;
  return {
    begin() {
      const token = ++epoch;
      const context = getState().context;
      return () => token === epoch && getState().view === "atlas" && getState().context === context;
    },
    invalidate() { epoch += 1; },
  };
}

const initialAtlasState = () => ({
  status: "idle",
  error: null,
  overview: null,
  selection: null,
  lens: "canonical",
  selectedBank: null,
});

export function createDomainViews({ getState, onInspect, getModelSection }) {
  let atlasState = initialAtlasState();
  let lastContext = null;
  const guard = createAtlasRequestGuard(getState);
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
      const isCurrent = guard.begin();
      atlasState = { ...atlasState, status: "loading", error: null };
      renderAtlasDomain();
      try {
        const selection = await loadSemanticIdentity(
          window.bamfMissionControl, state.context, semanticId,
        );
        if (!isCurrent()) return;
        atlasState = { ...atlasState, status: "ready", selection };
      } catch (error) {
        if (!isCurrent()) return;
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
      const isCurrent = guard.begin();
      atlasState = { ...atlasState, status: "loading", error: null, selectedBank: bank };
      renderAtlasDomain();
      try {
        const selection = await loadAbiRow(window.bamfMissionControl, state.context, bank, row);
        if (!isCurrent()) return;
        atlasState = { ...atlasState, status: "ready", selection };
      } catch (error) {
        if (!isCurrent()) return;
        atlasState = { ...atlasState, status: "error",
          error: error?.code ?? error?.message ?? "ABI query failed" };
      }
      renderAtlasDomain();
    });
  }

  async function ensureAtlasOverview() {
    const state = getState();
    if (state.view !== "atlas" || atlasState.status !== "idle") return;
    const isCurrent = guard.begin();
    atlasState = { ...atlasState, status: "loading", error: null };
    renderAtlasDomain();
    try {
      const overview = await loadAtlasOverview(window.bamfMissionControl, state.context);
      if (!isCurrent()) return;
      atlasState = { ...atlasState, status: "ready", overview };
    } catch (error) {
      if (!isCurrent()) return;
      atlasState = { ...atlasState, status: "error",
        error: error?.code ?? error?.message ?? "Semantic Atlas unavailable" };
    }
    if (state.view === "atlas") renderAtlasDomain();
  }

  function renderCurrentView() {
    const state = getState();
    const modelSection = getModelSection();
    if (lastContext !== state.context) {
      guard.invalidate(); atlasState = initialAtlasState(); lastContext = state.context;
    }
    if (state.view !== "atlas") {
      guard.invalidate();
      if (atlasState.status === "loading") atlasState = { ...atlasState, status: "idle" };
    }
    const domain = document.querySelector("#domain-view");
    const fixture = document.querySelector(".fixture-card");
    const catalog = document.querySelector("#visual-catalog");
    const summary = document.querySelector("#view-summary");
    document.querySelector("#model-nav").hidden = state.view !== "model";
    document.querySelectorAll("[data-model-section]").forEach(button => {
      button.setAttribute("aria-pressed", String(button.dataset.modelSection === modelSection));
    });
    domain.hidden = state.view === "model" && modelSection === "frames";
    document.querySelector("#domain-context-note").hidden = !["school", "learning", "model"].includes(state.view) || domain.hidden;
    if (state.view === "school") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
      renderSchoolView(domain, (id, row) => {
        onInspect({
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
      domain.hidden = modelSection === "frames";
      fixture.hidden = true;
      catalog.hidden = true;
      if (modelSection === "frames") {
        summary.textContent = "Frame Compiler Explorer · inspect exact packing receipts and causal visibility.";
        return;
      }
      summary.textContent = "Topology, attention health, depth routing and local refinement as measured telemetry only.";
      renderNeuralView(domain, (id, kind) => {
        onInspect({
          kind: "neural",
          id,
          details: {
            "Diagnostic class": kind,
            "Interpretation boundary": "Measured routing/runtime telemetry only",
          },
        });
      });
      return;
    }
    if (state.view === "learning") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Candidate proposal, work, assessment, retention and finalization reconstructed from bounded evidence.";
      renderEpisodesView(domain, (id, evidenceType) => {
        onInspect({
          kind: "evidence",
          id,
          details: {
            "Evidence type": evidenceType,
            "Episode replay": "Read-only durable evidence reference",
          },
        });
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


  return { render: renderCurrentView, ensureAtlasOverview };
}
