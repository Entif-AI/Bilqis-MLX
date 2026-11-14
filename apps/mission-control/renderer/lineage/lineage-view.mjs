import { LINEAGE_FIXTURE, LINEAGE_FIXTURE_CONTRACT } from "./lineage-fixture.mjs";
import {
  compareGenerations,
  currentLineageNode,
  historicalGenerationQuery,
  lineageDeepLink,
  lineageEdges,
  lineageNodes,
  manifestFieldRows,
  nodeByIdentity,
} from "./lineage-model.mjs";

const ui = {
  selected: currentLineageNode().manifestSha256,
  compareBefore: LINEAGE_FIXTURE.nodes[1].manifestSha256,
  compareAfter: LINEAGE_FIXTURE.nodes.at(-1).manifestSha256,
};

function compact(value) {
  return typeof value === "string" && /^[0-9a-f]{64}$/.test(value)
    ? value.slice(0, 8) + "…" + value.slice(-8)
    : value;
}

function stateBadge(value) {
  return `<span class="lineage-state" data-lineage-state="${value.toLowerCase().replaceAll("_", "-")}">${value}</span>`;
}

function graphMarkup(selected) {
  const nodes = lineageNodes().map((node) => `<button type="button"
    class="lineage-node" data-lineage-node="${node.manifestSha256}"
    data-transition="${node.transitionClass.toLowerCase().replaceAll("_", "-")}"
    aria-pressed="${selected.manifestSha256 === node.manifestSha256}">
      <span>Generation ${node.generation}</span>
      <strong>${node.transitionLabel}</strong>
      <small>${compact(node.manifestSha256)}</small>
    </button>`).join("");
  const edges = lineageEdges().map((edge) => `<li data-transition="${edge.transitionClass.toLowerCase().replaceAll("_", "-")}">
    <strong>G${edge.parentGeneration} → G${edge.childGeneration}</strong>
    <span>${edge.transitionClass}</span><small>${edge.label}</small>
  </li>`).join("");
  return `<section class="lineage-panel">
    <header><div><span class="eyebrow">Accepted generation DAG</span><h3>Manifest lineage</h3></div>${stateBadge("READ_ONLY")}</header>
    <div class="lineage-graph" aria-label="Generation lineage graph">${nodes}</div>
    <ol class="lineage-edges" aria-label="Exact parent child transitions">${edges}</ol>
    <table class="lineage-table"><thead><tr><th>Generation</th><th>Manifest</th><th>Parent</th><th>Transition</th></tr></thead>
      <tbody>${lineageNodes().map((node) => `<tr><td>${node.generation}</td><td>${compact(node.manifestSha256)}</td><td>${node.parentManifestSha256 ? compact(node.parentManifestSha256) : "GENESIS"}</td><td>${node.transitionClass}</td></tr>`).join("")}</tbody>
    </table>
  </section>`;
}

function inspectorMarkup(node) {
  const query = historicalGenerationQuery(node);
  return `<section class="lineage-panel">
    <header><div><span class="eyebrow">Exact immutable node</span><h3>Generation ${node.generation}</h3></div>${stateBadge(node.transitionClass)}</header>
    <p class="lineage-doctrine">Manifest <strong>${node.manifestSha256}</strong>. Parent <strong>${node.parentManifestSha256 ?? "GENESIS"}</strong>.</p>
    <dl class="lineage-manifest">${manifestFieldRows(node).map((field) => `
      <div><dt>${field.label}</dt><dd>${field.value}</dd><small>Source: ${field.sourceRef}</small></div>`).join("")}</dl>
    <div class="lineage-exact-route">
      <a href="${lineageDeepLink(node)}">Deep link this exact manifest</a>
      <code>CP03 ${query.mode} generation=${query.generation} record_id=${query.record_id}</code>
    </div>
  </section>`;
}

