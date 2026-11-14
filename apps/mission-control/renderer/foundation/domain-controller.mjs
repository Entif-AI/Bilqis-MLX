import {
  ensureAtlasOverview,
  invalidateAtlasRequests,
  renderAtlasDomain,
} from "../atlas/atlas-controller.mjs";

export function activateDomainViews({
  state, getState, defense, api, homeController, resourceController, onInspect,
}) {
  if (state?.view === "atlas") {
    const context = state.context;
    const isActive = () => getState()?.view === "atlas" && getState().context === context;
    renderAtlasDomain(api, context, isActive);
    void ensureAtlasOverview(api, context, isActive);
  }
  if (state?.view !== "atlas") invalidateAtlasRequests();
  if (state?.view === "mission-control") {
    void homeController.activate(state.context, {
      host: document.querySelector("#domain-view"),
      onInspect,
      defense,
    });
  } else {
    void homeController.deactivate();
  }
  if (state?.view === "resources") {
    void resourceController?.activate(state.context, {
      target: document.querySelector("#domain-view"),
      onInspect,
      defense,
    });
  } else {
    void resourceController?.deactivate();
  }
}
