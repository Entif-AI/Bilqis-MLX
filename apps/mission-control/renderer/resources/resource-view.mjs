import {
  decomposition,
  resourceComparison,
} from "./resource-model.mjs";

const PRESENT = "PRESENT";

const LABELS = Object.freeze({
  unifiedMemoryUsed: "Unified memory used",
  unifiedMemoryBudget: "Memory budget",
  forecastMemoryPeak: "Forecast peak",
  mlxAllocatedMemory: "MLX allocated",
  mlxCacheMemory: "MLX cache",
  cpuUtilization: "CPU utilization",
  preparationWorkers: "Preparation workers",
  diskFree: "Disk free",
  diskUsed: "Disk used",
  diskReserve: "Disk reserve floor",
  candidateSnapshotFootprint: "Candidate snapshot",
  acceptedStepsHour: "Accepted optimizer steps / h",
  sequenceDensity: "Compiled sequence density",
  frameDensity: "Compiled frame density",
  batchSize: "Batch size",
  actualLengthP50: "Actual length p50",
  actualLengthP95: "Actual length p95",
  actualLengthMax: "Actual length max",
  preparationCompileMs: "Preparation / compile",
  mlxWallMs: "MLX wall time",
  monetaryCost: "Monetary cost",
});

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function stateBadge(value) {
  const state = String(value ?? "UNKNOWN");
  return `<span class="resource-state" data-resource-state="${esc(state.toLowerCase().replaceAll("_", "-"))}">${esc(state)}</span>`;
}

function semanticBadge(metric) {
  const semantic = metric?.state === PRESENT ? metric.semantic ?? metric.origin ?? "MEASURED" : "UNAVAILABLE";
  return `<span class="resource-semantic" data-resource-semantic="${esc(String(semantic).toLowerCase().replaceAll("_", "-"))}">${esc(semantic)}</span>`;
}

function bytes(value) {
  if (!Number.isFinite(value)) return "UNAVAILABLE";
  const GiB = 1024 ** 3;
  const MiB = 1024 ** 2;
  return value >= GiB ? `${(value / GiB).toFixed(1)} GiB` : `${(value / MiB).toFixed(1)} MiB`;
}

function metricValue(metric) {
  if (metric?.state !== PRESENT) return "UNAVAILABLE";
  const value = metric.value;
  switch (metric.units) {
    case "bytes": return bytes(value);
    case "fraction": return `${(100 * value).toFixed(1)}%`;
    case "percent": return `${Number(value).toFixed(1)}%`;
    case "ms": return `${Number(value).toFixed(0)} ms`;
    case "USD": return `$${Number(value).toFixed(2)}`;
    default: return `${Number.isFinite(value) ? Number(value).toLocaleString() : esc(value)}${metric.units ? ` ${esc(metric.units)}` : ""}`;
  }
}

function metricCard(profile, key, note = "") {
  const metric = profile.aggregate[key] ?? { state: "UNAVAILABLE" };
  return `<article class="resource-metric" data-metric="${esc(key)}" data-state="${esc(metric.state.toLowerCase())}">
    <div><small>${esc(LABELS[key] ?? key)}</small>${semanticBadge(metric)}</div>
    <strong>${metricValue(metric)}</strong>
    ${note ? `<span>${esc(note)}</span>` : ""}
  </article>`;
}

function headline(profile) {
  return `<section class="resource-panel resource-headline">
    <header><div><span class="eyebrow">Budget at a glance</span><h3>Measured load, configured limits, and estimates stay separate</h3></div>${stateBadge(profile.pageState ?? "PRESENT")}</header>
    <div class="resource-metric-grid">
      ${metricCard(profile, "unifiedMemoryUsed", "aggregate accepted resource sample")}
      ${metricCard(profile, "mlxAllocatedMemory", "only when directly instrumented")}
      ${metricCard(profile, "mlxCacheMemory", "only when directly instrumented")}
      ${metricCard(profile, "diskReserve", "configured floor, not disk used")}
      ${metricCard(profile, "acceptedStepsHour", "resource throughput, not learning")}
      ${metricCard(profile, "batchSize", "actual batch evidence only")}
    </div>
    <p class="resource-doctrine"><strong>Truth boundary:</strong> high throughput is a resource fact. It is never rendered as capability improvement or retained learning without separate learning evidence.</p>
  </section>`;
}

