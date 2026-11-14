import { INSTRUMENTATION_STATES } from "./neural-fixture.mjs";
import {
  ccgqaEvidenceState,
  neuralFixture,
  refinementCostSummary,
  refinementHistogram,
} from "./neural-model.mjs";

const ui = { mode: "current", selected: "fixture:ccgqa:g44238:l3" };

function stateBadge(state) {
  const normalized = state.toLowerCase().replaceAll("_", "-");
  return `<span class="neural-state" data-neural-state="${normalized}">${state}</span>`;
}

function topologyPanel(fixture) {
  const topology = fixture.topology;
  const fields = topology.schema.endsWith("/v2")
    ? [
      ["Architecture", topology.architectureId],
      ["Layers", topology.layers],
      ["Width", topology.width],
      ["FFN", topology.ffnDimension],
      ["Q heads", topology.queryHeads],
      ["KV heads", topology.kvHeads],
      ["Head dim", topology.headDimension],
      ["Context", topology.context],
      ["Convolution", topology.convolution + " k=" + topology.convolutionKernel],
      ["Depth groups", topology.depthGroups],
    ]
    : [
      ["Layers", topology.layers],
      ["Heads", topology.heads],
      ["Width", topology.width],
      ["FFN", topology.ffnDimension],
      ["Context", topology.context],
    ];
  return `<section class="neural-panel">
    <header><div><span class="eyebrow">Exact topology manifest</span><h3>${topology.schema}</h3></div>${stateBadge("PRESENT")}</header>
    <div class="topology-path">${fixture.path.map((stage, index) => `<div><span>${index + 1}</span><strong>${stage}</strong></div>`).join("")}</div>
    <dl class="topology-facts">${fields.map(([label, value]) => `<div><dt>${label}</dt><dd>${value}</dd></div>`).join("")}</dl>
  </section>`;
}

function runtimeSummary(fixture) {
  const sample = fixture.telemetry;
  const values = [
    ["Optimizer step", sample.optimizerStep],
    ["Step duration", sample.stepDurationMs === null ? "UNAVAILABLE" : sample.stepDurationMs + " ms"],
    ["Active parameters", sample.activeParameters === null ? "UNAVAILABLE" : sample.activeParameters.toLocaleString()],
    ["Refinement fraction", sample.refinementFraction === null ? "UNAVAILABLE" : (100 * sample.refinementFraction).toFixed(1) + "%"],
  ];
  return `<section class="neural-panel runtime-summary">
    <header><div><span class="eyebrow">Mission Control projection</span><h3>${sample.schema}</h3></div>${stateBadge(sample.coverage)}</header>
    <div class="runtime-metrics">${values.map(([label, value]) => `<div><small>${label}</small><strong>${value}</strong></div>`).join("")}</div>
  </section>`;
}

