"""Carried unresolved R13 weakness debt and explicit scored closure."""
from __future__ import annotations

from .structural_weakness_contracts import (
    LEDGER_SCHEMA, SHA256_LENGTH, _invalid, validate_rejection_weaknesses,
    validate_weakness_evidence,
)


def _ledger_key(record: dict) -> str:
    return (
        record["context"]["context_sha256"] + ":"
        + record["weakness_class"]["class_sha256"])


def _validated_ledger(teacher: dict) -> dict:
    raw = teacher.get("structural_weaknesses")
    if raw is None:
        return {"schema": LEDGER_SCHEMA, "classes": {}}
    if (not isinstance(raw, dict) or raw.get("schema") != LEDGER_SCHEMA
            or not isinstance(raw.get("classes"), dict)):
        _invalid("BAMF_WEAKNESS_LEDGER_INVALID")
    for key, item in raw["classes"].items():
        if (not isinstance(key, str) or not isinstance(item, dict)
                or item.get("state") not in {"UNRESOLVED", "RESOLVED"}
                or not isinstance(item.get("weakness"), dict)):
            _invalid("BAMF_WEAKNESS_LEDGER_INVALID")
        validate_weakness_evidence(item["weakness"])
        exposure = item.get("exposure_count", 0)
        if type(exposure) is not int or exposure < 0:
            _invalid("BAMF_WEAKNESS_EXPOSURE_INVALID")
        if key != _ledger_key(item["weakness"]):
            _invalid("BAMF_WEAKNESS_LEDGER_DRIFT")
        if item["state"] == "RESOLVED":
            resolution = item.get("resolution_evidence_sha256")
            if (not isinstance(resolution, str)
                    or len(resolution) != SHA256_LENGTH
                    or any(char not in "0123456789abcdef" for char in resolution)):
                _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
    return raw


def apply_rejection_weaknesses(
        teacher: dict, evidence: dict, rejection_receipt_sha256: str,
) -> dict:
    """Fold authenticated rejection debt into carried teacher custody."""
    from copy import deepcopy

    wrappers = validate_rejection_weaknesses(
        evidence, rejection_receipt_sha256)
    if not wrappers:
        return deepcopy(teacher)
    result = deepcopy(teacher)
    ledger = deepcopy(_validated_ledger(result))
    for wrapper in wrappers:
        weakness = wrapper["weakness"]
        key = _ledger_key(weakness)
        existing = ledger["classes"].get(key)
        # Historical exposure may remain readable, but cannot replace scored debt.
        if (existing is not None
                and existing["weakness"].get("evidence_kind") == "SCORED_PARENT_MISS"
                and weakness.get("evidence_kind") != "SCORED_PARENT_MISS"):
            continue
        if (existing is not None and existing["state"] == "RESOLVED"
                and existing.get("rejection_receipt_sha256")
                == rejection_receipt_sha256):
            continue
        ledger["classes"][key] = {
            "state": "UNRESOLVED",
            "weakness": weakness,
            "candidate_evidence": wrapper["candidate_evidence"],
            "rejection_receipt_sha256": rejection_receipt_sha256,
            **({"exposure_count": existing["exposure_count"]}
               if existing is not None and "exposure_count" in existing else {}),
        }
    result["structural_weaknesses"] = ledger
    return result


def _resolution_authority(run_dir, wrapper, source_context, selection, assessment, instruments):
    from bilqis_mlx.factory._model.weakness import WeaknessClassId
    from bilqis_mlx.runtime.bamf_operator.evidence_parts.validation import (
        read_candidate_horizon_evidence,
    )
    from bilqis_mlx.runtime.capability_retention import Assessment, EvidenceKind
    from bilqis_mlx.runtime.factory_complete_solver import FactoryEvaluationInstrument
    from .structural_weakness_capture import _provider_for_context, weakness_is_current

    if (not isinstance(wrapper, dict)
            or not isinstance(wrapper.get("weakness"), dict)
            or not weakness_is_current(wrapper, source_context, selection)
            or type(assessment) is not Assessment
            or assessment.cohort.kind not in {
                EvidenceKind.FRESH_TARGET, EvidenceKind.FRESH_LESSON}
            or not isinstance(instruments, tuple) or not instruments
            or any(type(item) is not FactoryEvaluationInstrument for item in instruments)):
        _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
    weakness_record = wrapper["weakness"]
    weakness = WeaknessClassId.from_record(weakness_record["weakness_class"])
    capability = weakness_record["capability_id"]
    execution, adapter, admitted = _provider_for_context(source_context, capability)
    historical_ids = set(weakness_record.get("historical_source_ids") or ())
    if not historical_ids:
        candidate_evidence = wrapper.get("candidate_evidence")
        if not isinstance(candidate_evidence, dict):
            _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
        historical = read_candidate_horizon_evidence(run_dir, candidate_evidence)
        historical_ids = {
            row.get("id") for row in historical.get("source_objects", {}).values()
            if isinstance(row, dict) and row.get("capability") == capability
        }
    return weakness_record, weakness, capability, execution, adapter, admitted, historical_ids


