import { buildAppUri } from "./app-uri.mjs";

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function refLabel(ref) {
  return ref ? `${ref.kind} · ${ref.label ?? ref.id}` : "Empty";
}

function exactContext(ref) {
  return ref ? `${ref.runId} · generation ${ref.generation}` : "Choose from the inspector";
}

function compareMarkup(interaction, comparison) {
  const left = interaction.compare.left;
  const right = interaction.compare.right;
  return `<div class="investigation-compare">
    <div class="compare-slots">
      <article data-compare-side="left"><small>Left</small><strong>${esc(refLabel(left))}</strong><span>${esc(exactContext(left))}</span>
        ${left ? '<button type="button" data-clear-compare="left">Clear left</button>' : ""}</article>
      <article data-compare-side="right"><small>Right</small><strong>${esc(refLabel(right))}</strong><span>${esc(exactContext(right))}</span>
        ${right ? '<button type="button" data-clear-compare="right">Clear right</button>' : ""}</article>
    </div>
    <p class="investigation-doctrine" data-compare-state="${esc(comparison.state)}">
      ${esc(comparison.note)}
    </p>
    ${comparison.rows.length ? `<div class="investigation-table-wrap"><table class="investigation-table">
      <thead><tr><th>Dimension</th><th>Left</th><th>Right</th><th>State</th></tr></thead>
      <tbody>${comparison.rows.map((row) => `<tr data-state="${esc(row.state.toLowerCase())}">
        <th>${esc(row.label)}</th><td>${esc(row.left)}</td><td>${esc(row.right)}</td>
        <td>${esc(row.state)}${row.reason ? `<small>${esc(row.reason)}</small>` : ""}</td>
      </tr>`).join("")}</tbody>
    </table></div>` : ""}
  </div>`;
}

function pinsMarkup(metadata) {
  if (!metadata.pins.length) {
    return '<p class="investigation-empty">No operator pins. Pin a selected object from the inspector.</p>';
  }
  return `<div class="pin-list">${metadata.pins.map((pin, index) => `<article ${pin.kind ? `data-object-kind="${esc(pin.kind)}" data-object-id="${esc(pin.id)}"` : ""}>
    <div><small>${esc(pin.kind)} · generation ${pin.generation}</small><strong>${esc(pin.label)}</strong><span>${esc(pin.runId)}</span></div>
    <div><button type="button" data-open-pin="${index}">Open exact pin</button><button type="button" data-remove-pin="${index}">Remove</button></div>
  </article>`).join("")}</div>`;
}

function annotationsMarkup(metadata, currentRef) {
  const notes = metadata.annotations.filter((note) =>
    !currentRef || (note.target.kind === currentRef.kind && note.target.id === currentRef.id &&
      note.target.runId === currentRef.runId && note.target.generation === currentRef.generation));
  return `<div class="annotation-workspace">
    <div class="annotation-list">
      ${notes.length ? notes.map((note) => `<article>
        <header><strong>OPERATOR NOTE · NON-AUTHORITATIVE</strong><small>${esc(note.author)} · ${new Date(note.createdAt).toISOString()} · ${esc(note.scope)}</small></header>
        <p>${esc(note.body)}</p>
        <small>${esc(note.target.kind)} · ${esc(note.target.id)} · ${esc(note.target.runId)} · generation ${note.target.generation}</small>
      </article>`).join("") : '<p class="investigation-empty">No notes for this exact object context.</p>'}
    </div>
    ${currentRef ? `<form data-annotation-form>
      <label>Operator note for ${esc(currentRef.id)}
        <textarea name="body" maxlength="2000" required></textarea>
      </label>
      <p>Stored locally as operator metadata. This note is not source truth, evidence, or learner state.</p>
      <button type="submit">Save non-authoritative note</button>
    </form>` : '<p>Select an object before adding a note.</p>'}
  </div>`;
}

export function renderInvestigationMarkup({
  state,
  interaction,
  metadata,
  currentRef,
  comparison,
  currentAvailable,
}) {
  const panel = interaction.panel;
  const compareCount = Number(Boolean(interaction.compare.left)) +
    Number(Boolean(interaction.compare.right));
  const appUri = currentRef ? buildAppUri(currentRef) : null;
  const panelBody = panel === "compare" ? compareMarkup(interaction, comparison)
    : panel === "pins" ? pinsMarkup(metadata)
      : panel === "annotations" ? annotationsMarkup(metadata, currentRef)
        : "";
  return `<div class="investigation-strip-row">
    <form data-time-lens-form>
      <label>As of generation
        <input name="generation" type="number" min="0" step="1" value="${state ? state.context.generation : ""}" ${state ? "" : "disabled"} />
      </label>
      <button type="submit" ${state ? "" : "disabled"}>Apply historical</button>
      <button type="button" data-use-current ${currentAvailable ? "" : "disabled"}>Use verified current</button>
    </form>
    <div class="investigation-tabs" role="group" aria-label="Investigation tools">
      <button type="button" data-investigation-panel="compare" aria-pressed="${panel === "compare"}">Compare · ${compareCount}/2</button>
      <button type="button" data-investigation-panel="pins" aria-pressed="${panel === "pins"}">Pins · ${metadata.pins.length}</button>
      <button type="button" data-investigation-panel="annotations" aria-pressed="${panel === "annotations"}">Notes · ${metadata.annotations.length}</button>
    </div>
    <div class="investigation-link">${appUri
      ? `<small>Exact app URI</small><code>${esc(appUri)}</code>`
      : "<small>Select an object to expose its exact app URI.</small>"}</div>
  </div>
  <section id="investigation-panel" aria-label="Investigation panel" ${panel === "closed" ? "hidden" : ""}>
    ${panelBody}
  </section>`;
}
