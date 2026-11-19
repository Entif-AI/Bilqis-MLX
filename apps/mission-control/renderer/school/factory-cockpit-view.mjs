import { t } from "../foundation/i18n.mjs";
import { testIdAttribute } from "../foundation/test-hooks.mjs";
import { escapeText as esc } from "../frames/frame-model.mjs";

function short(value) {
  if (!value) return t("school.common.notExposed");
  return value.length > 18 ? `${value.slice(0, 9)}…${value.slice(-7)}` : value;
}

function list(values) {
  return values?.length ? values.map((value) => esc(value)).join(" · ") : esc(t("school.common.none"));
}

function topology(lineage) {
  const value = lineage?.at(-1)?.topology;
  if (!value) return esc(t("school.common.notExposed"));
  if (value.knowledge !== "EXACT") {
    return `<span data-factory-topology="compatibility">${esc(value.knowledge)}<br><small>${esc(value.view_schema_version)} · ${esc(value.compatibility_ref ?? t("school.common.notExposed"))}</small></span>`;
  }
  return `<span data-factory-topology="exact">${esc(value.architecture_id)} · ${value.layers}L · Q${value.query_heads}/KV${value.kv_heads} · d${value.model_dimension}/ff${value.feed_forward_dimension} · ctx ${value.context_length}<br><small>${esc(value.view_schema_version)} · ${esc(value.topology_schema)} · ${esc(short(value.topology_sha256))}</small></span>`;
}

function frontier(record) {
  const grades = record.grade_frontier?.length
    ? record.grade_frontier.map((grade) =>
      `<span class="factory-grade"><strong>${esc(grade.grade_id)}</strong> ${esc(grade.capability_ids.join(", "))}</span>`).join("")
    : `<span class="factory-grade">${list(record.capability_ids)}</span>`;
  const dependencies = record.dependency_edges?.length
    ? record.dependency_edges.map(([capability, prerequisite]) => `${esc(capability)} → ${esc(prerequisite)}`).join(" · ")
    : esc(t("school.common.none"));
  return `${grades}<span class="factory-grade"><strong>${esc(t("school.factory.frontier.dependencies"))}</strong> ${dependencies}</span><span class="factory-grade"><strong>${esc(t("school.factory.frontier.promoted"))}</strong> ${list(record.promoted_capability_ids)}</span><span class="factory-grade"><strong>${esc(t("school.factory.frontier.debt"))}</strong> ${list(record.debt_capability_ids)}</span>`;
}

function blockers(record) {
  if (!record.blockers?.length) return esc(t("school.common.none"));
  return record.blockers.map((item) =>
    `<span class="factory-blocker"><strong>${esc(item.reason)}</strong><br>${esc(item.owner_ref)} · ${esc(item.evidence_ref)}</span>`).join("");
}

function lineage(record) {
  if (!record.lineage?.length) return esc(t("school.common.notExposed"));
  return record.lineage.map((item) =>
    `<span class="factory-lineage">${esc(item.run_id)} · ${item.generation === null ? "?" : `g${item.generation}`} · ${esc(item.checkpoint_lineage_id)}<br><small>${esc(short(item.generation_manifest_sha256))} · checkpoint ${esc(short(item.checkpoint_sha256))}</small></span>`).join("");
}

export function renderFactoryCockpitView(container, { rows = [], state = "EMPTY", coverage = "UNKNOWN", onInspect = null } = {}) {
  const body = rows.length ? rows.map((record) => `
    <tr data-factory-subject="${esc(record.subject_sha256)}" data-currency="${esc(record.currency_state)}">
      <th scope="row"><button type="button" data-factory-inspect="${esc(record.subject_sha256)}">${esc(record.subject_kind)}<br><small>${esc(short(record.subject_sha256))}</small><br><small>${esc(t("school.factory.semantic"))} ${esc(short(record.semantic_release_sha256))}</small></button></th>
      <td><span class="factory-state">${esc(record.lifecycle_state)}</span><br><span class="factory-state">${esc(record.delivery_status)}</span></td>
      <td><span class="factory-state">${esc(record.currency_state)}</span></td>
      <td>${frontier(record)}</td>
      <td>${blockers(record)}</td>
      <td>${lineage(record)}</td>
      <td>${topology(record.lineage)}</td>
      <td>${record.receipt_refs?.length ?? 0}<br><small>${esc(t("school.factory.receipt.qualification"))} ${esc(short(record.qualification_receipt_sha256))}</small><br><small>${esc(t("school.factory.receipt.admission"))} ${esc(short(record.admission_receipt_sha256))}</small></td>
    </tr>`).join("") : `<tr><td colspan="8">${esc(t("school.factory.empty", { state }))}</td></tr>`;

  container.innerHTML = `<section class="school-view factory-cockpit" ${testIdAttribute("school", "factory", "cockpit")}>
    <header class="school-heading"><div><span class="eyebrow">${esc(t("school.factory.eyebrow"))}</span><h2>${esc(t("school.factory.title"))}</h2></div><p>${esc(t("school.factory.summary"))}</p></header>
    <div class="factory-authority" data-factory-authority="human-only"><strong>${esc(t("school.factory.authority.title"))}</strong> ${esc(t("school.factory.authority.body"))}</div>
    <p class="coverage-counter">${esc(t("school.factory.coverage", { state, coverage, count: rows.length }))}</p>
    <div class="matrix-scroll"><table class="school-matrix factory-table"><caption>${esc(t("school.factory.caption"))}</caption><thead><tr>
      <th>${esc(t("school.factory.column.subject"))}</th><th>${esc(t("school.factory.column.status"))}</th><th>${esc(t("school.factory.column.currency"))}</th><th>${esc(t("school.factory.column.frontier"))}</th><th>${esc(t("school.factory.column.blockers"))}</th><th>${esc(t("school.factory.column.lineage"))}</th><th>${esc(t("school.factory.column.topology"))}</th><th>${esc(t("school.factory.column.receipts"))}</th>
    </tr></thead><tbody>${body}</tbody></table></div>
  </section>`;

  container.querySelectorAll("[data-factory-inspect]").forEach((button) => {
    button.addEventListener("click", () => {
      const record = rows.find((item) => item.subject_sha256 === button.dataset.factoryInspect);
      if (!record || typeof onInspect !== "function") return;
      onInspect({
        kind: "factory",
        id: record.subject_sha256,
        details: {
          [t("school.factory.inspector.semantic")]: record.semantic_release_sha256,
          [t("school.factory.inspector.lifecycle")]: `${record.lifecycle_state} / ${record.delivery_status} / ${record.currency_state}`,
          [t("school.factory.inspector.receipts")]: record.receipt_refs,
          [t("school.factory.inspector.authority")]: record.admission_authority,
        },
      });
    });
  });
}
