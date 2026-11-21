import { objectRefKey } from "./model.mjs";

export const OPERATOR_METADATA_KEY = "bilqis.mc.operator-metadata.v1";
export const OPERATOR_METADATA_SCHEMA = "bilqis.bamf.mission-control.operator-metadata/v2";
const LEGACY_OPERATOR_METADATA_SCHEMA = "bilqis.bamf.mission-control.operator-metadata/v1";

const MAX_PINS = 64;
const MAX_ANNOTATIONS = 128;
const MAX_SAVED_INVESTIGATIONS = 32;
const MAX_NOTE_LENGTH = 2000;
const MAX_INVESTIGATION_NAME_LENGTH = 120;

function isTarget(target) {
  return target && typeof target === "object" &&
    typeof target.kind === "string" && target.kind.length > 0 &&
    typeof target.id === "string" && target.id.length > 0 &&
    typeof target.runId === "string" && target.runId.length > 0 &&
    Number.isSafeInteger(target.generation) && target.generation >= 0 &&
    typeof target.fixture === "boolean";
}

function storedTarget(target) {
  return Object.freeze({
    kind: target.kind,
    id: target.id,
    label: typeof target.label === "string" && target.label ? target.label : target.id,
    runId: target.runId,
    generation: target.generation,
    fixture: target.fixture === true,
  });
}

export function emptyOperatorMetadata() {
  return Object.freeze({
    schema: OPERATOR_METADATA_SCHEMA,
    pins: Object.freeze([]),
    annotations: Object.freeze([]),
    savedInvestigations: Object.freeze([]),
  });
}

function isSavedContext(context) {
  return context && typeof context === "object" &&
    typeof context.runId === "string" && context.runId.length > 0 &&
    Number.isSafeInteger(context.generation) && context.generation >= 0 &&
    ["LIVE", "HISTORICAL"].includes(context.mode) &&
    typeof context.fixture === "boolean";
}

function validSavedInvestigation(saved) {
  return saved && typeof saved === "object" &&
    typeof saved.investigationId === "string" && saved.investigationId.length > 0 &&
    typeof saved.name === "string" && saved.name.trim().length > 0 &&
    saved.name.length <= MAX_INVESTIGATION_NAME_LENGTH &&
    Number.isSafeInteger(saved.createdAt) && saved.createdAt >= 0 &&
    typeof saved.view === "string" && saved.view.length > 0 &&
    isSavedContext(saved.context) &&
    (saved.selected === null || isTarget(saved.selected)) &&
    (saved.compareLeft === null || isTarget(saved.compareLeft)) &&
    (saved.compareRight === null || isTarget(saved.compareRight)) &&
    saved.authority === "OPERATOR_WORKSPACE_NON_AUTHORITATIVE";
}

function storedInvestigation(saved) {
  return Object.freeze({
    ...saved,
    context: Object.freeze({ ...saved.context }),
    selected: saved.selected ? storedTarget(saved.selected) : null,
    compareLeft: saved.compareLeft ? storedTarget(saved.compareLeft) : null,
    compareRight: saved.compareRight ? storedTarget(saved.compareRight) : null,
  });
}

function validAnnotation(annotation) {
  return annotation && typeof annotation === "object" &&
    typeof annotation.annotationId === "string" && annotation.annotationId.length > 0 &&
    isTarget(annotation.target) &&
    annotation.author === "LOCAL_OPERATOR" &&
    Number.isSafeInteger(annotation.createdAt) && annotation.createdAt >= 0 &&
    ["OBJECT", "GENERATION"].includes(annotation.scope) &&
    annotation.authority === "OPERATOR_NOTE_NON_AUTHORITATIVE" &&
    typeof annotation.body === "string" &&
    annotation.body.trim().length > 0 &&
    annotation.body.length <= MAX_NOTE_LENGTH;
}

function validateParsed(value) {
  const legacy = value?.schema === LEGACY_OPERATOR_METADATA_SCHEMA;
  const current = value?.schema === OPERATOR_METADATA_SCHEMA;
  if (!value || (!legacy && !current) ||
      !Array.isArray(value.pins) || value.pins.length > MAX_PINS ||
      !Array.isArray(value.annotations) || value.annotations.length > MAX_ANNOTATIONS ||
      !value.pins.every(isTarget) || !value.annotations.every(validAnnotation) ||
      (current && (!Array.isArray(value.savedInvestigations) ||
        value.savedInvestigations.length > MAX_SAVED_INVESTIGATIONS ||
        !value.savedInvestigations.every(validSavedInvestigation)))) {
    return null;
  }
  return Object.freeze({
    schema: OPERATOR_METADATA_SCHEMA,
    pins: Object.freeze(value.pins.map(storedTarget)),
    annotations: Object.freeze(value.annotations.map((annotation) => Object.freeze({
      ...annotation,
      target: storedTarget(annotation.target),
    }))),
    savedInvestigations: Object.freeze(
      current ? value.savedInvestigations.map(storedInvestigation) : [],
    ),
  });
}

