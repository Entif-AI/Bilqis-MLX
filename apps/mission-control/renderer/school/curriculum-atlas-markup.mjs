import {
  blockerExplanation,
  buildCurriculumGraph,
  CURRICULUM_NODE_HEIGHT,
  boundedFamilyExpansion,
  curriculumConsequence,
  dependentsFor,
  gradeFamilySummary,
  nodeRelation,
  traceSelection,
} from "./curriculum-atlas-model.mjs";
import { curriculumLargeFixture } from "./curriculum-atlas-fixture.mjs";
import { FILTERS } from "./school-model.mjs";

export function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[char]);
}

export function route(view, kind, id) {
  const params = new URLSearchParams({ kind, id });
  return "#/view/" + view + "?" + params.toString();
}

function nodeState(node) {
  if (node.sourceState === "SOURCE_HELD") return "source-held";
  if (node.implementationState === "IMPLEMENTATION_UNCOVERED") return "uncovered";
  if (node.qualificationState === "QUALIFIED") return "qualified";
  if (node.lifecycleState === "EXPOSED") return "active";
  if (node.lifecycleState === "READY") return "eligible";
  return "staged";
}

function semanticDisplay(node, binding) {
  const concept = binding?.state === "PRESENT" ? binding.concepts[0] : null;
  const preferred = concept?.labels?.find((label) => label.role === "prefLabel") ??
    concept?.labels?.[0] ?? null;
  return Object.freeze({
    semanticId: concept?.semantic_id ?? node.semanticId,
    label: preferred?.value ?? node.label,
    authority: concept ? "SOURCE CANONICAL" : "FIXTURE DISPLAY ONLY",
    sourceLoci: concept?.source_loci ?? [],
  });
}

export function nodeCard(node, position, trace, visible, binding = null) {
  const display = semanticDisplay(node, binding);
  const relation = nodeRelation(trace, node.id);
  const newLabel = node.newThisGrade
    ? '<span class="curriculum-new">NEW THIS GRADE</span>'
    : "";
  const carryover = position.stratum === "current" && !node.newThisGrade
    ? '<span class="curriculum-carryover">CARRYOVER LEARNING</span>'
    : "";
  const blocked = node.blocker
    ? '<span class="curriculum-blocker">' + esc(node.blocker.code) + "</span>"
    : "";
  return '<button type="button" class="curriculum-node"' +
    ' data-curriculum-node="' + esc(node.id) + '"' +
    ' data-focus-key="curriculum:' + esc(node.id) + '"' +
    ' data-relation="' + relation + '"' +
    ' data-visible="' + visible + '"' +
    ' data-state="' + nodeState(node) + '"' +
    ' data-stratum="' + position.stratum + '"' +
    ' aria-pressed="' + (trace.selectedId === node.id) + '"' +
    ' style="left:' + position.x + 'px;top:' + position.y + 'px">' +
    newLabel + carryover +
    '<strong>' + esc(node.id) + '</strong>' +
    '<span>' + esc(display.label) + '</span>' +
    '<small>' + esc(display.semanticId) + ' · ' + esc(display.authority) + '</small>' +
    '<small>G' + esc(node.grade) + ' · ' + esc(node.lifecycleState) + ' · ' +
      esc(node.qualificationState) + '</small>' +
    '<small>NOW ' + node.now + '/' + node.total + ' · TOP ' + node.top + '/' +
      node.total + ' · debt ' + node.debt + '</small>' +
    blocked + '</button>';
}

export function edgeMarkup(edge, layout, trace) {
  const source = layout.positions.get(edge.source);
  const target = layout.positions.get(edge.target);
  if (!source || !target) return "";
  const sameColumn = source.x === target.x;
  const sx = source.x + 244;
  const halfNode = CURRICULUM_NODE_HEIGHT / 2;
  const sy = source.y + halfNode;
  const tx = sameColumn ? target.x + 122 : target.x;
  const ty = target.y + halfNode;
  const active = (trace.visibleUpstream.has(edge.source) &&
      (trace.selectedId === edge.target || trace.visibleUpstream.has(edge.target))) ||
    (trace.visibleDownstream.has(edge.target) &&
      (trace.selectedId === edge.source || trace.visibleDownstream.has(edge.source)));
  const path = sameColumn
    ? "M " + (source.x + 122) + " " + (source.y + CURRICULUM_NODE_HEIGHT) +
      " C " + (source.x + 300) + " " + (source.y + CURRICULUM_NODE_HEIGHT + 12) + ", " +
      (target.x + 300) + " " + (target.y - 8) + ", " + tx + " " + target.y
    : "M " + sx + " " + sy + " C " + (sx + 48) + " " + sy + ", " +
      (tx - 48) + " " + ty + ", " + tx + " " + ty;
  return '<path d="' + path + '" data-edge-kind="' + edge.kind +
    '" data-authority="' + edge.authority + '" data-trace="' +
    (active ? "active" : "context") + '" role="img" aria-label="' +
    esc(edge.source) + ' declared prerequisite of ' + esc(edge.target) + '">' +
    '<title>' + esc(edge.source) + ' → ' + esc(edge.target) +
    ' · declared prerequisite</title></path>';
}

