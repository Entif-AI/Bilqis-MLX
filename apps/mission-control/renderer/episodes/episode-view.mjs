import { EPISODE_FIXTURES, EPISODE_STAGES } from "./episode-fixture.mjs";
import {
  diffRows,
  episodeById,
  episodeDeepLink,
  episodeDurationText,
  rejectionClass,
  replaySlice,
  retainedTransition,
  rollbackInvariant,
  scoreText,
} from "./episode-model.mjs";

const ui = {
  selectedId: EPISODE_FIXTURES[0].recordId,
  stageIndex: EPISODE_STAGES.length - 1,
};

function stateBadge(state) {
  return `<span class="episode-state" data-state="${String(state).toLowerCase()}">${state}</span>`;
}

function headerPanel(episode) {
  return `<section class="episode-panel">
    <header><div><span class="eyebrow">Episode header</span><h3>${episode.episodeId}</h3></div>${stateBadge(episode.terminalState)}</header>
    <div class="episode-header-grid">
      <div><small>Candidate ID</small><strong>${episode.candidateId}</strong></div>
      <div><small>CP03 record ID</small><strong>${episode.recordId}</strong></div>
      <div><small>Target capability</small><strong>${episode.capabilityId}</strong></div>
      <div><small>Parent generation</small><strong>${episode.parentGeneration}</strong></div>
      <div><small>Strategy</small><strong>${episode.strategy}</strong></div>
      <div><small>Source family</small><strong>${episode.sourceFamily}</strong></div>
      <div><small>Lesson family</small><strong>${episode.lessonFamily}</strong></div>
      <div><small>Optimizer steps intended / attempted / retained</small><strong>${episode.intendedOptimizerSteps} / ${episode.attemptedOptimizerSteps} / ${episode.retainedOptimizerSteps ?? "UNKNOWN"}</strong></div>
      <div><small>Duration</small><strong>${episodeDurationText(episode.durationMs)}</strong></div>
      <div><small>Command state</small><strong>${episode.commandState}</strong></div>
      <div><small>Retention reason</small><strong>${episode.retentionReason}</strong></div>
      <div><small>Peak memory</small><strong>${episode.resourceCost.peakMemoryBytes ?? "UNAVAILABLE"}</strong></div>
      <div><small>Step rate / min</small><strong>${episode.resourceCost.stepRatePerMinute ?? "UNAVAILABLE"}</strong></div>
      <div><small>Resource coverage</small><strong>${episode.resourceCost.state}</strong></div>
    </div>
  </section>`;
}

function terminalProof(episode) {
  const transition = retainedTransition(episode);
  if (transition) {
    return `<section class="episode-panel">
      <header><div><span class="eyebrow">Retention result</span><h3>Exact accepted generation transition</h3></div>${stateBadge("PRESENT")}</header>
      <div class="episode-transition">
        <div><small>Parent generation</small><strong>${transition.parentGeneration}</strong></div>
        <span aria-hidden="true">→</span>
        <div><small>Child generation</small><strong>${transition.childGeneration} · ${transition.checkpointId}</strong></div>
      </div>
    </section>`;
  }
  const rollback = rollbackInvariant(episode);
  if (!rollback) {
    return `<section class="episode-panel">
      <header><div><span class="eyebrow">Terminal reconciliation</span><h3>Pending / unknown</h3></div>${stateBadge("UNKNOWN")}</header>
      <p class="reconciliation-note">No commit or rollback claim is made until a durable decision and finalization receipt are observed.</p>
    </section>`;
  }
  const classification = rejectionClass(episode);
  return `<section class="episode-panel">
    <header><div><span class="eyebrow">Rollback proof</span><h3>Rejected candidate did not mutate parent state</h3></div>${stateBadge("REJECTED")}</header>
    <div class="episode-rejection-banner" data-class="${classification}">
      <strong>${classification === "INTERFERENCE" ? "Measured interference / destructive-risk rejection" : "No-gain rejection"}</strong>
      <span>${episode.retentionReason}</span>
    </div>
    <div class="episode-rollback-proof">
      <div class="episode-proof" data-pass="${rollback.neuralUnchanged}"><small>Parent neural identity</small><strong>${rollback.neuralUnchanged ? "UNCHANGED" : "MISMATCH"}</strong></div>
      <div class="episode-proof" data-pass="${rollback.optimizerUnchanged}"><small>Parent optimizer identity</small><strong>${rollback.optimizerUnchanged ? "UNCHANGED" : "MISMATCH"}</strong></div>
      <div class="episode-proof" data-pass="${rollback.allocationUnchanged}"><small>Parent allocation identity</small><strong>${rollback.allocationUnchanged ? "UNCHANGED" : "MISMATCH"}</strong></div>
      <div class="episode-proof" data-pass="${rollback.retainedOptimizerStepsZero}"><small>Retained optimizer steps</small><strong>${episode.retainedOptimizerSteps}</strong></div>
      <div class="episode-proof" data-pass="${rollback.noChildGeneration}"><small>Child generation</small><strong>NONE</strong></div>
    </div>
  </section>`;
}