def _qualifying_resolution_rows(
        source_context, assessment, instruments, weakness, capability,
        execution, adapter, admitted, historical_ids):
    from bilqis_mlx.factory._model.weakness import classify_weakness
    from bilqis_mlx.runtime.capability_evaluation import _answer_identity
    from bilqis_mlx.runtime.factory_task_template import _source_view
    from bilqis_mlx.runtime.source_execution import source_content_digest

    scored = {
        case.case_id: (case, result)
        for case, result in zip(assessment.cohort.cases, assessment.results, strict=True)
        if case.capability_id == capability
    }
    qualifying = []
    for instrument in instruments:
        row = instrument.source_row
        row_id = row.get("id") if isinstance(row, dict) else None
        pair = scored.get(row_id)
        if (not isinstance(row_id, str) or not row_id
                or row_id in historical_ids or pair is None):
            continue
        template = instrument.compiled_case.task_template
        if (instrument.case != pair[0] or template.source_row_id != row_id
                or template.capability_id != capability
                or template.release_sha256 != source_context.release.release_sha256
                or template.source_row_sha256
                != source_content_digest((_source_view(row),))):
            _invalid("BAMF_WEAKNESS_RESOLUTION_ASSESSED_ROW_DRIFT")
        if adapter.check(
                row, source_root=source_context.source_root,
                graph=source_context.graph,
                course=source_context.release.curriculum) is not True:
            _invalid("BAMF_WEAKNESS_RESOLUTION_SOURCE_INVALID")
        classified = classify_weakness(
            adapter, execution, row, provider_descriptor=admitted)
        case, result = pair
        if (classified is not None
                and classified.class_sha256 == weakness.class_sha256
                and _answer_identity(result.answer) == _answer_identity(case.gold)):
            qualifying.append(instrument)
    if not qualifying:
        _invalid("BAMF_WEAKNESS_RESOLUTION_EQUIVALENT_SCORE_REQUIRED")
    return tuple(qualifying)


def _close_resolution(teacher, weakness_record, assessment, qualifying):
    from copy import deepcopy
    from .structural_weakness_contracts import _digest

    result = deepcopy(teacher)
    ledger = deepcopy(_validated_ledger(result))
    item = ledger["classes"].get(_ledger_key(weakness_record))
    if (item is None or item.get("state") != "UNRESOLVED"
            or item.get("weakness") != weakness_record):
        _invalid("BAMF_WEAKNESS_RESOLUTION_TARGET_INVALID")
    _mark_resolved(item, _digest({
        "schema": "bilqis.bamf.structural-weakness-resolution/v1",
        "weakness_evidence_sha256": weakness_record["weakness_evidence_sha256"],
        "assessment_sha256": assessment.digest(),
        "assessed_source_rows_sha256": _digest(tuple(
            instrument.compiled_case.task_template.source_row_sha256
            for instrument in qualifying)),
    }))
    result["structural_weaknesses"] = ledger
    return result


def _mark_resolved(item, proof_sha256):
    item["state"] = "RESOLVED"
    item["resolution_evidence_sha256"] = proof_sha256


def record_scored_resolutions(teacher: dict, observation: dict) -> None:
    """Fold only authenticated, exact-debt fresh scored closure proofs."""
    from bilqis_mlx.runtime.capability_evaluation import _sha
    from .structural_weakness_contracts import _digest, _validate_context

    proofs = observation.get("weakness_resolutions", [])
    if not proofs:
        return
    if not isinstance(proofs, list):
        _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
    ledger = _validated_ledger(teacher)
    decision = observation["decision"]
    seen = set()
    for proof in proofs:
        if not isinstance(proof, dict) or set(proof) != {
                "debt_key", "weakness_evidence_sha256", "cohort_sha256",
                "decision_evidence_sha256", "retained_candidate_sha256",
                "fresh_correct_rows", "context"}:
            _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
        key = proof["debt_key"]
        item = ledger["classes"].get(key)
        context = _validate_context(proof["context"])
        how = observation["context"]
        rows = proof["fresh_correct_rows"]
        if (item is None or key in seen or item["state"] != "UNRESOLVED"
                or item["weakness"].get("evidence_kind") != "SCORED_PARENT_MISS"
                or item["weakness"]["context"] != context
                or context["capability_id"] != observation["teacher_visit"]["capability_id"]
                or any(context[name] != how[name] for name in (
                    "factory_release_sha256", "source_binding_sha256",
                    "grade_definition_sha256", "rubric_sha256", "curriculum_scope"))
                or context["grade_id"] != how["grade"]
                or proof["weakness_evidence_sha256"] != item["weakness"]["weakness_evidence_sha256"]
                or proof["decision_evidence_sha256"] != decision["evidence_sha256"]
                or proof["retained_candidate_sha256"] != decision[
                    "candidate_generation" if decision["decision"] == "PROVISIONAL"
                    else "parent_generation"]
                or not _sha(proof["cohort_sha256"])
                or not isinstance(rows, list) or not rows):
            _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
        row_ids = []
        for row in rows:
            if (not isinstance(row, list) or len(row) != 2
                    or not isinstance(row[0], str) or not row[0]
                    or not _sha(row[1])):
                _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
            row_ids.append(row[0])
        if (row_ids != sorted(set(row_ids))
                or set(row_ids).intersection(item["weakness"]["historical_source_ids"])):
            _invalid("BAMF_WEAKNESS_RESOLUTION_FRESHNESS_DRIFT")
        seen.add(key)
        _mark_resolved(item, _digest(proof))


