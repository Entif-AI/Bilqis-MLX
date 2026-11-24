"""Compact C05 observation of the retained parent's scored target misses."""
from dataclasses import dataclass
import json

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory._model.weakness import WeaknessClassId, classify_weakness
from bilqis_mlx.runtime.capability_evaluation import Assessment, EvidenceKind, _answer_identity, _sha
from bilqis_mlx.runtime.capability_retention import Decision, DecisionStatus
from bilqis_mlx.runtime.factory_complete_solver import FactoryEvaluationInstrument, _factory_gold
from bilqis_mlx.runtime.factory_task_template import _source_view
from bilqis_mlx.runtime.source_execution import source_content_digest
from .structural_weakness_capture import _provider_for_context
from .structural_weakness_contracts import _invalid


SCHEMA = "bilqis.bamf.scored-target-weakness/v1"


@dataclass(frozen=True)
class TargetWeaknessObservation:
    capability_id: str
    execution_generation_sha256: str
    decision_evidence_sha256: str
    cohort_sha256: str | None
    status: str
    missed_count: int | None
    classes: tuple[tuple[str, tuple[str, ...]], ...] = ()
    correct_classes: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = ()

    def record(self, parent_identity):
        return {
            "schema": SCHEMA, "capability_id": self.capability_id,
            "execution_generation_sha256": self.execution_generation_sha256,
            "decision_evidence_sha256": self.decision_evidence_sha256,
            "parent_candidate_sha256": parent_identity,
            "cohort_sha256": self.cohort_sha256, "status": self.status,
            "missed_count": self.missed_count,
            "classes": [{"weakness_class": json.loads(weakness),
                         "source_ids": list(ids)} for weakness, ids in self.classes],
        }


def _validated_scored_rows(source_context, capability, assessment, instruments, generation):
    if (type(assessment) is not Assessment
            or assessment.cohort.kind is not EvidenceKind.FRESH_TARGET
            or assessment.generation_digest != generation
            or tuple(item.case for item in instruments) != assessment.cohort.cases):
        _invalid("BAMF_SCORED_TARGET_ASSESSMENT_DRIFT")
    scored = []
    for instrument, case, result in zip(
            instruments, assessment.cohort.cases, assessment.results, strict=True):
        if type(instrument) is not FactoryEvaluationInstrument:
            _invalid("BAMF_SCORED_TARGET_INSTRUMENT_INVALID")
        row = instrument.source_row
        template = instrument.compiled_case.task_template
        if (case.capability_id != capability or row.get("capability") != capability
                or row.get("id") != case.case_id or template.source_row_id != case.case_id
                or template.capability_id != capability
                or template.release_sha256 != source_context.release.release_sha256
                or template.source_row_sha256 != source_content_digest((_source_view(row),))
                or _answer_identity(_factory_gold(source_context, row, case.goal))
                != _answer_identity(case.gold)):
            _invalid("BAMF_SCORED_TARGET_SOURCE_DRIFT")
        scored.append((row, template.source_row_sha256,
                       _answer_identity(result.answer) == _answer_identity(case.gold)))
    return scored


def observe_retained_target(source_context, capability, pair, instruments, decision):
    """Use the already-scored target assessment of the actually retained student."""
    if type(decision) is not Decision or decision.status not in (
            DecisionStatus.REJECT, DecisionStatus.ELIGIBLE):
        return None
    accepted = decision.status is DecisionStatus.ELIGIBLE
    generation = decision.candidate_generation if accepted else decision.parent_generation

    def observed(status, count=None, classes=(), cohort=None, correct=()):
        return TargetWeaknessObservation(
            capability, generation, decision.evidence_sha256,
            cohort, status, count, classes, correct)

    try:
        assessment = pair.candidate if accepted else pair.parent
        scored = _validated_scored_rows(
            source_context, capability, assessment, instruments, generation)
        cohort = assessment.cohort.expected_case_digest
        count = sum(not correct for _, _, correct in scored)
        execution, adapter, admitted = _provider_for_context(source_context, capability)
        if admitted.weakness_classifier_id is None:
            return observed("UNSUPPORTED_CLASSIFIER" if count else "OBSERVED_NO_MISSES",
                            count, cohort=cohort)
        from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import strict_evidence_enabled
        missed, passed = {}, {}
        for row, source_sha, correct in scored:
            if (correct or strict_evidence_enabled()) and adapter.check(
                    row, source_root=source_context.source_root, graph=source_context.graph,
                    course=source_context.release.curriculum) is not True:
                _invalid("BAMF_SCORED_TARGET_SOURCE_DRIFT")
            weakness = classify_weakness(adapter, execution, row, provider_descriptor=admitted)
            if weakness is None:
                _invalid("BAMF_SCORED_TARGET_CLASSIFIER_DRIFT")
            key = json.dumps(weakness.to_record(), sort_keys=True, separators=(",", ":"))
            if correct:
                passed.setdefault(key, []).append((row["id"], source_sha))
            else:
                missed.setdefault(key, []).append(row["id"])
        classes = tuple((key, tuple(sorted(ids))) for key, ids in sorted(missed.items()))
        # Do not discharge a class that still has a wrong answer in this cohort.
        correct_classes = tuple((key, tuple(sorted(rows)))
                                for key, rows in sorted(passed.items()) if key not in missed)
        return observed("OBSERVED_CLASSES" if count else "OBSERVED_NO_MISSES",
                        count, classes, cohort, correct_classes)
    except (BilqisError, ValueError, TypeError, KeyError, AttributeError):
        return observed("EVIDENCE_INVALID")