function ccgqaPanel(fixture) {
  if (!fixture.ccgqa) {
    return `<section class="neural-panel unavailable-panel"><header><div><span class="eyebrow">CCGQA diagnostics</span><h3>Instrumentation unavailable for this topology</h3></div>${stateBadge("UNAVAILABLE")}</header><p>The historical v1 topology does not claim the BAMF CCGQA diagnostic contract. No Q/K/V, entropy, cache, or mask values are synthesized.</p></section>`;
  }
  return `<section class="neural-panel">
    <header><div><span class="eyebrow">CCGQA · measured-style fixture</span><h3>Utilization, mask, sequence and cache health</h3></div></header>
    <div class="ccgqa-grid">${fixture.ccgqa.map((sample) => {
      const state = ccgqaEvidenceState(sample);
      return `<article class="ccgqa-card" data-evidence-state="${state.toLowerCase()}">
        <header><strong>Layer ${sample.layer}</strong>${stateBadge(state)}</header>
        ${state === "INVALID" ? `<div class="invalid-evidence-banner"><strong>INVALID EVIDENCE</strong><span>mask-invalid violations: ${sample.maskInvalidViolations}</span></div>` : ""}
        <dl>
          <div><dt>Q utilization</dt><dd>${(100 * sample.qUtilization).toFixed(1)}%</dd></div>
          <div><dt>K utilization</dt><dd>${(100 * sample.kUtilization).toFixed(1)}%</dd></div>
          <div><dt>V utilization</dt><dd>${(100 * sample.vUtilization).toFixed(1)}%</dd></div>
          <div><dt>Channel utilization</dt><dd>${(100 * sample.channelUtilization).toFixed(1)}%</dd></div>
          <div><dt>Conv health</dt><dd>${sample.convolutionHealth}</dd></div>
          <div><dt>Entropy μ / p95</dt><dd>${sample.entropyMean.toFixed(2)} / ${sample.entropyP95.toFixed(2)}</dd></div>
          <div><dt>Active sequence / frames</dt><dd>${sample.activeSequenceLength} / ${sample.activeFrameLength}</dd></div>
          <div><dt>Cache</dt><dd>${sample.cacheState} · ${(100 * sample.cacheUsage).toFixed(1)}%</dd></div>
          <div><dt>Finite health</dt><dd>${sample.finite ? "FINITE" : "NONFINITE"}</dd></div>
        </dl>
        <button type="button" data-neural-inspect="${sample.evidenceId}" data-kind="ccgqa">Inspect fixture evidence</button>
      </article>`;
    }).join("")}</div>
  </section>`;
}

function attnResPanel(fixture) {
  if (!fixture.attnres) {
    return `<section class="neural-panel unavailable-panel"><header><div><span class="eyebrow">Block AttnRes</span><h3>Not part of inspected historical topology</h3></div>${stateBadge("UNAVAILABLE")}</header><p>No depth-selection weights are invented for a topology that does not declare the v2 depth contract.</p></section>`;
  }
  return `<section class="neural-panel">
    <header><div><span class="eyebrow">Block AttnRes · direct diagnostic fixture</span><h3>Routing / mixture telemetry</h3></div>${stateBadge("PRESENT")}</header>
    <p class="neural-doctrine">These weights are routing telemetry from <code>DepthSelectionDiagnostics.alpha</code>. They carry no semantic interpretation.</p>
    <div class="attnres-grid">${fixture.attnres.map((entry) => `<article>
      <header><strong>Boundary ${entry.boundaryGroup} · layer ${entry.completedLayer}</strong><span>Σ ${entry.weightSum.toFixed(2)} · gate ${entry.gate.toFixed(3)}</span></header>
      <div class="mixture-bars">${entry.pairs.map((pair) => `<div><span>${pair.source}</span><progress max="1" value="${pair.weight}"></progress><strong>${pair.weight.toFixed(2)}</strong></div>`).join("")}</div>
      <button type="button" data-neural-inspect="${entry.evidenceId}" data-kind="attnres">Inspect recorded weights</button>
    </article>`).join("")}</div>
  </section>`;
}