def resolve_structural_weakness(
        teacher: dict, *, run_dir, wrapper: dict, source_context, selection,
        assessment, instruments,
) -> dict:
    """Close one class only after fresh, current, source-scored equivalent proof."""
    authority = _resolution_authority(
        run_dir, wrapper, source_context, selection, assessment, instruments)
    weakness_record, weakness, capability, execution, adapter, admitted, historical_ids = authority
    qualifying = _qualifying_resolution_rows(
        source_context, assessment, instruments, weakness, capability,
        execution, adapter, admitted, historical_ids)
    return _close_resolution(teacher, weakness_record, assessment, qualifying)


def record_weakness_exposure(teacher: dict, exposures: dict) -> None:
    """Credit actual optimizer delivery once, inside the outcome owner's fold."""
    if not exposures:
        return
    ledger = _validated_ledger(teacher)
    for key, count in exposures.items():
        item = ledger["classes"].get(key)
        if (type(count) is not int or count < 1 or item is None
                or item["state"] != "UNRESOLVED"
                or item["weakness"].get("evidence_kind") != "SCORED_PARENT_MISS"):
            _invalid("BAMF_WEAKNESS_EXPOSURE_INVALID")
        item["exposure_count"] = item.get("exposure_count", 0) + count


def carried_structural_weaknesses(teacher: dict) -> tuple[dict, ...]:
    """Project unresolved carried classes; exact evidence stays in its B13 receipt."""
    ledger = _validated_ledger(teacher)
    return tuple(
        {
            "weakness": item["weakness"],
            "candidate_evidence": item["candidate_evidence"],
            "rejection_receipt_sha256": item["rejection_receipt_sha256"],
            **({"exposure_count": item["exposure_count"]}
               if "exposure_count" in item else {}),
        }
        for key, item in sorted(ledger["classes"].items())
        if item["state"] == "UNRESOLVED"
    )


def recorded_weakness_debt(teacher, how, frontier, capability):
    """True/False only for recorded current debt/resolution; None if unmeasured.

    This is a diagnostic, not authorization to deliver or close a weakness.
    The existing teaching owner still validates source/provider and row identity.
    """
    raw = teacher.get("structural_weaknesses")
    if raw is None:
        return None
    if (not isinstance(raw, dict) or raw.get("schema") != LEDGER_SCHEMA
            or not isinstance(raw.get("classes"), dict)):
        _invalid("BAMF_WEAKNESS_LEDGER_INVALID")
    if not raw["classes"]:
        return None
    from .structural_weakness_contracts import weakness_context_for_frontier

    context = weakness_context_for_frontier(how, frontier, capability)
    prefix = context["context_sha256"] + ":"
    resolved = False
    for key, item in raw["classes"].items():
        if not isinstance(key, str) or not key.startswith(prefix):
            continue
        if not isinstance(item, dict):
            _invalid("BAMF_WEAKNESS_LEDGER_INVALID")
        record = validate_weakness_evidence(item.get("weakness"))
        if record["context"] != context or key != _ledger_key(record):
            _invalid("BAMF_WEAKNESS_LEDGER_DRIFT")
        if item["state"] == "UNRESOLVED":
            return True
        proof = item.get("resolution_evidence_sha256")
        if (item["state"] != "RESOLVED" or not isinstance(proof, str)
                or len(proof) != SHA256_LENGTH
                or any(char not in "0123456789abcdef" for char in proof)):
            _invalid("BAMF_WEAKNESS_RESOLUTION_INVALID")
        resolved = True
    return False if resolved else None


__all__ = (
    "apply_rejection_weaknesses", "carried_structural_weaknesses",
    "resolve_structural_weakness",
)
