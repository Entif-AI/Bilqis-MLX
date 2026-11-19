import { t } from "../foundation/i18n.mjs";
import { authorizationPresentation, evidencePosture } from "./model.mjs";

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function hookPart(value) {
  const normalized = String(value).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
  return normalized || "item";
}

function refLabel(ref) {
  return ref
    ? t("investigation.ref.label", { kind: ref.kind, label: ref.label ?? ref.id })
    : t("investigation.ref.empty");
}

function exactContext(ref) {
  return ref
    ? t("investigation.context.exact", { runId: ref.runId, generation: ref.generation })
    : t("investigation.context.empty");
}

function stateLabel(state) {
  return t(`investigation.state.${String(state).toLowerCase()}`);
}

function compareSlot(side, ref) {
  const label = t(`investigation.compare.${side}`);
  const clear = t(`investigation.compare.clear${side[0].toUpperCase()}${side.slice(1)}`);
  return `<div data-compare-side="${side}" data-test-id="investigation-compare-${side}">
    <dt>${esc(label)}</dt>
    <dd><strong>${esc(refLabel(ref))}</strong><span>${esc(exactContext(ref))}</span>
      ${ref ? `<button type="button" data-clear-compare="${side}" data-test-id="investigation-compare-clear-${side}">${esc(clear)}</button>` : ""}
    </dd>
  </div>`;
}

function compareMarkup(interaction, comparison) {
  return `<div class="investigation-compare" data-test-id="investigation-compare-workspace">
    <dl class="compare-slots" data-test-id="investigation-compare-slots">
      ${compareSlot("left", interaction.compare.left)}
      ${compareSlot("right", interaction.compare.right)}
    </dl>
    <p class="investigation-doctrine" data-compare-state="${esc(comparison.state)}" data-test-id="investigation-compare-state">
      <strong>${esc(stateLabel(comparison.state))}</strong><span>${esc(comparison.note)}</span>
    </p>
    ${comparison.rows.length ? `<div class="investigation-table-wrap" data-test-id="investigation-compare-table-wrap"><table class="investigation-table" data-test-id="investigation-compare-table">
      <thead><tr><th>${esc(t("investigation.compare.dimension"))}</th><th>${esc(t("investigation.compare.left"))}</th><th>${esc(t("investigation.compare.right"))}</th><th>${esc(t("investigation.compare.state"))}</th></tr></thead>
      <tbody>${comparison.rows.map((row) => `<tr data-state="${esc(row.state.toLowerCase())}" data-test-id="investigation-compare-row-${hookPart(row.key)}">
        <th>${esc(row.label)}</th><td>${esc(row.left)}</td><td>${esc(row.right)}</td>
        <td><strong>${esc(stateLabel(row.state))}</strong>${row.reason ? `<small>${esc(row.reason)}</small>` : ""}</td>
      </tr>`).join("")}</tbody>
    </table></div>` : ""}
  </div>`;
}

function pinsMarkup(metadata) {
  if (!metadata.pins.length) {
    return `<p class="investigation-empty" data-test-id="investigation-pins-empty">${esc(t("investigation.pins.empty"))}</p>`;
  }
  return `<ul class="pin-list" data-test-id="investigation-pins-list">${metadata.pins.map((pin, index) => `<li ${pin.kind ? `data-object-kind="${esc(pin.kind)}" data-object-id="${esc(pin.id)}"` : ""} data-test-id="investigation-pin-${index}">
    <div class="pin-identity"><strong>${esc(pin.label)}</strong><span>${esc(t("investigation.pins.context", { kind: pin.kind, generation: pin.generation }))}</span><code>${esc(pin.runId)}</code><code>${esc(pin.id)}</code></div>
    <div class="pin-actions"><button type="button" data-open-pin="${index}" data-test-id="investigation-pin-open-${index}">${esc(t("investigation.pins.open"))}</button><button type="button" data-remove-pin="${index}" data-test-id="investigation-pin-remove-${index}">${esc(t("investigation.pins.remove"))}</button></div>
  </li>`).join("")}</ul>`;
}