function semanticsPanel(profile) {
  return `<section class="resource-panel">
    <header><div><span class="eyebrow">Budget semantics</span><h3>No metric category laundering</h3></div></header>
    <div class="resource-budget-semantics">
      <article><span>Measured value</span>${semanticBadge(profile.aggregate.unifiedMemoryUsed)}<strong>${metricValue(profile.aggregate.unifiedMemoryUsed)}</strong><small>Current observed unified memory.</small></article>
      <article><span>Configured limit</span>${semanticBadge(profile.aggregate.unifiedMemoryBudget)}<strong>${metricValue(profile.aggregate.unifiedMemoryBudget)}</strong><small>Budget value, not a measured peak.</small></article>
      <article><span>Forecast / estimate</span>${semanticBadge(profile.aggregate.forecastMemoryPeak)}<strong>${metricValue(profile.aggregate.forecastMemoryPeak)}</strong><small>Never promoted into measured evidence.</small></article>
    </div>
  </section>`;
}

function decompositionPanel(profile) {
  const totals = decomposition(profile);
  const aggregate = totals.aggregate === null ? "UNAVAILABLE" : bytes(totals.aggregate);
  const remainder = totals.remainder === null ? "UNAVAILABLE" : bytes(totals.remainder);
  return `<section class="resource-panel">
    <header><div><span class="eyebrow">Memory decomposition</span><h3>Reconcile measured categories to the aggregate</h3></div>${stateBadge(totals.aggregate === null ? "UNAVAILABLE" : totals.complete ? "COMPLETE" : "PARTIAL")}</header>
    <div class="resource-decomposition">
      ${profile.memoryDecomposition.map((item) => `<article data-resource-category="${esc(item.id)}" data-state="${esc(item.state.toLowerCase())}">
        <span>${esc(item.label)}</span><strong>${item.state === PRESENT ? bytes(item.value) : "UNAVAILABLE"}</strong>${stateBadge(item.state)}
      </article>`).join("")}
      <article class="resource-remainder"><span>Unallocated / uninstrumented remainder</span><strong>${remainder}</strong>${stateBadge(totals.remainder === 0 ? "RECONCILED" : totals.remainder === null ? "UNAVAILABLE" : "EXPLICIT_REMAINDER")}</article>
    </div>
    <p class="resource-reconciliation">Measured decomposition sum ${bytes(totals.allocated)} against aggregate ${aggregate}. Unknown categories remain unknown rather than being forced to zero.</p>
  </section>`;
}

function computePanel(profile) {
  return `<section class="resource-panel">
    <header><div><span class="eyebrow">Compute and batching</span><h3>Preparation, sequence density, batch shape, and MLX wall</h3></div></header>
    <div class="resource-compute-grid">
      ${metricCard(profile, "cpuUtilization")}
      ${metricCard(profile, "preparationWorkers")}
      ${metricCard(profile, "candidateSnapshotFootprint")}
      ${metricCard(profile, "preparationCompileMs")}
      ${metricCard(profile, "mlxWallMs")}
      ${metricCard(profile, "monetaryCost", "no price claim without cost evidence")}
    </div>
    <div class="resource-length-strip">
      ${metricCard(profile, "sequenceDensity")}${metricCard(profile, "frameDensity")}${metricCard(profile, "batchSize")}
      ${metricCard(profile, "actualLengthP50")}${metricCard(profile, "actualLengthP95")}${metricCard(profile, "actualLengthMax")}
    </div>
  </section>`;
}

function spikeDetails(sample) {
  const safe = (value) => typeof value === "string" ? esc(value) : value;
  const pairs = [
    ["Episode", sample.episodeId], ["Batch", sample.batchId], ["Resource sample", sample.id],
    ["Checkpoint", sample.checkpointId], ["Source / preparation", sample.sourceWorkload],
    ["Expansion / refinement count", sample.expansionCount],
  ].filter(([, value]) => value !== null && value !== undefined);
  if (sample.exactRefs?.length) pairs.push(["Accepted refs", sample.exactRefs.join(", ")]);
  return Object.fromEntries(pairs.map(([label, value]) => [label, safe(value)]));
}

function timelinePanel(profile) {
  if (!profile.timeline.length) {
    return `<section class="resource-panel"><header><div><span class="eyebrow">Timeline and correlation</span><h3>No resource samples available for this window</h3></div>${stateBadge("UNAVAILABLE")}</header><p class="resource-muted">No episode, batch, refinement, checkpoint, or preparation correlation is synthesized.</p></section>`;
  }
  const maxMemory = Math.max(...profile.timeline.map((row) => row.unifiedMemoryUsed ?? -Infinity));
  return `<section class="resource-panel">
    <header><div><span class="eyebrow">Timeline and correlation</span><h3>Select a resource sample to inspect its exact related evidence</h3></div><span>${profile.timeline.length} samples</span></header>
    <div class="resource-table-wrap"><table class="resource-timeline"><thead><tr><th>Sample</th><th>Memory</th><th>MLX</th><th>Batch</th><th>Seq density</th><th>Accepted steps/h</th><th>Expansion</th></tr></thead><tbody>
      ${profile.timeline.map((row) => `<tr data-resource-spike="${row.unifiedMemoryUsed === maxMemory ? "peak" : "sample"}"><td><button type="button" data-resource-inspect="${esc(row.id)}">${esc(row.id)}</button><small>t=${esc(row.observedAt ?? "UNKNOWN")}</small></td><td>${row.unifiedMemoryUsed === null ? "UNAVAILABLE" : bytes(row.unifiedMemoryUsed)}</td><td>${row.mlxAllocated === null ? "UNAVAILABLE" : bytes(row.mlxAllocated)}</td><td>${row.batchSize ?? "UNAVAILABLE"}</td><td>${row.sequenceDensity === null ? "UNAVAILABLE" : `${(100 * row.sequenceDensity).toFixed(1)}%`}</td><td>${row.acceptedStepsHour ?? "UNAVAILABLE"}</td><td>${row.expansionCount ?? "UNAVAILABLE"}</td></tr>`).join("")}
    </tbody></table></div>
  </section>`;
}

