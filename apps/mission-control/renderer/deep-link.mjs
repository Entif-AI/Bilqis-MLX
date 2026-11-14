export function parseDeepLink(hash = "") {
  const value = hash.replace(/^#\/?/, "");
  const [path, query = ""] = value.split("?");
  const [, view = "mission-control"] = path.split("/");
  const params = new URLSearchParams(query);
  const kind = params.get("kind");
  const id = params.get("id");
  const generation = Number(params.get("generation"));
  const context = params.has("run") && params.has("generation") &&
    Number.isSafeInteger(generation) && generation >= 0 && ["LIVE", "HISTORICAL"].includes(params.get("mode"))
    ? {
      runId: params.get("run"),
      generation,
      mode: params.get("mode"),
      fixture: params.get("fixture") === "true",
      historicalPinned: params.get("mode") === "HISTORICAL",
    } : null;
  return {
    ...(context ? { context } : {}),
    view,
    selected: kind && id ? { kind, id } : null,
  };
}

export function buildDeepLink(state) {
  const params = new URLSearchParams();
  if (state.selected?.kind) params.set("kind", state.selected.kind);
  if (state.selected?.id) params.set("id", state.selected.id);
  if (state.context) {
    params.set("run", state.context.runId);
    params.set("generation", state.context.generation);
    params.set("mode", state.context.mode);
    if (state.context.fixture) params.set("fixture", "true");
  }
  const query = params.toString();
  return `#/view/${state.view}${query ? `?${query}` : ""}`;
}
