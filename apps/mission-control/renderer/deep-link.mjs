export function parseDeepLink(hash = "") {
  const value = hash.replace(/^#\/?/, "");
  const [path, query = ""] = value.split("?");
  const [, view = "mission-control"] = path.split("/");
  const params = new URLSearchParams(query);
  const kind = params.get("kind");
  const id = params.get("id");
  return {
    view,
    selected: kind && id ? { kind, id } : null,
  };
}

export function buildDeepLink(state) {
  const params = new URLSearchParams();
  if (state.selected?.kind) params.set("kind", state.selected.kind);
  if (state.selected?.id) params.set("id", state.selected.id);
  const query = params.toString();
  return `#/view/${state.view}${query ? `?${query}` : ""}`;
}
