import {
  MEMORY_GENERATIONS,
  REJECTED_MEMORY_CANDIDATE,
} from "./memory-fixture.mjs";
import {
  capabilityInterpretation,
  currentMemoryGeneration,
  memoryCompare,
  pageSummaries,
  priorMemoryGeneration,
  receiptTotals,
  rejectedCandidateInvariant,
  slotAddress,
  slotByIdentity,
  slotGateUseRate,
  slotHitRate,
  slotsForPage,
  stableMemoryIdentity,
} from "./memory-model.mjs";

const ui = {
  generation: currentMemoryGeneration().generation,
  compareGeneration: priorMemoryGeneration().generation,
  selectedPage: 0,
  selectedIdentity: stableMemoryIdentity(currentMemoryGeneration().slots[0]),
};

function pct(value) {
  return value === null ? "UNAVAILABLE" : `${(100 * value).toFixed(1)}%`;
}

function bytes(value) {
  return `${(value / (1024 * 1024)).toFixed(1)} MiB`;
}

function stateBadge(state) {
  const normalized = String(state).toLowerCase().replaceAll("_", "-");
  return `<span class="memory-state" data-memory-state="${normalized}">${state}</span>`;
}

function summaryPanel(snapshot) {
  const totals = receiptTotals(snapshot);
  return `<section class="memory-panel">
    <header><div><span class="eyebrow">Generation ${snapshot.generation}</span><h3>Engram memory summary</h3></div>${stateBadge("PRESENT")}</header>
    <div class="memory-summary-grid">
      <div><small>Allocated / capacity</small><strong>${snapshot.allocatedSlots} / ${snapshot.capacitySlots}</strong></div>
      <div><small>Eligible hits</small><strong>${totals.hits}</strong><span>${totals.exact} exact · ${totals.structural} structural</span></div>
      <div><small>Misses</small><strong>${totals.misses}</strong><span>held/foreign/quarantine count as non-reads upstream</span></div>
      <div><small>Hit rate</small><strong>${pct(totals.hitRate)}</strong><span>retrieval telemetry only</span></div>
      <div><small>Gate/use rate</small><strong>${pct(totals.gateUseRate)}</strong><span>${totals.gateUses} / ${totals.gateEligibleHits} eligible hits used</span></div>
      <div><small>Memory state footprint</small><strong>${bytes(snapshot.memoryFootprint.stateBytes)}</strong><span>${bytes(snapshot.memoryFootprint.parameterBytes)} params · ${bytes(snapshot.memoryFootprint.optimizerBytes)} optimizer</span></div>
    </div>
    <div class="memory-site-receipts">${snapshot.readReceipts.map((receipt) => `<article>
      <strong>Read site ${receipt.siteIndex}</strong><span>${receipt.exactCount} exact · ${receipt.structuralCount} structural · ${receipt.missCount} miss</span><small>${receipt.receiptId}</small>
    </article>`).join("")}</div>
    <p class="memory-doctrine"><strong>Boundary:</strong> memory hits and gate use are operational evidence. They are not source truth and do not prove learned capability.</p>
  </section>`;
}

function atlasPanel(snapshot) {
  const pages = pageSummaries(snapshot);
  const pageSlots = slotsForPage(snapshot, ui.selectedPage);
  return `<section class="memory-panel">
    <header><div><span class="eyebrow">Memory atlas</span><h3>Aggregate → page → stable motif</h3></div><span>${snapshot.pageCount} page · ${snapshot.pageRows} rows/page</span></header>
    <div class="memory-pages">${pages.map((page) => `<button type="button" data-memory-page="${page.pageIndex}" aria-pressed="${page.pageIndex === ui.selectedPage}">
      <strong>motif.page.${page.pageIndex}</strong><span>${page.allocated} allocated · ${page.active} active · ${page.held} held</span><small>${page.optimizerParticipating} currently optimizer-participating</small>
    </button>`).join("")}</div>
    <div class="memory-slot-list">${pageSlots.length ? pageSlots.map((slot) => {
      const identity = stableMemoryIdentity(slot);
      return `<button type="button" data-memory-slot="${identity}" aria-pressed="${identity === ui.selectedIdentity}">
        <span class="slot-address">${slotAddress(slot)}</span><strong>${identity}</strong><span>${slot.frameSchemaId}</span>${stateBadge(slot.allocationState)}
      </button>`;
    }).join("") : `<p class="memory-muted">No allocated slots on this page.</p>`}</div>
  </section>`;
}

