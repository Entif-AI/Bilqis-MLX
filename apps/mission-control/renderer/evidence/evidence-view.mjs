import {
  buildEvidenceRequest,
  criteriaForSelection,
  loadEvidencePage,
  loadRecordById,
  loadRecordLinks,
  mergeEvidencePages,
} from "./evidence-query.mjs";
import { renderEvidenceMarkup } from "./evidence-markup.mjs";

export {
  assertEvidencePage,
  buildEvidenceRequest,
  criteriaForSelection,
  loadEvidencePage,
  loadRecordById,
  loadRecordLinks,
  mergeEvidencePages,
  SEARCH_KINDS,
} from "./evidence-query.mjs";
export { renderEvidenceMarkup } from "./evidence-markup.mjs";

const ui = {
  contextKey: null, status: "idle", criteria: { kind: "context", value: "" },
  page: null, records: [], links: [], selected: null, selectedLinks: null,
  pendingRecordId: null, raw: false, error: null,
};

async function search(
  container, api, context, criteria, cursor = null, append = false, onSelection = null,
) {
  ui.status = "loading"; ui.error = null; ui.criteria = criteria;
  paintEvidenceView(container, api, context, onSelection);
  try {
    const page = await loadEvidencePage(api, context, criteria, cursor);
    ui.page = append ? mergeEvidencePages(ui.page, page) : page; ui.status = "ready";
    ui.records = append ? [...ui.records, ...(page.records ?? [])] : [...(page.records ?? [])];
    ui.links = append ? [...ui.links, ...(page.links ?? [])] : [...(page.links ?? [])];
    if (!append) {
      ui.selected = null; ui.selectedLinks = null; ui.raw = false;
      if (ui.pendingRecordId) {
        ui.selected = ui.records.find(
          (record) => record?.meta?.record_id === ui.pendingRecordId,
        ) ?? null;
        ui.pendingRecordId = null;
        if (ui.selected) {
          try { ui.selectedLinks = await loadRecordLinks(api, ui.selected); } catch (_error) { ui.selectedLinks = null; }
        }
      }
    }
  } catch (error) {
    ui.status = "error"; ui.error = error?.code ?? error?.message ?? "Evidence query failed";
    if (!append) {
      ui.page = null; ui.records = []; ui.links = [];
      ui.selected = null; ui.selectedLinks = null; ui.raw = false; ui.pendingRecordId = null;
    }
  }
  paintEvidenceView(container, api, context, onSelection);
}

async function select(container, api, context, record, onSelection = null) {
  ui.selected = record; ui.raw = false; ui.selectedLinks = null;
  onSelection?.({ kind: "evidence", id: record.meta.record_id });
  paintEvidenceView(container, api, context, onSelection);
  try { ui.selectedLinks = await loadRecordLinks(api, record); } catch (_error) { ui.selectedLinks = null; }
  paintEvidenceView(container, api, context, onSelection);
}

function bind(container, api, context, onSelection = null) {
  container.querySelector("#evidence-search-form")?.addEventListener("submit", (event) => {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void search(container, api, context, {
      kind: data.get("kind")?.toString() ?? "context",
      value: data.get("value")?.toString() ?? "",
    }, null, false, onSelection);
  });
  container.querySelectorAll("[data-evidence-record]").forEach((button) => button.addEventListener("click", () =>
    void select(container, api, context, ui.records[Number(button.dataset.evidenceRecord)], onSelection)));
  container.querySelectorAll("[data-evidence-target]").forEach((button) => button.addEventListener("click", async () => {
    const link = ui.links[Number(button.dataset.evidenceTarget)];
    if (!link?.target_record_id) return;
    const found = await loadRecordById(api, context, link.target_record_id);
    if (found.record) void select(container, api, context, found.record, onSelection);
  }));
  container.querySelectorAll("[data-evidence-selected-target]").forEach((button) => button.addEventListener("click", async () => {
    const link = ui.selectedLinks?.links?.[Number(button.dataset.evidenceSelectedTarget)];
    if (!link?.target_record_id) return;
    const found = await loadRecordById(api, context, link.target_record_id);
    if (found.record) void select(container, api, context, found.record, onSelection);
  }));
  container.querySelectorAll("[data-evidence-ref]").forEach((button) => button.addEventListener("click", () =>
    void search(container, api, context, {
      kind: "reference", value: button.dataset.evidenceRef,
    }, null, false, onSelection)));
  container.querySelector("[data-evidence-raw]")?.addEventListener("click", () => {
    ui.raw = !ui.raw; paintEvidenceView(container, api, context, onSelection);
  });
  container.querySelector("[data-evidence-more]")?.addEventListener("click", () =>
    void search(
      container, api, context, ui.criteria, ui.page?.next_cursor ?? null, true, onSelection,
    ));
}

function paintEvidenceView(container, api, context, onSelection = null) {
  container.innerHTML = renderEvidenceMarkup(ui);
  bind(container, api, context, onSelection);
}

export function renderEvidenceView(
  container, api, context, initialSelection = null, onSelection = null,
) {
  const criteria = criteriaForSelection(initialSelection);
  const key = `${context.mode}:${context.runId}:${context.generation}:${criteria.kind}:${criteria.value}`;
  if (ui.contextKey !== key) Object.assign(ui, {
    contextKey: key, status: "idle", criteria,
    page: null, records: [], links: [], selected: null, selectedLinks: null,
    pendingRecordId: initialSelection?.kind === "evidence" ? initialSelection.id : null,
    raw: false, error: null,
  });
  paintEvidenceView(container, api, context, onSelection);
  if (ui.status === "idle") {
    void search(container, api, context, ui.criteria, null, false, onSelection);
  }
}
