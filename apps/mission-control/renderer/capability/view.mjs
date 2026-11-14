import { SECTIONS, RECORD_FAMILIES, escapeHtml as e, historyEntries, metricText } from "./model.mjs";

function metric(label, value) {
  return `<div class="dossier-metric"><dt>${e(label)}</dt><dd>${e(metricText(value))}</dd>
    <small>${e(value?.origin ?? "UNMEASURED")}</small></div>`;
}
function entryRow(entry) {
  const facts = entry.values.map((item) => `<div><dt>${e(item.name)}</dt><dd>${e(metricText(item.value))}
    <small>${e(item.value.origin ?? item.value.state)}</small></dd></div>`).join("");
  const refs = entry.refs.map((ref) => `<button type="button" data-evidence="${e(ref)}" data-entry="${e(entry.entry_id)}">${e(ref)}</button>`).join("");
  const related = entry.related_id ? `<button type="button" data-related-kind="${e(entry.related_kind)}"
    data-related-id="${e(entry.related_id)}">Open ${e(entry.related_kind)} · ${e(entry.related_id)}</button>` : "";
  return `<article class="dossier-entry" data-kind="${e(entry.kind)}"><header><div><span class="eyebrow">${e(entry.kind)}</span>
    <h3>${e(entry.label)}</h3></div><span class="dossier-stamp">G${entry.generation} · t=${entry.observed_at}</span></header>
    <dl class="dossier-facts">${facts}</dl><details><summary>Evidence & related objects · ${entry.refs.length} refs</summary>
    <div class="dossier-links">${refs}${related}</div></details></article>`;
}
export function renderDossier(state) {
  const { dossier: d, lens, status, fixture } = state;
  const notice = `<div class="dossier-notice" role="status">${fixture ? "FIXTURE · Synthetic demonstration · " : "SERVICE · "}
    ${e(lens?.mode)} · ${e(lens?.runId)} · Generation ${e(lens?.generation)} · ${e(status)} · Coverage ${e(state.coverage ?? "UNKNOWN")}</div>`;
  const controls = `<button type="button" data-reload>Reload dossier</button>${state.cursor ? '<button type="button" data-more>Load more capabilities</button>' : ""}`;
  const markers = state.markers?.length ? `<details open><summary>Projection markers</summary><pre>${e(JSON.stringify(state.markers, null, 2))}</pre></details>` : "";
  if (!d) return `${notice}<div class="dossier-empty"><h2>${e(status)}</h2><p>${state.cursor ? "More capability pages remain. Absence is not established." : "No dossier available for this exact capability and generation."}</p>
    <p>${e(state.error)}</p>${controls}</div>${markers}`;
  const metrics = [["NOW", d.now], ["TOP", d.top], ["Total", d.total], ["Debt", d.debt],
    ["Retention", d.retention], ["Eligibility", d.eligibility], ["Qualification", d.qualification], ["Source", d.source_state]];
  const sections = SECTIONS.map((section) => {
    const entries = section === "history" ? historyEntries(d) : d.entries.filter((entry) => entry.section === section);
    return `<section id="dossier-${section}" class="dossier-section" aria-label="${section}"><h2>${section === "history" ? "Learning history" : section}</h2>
      ${entries.length ? entries.map(entryRow).join("") : '<p class="dossier-empty">UNAVAILABLE · No observations supplied.</p>'}</section>`;
  }).join("");
  return `${notice}<div class="dossier-heading"><div><span class="eyebrow">Capability Explorer</span><h2>${e(d.name)}</h2>
    <code>${e(d.capability_id)}</code></div><div>${controls}</div></div><dl class="dossier-metrics">${metrics.map(([l, v]) => metric(l, v)).join("")}</dl>
    <nav class="dossier-tabs" aria-label="Dossier sections">${SECTIONS.map((section) => `<button type="button" data-section="${section}">${section === "history" ? "Learning history" : section}</button>`).join("")}</nav>
    ${sections}<details class="dossier-provenance"><summary>Exact dossier identity & provenance</summary><pre>${e(JSON.stringify(d.meta, null, 2))}</pre></details>
    ${markers}`;
}

export function renderEvidence(ref, entry, page, error = null) {
  return `<h2>Literal evidence</h2><code>${e(ref)}</code><p>${e(error ?? page?.state ?? "LOADING")}</p>
    ${entry ? `<pre>${e(JSON.stringify(entry, null, 2))}</pre>` : ""}
    ${(page?.links ?? []).map((link) => `<article><pre>${e(JSON.stringify(link, null, 2))}</pre>${link.target_record_id ?
      `<label>Record family <select data-family>${RECORD_FAMILIES.map((family) => `<option ${family === "capability" ? "selected" : ""}>${family}</option>`).join("")}</select></label>
      <button type="button" data-record="${e(link.target_record_id)}">${e(link.target_ref)} · Inspect record</button>` : '<p>Unresolved reference · No target record supplied.</p>'}</article>`).join("")}
    ${page?.next_cursor ? '<button type="button" data-evidence-more>Load more evidence links</button>' : ""}
    ${page?.records?.length ? `<pre>${e(JSON.stringify(page.records, null, 2))}</pre>` : ""}`;
}