function slotPanel(snapshot) {
  const slot = slotByIdentity(snapshot, ui.selectedIdentity);
  if (!slot) {
    return `<section class="memory-panel"><header><div><span class="eyebrow">Motif inspector</span><h3>No committed slot selected</h3></div>${stateBadge("MISSING")}</header></section>`;
  }
  const interpretation = capabilityInterpretation(slot);
  return `<section class="memory-panel memory-inspector">
    <header><div><span class="eyebrow">Stable BAMF memory identity</span><h3>${stableMemoryIdentity(slot)}</h3></div>${stateBadge(slot.allocationState)}</header>
    <dl class="memory-details">
      <dt>Identity contract</dt><dd><code>${slot.schema}</code></dd>
      <dt>Key digest</dt><dd><code>${slot.keyDigest}</code></dd>
      <dt>Semantic release</dt><dd><code>${slot.semanticRelease}</code></dd>
      <dt>Exact address</dt><dd>${slotAddress(slot)} · slot ${slot.slotId}</dd>
      <dt>Source eligibility</dt><dd>${slot.sourceEligibility}${slot.heldReason ? ` · ${slot.heldReason}` : ""}</dd>
      <dt>Creation generation</dt><dd>${slot.createdGeneration}</dd>
      <dt>Last use</dt><dd>g${slot.lastUse.generation} · step ${slot.lastUse.optimizerStep} · ${slot.lastUse.receiptId}</dd>
      <dt>Lifetime hits</dt><dd>${slot.hitCount} / ${slot.eligibleReadCount} eligible reads · ${pct(slotHitRate(slot))}</dd>
      <dt>Gate activity</dt><dd>${slot.gateUseCount} uses · ${pct(slotGateUseRate(slot))} of hits</dd>
      <dt>Parameter bank</dt><dd>${slot.parameterBank} · ${slot.allocationExtent}</dd>
      <dt>Optimizer participation</dt><dd>${slot.optimizerParticipated ? `YES · ${slot.optimizerUpdateCount} updates` : "NO"}</dd>
      <dt>Correction / requalification</dt><dd>${slot.correctionState}${slot.correctionRef ? ` · ${slot.correctionRef}` : ""}</dd>
      <dt>Source refs</dt><dd>${slot.sourceRefs.join("<br>")}</dd>
      <dt>Evidence refs</dt><dd>${slot.evidenceRefs.join("<br>")}</dd>
      <dt>Related capabilities</dt><dd>${slot.capabilities.join("<br>") || "none"}</dd>
      <dt>Related episodes</dt><dd>${slot.episodes.join("<br>") || "none"}</dd>
      <dt>Capability interpretation</dt><dd><strong>${interpretation.label}</strong></dd>
    </dl>
  </section>`;
}

function comparePanel(snapshot) {
  const before = MEMORY_GENERATIONS.find((item) => item.generation === ui.compareGeneration) ?? priorMemoryGeneration();
  const delta = memoryCompare(before, snapshot);
  const rows = [
    ["Created", delta.created],
    ["Removed", delta.removed],
    ["Held", delta.held],
    ["Requalified", delta.requalified],
  ];
  return `<section class="memory-panel">
    <header><div><span class="eyebrow">Generation comparison</span><h3>g${before.generation} → g${snapshot.generation}</h3></div>${stateBadge("DIFF")}</header>
    <div class="memory-compare-controls"><label>Compare from <select data-memory-compare>${MEMORY_GENERATIONS.filter((item) => item.generation !== snapshot.generation).map((item) => `<option value="${item.generation}" ${item.generation === before.generation ? "selected" : ""}>Generation ${item.generation}</option>`).join("")}</select></label></div>
    <div class="memory-delta-grid">${rows.map(([label, identities]) => `<article data-delta-kind="${label.toLowerCase()}"><strong>${label} · ${identities.length}</strong>${identities.length ? `<ul>${identities.map((identity) => `<li>${identity}</li>`).join("")}</ul>` : `<span>none</span>`}</article>`).join("")}</div>
    <dl class="memory-compare-metrics">
      <div><dt>Allocation Δ</dt><dd>${delta.allocationDelta >= 0 ? "+" : ""}${delta.allocationDelta}</dd></div>
      <div><dt>Capacity Δ</dt><dd>${delta.capacityDelta >= 0 ? "+" : ""}${delta.capacityDelta}</dd></div>
      <div><dt>Batch hit Δ</dt><dd>${delta.hitDelta >= 0 ? "+" : ""}${delta.hitDelta}</dd></div>
      <div><dt>Batch miss Δ</dt><dd>${delta.missDelta >= 0 ? "+" : ""}${delta.missDelta}</dd></div>
      <div><dt>Gate-use Δ</dt><dd>${delta.gateUseDelta >= 0 ? "+" : ""}${delta.gateUseDelta}</dd></div>
    </dl>
    <p class="memory-doctrine">The retained manifest is append-only. A zero physical-removal count is expected here; correction-driven loss of eligibility appears as HELD rather than silently deleting memory identity.</p>
  </section>`;
}