function compareCell(metric) {
  return metricValue(metric ?? { state: "UNAVAILABLE" });
}

function comparisonPanel(current, comparison, comparisonState) {
  const rows = comparison ? resourceComparison(comparison, current) : [];
  return `<section class="resource-panel">
    <header><div><span class="eyebrow">Historical comparison</span><h3>Exact generation against inspected profile</h3></div>${stateBadge(comparisonState)}</header>
    <form class="resource-compare-form" data-resource-compare-form>
      <label>Historical generation <input name="generation" type="number" min="0" step="1" value="${comparison?.generation ?? ""}" inputmode="numeric" /></label>
      <button type="submit">Load exact generation</button>
      <span>Read-only CP03 historical query. No generation is inferred.</span>
    </form>
    ${comparison ? `<div class="resource-table-wrap"><table class="resource-compare"><thead><tr><th>Metric</th><th>g${esc(comparison.generation)}</th><th>g${esc(current.generation)}</th><th>Delta</th></tr></thead><tbody>${rows.map((row) => `<tr><td>${esc(LABELS[row.key] ?? row.key)}</td><td>${compareCell(row.before)}</td><td>${compareCell(row.after)}</td><td>${row.delta === null ? "UNAVAILABLE" : `${row.delta >= 0 ? "+" : ""}${Number(row.delta).toFixed(row.after.units === "fraction" ? 3 : 1)} ${esc(row.after.units ?? "")}`}</td></tr>`).join("")}</tbody></table></div>` : `<p class="resource-muted">Enter an exact generation to compare. The view does not invent a historical generation catalog.</p>`}
  </section>`;
}

export function renderResourceMarkup(state, { historical = false } = {}) {
  const current = state?.current;
  if (!current) {
    return `<div class="resource-view"><section class="resource-panel"><header><div><span class="eyebrow">GUI15 · Resources</span><h2>Resource evidence unavailable</h2></div>${stateBadge(state?.currentState ?? "UNAVAILABLE")}</header><p class="resource-muted">No accepted resource projection is available. Missing metrics are not rendered as zero.</p></section></div>`;
  }
  const provenance = current.provenance === "FIXTURE" ? "FIXTURE-BACKED DIAGNOSTICS" : historical ? "HISTORICAL CP03 QUERY" : "LIVE CP03 QUERY";
  return `<div class="resource-view">
    <header class="resource-heading"><div><span class="eyebrow">GUI15 · Resources</span><h2>Explain the budget, do not mythologize it</h2></div><p>Memory, compute, batching and preparation are rendered only at the semantic strength their evidence supports.</p></header>
    <div class="resource-provenance" data-provenance="${esc(current.provenance.toLowerCase())}"><strong>${provenance}</strong><span>Generation ${esc(current.generation ?? "UNKNOWN")} · ${esc(current.window)}</span></div>
    ${headline(current)}
    ${semanticsPanel(current)}
    ${decompositionPanel(current)}
    ${computePanel(current)}
    ${timelinePanel(current)}
    ${comparisonPanel(current, state.comparison, state.comparisonState ?? "EMPTY")}
  </div>`;
}

export function bindResourceInteractions(host, { onInspect, onCompare }) {
  host.querySelectorAll("[data-resource-inspect]").forEach((button) => {
    button.addEventListener("click", () => {
      const sample = host.__resourceState?.current?.timeline?.find((row) => row.id === button.dataset.resourceInspect);
      if (!sample) return;
      onInspect?.({ kind: "resource", id: sample.id, details: spikeDetails(sample) });
    });
  });
  host.querySelector("[data-resource-compare-form]")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const generation = Number(new FormData(event.currentTarget).get("generation"));
    if (Number.isSafeInteger(generation) && generation >= 0) onCompare?.(generation);
  });
}
