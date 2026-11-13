export const DESTINATIONS = Object.freeze([
  ["mission-control", "Mission Control"],
  ["school", "School"],
  ["learning", "Learning"],
  ["atlas", "Atlas"],
  ["model", "Model"],
  ["memory", "Memory"],
  ["teacher", "Teacher"],
  ["corrections", "Corrections"],
  ["lineage", "Lineage"],
  ["resources", "Resources"],
  ["evidence", "Evidence"],
  ["operate", "Operate"],
]);

export const INSPECTOR_OWNERS = Object.freeze({
  capability: "school",
  episode: "learning",
  semantic: "atlas",
  memory: "memory",
  checkpoint: "lineage",
  evidence: "evidence",
  correction: "corrections",
  warning: "resources",
});

export function normalizeContext(raw = {}) {
  return Object.freeze({
    runId: raw.runId ?? "UNKNOWN_RUN",
    mode: raw.mode === "HISTORICAL" ? "HISTORICAL" : "LIVE",
    generation: raw.generation ?? "UNKNOWN",
    checkpoint: raw.checkpoint ?? "UNKNOWN",
    topologyId: raw.topologyId ?? "UNKNOWN",
    factoryRelease: raw.factoryRelease ?? "UNKNOWN",
    semanticRelease: raw.semanticRelease ?? "UNKNOWN",
    optimizerStep: raw.optimizerStep ?? "UNKNOWN",
    admissionLease: raw.admissionLease ?? "UNKNOWN",
    correctionFrontier: raw.correctionFrontier ?? "UNKNOWN",
    freshness: raw.freshness ?? "UNKNOWN",
    resourceHealth: raw.resourceHealth ?? "UNKNOWN",
  });
}

export function createShellState(context, route = {}) {
  const destinations = new Set(DESTINATIONS.map(([id]) => id));
  const view = destinations.has(route.view) ? route.view : "mission-control";
  return {
    context: normalizeContext(context),
    view,
    selected: route.selected ?? null,
    inspectorOpen: Boolean(route.selected),
  };
}

export function navigate(state, view, selected = null) {
  const destinations = new Set(DESTINATIONS.map(([id]) => id));
  if (!destinations.has(view)) return state;
  return {
    ...state,
    view,
    selected,
    inspectorOpen: selected !== null,
  };
}

export function inspect(state, selected) {
  return { ...state, selected, inspectorOpen: Boolean(selected) };
}

export function openSelectionOwner(state) {
  if (!state.selected) return state;
  const owner = INSPECTOR_OWNERS[state.selected.kind];
  return owner ? navigate(state, owner, state.selected) : state;
}

export function withContext(state, nextContext) {
  return { ...state, context: normalizeContext(nextContext) };
}

export function shellPosture(context) {
  if (context.mode === "HISTORICAL") return "historical";
  if (context.freshness === "STALE" || context.freshness === "DISCONNECTED") return "stale";
  return "live";
}