function rejectedCandidatePanel(snapshot) {
  const invariant = rejectedCandidateInvariant(REJECTED_MEMORY_CANDIDATE, snapshot);
  return `<section class="memory-panel rejected-memory">
    <header><div><span class="eyebrow">Rejected candidate boundary</span><h3>${REJECTED_MEMORY_CANDIDATE.candidateId}</h3></div>${stateBadge("REJECTED")}</header>
    <div class="rejected-memory-proof">
      <div><small>Proposed-only memory identity</small><strong>${invariant.proposedIdentity}</strong></div>
      <div><small>Parent allocation preserved</small><strong>${invariant.parentAllocationPreserved ? "YES" : "NO"}</strong></div>
      <div><small>Committed child generation</small><strong>${invariant.noCommittedGeneration ? "NONE" : REJECTED_MEMORY_CANDIDATE.committedGeneration}</strong></div>
      <div><small>Proposed slot in committed memory</small><strong>${invariant.proposedSlotAbsent ? "ABSENT" : "PRESENT · INVALID"}</strong></div>
    </div>
    <p>${REJECTED_MEMORY_CANDIDATE.reasonCode} · candidate-local allocation evidence is not retained memory.</p>
  </section>`;
}

function bind(container, inspectMemory) {
  container.querySelectorAll("[data-memory-page]").forEach((button) => button.addEventListener("click", () => {
    ui.selectedPage = Number(button.dataset.memoryPage);
    const snapshot = currentMemoryGeneration();
    const first = slotsForPage(snapshot, ui.selectedPage)[0];
    if (first) ui.selectedIdentity = stableMemoryIdentity(first);
    renderMemoryView(container, inspectMemory, ui.selectedIdentity);
  }));
  container.querySelectorAll("[data-memory-slot]").forEach((button) => button.addEventListener("click", () => {
    ui.selectedIdentity = button.dataset.memorySlot;
    renderMemoryView(container, inspectMemory, ui.selectedIdentity);
    const slot = slotByIdentity(currentMemoryGeneration(), ui.selectedIdentity);
    if (slot) inspectMemory(ui.selectedIdentity, slot);
  }));
  container.querySelector("[data-memory-compare]")?.addEventListener("change", (event) => {
    ui.compareGeneration = Number(event.currentTarget.value);
    renderMemoryView(container, inspectMemory, ui.selectedIdentity);
  });
}

export function renderMemoryView(container, inspectMemory, selectedIdentity = null) {
  const snapshot = currentMemoryGeneration();
  if (selectedIdentity && slotByIdentity(snapshot, selectedIdentity)) {
    ui.selectedIdentity = selectedIdentity;
  }
  const selected = slotByIdentity(snapshot, ui.selectedIdentity);
  if (selected) ui.selectedPage = selected.pageIndex;
  container.innerHTML = `<div class="memory-view">
    <header class="memory-heading"><div><span class="eyebrow">GUI10 · Engram Memory</span><h2>Retained motif memory atlas</h2></div><p>Inspect retained allocation and read telemetry. Memory retrieval is not semantic authority and is never promoted into a capability claim.</p></header>
    <div class="memory-fixture-notice" role="status"><strong>FIXTURE · RETAINED-CONTRACT SHAPE</strong><span>Detailed slot telemetry is a checked-in fixture grounded in B07/B08/B12 contracts because the current CP03 MemorySnapshot remains summary-only.</span></div>
    ${summaryPanel(snapshot)}
    ${atlasPanel(snapshot)}
    ${slotPanel(snapshot)}
    ${comparePanel(snapshot)}
    ${rejectedCandidatePanel(snapshot)}
  </div>`;
  bind(container, inspectMemory);
}
