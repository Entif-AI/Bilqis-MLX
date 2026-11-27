import { observedHomeState } from "./home-observed.mjs";
import { formatDurationSeconds } from "../foundation/temporal.mjs";

const QUERY_SCHEMA = "bilqis.bamf.control-plane.query/v1";
const PRESENT = "PRESENT";
export const HISTORY_SUMMARY_SCHEMA = "bilqis.bamf.mission-control.learning-history-summary/v1";
const NOTIFICATION_EVENT_FAMILIES = new Set([
  "capability.graduated", "grade.promoted", "semantic.release.changed",
  "graph.materialized", "qualification.gate.changed", "blocker.changed",
  "drift.detected", "warning.failure",
]);

export const HOME_FAMILIES = Object.freeze([
  "run", "school", "capability", "episode", "semantic", "neural", "resource", "correction", "teacher", "notification",
]);

export function queryRequest(family, context, overrides = {}) {
  const historical = context?.mode === "HISTORICAL";
  return Object.freeze({
    schema: QUERY_SCHEMA,
    family,
    mode: historical ? "historical" : "current",
    run_id: context?.runId ?? null,
    record_id: null,
    schema_version: null,
    generation: historical ? context.generation : null,
    frontier_id: null,
    as_of: null,
    reference: null,
    cursor: null,
    limit: 32,
    ...overrides,
  });
}

export function familyForEvent(event) {
  const family = String(event?.event_family ?? "");
  if (family.startsWith("lesson.") || family.startsWith("candidate.")) return "episode";
  if (family.startsWith("capability.")) return "capability";
  if (family.startsWith("semantic.")) return "semantic";
  if (family.startsWith("teacher.")) return "teacher";
  if (family.startsWith("correction.")) return "correction";
  if (family.startsWith("resource.")) return "resource";
  if (family.startsWith("run.") || family.startsWith("checkpoint.")) return "run";
  return null;
}

export function isNotificationEvent(event) {
  return NOTIFICATION_EVENT_FAMILIES.has(String(event?.event_family ?? ""));
}

export function familiesForEvent(event) {
  const name = event?.event_family;
  if (name === "operator.action.state") return ["status"];
  const families = new Set();
  const family = familyForEvent(event);
  if (family) families.add(family);
  if (isNotificationEvent(event)) families.add("notification");
  if (name === "capability.graduated" || name === "grade.promoted" ||
      name === "semantic.release.changed" || name === "qualification.gate.changed") {
    families.add("school");
    families.add("capability");
  }
  if (name === "graph.materialized") families.add("semantic");
  if (name === "resource.health.sample") families.add("neural");
  if (name === "blocker.changed" || name === "drift.detected") families.add("correction");
  return [...families];
}

function value(record, field) {
  const datum = record?.[field];
  return datum?.state === PRESENT ? datum.value : null;
}

function latest(records, schema) {
  return records.filter((record) => record?.schema_version === schema).at(-1) ?? null;
}

function newestFirst(records) {
  return records.toSorted((left, right) => {
    const leftTime = left?.meta?.observed_at ?? left?.meta?.materialized_at ?? -1;
    const rightTime = right?.meta?.observed_at ?? right?.meta?.materialized_at ?? -1;
    return rightTime - leftTime;
  });
}

function pageRecords(pages, family) {
  const page = pages[family];
  return page?.accepted === true && Array.isArray(page.records) ? page.records : [];
}

function pageState(pages, family) {
  const page = pages[family];
  return page?.accepted === true ? page.state : "UNAVAILABLE";
}

function completePage(pages, family) {
  const page = pages[family];
  return page?.accepted === true && page.coverage === "COMPLETE" &&
    ["PRESENT", "EMPTY"].includes(page.state) && page.truncated !== true;
}

function observedCount(rows, complete) {
  return rows.length || (complete ? 0 : null);
}

function measuredSum(rows, field) {
  const values = rows.map((row) => value(row, field));
  return values.length && values.every(Number.isFinite)
    ? values.reduce((sum, item) => sum + item, 0) : null;
}

function ratio(numerator, denominator) {
  return Number.isFinite(numerator) && Number.isFinite(denominator) && denominator > 0
    ? numerator / denominator : null;
}