export function tableMarkup(graph, visibility, semanticBindings = null) {
  const body = graph.nodes.map((node) => {
    const dependents = dependentsFor(graph, node.id);
    const display = semanticDisplay(node, semanticBindings?.get?.(node.id));
    return '<tr data-visible="' + visibility.get(node.id) + '">' +
      '<th scope="row"><button type="button" data-curriculum-node="' + esc(node.id) +
      '" data-focus-key="curriculum-table:' + esc(node.id) + '">' + esc(node.id) + '</button></th>' +
      '<td>' + esc(display.semanticId) + '<br><small>' + esc(display.label) + ' · ' +
        esc(display.authority) + '</small></td>' +
      '<td>' + esc(node.grade) + '</td>' +
      '<td>' + esc(node.lifecycleState) + ' · ' + esc(node.qualificationState) +
        (node.blocker ? ' · ' + esc(node.blocker.code) : '') + '</td>' +
      '<td>' + (node.prerequisites.length ? esc(node.prerequisites.join(", ")) : '—') + '</td>' +
      '<td>' + esc(dependents.join(", ") || '—') + '</td>' +
      '<td>NOW ' + node.now + '/' + node.total + ' · TOP ' + node.top + '/' +
        node.total + ' · debt ' + node.debt + '</td></tr>';
  }).join("");
  return '<div class="curriculum-table-wrap" role="region" aria-label="Curriculum semantic table" tabindex="0">' +
    '<table class="curriculum-table"><thead><tr><th>Capability</th><th>Semantic display identity</th>' +
    '<th>Grade</th><th>State</th><th>Prerequisites</th><th>Dependents</th><th>Evidence</th>' +
    '</tr></thead><tbody>' + body + '</tbody></table></div>';
}

function actionsMarkup(node, semanticBinding, ui) {
  const school = route("school", "capability", node.id);
  const evidence = route("evidence", "capability", node.id);
  let atlas = '<button type="button" data-resolve-semantic="' + esc(node.id) + '" data-focus-key="curriculum:resolve-semantic"' +
    (ui.semanticLoading === node.id ? ' disabled' : '') + '>' +
    (ui.semanticLoading === node.id ? 'Resolving canonical identity…' : 'Resolve canonical identity') +
    '</button>';
  if (semanticBinding?.state === "PRESENT") {
    atlas = semanticBinding.concepts.map((concept) =>
      '<a href="' + route("atlas", "semantic", concept.semantic_id) + '">' +
      'Open in Semantic Atlas · ' + esc(concept.semantic_id) + '</a>').join("");
  }
  return '<div class="curriculum-actions">' +
    '<button type="button" data-school-mode="matrix" data-focus-key="school-mode:matrix">Open in School</button>' +
    '<button type="button" disabled title="Capability Explorer is not landed yet (#1060).">' +
      'Open in Capability · unavailable</button>' + atlas +
    '<button type="button" disabled title="Lineage is available, but GUI14 does not expose a capability-specific generation route.">' +
      'Open in Lineage · capability route unavailable</button>' +
    '<a href="' + evidence + '">Open in Evidence</a>' +
    '<a href="' + school + '">Stable School deep link</a></div>';
}