function annotationsMarkup(metadata, currentRef) {
  const notes = metadata.annotations.filter((note) =>
    !currentRef || (note.target.kind === currentRef.kind && note.target.id === currentRef.id &&
      note.target.runId === currentRef.runId && note.target.generation === currentRef.generation));
  return `<div class="annotation-workspace" data-test-id="investigation-notes-workspace">
    <ul class="annotation-list" data-test-id="investigation-notes-list">
      ${notes.length ? notes.map((note, index) => `<li data-test-id="investigation-note-${index}">
        <header><strong>${esc(t("investigation.notes.marker"))}</strong><small>${esc(note.author)} · ${new Date(note.createdAt).toISOString()} · ${esc(note.scope)}</small></header>
        <p>${esc(note.body)}</p>
        <small>${esc(t("investigation.notes.context", { kind: note.target.kind, id: note.target.id, runId: note.target.runId, generation: note.target.generation }))}</small>
      </li>`).join("") : `<li class="investigation-empty" data-test-id="investigation-notes-empty">${esc(t("investigation.notes.empty"))}</li>`}
    </ul>
    ${currentRef ? `<form data-annotation-form data-test-id="investigation-note-form">
      <label>${esc(t("investigation.notes.target", { id: currentRef.id }))}
        <textarea name="body" maxlength="2000" required data-test-id="investigation-note-body"></textarea>
      </label>
      <small data-test-id="investigation-note-target-context">${esc(t("investigation.notes.exactTarget", currentRef))}</small>
      <p>${esc(t("investigation.notes.help"))}</p>
      <button type="submit" data-test-id="investigation-note-save">${esc(t("investigation.notes.save"))}</button>
    </form>` : `<p data-test-id="investigation-note-select">${esc(t("investigation.notes.select"))}</p>`}
  </div>`;
}

function savedInvestigationsMarkup(metadata, state) {
  const saved = metadata.savedInvestigations ?? [];
  const list = saved.length
    ? `<ul class="saved-investigation-list" data-test-id="investigation-saved-list">${saved.map((item, index) => `<li data-test-id="investigation-saved-${index}">
      <div class="saved-investigation-identity"><strong>${esc(item.name)}</strong><span>${esc(t("investigation.saved.context", {
        mode: item.context.mode,
        runId: item.context.runId,
        generation: item.context.generation,
      }))}</span><small>${esc(t("investigation.saved.nonAuthoritative"))}</small></div>
      <div class="pin-actions"><button type="button" data-open-saved="${esc(item.investigationId)}" data-test-id="investigation-saved-open-${index}">${esc(t("investigation.saved.open"))}</button><button type="button" data-remove-saved="${esc(item.investigationId)}" data-test-id="investigation-saved-remove-${index}">${esc(t("investigation.saved.remove"))}</button></div>
    </li>`).join("")}</ul>`
    : `<p class="investigation-empty" data-test-id="investigation-saved-empty">${esc(t("investigation.saved.empty"))}</p>`;
  const form = state ? `<form data-saved-investigation-form data-test-id="investigation-saved-form">
    <label>${esc(t("investigation.saved.name"))}<input name="name" maxlength="120" required data-test-id="investigation-saved-name" /></label>
    <small>${esc(t("investigation.saved.help"))}</small>
    <button type="submit" data-test-id="investigation-saved-save">${esc(t("investigation.saved.save"))}</button>
  </form>` : "";
  return `<div class="saved-investigation-workspace">${list}${form}</div>`;
}

function authorityMarkup(state) {
  const auth = authorizationPresentation(state);
  const item = (label, value, id) => `<div data-test-id="investigation-authority-${id}"><dt>${esc(label)}</dt><dd>${esc(value)}</dd></div>`;
  return `<div class="investigation-authority" data-test-id="investigation-authority-workspace" data-generalized="${auth.generalized}">
    <p>${esc(t(auth.generalized ? "investigation.authority.generalizedHelp" : "investigation.authority.ownerHelp"))}</p>
    <dl>${item(t("investigation.authority.state"), auth.state, "state")}${item(t("investigation.authority.principal"), auth.principal, "principal")}${item(t("investigation.authority.roles"), auth.roles.join(", "), "roles")}${item(t("investigation.authority.inspect"), auth.inspectionScopes.join(", ") || t("investigation.value.none"), "inspection-scopes")}${item(t("investigation.authority.action"), auth.actionScopes.join(", ") || t("investigation.value.none"), "action-scopes")}${item(t("investigation.authority.source"), auth.sourceRef, "source")}</dl>
  </div>`;
}

