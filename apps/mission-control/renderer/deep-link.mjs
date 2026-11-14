export function parseDeepLink(hash = "") {
  const value = hash.replace(/^#\/?/, "");
  const [path, query = ""] = value.split("?");
  const [, view = "mission-control"] = path.split("/");
  const params = new URLSearchParams(query);
  const kind = params.get("kind");
  const id = params.get("id");
  const originView = params.get("originView");
  const originKind = params.get("originKind");
  const originId = params.get("originId");
  const route = {
    view,
    selected: kind && id ? { kind, id } : null,
  };
  if (originView) {
    route.evidenceOrigin = {
      view: originView,
      selected: originKind && originId ? { kind: originKind, id: originId } : null,
      inspectorOpen: params.get("originInspector") === "1",
    };
  }
  return route;
}

export function buildDeepLink(state) {
  const params = new URLSearchParams();
  if (state.selected?.kind) params.set("kind", state.selected.kind);
  if (state.selected?.id) params.set("id", state.selected.id);
  if (state.view === "evidence" && state.evidenceOrigin?.view) {
    params.set("originView", state.evidenceOrigin.view);
    if (state.evidenceOrigin.selected?.kind) {
      params.set("originKind", state.evidenceOrigin.selected.kind);
    }
    if (state.evidenceOrigin.selected?.id) {
      params.set("originId", state.evidenceOrigin.selected.id);
    }
    if (state.evidenceOrigin.inspectorOpen) params.set("originInspector", "1");
  }
  const query = params.toString();
  return `#/view/${state.view}${query ? `?${query}` : ""}`;
}

export function routeFromState(state) {
  return parseDeepLink(buildDeepLink(state));
}
