import { DossierController } from "./controller.mjs";
import { buildQuery, escapeHtml as e } from "./model.mjs";
import { fixtureQuery, FIXTURE_RUN } from "./fixture.mjs";
import { renderDossier, renderEvidence } from "./view.mjs";

export function createCapabilityExplorer({ host, changeLens, openObject, serviceQuery, resolvePins }) {
  let lens;
  let capabilityId;
  let fixture = false;
  let key = null;
  let evidenceEpoch = 0;
  let evidencePage;
  let evidenceRef;
  let evidenceEntry;
  const query = (request) => fixture ? fixtureQuery(request) : serviceQuery(request);
  const controller = new DossierController(query, () => draw());
  function draw() {
    if (!lens) return;
    host.innerHTML = `<div class="capability-explorer"><div class="capability-tools"><label>Data source<select id="dossier-source"><option value="service" ${!fixture ? "selected" : ""}>Control-plane service</option>
      <option value="fixture" ${fixture ? "selected" : ""}>FIXTURE · Synthetic demonstration</option></select></label>
      <form id="dossier-lens"><label>Run ID<input name="run" value="${e(lens.runId)}" required></label>
      <label>Generation<input name="generation" type="number" min="0" step="1" value="${lens.generation}" required></label>
      <label>Capability ID<input name="capability" value="${e(capabilityId)}" required></label><button>Inspect as of</button></form></div>
      <div id="dossier-host">${renderDossier(controller.state)}</div><section id="evidence-detail" aria-live="polite" tabindex="-1"></section></div>`;
    host.querySelector("#dossier-source").onchange = (event) => {
      fixture = event.target.value === "fixture";
      changeLens({ runId: fixture ? FIXTURE_RUN : "", generation: fixture ? 3 : 0,
        mode: "HISTORICAL", fixture }, "B.AND");
    };
    host.querySelector("#dossier-lens").onsubmit = (event) => {
      event.preventDefault();
      const data = new FormData(event.target);
      const generation = Number(data.get("generation"));
      if (!Number.isSafeInteger(generation) || generation < 0) return;
      changeLens({ runId: data.get("run"), generation, mode: "HISTORICAL", fixture }, data.get("capability"));
    };
    host.querySelector("[data-reload]").onclick = () => void controller.load(lens, capabilityId, fixture);
    host.querySelector("[data-more]")?.addEventListener("click", () => void controller.more());
    host.querySelectorAll("[data-section]").forEach((button) => {
      button.onclick = () => {
        const section = host.querySelector(`#dossier-${button.dataset.section}`);
        section.tabIndex = -1;
        section.focus(); section.scrollIntoView({ block: "start" });
      };
    });
    host.querySelectorAll("[data-evidence]").forEach((button) => {
      button.onclick = () => {
        evidenceEntry = controller.state.dossier.entries.find((entry) => entry.entry_id === button.dataset.entry);
        evidenceRef = button.dataset.evidence;
        void showEvidence();
      };
    });
    host.querySelectorAll("[data-related-id]").forEach((button) => {
      button.onclick = () => openObject({ kind: button.dataset.relatedKind, id: button.dataset.relatedId });
    });
    if (controller.state.dossier) resolvePins(controller.state.dossier.meta);
  }
  async function showEvidence(cursor = null, override = null) {
    const epoch = ++evidenceEpoch;
    const target = host.querySelector("#evidence-detail");
    const request = buildQuery(lens, override ?? { family: "reference", schema_version: null,
      reference: evidenceRef, cursor });
    target.innerHTML = renderEvidence(evidenceRef, evidenceEntry, null);
    target.focus(); target.scrollIntoView({ block: "start" });
    try {
      const page = await query(request);
      if (epoch !== evidenceEpoch || !target.isConnected) return;
      evidencePage = cursor ? { ...page, links: [...evidencePage.links, ...page.links] } : page;
      target.innerHTML = renderEvidence(evidenceRef, evidenceEntry, evidencePage);
      target.querySelector("[data-evidence-more]")?.addEventListener("click", () => void showEvidence(page.next_cursor));
      target.querySelectorAll("[data-record]").forEach((button) => {
        button.onclick = () => void showEvidence(null, { family: button.parentElement.querySelector("[data-family]").value,
          schema_version: null, record_id: button.dataset.record, reference: null, cursor: null });
      });
    } catch (error) {
      if (epoch === evidenceEpoch && target.isConnected) target.innerHTML = renderEvidence(evidenceRef, evidenceEntry, null, error.message);
    }
  }
  return {
    update(state) {
      const nextId = state.selected?.kind === "capability" ? state.selected.id : "B.AND";
      const nextKey = JSON.stringify([state.context.runId, state.context.generation,
        state.context.mode, state.context.fixture, nextId]);
      if (nextKey === key) return;
      evidenceEpoch += 1;
      key = nextKey; lens = state.context; capabilityId = nextId;
      fixture = Boolean(state.context.fixture);
      void controller.load(lens, capabilityId, fixture);
    },
    hide() { evidenceEpoch += 1; key = null; controller.epoch += 1; },
  };
}