function observedBytes(value, divisor, unit) {
  return Number.isFinite(value) ? `${(value / divisor).toFixed(1)} ${unit}` : null;
}

function visitScoreSummary(score) {
  if (!score || score.state !== "MEASURED") return score?.state ?? null;
  if (![score.before, score.after, score.total, score.delta].every(Number.isInteger)) return "UNKNOWN";
  const delta = score.delta > 0 ? `+${score.delta}` : `${score.delta}`;
  return `${score.before}/${score.total} -> ${score.after}/${score.total} (${delta})`;
}

function protectedSummary(evidence) {
  if (!evidence) return null;
  const state = evidence.protected_scope_state ?? "UNKNOWN";
  const measured = Array.isArray(evidence.protected)
    ? evidence.protected.filter((item) => item?.state === "MEASURED").length : 0;
  return measured ? `${state} · ${measured} measured` : state;
}

export function classifyLearning({ retained = 0, freshRetainedImprovements = 0, regressions = 0 } = {}) {
  if (regressions > 0) return "REGRESSION";
  if (freshRetainedImprovements > 0) return "IMPROVING";
  if (retained > 0) return "THROUGHPUT_ONLY";
  return retained === null || freshRetainedImprovements === null ? "UNKNOWN" : "NO_FRESH_GAIN";
}

export function homeStatus(model) {
  const invalidStates = new Set(["INVALID", "INVALIDITY", "CONFLICT", "DENIED", "REVOKED", "INCOMPATIBLE"]);
  const regression = model?.learningStatus === "REGRESSION" ||
    model?.pulse?.some((event) => ["regress", "regression"].includes(event.kind)) === true;
  const blocked = model?.attention?.some((item) => item.severity === "blocker" || item.kind === "blocked") === true;
  const invalidity = Object.values(model?.state ?? {}).some((state) => invalidStates.has(state)) ||
    model?.attention?.some((item) => item.severity === "invalid") === true;
  return Object.freeze({
    running: model?.runtime?.running ?? null,
    learning: model?.learningStatus ?? "UNKNOWN",
    regression: regression || (model?.evidence?.regression === false ? null : false),
    blocked: blocked || (model?.evidence?.attention === false ? null : false),
    invalidity: invalidity || (model?.evidence?.attention === false ? null : false),
    attentionPriority: regression || blocked || invalidity ? "primary" : "secondary",
  });
}

