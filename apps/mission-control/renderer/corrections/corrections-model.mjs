import { CORRECTION_FIXTURE } from "./corrections-fixture.mjs";

const TERMINAL_EVIDENCE_STATES = new Set(["RECOMPUTED", "REQUALIFIED"]);

export function correctionById(id = CORRECTION_FIXTURE.correction.id) {
  if (id !== CORRECTION_FIXTURE.correction.id) throw new RangeError(`CORRECTION_UNKNOWN:${id}`);
  return CORRECTION_FIXTURE.correction;
}

export function nodeById(id) {
  return CORRECTION_FIXTURE.nodes.find((node) => node.id === id) ?? null;
}

export function evidencedDescendants(rootId = CORRECTION_FIXTURE.correction.currentRevision) {
  const outgoing = new Map();
  for (const edge of CORRECTION_FIXTURE.edges) {
    const list = outgoing.get(edge.from) ?? [];
    list.push(edge.to);
    outgoing.set(edge.from, list);
  }
  const seen = new Set([rootId]);
  const queue = [rootId];
  while (queue.length) {
    const from = queue.shift();
    for (const to of outgoing.get(from) ?? []) {
      if (seen.has(to)) continue;
      seen.add(to);
      queue.push(to);
    }
  }
  return Object.freeze(CORRECTION_FIXTURE.nodes.filter((node) => seen.has(node.id)));
}

export function impactRows() {
  return Object.freeze(evidencedDescendants().map((node) => Object.freeze({
    id: node.id,
    kind: node.kind,
    state: node.state,
    evidenceRefs: node.evidenceRefs,
  })));
}

export function unknownInfluenceRows() {
  return Object.freeze(impactRows().filter((row) => row.state === "UNAVAILABLE_UNKNOWN"));
}

export function requalificationQueue() {
  return CORRECTION_FIXTURE.queue;
}

export function historyFor(id) {
  return Object.freeze(CORRECTION_FIXTURE.history
    .filter((entry) => Object.hasOwn(entry.states, id))
    .map((entry) => Object.freeze({
      historyId: entry.id,
      phase: entry.phase,
      generation: entry.atGeneration,
      state: entry.states[id],
      receipt: entry.receipt,
    })));
}

export function assertReceiptBackedTerminalStates() {
  for (const row of impactRows()) {
    if (!TERMINAL_EVIDENCE_STATES.has(row.state)) continue;
    if (!row.evidenceRefs.length) throw new TypeError(`CORRECTION_TERMINAL_STATE_UNRECEIPTED:${row.id}`);
  }
  for (const entry of CORRECTION_FIXTURE.history) {
    for (const [id, state] of Object.entries(entry.states)) {
      if (state === "REQUALIFIED" && !entry.receipt) {
        throw new TypeError(`CORRECTION_REQUALIFIED_UNRECEIPTED:${id}`);
      }
    }
  }
  return true;
}

export function correctionDeepLink(id = CORRECTION_FIXTURE.correction.id) {
  return `#view=corrections&kind=correction&id=${encodeURIComponent(id)}`;
}
