import { FRAME_QUERY, assertFramePage, sameFrameRequest } from "./frame-contract.mjs";
import { escapeText as esc, packingMetrics, visiblePosition, visibility } from "./frame-model.mjs";

const unavailable = "Unavailable";
const show = value => esc(value ?? unavailable);
const pair = (label, value) => `<dt>${esc(label)}</dt><dd>${show(value)}</dd>`;

export function renderPackingMetrics(examples, label) {
  const metrics = packingMetrics(examples);
  const labels = {
    atoms: "Raw atoms N", positions: "Neural positions F", ratio: "Packing N/F",
    fastFraction: "Fast-frame fraction", partial: "Partial positions", extended: "Extended positions",
    atomic: "Atomic positions", expansions: "Expansion count (sum)", passes: "Expansion passes (sum)",
    sidecarBytes: "Sidecar bytes (sum)", preparationMs: "Measured preparation ms (sum)",
  };
  return `<section class="frame-metrics" aria-label="${esc(label)}"><h3>${esc(label)}</h3>
    <p>Full-source receipt metrics · outside the frontier lens</p><dl>${Object.entries(metrics)
      .map(([key, value]) => pair(labels[key], value === null ? null : Number(value.toFixed(3)))).join("")}</dl></section>`;
}

export function renderFrameExample(example, frontier) {
  const identity = `<details class="frame-position"><summary>Receipt provenance · ${show(example.compiler?.version)}</summary><dl class="frame-identity">${pair("Receipt", example.receiptId)}${pair("Frame", example.frameId)}
    ${pair("Source", example.sourceId)}${pair("Generation manifest", example.generationManifest)}
    ${pair("Compiler version", example.compiler?.version)}${pair("Compiler digest", example.compiler?.digest)}
    ${pair("Source digest", example.sourceDigest)}${pair("Compiled digest", example.compiledDigest)}</dl></details>`;
  if (example.positions === null) return `${identity}<p role="status">Unavailable: sidecar/compiler detail was not recorded.</p>`;
  const positions = example.positions.map(position => {
    const view = visiblePosition(position, frontier);
    const metadata = view.metadata;
    const heading = metadata ? `${show(metadata.path)} · ${show(metadata.schema)}` : show(view.state);
    const rows = view.constituents.map(atom => atom.state
      ? `<tr><td>${atom.sourceOrder}</td><td colspan="6">${esc(atom.state)} · contents hidden</td></tr>`
      : `<tr><td>${atom.sourceOrder}</td><td>${esc(atom.atom)}</td><td>${esc(atom.role)}</td>
         <td>${atom.occurrenceIndex}</td><td>${esc(atom.semanticId)}</td><td>${esc(atom.sourceRef)}</td><td>Legal</td></tr>`).join("");
    const metadataHtml = metadata ? `<dl class="frame-identity">${pair("Schema tag", metadata.tag)}
      ${pair("Occurrence", metadata.occurrenceId)}${pair("Literal reason", metadata.reason)}${pair("Sidecar reference", metadata.sidecarRef)}</dl>` : "";
    const fields = metadata ? position.fields?.map(field => visibility(field.visibleAt, frontier) === "Legal"
      ? pair(field.name, field.value) : pair("Codec field", `${visibility(field.visibleAt, frontier)} · contents hidden`)).join("") : null;
    return `<details class="frame-position"><summary>Position ${position.index} · ${heading} · Expand constituents</summary>
      ${metadataHtml}<div class="frame-table-scroll"><table><caption>Source-addressed constituents · frontier ${frontier}</caption>
      <thead><tr><th>Order</th><th>Atom</th><th>Role</th><th>Occurrence index</th><th>Canonical semantic ID</th><th>Source reference</th><th>Legality</th></tr></thead>
      <tbody>${rows}</tbody></table></div><dl class="frame-identity">${fields ?? pair("Codec fields", unavailable)}</dl></details>`;
  }).join("");
  return `${identity}${positions}`;
}