function compareMarkup() {
  const comparison = compareGenerations(ui.compareBefore, ui.compareAfter);
  const options = lineageNodes().map((node) =>
    `<option value="${node.manifestSha256}">Generation ${node.generation} · ${compact(node.manifestSha256)}</option>`,
  ).join("");
  return `<section class="lineage-panel">
    <header><div><span class="eyebrow">Structured generation diff</span><h3>Literal evidence changes</h3></div>${stateBadge(comparison.relation)}</header>
    <div class="lineage-compare-controls">
      <label>From <select data-lineage-before>${options}</select></label>
      <label>To <select data-lineage-after>${options}</select></label>
    </div>
    <p class="lineage-doctrine">${comparison.interpretation}</p>
    <table class="lineage-diff"><thead><tr><th>Dimension</th><th>Before</th><th>After</th><th>State / availability</th></tr></thead>
      <tbody>
        ${comparison.rows.map((row) => `<tr data-state="${row.state.toLowerCase()}"><th>${row.label}</th><td>${compact(row.before)}</td><td>${compact(row.after)}</td><td>${row.state}${row.reason ? ` · ${row.reason}` : ""}<small>${row.source}</small></td></tr>`).join("")}
      </tbody>
    </table>
    <h4>Capability evidence</h4>
    <table class="lineage-diff"><thead><tr><th>Capability</th><th>Before</th><th>After</th><th>Evidence state</th></tr></thead>
      <tbody>${comparison.capabilityChanges.map((row) => `<tr data-state="${row.state.toLowerCase()}"><th>${row.id}</th><td>${row.before}</td><td>${row.after}</td><td>${row.state}</td></tr>`).join("")}</tbody>
    </table>
  </section>`;
}

function rejectedMarkup() {
  return `<section class="lineage-panel lineage-rejected">
    <header><div><span class="eyebrow">Non-lineage evidence</span><h3>Rejected candidates stay outside committed history</h3></div>${stateBadge("REJECTED")}</header>
    ${LINEAGE_FIXTURE.rejectedCandidates.map((candidate) => `<p><strong>${candidate.candidateId}</strong> · ${candidate.reason} · committed generation: NONE</p>`).join("")}
  </section>`;
}

function bind(container, inspectGeneration) {
  container.querySelectorAll("[data-lineage-node]").forEach((button) => button.addEventListener("click", () => {
    ui.selected = button.dataset.lineageNode;
    const node = nodeByIdentity(ui.selected);
    renderLineageView(container, inspectGeneration, node.manifestSha256);
    inspectGeneration(node.manifestSha256, node);
  }));
  const before = container.querySelector("[data-lineage-before]");
  const after = container.querySelector("[data-lineage-after]");
  if (before) {
    before.value = ui.compareBefore;
    before.addEventListener("change", (event) => {
      ui.compareBefore = event.currentTarget.value;
      renderLineageView(container, inspectGeneration, ui.selected);
    });
  }
  if (after) {
    after.value = ui.compareAfter;
    after.addEventListener("change", (event) => {
      ui.compareAfter = event.currentTarget.value;
      renderLineageView(container, inspectGeneration, ui.selected);
    });
  }
}

export function renderLineageView(container, inspectGeneration, selectedIdentity = null) {
  const selected = nodeByIdentity(selectedIdentity ?? ui.selected);
  ui.selected = selected.manifestSha256;
  container.innerHTML = `<div class="lineage-view">
    <header class="lineage-heading"><div><span class="eyebrow">GUI14 · Lineage and Checkpoints</span><h2>Accepted generation history</h2></div>
      <p>Inspect immutable generation identity and literal state transitions. Difference is not a claim of improvement.</p></header>
    <div class="lineage-fixture-notice" role="status"><strong>${LINEAGE_FIXTURE_CONTRACT.posture}</strong>
      <span>CP03 exposes the authenticated GenerationManifest spine. Rich manifest fields and structured comparison are checked-in fixtures grounded in B13 accepted-generation sidecars and C10 immutable projections.</span></div>
    ${graphMarkup(selected)}
    ${inspectorMarkup(selected)}
    ${compareMarkup()}
    ${rejectedMarkup()}
    <p class="lineage-doctrine"><strong>Authority boundary:</strong> this view cannot restore, prune, mutate checkpoints, or select champions.</p>
  </div>`;
  bind(container, inspectGeneration);
}