function refinementPanel(fixture) {
  if (!fixture.refinementReceipts) {
    return `<section class="neural-panel unavailable-panel"><header><div><span class="eyebrow">Local refinement</span><h3>Receipts unavailable</h3></div>${stateBadge("UNAVAILABLE")}</header><p>No refinement distribution is projected for this historical topology.</p></section>`;
  }
  const histogram = refinementHistogram(fixture.refinementReceipts);
  const cost = refinementCostSummary(fixture.refinementReceipts);
  return `<section class="neural-panel">
    <header><div><span class="eyebrow">Local refinement · receipt reconciliation</span><h3>Expansion passes and resource cost</h3></div>${stateBadge("PRESENT")}</header>
    <div class="refinement-histogram">
      <div><span>No expansion</span><strong>${histogram.none}</strong><progress max="${histogram.total}" value="${histogram.none}"></progress></div>
      <div><span>One pass</span><strong>${histogram.one}</strong><progress max="${histogram.total}" value="${histogram.one}"></progress></div>
      <div><span>Multiple passes</span><strong>${histogram.multiple}</strong><progress max="${histogram.total}" value="${histogram.multiple}"></progress></div>
    </div>
    <p class="reconciliation-note">Histogram total ${histogram.total} = ${fixture.refinementReceipts.length} frame/episode receipts. Active refinement cost ${cost.totalCostMs.toFixed(1)} ms across ${cost.activeFrames} frames; mean active frame density ${cost.averageFrameDensity.toFixed(2)}.</p>
    <div class="refinement-table-wrap"><table class="refinement-table"><thead><tr><th>Frame</th><th>Episode receipt</th><th>Eligible</th><th>Quota</th><th>Passes</th><th>Frame density</th><th>Cost ms</th></tr></thead><tbody>
      ${fixture.refinementReceipts.map((row) => `<tr><td>${row.frameId}</td><td><button type="button" data-neural-inspect="${row.episodeReceipt}" data-kind="refinement">${row.episodeReceipt}</button></td><td>${row.eligibleFrames}</td><td>${row.quota}</td><td>${row.passes}</td><td>${row.frameDensity.toFixed(2)}</td><td>${row.resourceCostMs.toFixed(1)}</td></tr>`).join("")}
    </tbody></table></div>
  </section>`;
}

function instrumentationPanel(fixture) {
  const states = fixture.mode === "historical"
    ? INSTRUMENTATION_STATES.map((item) => ({ ...item, state: "UNAVAILABLE", source: "not present in inspected historical topology" }))
    : INSTRUMENTATION_STATES;
  return `<section class="neural-panel instrumentation-panel">
    <header><div><span class="eyebrow">Instrumentation coverage</span><h3>Never synthesize absent metrics</h3></div></header>
    <div>${states.map((item) => `<article><div><strong>${item.label}</strong><small>${item.source}</small></div>${stateBadge(item.state)}</article>`).join("")}</div>
  </section>`;
}

function bind(container, inspect) {
  container.querySelectorAll("[data-neural-mode]").forEach((button) => button.addEventListener("click", () => {
    ui.mode = button.dataset.neuralMode;
    renderNeuralView(container, inspect);
  }));
  container.querySelectorAll("[data-neural-inspect]").forEach((button) => button.addEventListener("click", () => {
    ui.selected = button.dataset.neuralInspect;
    inspect(button.dataset.neuralInspect, button.dataset.kind);
  }));
}

export function renderNeuralView(container, inspect) {
  const fixture = neuralFixture(ui.mode);
  container.innerHTML = `<div class="neural-view">
    <header class="neural-heading"><div><span class="eyebrow">GUI09 · Neural Runtime</span><h2>Measured mechanisms, bounded claims</h2></div><p>Inspect topology, routing, attention health and local refinement strictly as recorded runtime telemetry.</p></header>
    <div class="neural-fixture-notice"><strong>FIXTURE-BACKED DIAGNOSTICS</strong><span>Rich CCGQA/AttnRes/refinement details are literal, provenance-labeled fixtures because the accepted Electron bridge currently projects only the bounded Mission Control runtime summary.</span></div>
    <div class="neural-mode-switch" role="group" aria-label="Inspected generation fixture">
      <button type="button" data-neural-mode="current" aria-pressed="${ui.mode === "current"}">Current BAMF v2 fixture</button>
      <button type="button" data-neural-mode="historical" aria-pressed="${ui.mode === "historical"}">Historical v1 fixture</button>
    </div>
    ${topologyPanel(fixture)}
    ${runtimeSummary(fixture)}
    ${ccgqaPanel(fixture)}
    ${attnResPanel(fixture)}
    ${refinementPanel(fixture)}
    ${instrumentationPanel(fixture)}
  </div>`;
  bind(container, inspect);
}

export function neuralViewModeForTest() {
  return ui.mode;
}