def observe_rejected_target(source_context, capability, pair, instruments, decision):
    """Rejected-only observation for the existing B13 rejection contract."""
    if type(decision) is not Decision or decision.status is not DecisionStatus.REJECT:
        return None
    return observe_retained_target(source_context, capability, pair, instruments, decision)


def live_resolution_proofs(selection, evaluation, decision):
    """Project matching fresh C05 proof into the live-issued HOW outcome."""
    from bilqis_mlx.learning.teacher_lineage import restore_teacher_lineage
    from .structural_weakness_contracts import issue_weakness_context
    from .structural_weakness_ledger import carried_structural_weaknesses, _ledger_key

    observation = evaluation.target_weakness_observation
    if observation is None or not observation.correct_classes:
        return []
    context = issue_weakness_context(selection)
    if observation.capability_id != context["capability_id"]:
        _invalid("BAMF_WEAKNESS_RESOLUTION_CONTEXT_DRIFT")
    teacher = restore_teacher_lineage(selection.visit.projection.teacher_state).teacher()
    correct = {
        WeaknessClassId.from_record(json.loads(record)).class_sha256: rows
        for record, rows in observation.correct_classes
    }
    proofs = []
    for wrapper in carried_structural_weaknesses(teacher):
        weakness = wrapper["weakness"]
        if (weakness.get("evidence_kind") != "SCORED_PARENT_MISS"
                or weakness["context"] != context):
            continue
        rows = correct.get(weakness["weakness_class"]["class_sha256"], ())
        fresh = [[row_id, digest] for row_id, digest in rows
                 if row_id not in weakness["historical_source_ids"]]
        if fresh:
            proofs.append({
                "debt_key": _ledger_key(weakness),
                "weakness_evidence_sha256": weakness["weakness_evidence_sha256"],
                "cohort_sha256": observation.cohort_sha256,
                "decision_evidence_sha256": observation.decision_evidence_sha256,
                "retained_candidate_sha256": (
                    decision.candidate_generation if decision.accepted else decision.parent_generation),
                "fresh_correct_rows": fresh, "context": context,
            })
    return proofs


def validate_target_weakness_observation(record, evidence):
    """Validate authenticated cold data; live issuance is checked separately."""
    decision = evidence.get("decision")
    if (not isinstance(record, dict) or set(record) != {
            "schema", "capability_id", "execution_generation_sha256",
            "decision_evidence_sha256", "parent_candidate_sha256", "cohort_sha256",
            "status", "missed_count", "classes"}
            or record["schema"] != SCHEMA or not isinstance(decision, dict)
            or record["capability_id"] != evidence.get("capability")
            or record["parent_candidate_sha256"] != decision.get("parent_generation")
            or record["decision_evidence_sha256"] != decision.get("evidence_sha256")
            or not all(_sha(record[key]) for key in (
                "execution_generation_sha256", "parent_candidate_sha256",
                "decision_evidence_sha256"))
            or not isinstance(record["classes"], list)):
        _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
    status, count, classes = record["status"], record["missed_count"], record["classes"]
    if status in ("NOT_MEASURED", "EVIDENCE_INVALID"):
        if count is not None or classes or record["cohort_sha256"] is not None:
            _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
        return record
    if not _sha(record["cohort_sha256"]) or type(count) is not int or count < 0:
        _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
    if status == "OBSERVED_NO_MISSES" and count == 0 and not classes:
        return record
    if status == "UNSUPPORTED_CLASSIFIER" and count > 0 and not classes:
        return record
    if status != "OBSERVED_CLASSES" or count < 1 or not classes:
        _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
    seen_classes, seen_ids = set(), set()
    for item in classes:
        if not isinstance(item, dict) or set(item) != {"weakness_class", "source_ids"}:
            _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
        weakness = WeaknessClassId.from_record(item["weakness_class"])
        ids = item["source_ids"]
        if (weakness.capability_id != record["capability_id"]
                or weakness.class_sha256 in seen_classes or not isinstance(ids, list)
                or not ids or any(not isinstance(row_id, str) or not row_id for row_id in ids)
                or ids != sorted(set(ids)) or seen_ids.intersection(ids)):
            _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
        seen_classes.add(weakness.class_sha256)
        seen_ids.update(ids)
    if len(seen_ids) != count:
        _invalid("BAMF_SCORED_TARGET_OBSERVATION_INVALID")
    return record