function diffPanel(episode) {
  return `<section class="episode-panel">
    <header><div><span class="eyebrow">Before / after</span><h3>Challenger effects vs committed parent state</h3></div></header>
    <div class="episode-diff-wrap"><table class="episode-diff">
      <thead><tr><th>Evidence</th><th>Before</th><th>Challenger after</th><th>Committed after</th><th>Coverage</th></tr></thead>
      <tbody>${diffRows(episode).map((row) => `<tr data-state="${String(row.state).toLowerCase()}"><th>${row.label}</th><td>${row.before}</td><td>${row.challenger}</td><td>${row.committed}</td><td>${stateBadge(row.state)}</td></tr>`).join("")}</tbody>
    </table></div>
    <p class="reconciliation-note">For rejected candidates, challenger measurements describe the disposable candidate only. The committed-after column remains bound to the parent state.</p>
  </section>`;
}

function evidenceButtons(stage) {
  if (!stage.evidence.length) return '<span class="episode-evidence-empty">No durable evidence refs observed.</span>';
  return stage.evidence.map((item) => `<button type="button" data-episode-evidence="${item.id}" data-evidence-type="${item.type}">${item.type}: ${item.id}</button>`).join("");
}

function replayPanel(episode) {
  const replay = replaySlice(episode, ui.stageIndex);
  return `<section class="episode-panel">
    <header><div><span class="eyebrow">Lifecycle replay</span><h3>Durable event / receipt reconstruction</h3></div><span>Stage ${replay.stageIndex + 1} / ${EPISODE_STAGES.length}</span></header>
    <div class="episode-replay">
      <div>
        <input aria-label="Episode replay stage" type="range" min="0" max="${EPISODE_STAGES.length - 1}" step="1" value="${replay.stageIndex}" data-stage-range />
        <div class="episode-stage-list">
          ${episode.stages.map((stage, index) => `<div class="episode-stage" data-active="${index === replay.stageIndex}">
            ${stateBadge(stage.state)}
            <button type="button" data-stage-index="${index}">${index + 1}. ${stage.label}</button>
          </div>`).join("")}
        </div>
      </div>
      <article class="episode-stage-detail">
        <span class="eyebrow">Selected stage</span>
        <h3>${replay.active.label}</h3>
        ${stateBadge(replay.active.state)}
        <p>${replay.active.detail}</p>
        <div class="episode-evidence">${evidenceButtons(replay.active)}</div>
      </article>
    </div>
  </section>`;
}

function picker() {
  return `<div class="episode-picker" aria-label="Episode fixture selector">
    ${EPISODE_FIXTURES.map((episode) => `<button type="button" data-episode-id="${episode.recordId}" aria-pressed="${episode.recordId === ui.selectedId}">
      ${episode.capabilityId} · ${episode.terminalState} · ${episode.retentionReason}
    </button>`).join("")}
  </div>`;
}

function bind(container, inspectEvidence) {
  container.querySelectorAll("[data-episode-id]").forEach((button) => button.addEventListener("click", () => {
    ui.selectedId = button.dataset.episodeId;
    ui.stageIndex = EPISODE_STAGES.length - 1;
    renderEpisodesView(container, inspectEvidence, ui.selectedId);
  }));
  container.querySelectorAll("[data-stage-index]").forEach((button) => button.addEventListener("click", () => {
    ui.stageIndex = Number(button.dataset.stageIndex);
    renderEpisodesView(container, inspectEvidence, ui.selectedId);
  }));
  container.querySelector("[data-stage-range]")?.addEventListener("input", (event) => {
    ui.stageIndex = Number(event.currentTarget.value);
    renderEpisodesView(container, inspectEvidence, ui.selectedId);
  });
  container.querySelectorAll("[data-episode-evidence]").forEach((button) => button.addEventListener("click", () => {
    inspectEvidence(button.dataset.episodeEvidence, button.dataset.evidenceType);
  }));
}

export function renderEpisodesView(container, inspectEvidence, selectedId = null) {
  if (selectedId) {
    const selected = episodeById(selectedId);
    if (selected.recordId === selectedId || selected.episodeId === selectedId || selected.candidateId === selectedId) {
      ui.selectedId = selected.recordId;
    }
  }
  const episode = episodeById(ui.selectedId);
  container.innerHTML = `<div class="episodes-view">
    <header class="episodes-heading"><div><span class="eyebrow">GUI06 · Learning Episodes</span><h2>Candidate transaction replay</h2></div><p>Replay only durable proposal, work, assessment, retention and finalization evidence. Controls are read-only and cannot mutate learner state.</p></header>
    <div class="episodes-fixture-notice" role="status"><strong>FIXTURE · DURABLE-CONTRACT SHAPE</strong><span>Rich episode rows are representative fixtures grounded in retention/runtime contracts because current CP02 episode and candidate records are intentionally narrow.</span></div>
    ${picker()}
    <div class="run-identity">CP03 record identity deep link · ${episodeDeepLink(episode.recordId)}</div>
    ${headerPanel(episode)}
    ${terminalProof(episode)}
    ${diffPanel(episode)}
    ${replayPanel(episode)}
  </div>`;
  bind(container, inspectEvidence);
}

export function currentEpisodeForTest() {
  return ui.selectedId;
}
