export const EVIDENCE_KINDS = Object.freeze({
  measured: { label: "Measured", marker: "M", cue: "solid" },
  inferred: { label: "Estimated / inferred", marker: "≈", cue: "dashed" },
  source: { label: "Source-authoritative", marker: "S", cue: "double" },
  derived: { label: "Learned / derived", marker: "D", cue: "single" },
});

export const STATUS_GROUPS = Object.freeze({
  health: ["healthy", "attention", "invalid"],
  availability: ["held", "unavailable", "denied", "unknown", "stale", "partial"],
  operation: ["proposed", "accepted", "attempted", "reconciled"],
  time: ["live", "historical"],
});

export const STATUS_META = Object.freeze({
  healthy: ["✓", "Healthy"],
  attention: ["!", "Attention"],
  invalid: ["×", "Invalid evidence / custody"],
  held: ["Ⅱ", "Held"],
  unavailable: ["∅", "Unavailable"],
  denied: ["⊘", "Denied"],
  unknown: ["?", "Unknown"],
  stale: ["↻", "Stale"],
  partial: ["◐", "Partial"],
  proposed: ["◇", "Proposed"],
  accepted: ["◆", "Accepted"],
  attempted: ["→", "Attempted"],
  reconciled: ["✓", "Reconciled"],
  live: ["●", "LIVE"],
  historical: ["◷", "HISTORICAL / AS-OF"],
});

export function statusBadge(status, detail = "") {
  const [marker, label] = STATUS_META[status] ?? ["?", status];
  return `<span class="status-badge" data-state="${status}"><span aria-hidden="true">${marker}</span><span>${label}</span>${detail ? `<small>${detail}</small>` : ""}</span>`;
}

export function evidenceValue(value, evidenceKind, authorityKind, unit = "") {
  const evidence = EVIDENCE_KINDS[evidenceKind];
  const authority = EVIDENCE_KINDS[authorityKind];
  return `<span class="evidence-value" data-evidence="${evidenceKind}" data-authority="${authorityKind}">
    <span class="value">${value}${unit}</span>
    <small><b aria-hidden="true">${evidence.marker}</b> ${evidence.label} · <b aria-hidden="true">${authority.marker}</b> ${authority.label}</small>
  </span>`;
}

export function semanticStateInventory() {
  return Object.values(STATUS_GROUPS).flat();
}