export function projectionFromPages(pages, context) {
  const capabilities = pageRecords(pages, "capability");
  const episodes = pageRecords(pages, "episode");
  const schoolRecords = pageRecords(pages, "school");
  const runRecords = pageRecords(pages, "run");
  const semanticRecords = pageRecords(pages, "semantic");
  const neuralRecords = pageRecords(pages, "neural");
  const resources = pageRecords(pages, "resource");
  const corrections = pageRecords(pages, "correction");
  const teachers = pageRecords(pages, "teacher");
  const notifications = pageRecords(pages, "notification");

  const run = latest(runRecords, "bilqis.bamf.mission-control.run-context/v1");
  const neural = latest(neuralRecords, "bilqis.bamf.mission-control.neural-runtime-sample/v1");
  const acceptedStepDurationMs = value(neural, "step_duration_ms");
  const observed = Object.freeze({
    ...observedHomeState(runRecords, context, run),
    acceptedStepDurationSeconds: Number.isFinite(acceptedStepDurationMs)
      ? acceptedStepDurationMs / 1000 : null,
  });
  const frontier = latest(schoolRecords, "bilqis.bamf.mission-control.curriculum-frontier/v1");
  const semantic = latest(semanticRecords, "bilqis.bamf.mission-control.semantic-atlas-snapshot/v1");
  const resource = latest(resources, "bilqis.bamf.mission-control.resource-sample/v1");
  const teacher = latest(teachers, "bilqis.bamf.mission-control.teacher-snapshot/v1");
  const capabilityRows = capabilities.filter((record) => record.schema_version === "bilqis.bamf.mission-control.capability-snapshot/v1");
  const episodeRows = episodes.filter((record) => record.schema_version === "bilqis.bamf.mission-control.learning-episode/v1");
  const summary = latest(episodes, HISTORY_SUMMARY_SCHEMA);
  const decisions = summary?.recent_decisions ?? episodes.filter((record) => record.schema_version === "bilqis.bamf.mission-control.candidate-decision/v1");
  const episodeComplete = completePage(pages, "episode");
  const currentCorrect = measuredSum(capabilityRows, "score_correct");
  const currentTotal = measuredSum(capabilityRows, "score_total");
  const debt = measuredSum(capabilityRows, "debt");
  const count = (number) => number || (episodeComplete ? 0 : null);
  const retained = count(summary?.accepted_count ?? decisions.filter((record) => record.outcome === "ACCEPTED").length);
  const rejected = count(summary?.rejected_count ?? decisions.filter((record) => record.outcome === "REJECTED").length);
  const activeEpisode = summary?.active_episode ?? episodeRows.find((record) => record.state !== "COMPLETED") ?? null;
  const correctionDebt = observedCount(corrections.filter((record) => record.state === "REQUALIFICATION_REQUIRED"), completePage(pages, "correction"));
  const qualified = capabilityRows.filter((record) => record.status === "QUALIFIED").length;
  const domainRecordCount = (
    capabilities.length + (summary ? summary.visit_count + summary.decision_count : episodes.length) + schoolRecords.length + semanticRecords.length + neuralRecords.length +
    resources.length + corrections.length + teachers.length + notifications.length
  );
  const startup = run && !observed.current && context?.mode !== "HISTORICAL" && domainRecordCount === 0
    ? Object.freeze({
      state: context?.operatorActive === true
        ? "WAITING_FOR_FIRST_TRAINING_EVENT"
        : run.optimizer_step === 0 ? "GENERATION_ZERO_READY" : "IDLE_NO_DOMAIN_EVIDENCE",
      generation: run.meta.run.generation,
      optimizerStep: run.optimizer_step,
      stage: run.stage,
      running: typeof context?.operatorActive === "boolean" ? context.operatorActive : null,
    })
    : null;
  const learningEvidence = observed.latestLearningEvidence;
  const health = learningEvidence?.learning_health;
  const visitEvidence = observed.current?.visit_evidence;
  const checkpoints = Array.isArray(health?.recent_checkpoints)
    ? health.recent_checkpoints : [];
  const latestCheckpoint = checkpoints.at(-1);
  const previousCheckpoint = checkpoints.at(-2);
  const acceptedLearningEvidence = learningEvidence?.outcome === "ACCEPTED";
  const freshGain = acceptedLearningEvidence && latestCheckpoint && previousCheckpoint &&
    latestCheckpoint.total === previousCheckpoint.total &&
    latestCheckpoint.correct > previousCheckpoint.correct ? 1 : 0;
  const freshRegression = acceptedLearningEvidence && latestCheckpoint && previousCheckpoint &&
    latestCheckpoint.total === previousCheckpoint.total &&
    latestCheckpoint.correct < previousCheckpoint.correct ? 1 : 0;
  const healthRegressions = Array.isArray(health?.regressed_protected_capabilities)
    ? health.regressed_protected_capabilities.length +
      (health.regressed_from_first === true ? 1 : 0) +
      freshRegression +
      (health.certified_surface_regression_state === "OBSERVED_REGRESSION" ? 1 : 0)
    : 0;

  return Object.freeze({
    provenance: "LIVE_QUERY",
    disconnected: context?.transportDisconnected === true,
    observed,
    startup,
    state: Object.freeze(Object.fromEntries(HOME_FAMILIES.map((family) => [family, pageState(pages, family)]))),
    learningStatus: classifyLearning({
      retained: health?.state === "MEASURED" ? retained ?? 0 : retained, freshRetainedImprovements: freshGain, regressions: healthRegressions,
    }),
    evidence: Object.freeze({
      pulse: episodeComplete || decisions.length > 0,
      attention: completePage(pages, "correction") && completePage(pages, "notification") && completePage(pages, "run"),
      regression: health?.protected_regression_state === "MEASURED" && health?.certified_surface_regression_state !== "NOT_MEASURED",
      notification: completePage(pages, "notification") || notifications.length > 0,
    }),
    learning: Object.freeze({
      latestSchoolScore: pages.capability?.truncated ? null : ratio(currentCorrect, currentTotal),
      bestSchoolScore: null,
      wholeSchoolGrowth: null,
      gRtn: null,
      pRet: null,
      retainedOptimizerSteps: null,
    }),
    curriculum: Object.freeze({
      qualifiedCapabilities: qualified || (completePage(pages, "capability") && capabilityRows.every((row) => ["QUALIFIED", "NOT_QUALIFIED"].includes(row.status)) ? 0 : null),
      observedDebt: pages.capability?.truncated ? null : debt,
      activeConcepts: value(semantic, "active_concepts"),
      ready: frontier?.meta?.coverage === "COMPLETE" ? frontier.ready_capability_ids.length : null,
      held: frontier?.meta?.coverage === "COMPLETE" ? frontier.held_capability_ids.length : null,
      uncovered: null,
    }),
    runtime: Object.freeze({
      running: typeof context?.operatorActive === "boolean" ? context.operatorActive : null,
      elapsed: Number.isFinite(observed.current?.elapsed_ms)
        ? formatDurationSeconds(observed.current.elapsed_ms / 1000) : null,
      visits: count(summary?.visit_count ?? episodeRows.length),
      visitRate: null,
      retainedCandidates: retained,
      rejectedCandidates: rejected,
      acceptedStepsHour: value(resource, "step_rate_per_minute") === null
        ? null : value(resource, "step_rate_per_minute") * 60,
    }),
    system: Object.freeze({
      memoryPressure: ratio(value(resource, "memory_used_bytes"), value(resource, "memory_budget_bytes")),
      peakMemory: observedBytes(observed.current?.peak_rss_bytes, 1048576, "MiB"),
      diskFree: observedBytes(observed.current?.disk_free_bytes, 1073741824, "GiB"),
      diskReserve: null,
      correctionDebt,
      hardWarnings: null,
    }),
    currentWork: Object.freeze({
      capabilityId: observed.current?.capability_id ?? activeEpisode?.capability_id ?? context?.activeCapabilityId ?? null,
      strategy: visitEvidence?.teacher_policy_key ?? teacher?.strategy_id ?? null,
      candidateIntent: observed.current?.phase ?? activeEpisode?.state ?? run?.stage ?? null,
      sourceFamily: null,
      targetAssessment: visitScoreSummary(visitEvidence?.target),
      protectedAssessment: protectedSummary(visitEvidence),
      recordId: activeEpisode?.meta?.record_id ?? null,
      observedAt: activeEpisode?.meta?.observed_at ?? null,
      materializedAt: activeEpisode?.meta?.materialized_at ?? null,
    }),
    schoolRows: Object.freeze(capabilityRows.slice(0, 8).map((record) => Object.freeze({
      id: record.capability_id,
      now: value(record, "score_correct"),
      total: value(record, "score_total"),
      debt: value(record, "debt"),
      status: record.status,
      recordId: record.meta?.record_id ?? record.capability_id,
    }))),
    pulse: Object.freeze(newestFirst(decisions).slice(0, 8).map((record) => Object.freeze({
      kind: record.outcome === "ACCEPTED" ? "retain" : "reject",
      capabilityId: record.capability_id,
      reasonCode: record.reason_code,
      observedAt: record.meta?.observed_at ?? null,
      materializedAt: record.meta?.materialized_at ?? null,
      target: Object.freeze({ kind: "capability", id: record.capability_id }),
    }))),
    notifications: Object.freeze(notifications
      .filter((record) => record.schema_version === "bilqis.bamf.mission-control.notification/v1" && record.state === "ACTIVE")
      .reverse().map((record) => Object.freeze({
        id: record.notification_id,
        kind: record.kind,
        severity: record.severity,
        subjectRef: record.subject_ref,
        evidenceRef: record.evidence_ref,
        createdAt: record.created_at,
        supersedesNotificationId: record.supersedes_notification_id,
        target: Object.freeze({ kind: "reference", id: record.evidence_ref }),
      }))),
    attention: Object.freeze([
      ...(correctionDebt ? [{
        kind: "correction", severity: "invalid", count: correctionDebt, id: corrections[0]?.meta?.record_id,
        target: { kind: "correction", id: corrections[0]?.meta?.record_id },
        observedAt: corrections[0]?.meta?.observed_at ?? null,
        materializedAt: corrections[0]?.meta?.materialized_at ?? null,
      }] : []),
    ]),
  });
}
