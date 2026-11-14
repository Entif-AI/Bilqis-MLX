import { renderComponentCatalog } from "../component-catalog.mjs";
import {
  loadAbiRow,
  loadAtlasOverview,
  loadSemanticIdentity,
  renderAtlasMarkup,
} from "./semantic/semantic-atlas.mjs";
import { renderSchoolView } from "./school/school-view.mjs";
import { renderNeuralView } from "./neural/neural-view.mjs";
import { renderEpisodesView } from "./episodes/episode-view.mjs";
import { renderMemoryView } from "./memory/memory-view.mjs";

export function createDomainController({ api, getState, onInspect, onRouteChange }) {
  let atlas = {
    status: "idle",
    error: null,
    overview: null,
    selection: null,
    lens: "canonical",
    selectedBank: null,
  };

  function inspect(selected) {
    onInspect(selected);
    onRouteChange();
  }

  function renderAtlas(host) {
    const state = getState();
    host.innerHTML = renderAtlasMarkup({ ...atlas, context: state.context });
    host.querySelectorAll("[data-atlas-lens]").forEach((button) => {
      button.addEventListener("click", () => {
        atlas = { ...atlas, lens: button.dataset.atlasLens };
        renderAtlas(host);
      });
    });
    host.querySelectorAll("[data-atlas-bank]").forEach((button) => {
      button.addEventListener("click", () => {
        atlas = { ...atlas, selectedBank: Number(button.dataset.atlasBank) };
        renderAtlas(host);
      });
    });
    host.querySelector("#atlas-search-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const semanticId = new FormData(event.currentTarget).get("semanticId")?.toString().trim();
      if (!semanticId) return;
      atlas = { ...atlas, status: "loading", error: null };
      renderAtlas(host);
      try {
        const selection = await loadSemanticIdentity(api, getState().context, semanticId);
        atlas = { ...atlas, status: "ready", selection };
      } catch (error) {
        atlas = { ...atlas, status: "error",
          error: error?.code ?? error?.message ?? "Semantic query failed" };
      }
      if (getState().view === "atlas") renderAtlas(host);
    });
    host.querySelector("#atlas-abi-form")?.addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      const bank = Number(form.get("bank"));
      const row = Number(form.get("row"));
      if (!Number.isSafeInteger(bank) || bank < 0 || !Number.isSafeInteger(row) || row < 0) return;
      atlas = { ...atlas, status: "loading", error: null, selectedBank: bank };
      renderAtlas(host);
      try {
        const selection = await loadAbiRow(api, getState().context, bank, row);
        atlas = { ...atlas, status: "ready", selection };
      } catch (error) {
        atlas = { ...atlas, status: "error",
          error: error?.code ?? error?.message ?? "ABI query failed" };
      }
      if (getState().view === "atlas") renderAtlas(host);
    });
  }

  async function ensureAtlas(host) {
    if (getState().view !== "atlas" || atlas.status !== "idle") return;
    atlas = { ...atlas, status: "loading", error: null };
    renderAtlas(host);
    try {
      const overview = await loadAtlasOverview(api, getState().context);
      atlas = { ...atlas, status: "ready", overview };
    } catch (error) {
      atlas = { ...atlas, status: "error",
        error: error?.code ?? error?.message ?? "Semantic Atlas unavailable" };
    }
    if (getState().view === "atlas") renderAtlas(host);
  }

  function render({ domain, fixture, catalog, summary }) {
    const state = getState();
    if (state.view === "school") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
      renderSchoolView(domain, (id, row) => inspect({
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
      renderAtlas(domain);
      void ensureAtlas(domain);
      return;
    }
    if (state.view === "model") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Topology, attention health, depth routing and local refinement as measured telemetry only.";
      renderNeuralView(domain, (id, kind) => inspect({
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
      renderEpisodesView(domain, (id, evidenceType) => inspect({
        kind: "evidence",
        id,
        details: {
          "Evidence type": evidenceType,
          "Episode replay": "Read-only durable evidence reference",
        },
      }), state.selected?.kind === "episode" ? state.selected.id : null);
      return;
    }
    if (state.view === "memory") {
      domain.hidden = false;
      fixture.hidden = true;
      catalog.hidden = true;
      summary.textContent = "Retained Engram allocation, retrieval telemetry, correction state, and generation deltas without promoting memory hits into semantic or capability authority.";
      renderMemoryView(domain, (id, slot) => inspect({
        kind: "memory",
        id,
        details: {
          "Slot address": `motif.page.${slot.pageIndex}[${slot.rowIndex}]`,
          "Creation generation": slot.createdGeneration,
          "Source eligibility": slot.sourceEligibility,
          "Correction state": slot.correctionState,
          "Parameter bank": slot.parameterBank,
          "Related capabilities": slot.capabilities,
          "Related episodes": slot.episodes,
        },
      }), state.selected?.kind === "memory" ? state.selected.id : null);
      return;
    }
    domain.hidden = true;
    fixture.hidden = false;
    catalog.hidden = false;
    domain.innerHTML = "";
    summary.textContent = "Shell foundation ready for provider-neutral BAMF views.";
    catalog.innerHTML = renderComponentCatalog();
  }

  return Object.freeze({ render });
}
