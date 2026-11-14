import {
  OPERATE_ACTIONS,
  actionSpec,
  authorizationPhrase,
  terminalReceipt,
} from "./operate-model.mjs";

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[char]));
}

function short(value) {
  if (value === null || value === undefined) return "UNAVAILABLE";
  const text = String(value);
  return /^[0-9a-f]{64}$/.test(text) ? `${text.slice(0, 9)}…${text.slice(-9)}` : text;
}

function stateBadge(state) {
  const token = String(state ?? "UNKNOWN").toLowerCase().replaceAll("_", "-");
  return `<span class="operate-state" data-operate-state="${esc(token)}">${esc(state ?? "UNKNOWN")}</span>`;
}

function actionCatalog(state) {
  return `<section class="operate-actions" aria-label="Supported operator actions">
    ${OPERATE_ACTIONS.map((item) => `<button type="button" data-operate-action="${esc(item.id)}"
      aria-pressed="${state.action === item.id}" ${item.supported ? "" : "disabled"}>
      <strong>${esc(item.label)}</strong>
      <small>${esc(item.description)}</small>
      <span>${item.supported ? (item.mutation ? "AUTHORIZATION REQUIRED" : "READ ONLY") : "UNAVAILABLE"}</span>
    </button>`).join("")}
  </section>`;
}

function parameterPanel(state) {
  const spec = actionSpec(state.action);
  const dryRun = spec?.dryRun ? `<label class="operate-check"><input type="checkbox" data-operate-dry-run ${state.dryRun ? "checked" : ""} /> Execute final command as a no-mutation dry-run</label>` : "";
  return `<section class="operate-panel">
    <header><div><span class="eyebrow">1 · Exact request</span><h3>${esc(spec?.label ?? "Action")}</h3></div>${stateBadge(state.phase)}</header>
    <p>${esc(spec?.description ?? "")}</p>
    ${dryRun}
    <label class="operate-json">CP05 parameters · JSON object
      <textarea data-operate-parameters rows="6" spellcheck="false">${esc(state.parametersText)}</textarea>
    </label>
    <p class="operate-hint">Only CP05/C11-admitted parameter keys are accepted. Paths typed here stay explicit operator input; no shell command is accepted.</p>
    <button type="button" class="operate-primary" data-operate-preview ${spec?.supported ? "" : "disabled"}>Run read-only preflight</button>
  </section>`;
}

function targetFact(label, value) {
  return `<div class="operate-fact"><small>${esc(label)}</small><strong title="${esc(value)}">${esc(short(value))}</strong></div>`;
}

function previewPanel(state) {
  const preview = state.preview;
  if (!preview) return `<section class="operate-panel operate-empty"><span class="eyebrow">2 · Preflight</span><p>No command has crossed the mutation boundary. Run a read-only preflight to resolve the exact CP05 target and consequence.</p></section>`;
  const target = preview.target ?? {};
  const profile = preview.preflight?.resource_profile ?? {};
  const mutating = preview.consequence?.mutation === "MUTATING";
  const conflicts = state.conflicts ?? [];
  return `<section class="operate-panel" data-command-consequence="${mutating ? "mutating" : "read-only"}">
    <header><div><span class="eyebrow">2 · Preflight</span><h3>Resolved target and consequence</h3></div>${stateBadge(preview.mode ?? "UNKNOWN")}</header>
    <div class="operate-consequence ${mutating ? "is-mutating" : "is-read-only"}">
      <strong>${mutating ? "MUTATION PERMITTED IF AUTHORIZED" : "NO NEURAL MUTATION"}</strong>
      <span>${mutating ? "The accepted owner command may change learner state." : "This operation is read-only or dry-run only."}</span>
    </div>
    <div class="operate-facts">
      ${targetFact("Target ref", preview.target_ref)}
      ${targetFact("Run", target.run_id)}
      ${targetFact("Generation", target.generation)}
      ${targetFact("Generation manifest", target.generation_manifest_sha256)}
      ${targetFact("Topology", target.topology_sha256)}
      ${targetFact("Factory release", target.factory_release_sha256)}
      ${targetFact("Semantic release", target.semantic_release_sha256)}
      ${targetFact("Source identity", target.source_identity)}
      ${targetFact("Admission policy", preview.preflight?.admission_policy)}
      ${targetFact("Expected postcondition", preview.expected_postcondition)}
    </div>
    <div class="operate-resource-strip">
      ${Object.entries(profile).map(([key, value]) => targetFact(key.replaceAll("_", " "), value)).join("")}
    </div>
    ${conflicts.length ? `<div class="operate-blocker" role="alert"><strong>STALE CONTEXT · authorization blocked</strong><ul>${conflicts.map((item) => `<li>${esc(item.label)}: shell ${esc(short(item.expected))} ≠ target ${esc(short(item.actual))}</li>`).join("")}</ul><span>Refresh the live command context and preflight again. GUI17 will not rebind silently.</span></div>` : ""}
  </section>`;
}

