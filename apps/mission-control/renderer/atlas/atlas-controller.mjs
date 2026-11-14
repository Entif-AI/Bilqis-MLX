import {
  loadAbiRow,
  loadAtlasOverview,
  loadSemanticIdentity,
  renderAtlasMarkup,
} from "./semantic-atlas.mjs";

let atlasState = {
  status: "idle",
  error: null,
  overview: null,
  selection: null,
  lens: "canonical",
  selectedBank: null,
};
let contextIdentity = null;

function identityFor(context) {
  if (!context) return "none";
  return [context.runId, context.generation, context.mode, context.semanticRelease].join(":");
}

function bindContext(context) {
  const next = identityFor(context);
  if (contextIdentity === next) return;
  contextIdentity = next;
  atlasState = {
    status: "idle",
    error: null,
    overview: null,
    selection: null,
    lens: "canonical",
    selectedBank: null,
  };
}

export function renderAtlasDomain(api, context) {
  bindContext(context);
  const host = document.querySelector("#domain-view");
  host.hidden = false;
  host.innerHTML = renderAtlasMarkup({ ...atlasState, context });
  host.querySelectorAll("[data-atlas-lens]").forEach((button) => {
    button.addEventListener("click", () => {
      atlasState = { ...atlasState, lens: button.dataset.atlasLens };
      renderAtlasDomain(api, context);
    });
  });
  host.querySelectorAll("[data-atlas-bank]").forEach((button) => {
    button.addEventListener("click", () => {
      atlasState = { ...atlasState, selectedBank: Number(button.dataset.atlasBank) };
      renderAtlasDomain(api, context);
    });
  });
  host.querySelector("#atlas-search-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const semanticId = new FormData(event.currentTarget).get("semanticId")?.toString().trim();
    if (!semanticId) return;
    atlasState = { ...atlasState, status: "loading", error: null };
    renderAtlasDomain(api, context);
    try {
      const selection = await loadSemanticIdentity(api, context, semanticId);
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      atlasState = {
        ...atlasState,
        status: "error",
        error: error?.code ?? error?.message ?? "Semantic query failed",
      };
    }
    renderAtlasDomain(api, context);
  });
  host.querySelector("#atlas-abi-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const bank = Number(form.get("bank"));
    const row = Number(form.get("row"));
    if (!Number.isSafeInteger(bank) || bank < 0 || !Number.isSafeInteger(row) || row < 0) return;
    atlasState = { ...atlasState, status: "loading", error: null, selectedBank: bank };
    renderAtlasDomain(api, context);
    try {
      const selection = await loadAbiRow(api, context, bank, row);
      atlasState = { ...atlasState, status: "ready", selection };
    } catch (error) {
      atlasState = {
        ...atlasState,
        status: "error",
        error: error?.code ?? error?.message ?? "ABI query failed",
      };
    }
    renderAtlasDomain(api, context);
  });
}

export async function ensureAtlasOverview(api, context, isActive = () => true) {
  bindContext(context);
  if (atlasState.status !== "idle") return;
  atlasState = { ...atlasState, status: "loading", error: null };
  renderAtlasDomain(api, context);
  try {
    const overview = await loadAtlasOverview(api, context);
    atlasState = { ...atlasState, status: "ready", overview };
  } catch (error) {
    atlasState = {
      ...atlasState,
      status: "error",
      error: error?.code ?? error?.message ?? "Semantic Atlas unavailable",
    };
  }
  if (isActive()) renderAtlasDomain(api, context);
}