export function loadOperatorMetadata(storage) {
  try {
    const raw = storage?.getItem?.(OPERATOR_METADATA_KEY);
    if (!raw) return emptyOperatorMetadata();
    return validateParsed(JSON.parse(raw)) ?? emptyOperatorMetadata();
  } catch (_error) {
    return emptyOperatorMetadata();
  }
}

export function saveOperatorMetadata(storage, metadata) {
  try {
    storage?.setItem?.(OPERATOR_METADATA_KEY, JSON.stringify(metadata));
    return true;
  } catch (_error) {
    return false;
  }
}

export function togglePin(metadata, target) {
  if (!isTarget(target)) return metadata;
  const key = objectRefKey(target);
  const exists = metadata.pins.some((pin) => objectRefKey(pin) === key);
  const pins = exists
    ? metadata.pins.filter((pin) => objectRefKey(pin) !== key)
    : [...metadata.pins, storedTarget(target)].slice(-MAX_PINS);
  return Object.freeze({
    ...metadata,
    pins: Object.freeze(pins),
  });
}

export function addAnnotation(metadata, target, body, {
  now = Date.now(),
  author = "LOCAL_OPERATOR",
  scope = target?.kind === "generation" ? "GENERATION" : "OBJECT",
} = {}) {
  const note = typeof body === "string" ? body.trim() : "";
  if (!isTarget(target) || !note || note.length > MAX_NOTE_LENGTH ||
      author !== "LOCAL_OPERATOR" || !["OBJECT", "GENERATION"].includes(scope) ||
      !Number.isSafeInteger(now) || now < 0) {
    return metadata;
  }
  const annotation = Object.freeze({
    annotationId: `annotation:${now}:${metadata.annotations.length + 1}`,
    target: storedTarget(target),
    author,
    createdAt: now,
    scope,
    authority: "OPERATOR_NOTE_NON_AUTHORITATIVE",
    body: note,
  });
  return Object.freeze({
    ...metadata,
    annotations: Object.freeze(
      [...metadata.annotations, annotation].slice(-MAX_ANNOTATIONS),
    ),
  });
}

export function saveInvestigation(metadata, {
  name,
  view,
  context,
  selected = null,
  compareLeft = null,
  compareRight = null,
}, { now = Date.now() } = {}) {
  const label = typeof name === "string" ? name.trim() : "";
  if (!label || label.length > MAX_INVESTIGATION_NAME_LENGTH ||
      typeof view !== "string" || !view || !isSavedContext(context) ||
      (selected !== null && !isTarget(selected)) ||
      (compareLeft !== null && !isTarget(compareLeft)) ||
      (compareRight !== null && !isTarget(compareRight)) ||
      !Number.isSafeInteger(now) || now < 0) {
    return metadata;
  }
  const saved = storedInvestigation({
    investigationId: `investigation:${now}:${metadata.savedInvestigations.length + 1}`,
    name: label,
    createdAt: now,
    view,
    context: {
      runId: context.runId,
      generation: context.generation,
      mode: context.mode,
      fixture: context.fixture === true,
    },
    selected,
    compareLeft,
    compareRight,
    authority: "OPERATOR_WORKSPACE_NON_AUTHORITATIVE",
  });
  return Object.freeze({
    ...metadata,
    savedInvestigations: Object.freeze(
      [...metadata.savedInvestigations, saved].slice(-MAX_SAVED_INVESTIGATIONS),
    ),
  });
}

export function removeSavedInvestigation(metadata, investigationId) {
  if (typeof investigationId !== "string" || !investigationId) return metadata;
  const savedInvestigations = metadata.savedInvestigations.filter(
    (saved) => saved.investigationId !== investigationId,
  );
  if (savedInvestigations.length === metadata.savedInvestigations.length) return metadata;
  return Object.freeze({ ...metadata, savedInvestigations: Object.freeze(savedInvestigations) });
}
