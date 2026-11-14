import { renderSchoolView } from "./school-view.mjs";
import {
  invalidateCurriculumAtlasRequests,
  renderCurriculumAtlasView,
} from "./curriculum-atlas-view.mjs";

let schoolMode = "matrix";
let schoolSelectedId = null;

export function invalidateSchoolDomainRequests() {
  invalidateCurriculumAtlasRequests();
}

function subnav(container, mode, onModeChange) {
  const nav = document.createElement("nav");
  nav.className = "school-subnav";
  nav.setAttribute("aria-label", "School views");
  nav.innerHTML =
    '<button type="button" data-school-mode="matrix" data-focus-key="school-mode:matrix" aria-current="' +
      (mode === "matrix" ? "page" : "false") + '">Capability matrix</button>' +
    '<button type="button" data-school-mode="atlas" data-focus-key="school-mode:atlas" aria-current="' +
      (mode === "atlas" ? "page" : "false") + '">Curriculum Semantic Atlas</button>';
  nav.querySelectorAll("[data-school-mode]").forEach((button) => {
    button.addEventListener("click", () => onModeChange(button.dataset.schoolMode, null, true));
  });
  container.prepend(nav);
}

export function activateSchoolDomain({ state, api, onInspect, isActive = () => true }) {
  if (state?.view !== "school") return;
  const container = document.querySelector("#domain-view");
  const summary = document.querySelector("#view-summary");
  if (state.selected?.kind === "capability" && state.selected.id) {
    schoolSelectedId = state.selected.id;
  }

  function renderMode(mode, requestedSelectedId = null, restoreModeFocus = false) {
    schoolMode = mode === "atlas" ? "atlas" : "matrix";
    if (requestedSelectedId) schoolSelectedId = requestedSelectedId;
    if (schoolMode === "atlas") {
      summary.textContent =
        "Temporal curriculum dependency atlas. Grade is visual only; edges come from declared School prerequisites.";
      renderCurriculumAtlasView(container, {
        context: state.context,
        api,
        selectedId: schoolSelectedId,
        isActive,
        onInspect: (id, node, binding = null) => {
          schoolSelectedId = id;
          const concept = binding?.state === "PRESENT" ? binding.concepts[0] : null;
          const preferred = concept?.labels?.find((label) => label.role === "prefLabel") ??
            concept?.labels?.[0] ?? null;
          onInspect({
            kind: "capability",
            id,
            details: {
              "Semantic display identity": concept
                ? concept.semantic_id + " · " + (preferred?.value ?? node.label) + " · SOURCE CANONICAL"
                : node.semanticId + " · FIXTURE DISPLAY ONLY",
              Grade: node.grade,
              "First introduced": node.firstIntroducedGrade,
              "Lifecycle / qualification": node.lifecycleState + " / " + node.qualificationState,
              "NOW / TOP / debt": node.now + "/" + node.total + " · " +
                node.top + "/" + node.total + " · " + node.debt,
              Prerequisites: node.prerequisites.length ? node.prerequisites : ["none"],
              "Source state": node.sourceState,
              "Implementation state": node.implementationState,
              "Source refs": node.sourceRefs,
            },
          });
        },
        onModeChange: renderMode,
      });
      if (restoreModeFocus) container.querySelector('[data-school-mode="atlas"]')?.focus();
      return;
    }
    invalidateCurriculumAtlasRequests();
    summary.textContent =
      "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
    renderSchoolView(container, (id, row) => {
      schoolSelectedId = id;
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
    }, schoolSelectedId);
    subnav(container, schoolMode, renderMode);
  }

  renderMode(schoolMode);
}
