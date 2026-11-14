import {
  ensureAtlasOverview,
  renderAtlasDomain,
} from "../atlas/atlas-controller.mjs";

export function activateDomainViews({ state, defense, api, homeController, resourceController, onInspect }) {
  if (state?.view === "atlas") {
    renderAtlasDomain(api, state.context);
    void ensureAtlasOverview(api, state.context, () => state?.view === "atlas");
  }
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
    void resourceController.activate(state.context, {
      target: document.querySelector("#domain-view"),
      onInspect,
      defense,
    });
  } else {
    void resourceController.deactivate();
  }
}