export function dossierMarkup(graph, node, semanticBinding, ui) {
  const display = semanticDisplay(node, semanticBinding);
  const blocker = node.blocker ? blockerExplanation(node) : null;
  const dependents = dependentsFor(graph, node.id);
  const consequence = curriculumConsequence(graph, node.id);
  const consequenceBody = consequence.byGrade.length
    ? consequence.byGrade.map((group) =>
      '<p>Grade ' + esc(group.grade) + ' · ' + group.ids.length + ': ' +
      esc(group.ids.join(", ")) + '</p>').join("")
    : '<p>No later-grade reachable semantics in this bounded fixture.</p>';
  return '<section class="curriculum-dossier" aria-labelledby="curriculum-dossier-title">' +
    '<header><div><span class="eyebrow">Selected semantic</span><h2 id="curriculum-dossier-title">' +
      esc(node.id) + ' · ' + esc(node.label) + '</h2></div><span class="curriculum-state">' +
      esc(node.lifecycleState) + '</span></header>' +
    '<div class="curriculum-dossier-grid"><dl>' +
      '<dt>Capability identity</dt><dd>' + esc(node.id) + '</dd>' +
      '<dt>Semantic identity</dt><dd>' + esc(display.semanticId) + ' · ' +
        esc(display.label) + ' · ' + esc(display.authority) + '</dd>' +
      '<dt>Canonical source loci</dt><dd>' +
        (display.sourceLoci.length ? esc(display.sourceLoci.join(", ")) : 'UNAVAILABLE') + '</dd>' +
      '<dt>Grade / first introduced</dt><dd>' + esc(node.grade) + ' / ' + esc(node.firstIntroducedGrade) + '</dd>' +
      '<dt>Lifecycle / qualification</dt><dd>' + esc(node.lifecycleState) + ' / ' + esc(node.qualificationState) + '</dd>' +
      '<dt>NOW / TOP / debt / P(RET)</dt><dd>' + node.now + '/' + node.total + ' · ' +
        node.top + '/' + node.total + ' · ' + node.debt + ' · ' + (node.pRet ?? 'NOT MEASURED') + '</dd>' +
      '<dt>Prerequisites</dt><dd>' + (node.prerequisites.length ? esc(node.prerequisites.join(", ")) : 'none') + '</dd>' +
      '<dt>Direct downstream unlock count</dt><dd>' + dependents.length + '</dd>' +
      '<dt>Direct dependents</dt><dd>' + (dependents.length ? esc(dependents.join(", ")) : 'none') + '</dd>' +
      '<dt>Transitive downstream</dt><dd>' + traceSelection(graph, node.id, "unlocks").downstream.size + '</dd>' +
      '<dt>Source refs</dt><dd>' + esc(node.sourceRefs.join(", ") || 'none') + '</dd>' +
      '<dt>Source / Factory release</dt><dd>UNAVAILABLE · shared School fixture exposes source family, not release hashes</dd>' +
      '<dt>Last relevant event</dt><dd>' + esc(node.lastRelevantEvent) + '</dd>' +
      '<dt>Correction / requalification</dt><dd>' + esc(node.requalificationState) + '</dd></dl>' +
    '<div class="curriculum-investigation"><p><strong>Experience rule.</strong> Grade is a display stratum. ' +
      'Every graph edge is a declared School prerequisite. No edge is inferred from layout, grade order, or learned similarity.</p>' +
      (blocker
        ? '<div class="curriculum-why"><strong>Why blocked?</strong><span>' + esc(blocker.code) +
          ' · ' + esc(blocker.detail) + '</span><small>' +
          esc(blocker.evidence.join(", ") || 'No more specific evidence projected.') + '</small></div>'
        : '<div class="curriculum-why"><strong>Why blocked?</strong><span>Not blocked by an explicit projected condition.</span></div>') +
      '<div class="curriculum-history"><strong>Bounded event history</strong><ol>' +
        node.historyEvents.map((event) => '<li data-history-posture="' + esc(event.posture) + '">' +
          '<span>' + esc(event.posture) + '</span> · ' + esc(event.kind) + ' · ' +
          esc(event.label) + '</li>').join("") +
      '</ol></div>' +
      '<button type="button" data-consequence-toggle data-focus-key="curriculum:consequence" aria-expanded="' + ui.consequenceOpen +
        '">Show curriculum consequence</button>' +
      (ui.consequenceOpen
        ? '<div class="curriculum-consequence"><strong>Declared downstream reachability only · no scheduling guarantee</strong>' +
          consequenceBody + '</div>'
        : '') +
      '<div class="semantic-binding"><strong>Canonical semantic identity</strong><span>' +
        (semanticBinding ? esc(semanticBinding.state) + ' · ' + esc(semanticBinding.reason)
          : 'UNRESOLVED · use exact-release CP03 lookup') +
      '</span></div>' + actionsMarkup(node, semanticBinding, ui) +
    '</div></div></section>';
}