function postureMarkup(state) {
  const posture = evidencePosture(state);
  return `<div class="investigation-posture" data-test-id="investigation-evidence-posture">
    <span data-posture="mode" data-test-id="investigation-posture-mode">${esc(t("investigation.posture.mode", { value: posture.mode }))}</span>
    <span data-posture="custody" data-test-id="investigation-posture-custody">${esc(t("investigation.posture.custody", { value: posture.custody }))}</span>
    <span data-posture="authority" data-test-id="investigation-posture-authority">${esc(t("investigation.posture.authority", { value: posture.authority }))}</span>
    <span data-posture="coverage" data-test-id="investigation-posture-coverage">${esc(t("investigation.posture.coverage", { value: posture.coverage }))}</span>
  </div>`;
}

function timeLensMarkup(state, currentAvailable) {
  const generation = state?.context.generation;
  const lens = state
    ? t(state.context.historicalPinned ? "investigation.time.historical" : "investigation.time.current", { generation })
    : t("investigation.context.empty");
  return `<details class="investigation-time" data-test-id="investigation-time-lens">
    <summary data-test-id="investigation-time-toggle"><span>${esc(t("investigation.time.label"))}</span><strong data-test-id="investigation-time-state">${esc(lens)}</strong></summary>
    <form data-time-lens-form data-test-id="investigation-time-form">
      <label>${esc(t("investigation.time.generation"))}
        <input name="generation" type="number" min="0" step="1" value="${state ? generation : ""}" ${state ? "" : "disabled"} data-test-id="investigation-time-generation" />
      </label>
      <div><button type="submit" ${state ? "" : "disabled"} data-test-id="investigation-time-apply">${esc(t("investigation.time.apply"))}</button>
      <button type="button" data-use-current ${currentAvailable ? "" : "disabled"} data-test-id="investigation-time-current">${esc(t("investigation.time.currentAction"))}</button></div>
    </form>
  </details>`;
}

export function renderInvestigationMarkup({ state, interaction, metadata, currentRef, comparison, currentAvailable }) {
  const panel = interaction.panel;
  const compareCount = Number(Boolean(interaction.compare.left)) + Number(Boolean(interaction.compare.right));
  const panelBody = panel === "compare" ? compareMarkup(interaction, comparison)
    : panel === "pins" ? pinsMarkup(metadata)
      : panel === "annotations" ? annotationsMarkup(metadata, currentRef)
        : panel === "saved" ? savedInvestigationsMarkup(metadata, state)
          : panel === "authority" ? authorityMarkup(state)
        : "";
  return `<div class="investigation-strip-row" data-test-id="investigation-toolbar">
    <div class="investigation-context-tools">${timeLensMarkup(state, currentAvailable)}${postureMarkup(state)}</div>
    <div class="investigation-tabs" role="group" aria-label="${esc(t("investigation.toolbar.label"))}" data-test-id="investigation-tools">
      <button type="button" data-investigation-panel="compare" data-test-id="investigation-open-compare" aria-pressed="${panel === "compare"}">${esc(t("investigation.panel.compare", { count: compareCount }))}</button>
      <button type="button" data-investigation-panel="pins" data-test-id="investigation-open-pins" aria-pressed="${panel === "pins"}">${esc(t("investigation.panel.pins", { count: metadata.pins.length }))}</button>
      <button type="button" data-investigation-panel="annotations" data-test-id="investigation-open-notes" aria-pressed="${panel === "annotations"}">${esc(t("investigation.panel.notes", { count: metadata.annotations.length }))}</button>
      <button type="button" data-investigation-panel="saved" data-test-id="investigation-open-saved" aria-pressed="${panel === "saved"}">${esc(t("investigation.panel.saved", { count: metadata.savedInvestigations?.length ?? 0 }))}</button>
      <button type="button" data-investigation-panel="authority" data-test-id="investigation-open-authority" aria-pressed="${panel === "authority"}">${esc(t("investigation.panel.authority"))}</button>
    </div>
  </div>
  <section id="investigation-panel" aria-label="${esc(t("investigation.toolbar.label"))}" data-test-id="investigation-panel" ${panel === "closed" ? "hidden" : ""}>
    ${panelBody}
  </section>`;
}