// A controller instance owns one mount; disposal invalidates every pending query.
export class FrameQueryController {
  constructor(querySnapshot, publish) {
    this.querySnapshot = querySnapshot;
    this.publish = publish;
    this.epoch = 0;
  }
  dispose() { this.epoch += 1; }
  async load(request) {
    const epoch = ++this.epoch;
    this.publish({ state: "LOADING", request, page: null });
    try {
      const page = assertFramePage(await this.querySnapshot(request));
      if (!sameFrameRequest(request, page.request)) throw new TypeError("FRAME_INSPECTION_REQUEST_MISMATCH");
      if (epoch === this.epoch) this.publish({ state: page.state, request, page });
    } catch {
      if (epoch === this.epoch) this.publish({ state: "ERROR", request, page: null });
    }
  }
}

export function mountFrameExplorer(host, { querySnapshot, context, selectedId, onContext, onSelection }) {
  let selected = selectedId;
  host.innerHTML = `<div class="frame-explorer"><p class="frame-fixture-label">ILLUSTRATIVE FIXTURE · read-only · no live compiler producer</p>
    <p>Inspect recorded packing and causal visibility. Compression does not establish learned semantic competence.</p>
    <label>Fixture generation <select data-frame-generation aria-label="Frame fixture generation">
      <option value="7">7 · CURRENT FIXTURE</option><option value="6">6 · HISTORICAL FIXTURE</option></select></label>
    <p data-frame-state role="status"></p><div data-frame-results></div></div>`;
  const results = host.querySelector("[data-frame-results]");
  const generationSelect = host.querySelector("[data-frame-generation]");
  generationSelect.value = String(context.generation);
  const controller = new FrameQueryController(querySnapshot, result => {
    const state = host.querySelector("[data-frame-state]");
    state.textContent = `${result.state} · requested ${result.request.runId} / generation ${result.request.generation} / ${result.request.mode.toUpperCase()} FIXTURE`;
    results.replaceChildren();
    const page = result.page;
    if (!page?.operatorView) return;
    onContext(page.operatorView, page.request.mode);
    const examples = page.examples;
    if (!examples.length) return;
    results.innerHTML = `<p>Coverage ${esc(page.coverage)} · ${examples.length} returned fixture receipts</p>
      <label>Compiled example <select data-frame-example aria-label="Compiled example"><option value="">Select an exact frame</option>
      ${examples.map(example => `<option value="${esc(example.frameId)}">${esc(example.frameId)}</option>`).join("")}</select></label>
      <div data-frame-detail></div><details class="frame-position"><summary>Aggregate packing · ${examples.length} returned receipts</summary>
      ${renderPackingMetrics(examples, "All returned examples")}</details>`;
    const selector = results.querySelector("[data-frame-example]");
    const detail = results.querySelector("[data-frame-detail]");
    function selectExample(id) {
      selected = id;
      const example = examples.find(item => item.frameId === id);
      selector.value = example?.frameId ?? "";
      if (!example) {
        detail.textContent = id ? `MISSING: exact frame ${id} is absent from this generation.` : "Select a compiled example.";
        return;
      }
      const atoms = packingMetrics([example]).atoms;
      detail.innerHTML = `${renderPackingMetrics([example], "Selected example")}
        <p>Receipt provenance below is outside the frontier lens.</p>
        <label>Prediction frontier <select data-frame-frontier aria-label="Prediction frontier" ${atoms === null ? "disabled" : ""}>
        ${atoms === null ? '<option>Unavailable</option>' : Array.from({ length: atoms + 1 }, (_, p) => `<option value="${p}">${p} source atoms visible</option>`).join("")}</select></label>
        <div data-frame-positions></div>`;
      const frontier = detail.querySelector("[data-frame-frontier]");
      const draw = () => { detail.querySelector("[data-frame-positions]").innerHTML = renderFrameExample(example, Number(frontier.value) || 0); };
      if (atoms !== null) frontier.value = String(atoms);
      frontier.addEventListener("change", draw);
      draw();
    }
    selector.addEventListener("change", () => {
      onSelection(selector.value);
      selectExample(selector.value);
    });
    selectExample(selected);
  });
  const load = () => {
    const generation = Number(generationSelect.value);
    void controller.load({ schemaVersion: FRAME_QUERY, runId: context.runId,
      generation, mode: generation === 7 ? "current" : "historical" });
  };
  generationSelect.addEventListener("change", () => {
    selected = null;
    onSelection(null);
    load();
  });
  load();
  return { dispose: () => controller.dispose() };
}