export function toolbarMarkup(graph, snapshot, ui) {
  const grades = [...new Set(graph.nodes.map((node) => node.grade))].sort();
  const states = [...new Set(graph.nodes.flatMap((node) =>
    [node.lifecycleState, node.qualificationState]))].sort();
  const families = [...new Set(graph.nodes.map((node) => node.family))].sort();
  const options = (values, selected) => '<option value="all">All</option>' + values.map((value) =>
    '<option value="' + esc(value) + '"' + (selected === value ? ' selected' : '') +
    '>' + esc(value) + '</option>').join("");
  return '<section class="curriculum-toolbar" aria-label="Curriculum Atlas controls">' +
    '<form data-curriculum-search><label>Find a semantic <input name="search" data-focus-key="curriculum:search" value="' + esc(ui.search) +
      '" placeholder="Capability, label, fixture semantic ID…" /></label><button type="submit" data-focus-key="curriculum:find">Find</button>' +
      '<button type="button" data-jump-active data-focus-key="curriculum:jump-active">Jump to active · ' + esc(snapshot.activeId) + '</button></form>' +
    '<div class="trace-controls" role="group" aria-label="Trace mode">' +
      [["prerequisites","Prerequisites"],["both","Both directions"],["unlocks","Unlocks"]]
        .map(([id,label]) => '<button type="button" data-trace-mode="' + id +
          '" data-focus-key="curriculum:trace:' + id + '" aria-pressed="' + (ui.traceMode === id) + '">' + label + '</button>').join("") +
    '</div><div class="curriculum-filters">' +
      '<label>Grade <select data-filter="grade" data-focus-key="curriculum:filter:grade">' + options(grades, ui.grade) + '</select></label>' +
      '<label>State <select data-filter="state" data-focus-key="curriculum:filter:state">' + options(states, ui.state) + '</select></label>' +
      '<label>Family <select data-filter="family" data-focus-key="curriculum:filter:family">' + options(families, ui.family) + '</select></label>' +
      '<label>Attention <select data-filter="issue" data-focus-key="curriculum:filter:issue">' +
        [...new Set(["all", "debt", "blocked", ...FILTERS])].map((value) =>
          '<option value="' + value + '"' + (ui.issue === value ? ' selected' : '') + '>' +
          value + '</option>').join("") + '</select></label>' +
      '<label><input type="checkbox" data-new-only data-focus-key="curriculum:filter:new"' + (ui.newOnly ? ' checked' : '') +
        ' /> Newly introduced only</label><button type="button" data-reset-filters data-focus-key="curriculum:reset">Reset / focus all</button>' +
    '</div></section>';
}

export function scaleMarkup(ui) {
  const large = curriculumLargeFixture(243);
  const largeGraph = buildCurriculumGraph({ nodes: large, currentGrade: "C" });
  const preview = gradeFamilySummary(large).slice(0, 12);
  let expansion = "";
  if (ui.familyFocus) {
    const [grade, family] = ui.familyFocus.split("::");
    const expanded = boundedFamilyExpansion(large, grade, family, 12);
    const selected = expanded.find((node) => node.id === ui.largeSelectedId) ?? expanded[0] ?? null;
    const directDependents = selected ? dependentsFor(largeGraph, selected.id) : [];
    const transitive = selected
      ? [...traceSelection(largeGraph, selected.id, "unlocks").downstream].slice(0, 24)
      : [];
    expansion = '<div class="curriculum-scale-expansion"><strong>Bounded family expansion · ' +
      esc(ui.familyFocus) + '</strong><div class="family-summary">' + expanded.map((node) =>
        '<button type="button" data-large-semantic="' + esc(node.id) +
        '" data-focus-key="curriculum:large:' + esc(node.id) + '">' + esc(node.id) + '</button>').join("") +
      '</div>' + (selected ? '<p><strong>Selected:</strong> ' + esc(selected.id) +
        ' · prerequisites ' + esc(selected.prerequisites.join(", ") || "none") +
        ' · direct dependents ' + esc(directDependents.join(", ") || "none") + '</p>' +
        '<p><strong>Bounded transitive unlocks:</strong> ' + esc(transitive.join(", ") || "none") +
        (traceSelection(largeGraph, selected.id, "unlocks").downstream.size > transitive.length
          ? ' · additional descendants withheld until further expansion'
          : '') + '</p>' : '') + '</div>';
  }
  return '<details class="curriculum-scale"><summary>Scale / progressive disclosure · 243-row representative School fixture</summary>' +
    '<p>Large scopes summarize by grade + semantic family. Family and semantic expansion are bounded; graph identity remains capability-stable.</p>' +
    '<div class="family-summary">' + preview.map((group) =>
      '<button type="button" data-family-focus="' + esc(group.grade) + '::' + esc(group.family) +
      '" data-focus-key="curriculum:family:' + esc(group.grade) + ':' + esc(group.family) + '">' +
      'G' + esc(group.grade) + ' · ' + esc(group.family) + ' · ' + group.count + '</button>').join("") +
    '</div>' + expansion + '</details>';
}