function authorizePanel(state) {
  const preview = state.preview;
  if (!preview) return "";
  const mutating = preview.consequence?.mutation === "MUTATING";
  const phrase = authorizationPhrase(preview);
  const blocked = (state.conflicts?.length ?? 0) > 0 || state.phase === "SUBMITTING";
  const authorized = !mutating || state.authorization === phrase;
  const label = preview.request?.dry_run ? "Execute dry-run" : mutating ? "Authorize exact command" : "Execute read-only command";
  return `<section class="operate-panel operate-authorization">
    <header><div><span class="eyebrow">3 · Deliberate authorization</span><h3>Bind action to reviewed target</h3></div>${stateBadge(mutating ? "HUMAN GATE" : "READ ONLY")}</header>
    <p>GUI17 submits the same reviewed intent with <code>expectedTargetRef</code>. If CP05 resolves a different target, dispatch is rejected before worker launch.</p>
    ${mutating ? `<label>Type <code>${esc(phrase)}</code> to authorize this exact mutation
      <input type="text" data-operate-authorization autocomplete="off" value="${esc(state.authorization)}" />
    </label>` : ""}
    <button type="button" class="operate-danger" data-operate-submit ${blocked || !authorized ? "disabled" : ""}>${esc(label)}</button>
  </section>`;
}

function lifecyclePanel(state) {
  const inspection = state.inspection;
  if (!inspection && state.phase !== "LOST_ACK" && state.phase !== "OUTCOME_UNKNOWN") return "";
  if (!inspection) {
    return `<section class="operate-panel operate-blocker"><span class="eyebrow">4 · Reconciliation</span><h3>Acknowledgement lost · outcome not inferred</h3><p>The command is not retried. GUI17 retains operation identity ${esc(state.preview?.operation_id)} and asks CP05 for authoritative readback.</p><button type="button" data-operate-reconcile>Reconcile operation</button></section>`;
  }
  const receipt = inspection.receipt;
  const terminal = terminalReceipt(receipt?.state);
  return `<section class="operate-panel">
    <header><div><span class="eyebrow">4 · Receipt and readback</span><h3>${esc(inspection.operation_id)}</h3></div>${stateBadge(receipt?.state)}</header>
    <div class="operate-lifecycle">
      <span>reviewed</span><span>preflighted</span><span>authorized</span><span>accepted/rejected</span><span>readback</span><span>${terminal ? "terminal" : "pending"}</span>
    </div>
    <div class="operate-facts">
      ${targetFact("Receipt record", receipt?.meta?.record_id)}
      ${targetFact("Target", receipt?.target_ref)}
      ${targetFact("Postcondition ref", receipt?.postcondition_ref)}
      ${targetFact("Error ref", receipt?.error_ref)}
    </div>
    <div class="operate-receipt-actions">
      <button type="button" data-operate-open-receipt>Open receipt</button>
      ${inspection.postcondition ? `<button type="button" data-operate-open-postcondition>Open postcondition</button>` : ""}
      ${!terminal || receipt?.state === "OUTCOME_UNKNOWN" ? `<button type="button" data-operate-reconcile>Reconcile operation</button>` : ""}
    </div>
    <details><summary>Literal bounded inspection</summary><pre>${esc(JSON.stringify(inspection, null, 2))}</pre></details>
  </section>`;
}

export function renderOperateMarkup(state, defense) {
  const unavailable = !defense?.mutationAllowed;
  return `<div class="operate-view" data-operate-phase="${esc(state.phase)}">
    <header class="operate-heading">
      <div><span class="eyebrow">GUI17 · Operate</span><h2>Command boundary, not another dashboard</h2></div>
      <div class="operate-zone"><strong>MUTATION ZONE</strong><span>Observation views cannot dispatch commands.</span></div>
    </header>
    ${unavailable ? `<section class="operate-panel operate-blocker" role="alert"><strong>LIVE COMMAND CONTEXT REQUIRED</strong><p>${esc(defense?.detail ?? "Mutation is unavailable in the current posture.")}</p></section>` : ""}
    ${state.error ? `<section class="operate-panel operate-error" role="alert"><strong>${esc(state.error.code ?? "GUI17_COMMAND_ERROR")}</strong><p>${esc(state.error.message ?? state.error)}</p></section>` : ""}
    ${actionCatalog(state)}
    ${parameterPanel(state)}
    ${previewPanel(state)}
    ${authorizePanel(state)}
    ${lifecyclePanel(state)}
  </div>`;
}

export function bindOperateInteractions(host, handlers) {
  host.querySelectorAll("[data-operate-action]").forEach((button) => {
    button.addEventListener("click", () => handlers.onAction?.(button.dataset.operateAction));
  });
  host.querySelector("[data-operate-dry-run]")?.addEventListener("change", (event) => handlers.onDryRun?.(event.currentTarget.checked));
  host.querySelector("[data-operate-parameters]")?.addEventListener("input", (event) => handlers.onParameters?.(event.currentTarget.value));
  host.querySelector("[data-operate-authorization]")?.addEventListener("input", (event) => handlers.onAuthorization?.(event.currentTarget.value));
  host.querySelector("[data-operate-preview]")?.addEventListener("click", () => handlers.onPreview?.());
  host.querySelector("[data-operate-submit]")?.addEventListener("click", () => handlers.onSubmit?.());
  host.querySelectorAll("[data-operate-reconcile]").forEach((button) => button.addEventListener("click", () => handlers.onReconcile?.()));
  host.querySelector("[data-operate-open-receipt]")?.addEventListener("click", () => handlers.onOpenReceipt?.());
  host.querySelector("[data-operate-open-postcondition]")?.addEventListener("click", () => handlers.onOpenPostcondition?.());
}
