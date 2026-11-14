import { renderComponentCatalog } from "../component-catalog.mjs";
import { renderSchoolView } from "../school/school-view.mjs";
import { renderNeuralView } from "../neural/neural-view.mjs";
import { renderEpisodesView } from "../episodes/episode-view.mjs";
import { renderMemoryView } from "../memory/memory-view.mjs";
import { renderTeacherView } from "../teacher/teacher-view.mjs";
import { renderCorrectionsView } from "../corrections/corrections-view.mjs";
import { renderSalienceView } from "../salience/salience-view.mjs";
import { renderLineageView } from "../lineage/lineage-view.mjs";
import { renderEvidenceView } from "../evidence/evidence-view.mjs";

export function renderCurrentView(
  state, defense, onInspect, api, onEvidenceSelect, onEvidenceReturn,
) {
  const domain = document.querySelector("#domain-view");
  const fixture = document.querySelector(".fixture-card");
  const catalog = document.querySelector("#visual-catalog");
  const summary = document.querySelector("#view-summary");
  document.querySelector("#shell").dataset.view = state?.view ?? "mission-control";
  if (!state) {
    fixture.hidden = true;
    catalog.hidden = false;
    domain.hidden = true;
    domain.innerHTML = "";
    summary.textContent = defense.description;
    catalog.innerHTML = renderComponentCatalog();
    return;
  }
  if (state.view === "school") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Exact capability comparison and declared prerequisite topology. Grade labels organize only.";
    renderSchoolView(domain, (id, row) => onInspect({
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
  if (state.view === "mission-control") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Outcome-first learner health, current work, learning pulse and actionable attention.";
    return;
  }
  if (state.view === "atlas") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Source-authoritative semantic identity and generation-scoped ABI state, with learned similarity isolated behind a separate lens.";
    return;
  }
  if (state.view === "capability") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Measured chronology, source support, and literal evidence. No inferred causes.";
    return;
  }
  if (state.view === "model") {
    domain.hidden = state.modelSection === "frames";
    if (state.modelSection === "frames") {
      fixture.hidden = true; catalog.hidden = true;
      summary.textContent = "Frame Compiler Explorer · inspect exact packing receipts and causal visibility.";
      return;
    }
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Topology, attention health, depth routing and local refinement as measured telemetry only.";
    renderNeuralView(domain, (id, kind) => onInspect({
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
    summary.textContent = "Durable candidate transaction replay with explicit retention, rollback and evidence boundaries.";
    renderEpisodesView(domain, (id, kind) => onInspect({
      kind: "evidence",
      id,
      details: { "Evidence type": kind, "Interpretation boundary": "Durable episode evidence only" },
    }), state.selected?.kind === "episode" ? state.selected.id : null);
    return;
  }
  if (state.view === "memory") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Retained Engram allocation, retrieval telemetry, correction state, and generation deltas without promoting memory hits into semantic or capability authority.";
    renderMemoryView(domain, (id, slot) => onInspect({
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
  if (state.view === "teacher") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Teacher strategy population, measured outcomes, cost and fidelity observations without unsupported ranking.";
    renderTeacherView(domain, (id) => onInspect({
      kind: "strategy",
      id,
      details: {
        "Comparison posture": "Descriptive evidence only",
        "Policy mutation": "None",
      },
    }));
    return;
  }
  if (state.view === "corrections") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Evidenced correction blast radius, append-only correction history, and receipt-backed requalification state without implying perfect neural unlearning.";
    renderCorrectionsView(domain, (id, node) => onInspect({
      kind: "correction",
      id,
      details: {
        "Artifact class": node.kind,
        "Impact state": node.state,
        "Evidence refs": node.evidenceRefs.length ? node.evidenceRefs : ["UNTRACKED / UNKNOWN"],
        "Interpretation boundary": "Known exposure and requalification evidence only",
      },
    }));
    return;
  }
  if (state.view === "salience") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Independent Impact, Exigency and Osmotic Novelty evidence with reversible aggregation and admitted routing rationale.";
    renderSalienceView(domain, (id, details) => onInspect({
      kind: "salience-observation",
      id,
      details,
    }));
    return;
  }
  if (state.view === "lineage") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Immutable accepted-generation lineage, exact manifest provenance, and literal structured generation differences without winner synthesis.";
    renderLineageView(domain, (id, node) => onInspect({
      kind: "generation",
      id,
      details: {
        Generation: node.generation,
        "Manifest SHA-256": node.manifestSha256,
        "Parent manifest": node.parentManifestSha256 ?? "GENESIS",
        Transition: node.transitionClass,
        "Checkpoint SHA-256": node.checkpointSha256,
      },
    }), ["generation", "checkpoint"].includes(state.selected?.kind) ? state.selected.id : null);
    return;
  }
  if (state.view === "evidence") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Exact Mission Control records, provenance links, bounded pagination and literal raw payloads.";
    renderEvidenceView(
      domain, api, state.context, state.selected, onEvidenceSelect,
      state.evidenceOrigin ? onEvidenceReturn : null,
    );
    return;
  }
  if (state.view === "resources") {
    domain.hidden = false;
    fixture.hidden = true;
    catalog.hidden = true;
    summary.textContent = "Measured resource budgets, decomposed where instrumented, with exact historical comparison and spike correlation.";
    return;
  }
  fixture.hidden = false;
  catalog.hidden = false;
  domain.hidden = true;
  domain.innerHTML = "";
  summary.textContent = defense.historical
    ? "Inspection-only evidence retained while the live command context is unavailable."
    : "Shell foundation ready for provider-neutral BAMF views.";
  catalog.innerHTML = renderComponentCatalog();
}