def bind_live_target_observation(evidence, evaluation, decision, selection=None):
    """Only the existing live C05 evaluation and issued decision may add evidence."""
    if "target_weakness_observation" in evidence:
        _invalid("BAMF_SCORED_TARGET_OBSERVATION_CALLER_SUPPLIED")
    if evaluation is None and decision is None:
        return evidence
    from bilqis_mlx.learning.atlas_retention_decision import CandidateRetentionDecision
    from bilqis_mlx.runtime.factory_retention_owner import (
        FactoryRetentionEvaluation, _require_factory_evaluation,
    )
    if type(evaluation) is not FactoryRetentionEvaluation or type(decision) is not CandidateRetentionDecision:
        _invalid("BAMF_SCORED_TARGET_EVALUATION_DRIFT")
    _require_factory_evaluation(evaluation)
    decision.__post_init__()
    evaluation.__post_init__()
    if (decision.accepted or evaluation.decision.status is not DecisionStatus.REJECT
            or decision.to_record() != evidence.get("decision")
            or decision.parent_generation != evaluation.parent_candidate_sha256
            or decision.candidate_generation != evaluation.candidate_candidate_sha256
            or decision.evidence_sha256 != evaluation.decision.evidence_sha256
            or decision.reason != evaluation.decision.reason
            or decision.policy_sha256 != evaluation.decision.policy_sha256
            or decision.parent_generation != evidence.get("teacher_visit", {}).get("student_sha256")):
        _invalid("BAMF_SCORED_TARGET_EVALUATION_DRIFT")
    observation = evaluation.target_weakness_observation
    if observation is None:
        observation = TargetWeaknessObservation(
            evidence["capability"], evaluation.decision.parent_generation,
            decision.evidence_sha256, None, "NOT_MEASURED", None)
    record = observation.record(evaluation.parent_candidate_sha256)
    validate_target_weakness_observation(record, evidence)
    result = {**evidence, "target_weakness_observation": record}
    if selection is not None:
        from .structural_weakness_contracts import (
            EVIDENCE_SCHEMA, _digest, issue_weakness_context,
            validate_rejection_weaknesses,
        )
        context = issue_weakness_context(selection)
        if (selection.visit.identity.to_record() != evidence["teacher_visit"]
                or context["capability_id"] != evidence["capability"]):
            _invalid("BAMF_SCORED_TARGET_SELECTION_DRIFT")
        candidate = evidence.get("candidate_evidence")
        candidate_sha = (candidate.get("object", {}).get("sha256")
                         if isinstance(candidate, dict) else None)
        records = []
        for item in record["classes"]:
            weakness = {
                "schema": EVIDENCE_SCHEMA, "state": "UNRESOLVED",
                "freshness": "FRESH_EQUIVALENT_REQUIRED",
                "capability_id": context["capability_id"],
                "weakness_class": item["weakness_class"], "context": context,
                "candidate_evidence_sha256": candidate_sha,
                "historical_source_ids": item["source_ids"],
                "outcome_sha256": evidence["how_outcome"]["outcome_sha256"],
                "retention_reason": evidence["retention_reason"],
                "evidence_kind": "SCORED_PARENT_MISS",
            }
            weakness["weakness_evidence_sha256"] = _digest(weakness)
            records.append(weakness)
        result["structural_weaknesses"] = records
        validate_rejection_weaknesses(result)
    return result
