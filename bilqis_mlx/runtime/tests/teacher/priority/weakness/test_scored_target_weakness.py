"""Scored weakness evidence is not synonymous with exposed lesson rows."""
from dataclasses import replace
from types import SimpleNamespace as N

import pytest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.runtime import scored_target_weakness as scored
from bilqis_mlx.runtime._factory_identity_evaluation import _raw_issue_owner_evaluation
from bilqis_mlx.runtime.baseline.lifecycle import BaselineLedger
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.capability_retention import (
    AssessmentPair, Decision, DecisionStatus, EvaluationCohort, EvidenceKind,
    case_census_digest, evaluate_capabilities,
)
from bilqis_mlx.runtime.factory_task_template import _source_view
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.tests.capability.capability_retention_helpers import (
    PARENT, CANDIDATE, _cases, _solver,
)
from bilqis_mlx.runtime.tests.teacher.priority.weakness.test_structural_weakness_replay import (
    CAPABILITY, _SourceContext,
)


@pytest.fixture
def witness(monkeypatch):
    cases, contexts = _cases(CAPABILITY, "Z", 3, "fresh")
    rows = tuple({"id": case.case_id, "capability": CAPABILITY,
                  "shape": ["edge", index], "answer_kind": "numeric_active",
                  "gold": str(case.gold.value)}
                 for index, case in enumerate(cases))
    context = _SourceContext(rows)
    context.answer_registry = live_answer_registry()
    base_execution = context.execution_for(CAPABILITY)
    base_execution.answer_families = (N(kind="numeric_active", values=("0", "1", "2", "3", "4", "5")),)
    context.execution_for = lambda _capability: base_execution
    cohort = EvaluationCohort(
        EvidenceKind.FRESH_TARGET, cases, ((CAPABILITY, "Z"),),
        "1" * 64, "2" * 64, "3" * 64, "4" * 64, (), (), case_census_digest(cases))
    pair = AssessmentPair(
        evaluate_capabilities(_solver(contexts, {cases[0].case_id}), cohort, PARENT),
        evaluate_capabilities(_solver(contexts, {case.case_id for case in cases}), cohort, CANDIDATE))
    decision = Decision(DecisionStatus.REJECT, "PROTECTED_REGRESSION",
                        PARENT, CANDIDATE, "e" * 64, "d" * 64)

    class Instrument:
        def __init__(self, row, case):
            self.case, self.source_row = case, row
            self.compiled_case = N(task_template=N(
                source_row_id=case.case_id, capability_id=CAPABILITY,
                release_sha256=context.release.release_sha256,
                source_row_sha256=source_content_digest((_source_view(row),))))

    monkeypatch.setattr(scored, "FactoryEvaluationInstrument", Instrument)
    instruments = tuple(Instrument(row, case) for row, case in zip(rows, cases))
    return context, pair, instruments, decision


def observe(witness):
    context, pair, instruments, decision = witness
    with evidence_mode(strict=False):
        return scored.observe_rejected_target(context, CAPABILITY, pair, instruments, decision)


def test_only_retained_parent_misses_create_classes(witness):
    observation = observe(witness)
    assert observation.status == "OBSERVED_CLASSES"
    assert observation.missed_count == 2
    record = observation.record("9" * 64)
    by_shape = {tuple(item["weakness_class"]["signature"]["shape"]): item["source_ids"]
                for item in record["classes"]}
    assert by_shape == {("edge", 1): ["fresh:1"], ("edge", 2): ["fresh:2"]}
    assert observation.cohort_sha256 == witness[1].parent.cohort.expected_case_digest


@pytest.mark.parametrize("change", ["gold", "shape"])
def test_same_id_mutation_of_even_correct_row_invalidates_observation(witness, change):
    witness[2][0].source_row[change] = "3" if change == "gold" else ["edge", 99]
    assert observe(witness).status == "EVIDENCE_INVALID"


def test_reordered_instruments_are_not_scored_evidence(witness):
    context, pair, instruments, decision = witness
    assert observe((context, pair, instruments[::-1], decision)).status == "EVIDENCE_INVALID"


def test_missing_classifier_is_distinct_from_no_parent_misses(witness, monkeypatch):
    context, pair, instruments, decision = witness
    monkeypatch.setattr(scored, "_provider_for_context",
                        lambda *_: (None, None, N(weakness_classifier_id=None)))
    observation = observe(witness)
    assert (observation.status, observation.missed_count, observation.classes) == (
        "UNSUPPORTED_CLASSIFIER", 2, ())
    perfect_parent = replace(pair.candidate, generation_digest=PARENT,
                             results=tuple(replace(result, generation_digest=PARENT)
                                           for result in pair.candidate.results))
    observation = observe((context, AssessmentPair(perfect_parent, pair.candidate),
                           instruments, decision))
    assert (observation.status, observation.missed_count) == ("OBSERVED_NO_MISSES", 0)


def _issued(witness):
    from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
    evaluation = _raw_issue_owner_evaluation(
        witness[3], "9" * 64, "8" * 64, None,
        baseline_ledger=BaselineLedger.from_optional_record(None),
        target_weakness_observation=observe(witness))
    decision = issue_factory_retention_decision(evaluation)
    evidence = {"decision": decision.to_record(), "capability": CAPABILITY,
                "teacher_visit": {"student_sha256": "9" * 64}}
    return evaluation, decision, evidence


def test_publication_binds_live_decision_and_exact_parent(witness):
    evaluation, decision, evidence = _issued(witness)
    published = scored.bind_live_target_observation(evidence, evaluation, decision)
    record = published["target_weakness_observation"]
    assert record["missed_count"] == 2
    assert record["parent_candidate_sha256"] == "9" * 64
    assert scored.validate_target_weakness_observation(record, published) is record
    with pytest.raises(BilqisError):
        scored.bind_live_target_observation(published, evaluation, decision)
    tampered = {**evidence, "decision": {**evidence["decision"], "candidate_generation": "7" * 64}}
    with pytest.raises(BilqisError):
        scored.bind_live_target_observation(tampered, evaluation, decision)
    with pytest.raises(BilqisError):
        scored.bind_live_target_observation(
            {**evidence, "teacher_visit": {"student_sha256": "7" * 64}}, evaluation, decision)


def _published(witness, monkeypatch):
    from bilqis_mlx.runtime.tests.teacher.priority.weakness.test_structural_weakness_replay import _selection

    evaluation, decision, evidence = _issued(witness)
    selection = _selection()
    original = selection.visit.identity.to_record
    selection.visit.identity.to_record = lambda: {
        **original(), "student_sha256": "9" * 64,
    }
    # Test the publication's class projection independently of strict issuance,
    # whose receipt is exercised in the existing priority authority tests.
    import bilqis_mlx.runtime.accepted_priority_visit_contracts as owner
    monkeypatch.setattr(owner, "_require_issued", lambda result: None)
    evidence.update(
        teacher_visit=selection.visit.identity.to_record(),
        candidate_evidence=None,
        retention_reason=decision.reason,
        how_outcome={"outcome_sha256": "7" * 64},
        structural_weaknesses=[],
    )
    published = scored.bind_live_target_observation(
        evidence, evaluation, decision, selection)
    return published, selection


def test_scored_classes_become_bound_rehearsal_debt(witness, monkeypatch):
    from bilqis_mlx.runtime.structural_weakness_contracts import (
        _digest, validate_rejection_weaknesses,
    )

    published, _selection = _published(witness, monkeypatch)
    wrappers = validate_rejection_weaknesses(published, "6" * 64)
    assert len(wrappers) == 2
    assert {tuple(item["weakness"]["historical_source_ids"]) for item in wrappers} == {
        ("fresh:1",), ("fresh:2",)}
    assert all(item["weakness"]["evidence_kind"] == "SCORED_PARENT_MISS" for item in wrappers)
    forged = dict(published["structural_weaknesses"][0])
    forged["historical_source_ids"] = ["not-a-miss"]
    forged["weakness_evidence_sha256"] = _digest({
        k: v for k, v in forged.items() if k != "weakness_evidence_sha256"})
    with pytest.raises(BilqisError):
        validate_rejection_weaknesses({
            **published, "structural_weaknesses": [
                forged, published["structural_weaknesses"][1]]})


def test_historical_exposure_cannot_shadow_scored_debt(witness, monkeypatch):
    from bilqis_mlx.runtime import priority_rejection_replay as replay
    from bilqis_mlx.runtime import structural_weakness_replay as ledger
    from bilqis_mlx.runtime.structural_weakness_contracts import (
        _digest, validate_rejection_weaknesses,
    )

    published, selection = _published(witness, monkeypatch)
    scored_wrappers = validate_rejection_weaknesses(published, "6" * 64)
    legacy = {k: v for k, v in published.items() if k != "target_weakness_observation"}
    historical = []
    for record in published["structural_weaknesses"]:
        old = {k: v for k, v in record.items()
               if k not in {"evidence_kind", "weakness_evidence_sha256"}}
        old["weakness_evidence_sha256"] = _digest(old)
        historical.append(old)
    legacy["structural_weaknesses"] = historical
    historical_wrappers = validate_rejection_weaknesses(legacy, "5" * 64)
    teacher = ledger.apply_rejection_weaknesses({}, published, "6" * 64)
    teacher = ledger.apply_rejection_weaknesses(teacher, legacy, "5" * 64)
    assert {item["rejection_receipt_sha256"] for item in
            ledger.carried_structural_weaknesses(teacher)} == {"6" * 64}

    # Exercise the actual currentness projection with a later historical event.
    from bilqis_mlx.learning import teacher_lineage
    selection.visit.projection = N(teacher_state=teacher)
    monkeypatch.setattr(teacher_lineage, "restore_teacher_lineage",
                        lambda state: N(teacher=lambda: state))
    monkeypatch.setattr(ledger, "weakness_is_current", lambda *_: True)
    monkeypatch.setattr(replay, "_current_projection", lambda *_:
                        N(weaknesses_view=lambda: (*scored_wrappers, *historical_wrappers)))
    current = replay.current_structural_weaknesses(
        "/run", object(), object(), witness[0], selection)
    assert len(current) == 2
    assert {item["rejection_receipt_sha256"] for item in current} == {"6" * 64}


def test_retained_class_closure_and_realized_exposure_fold_once(witness, monkeypatch):
    from bilqis_mlx.learning import teacher_lineage
    from bilqis_mlx.learning.teacher_realized_action import describe, weakness_delivery_facts
    from bilqis_mlx.runtime.outcomes.observations import apply_outcome
    from bilqis_mlx.runtime.structural_weakness_ledger import (
        _ledger_key, apply_rejection_weaknesses, carried_structural_weaknesses,
    )
    from bilqis_mlx.runtime.tests.teacher.outcomes.test_outcome_credit import (
        teacher_fixture, outcome, signed,
    )

    published, selection = _published(witness, monkeypatch)
    teacher = apply_rejection_weaknesses(teacher_fixture(), published, "6" * 64)
    debts = {item["weakness"]["historical_source_ids"][0]: item["weakness"]
             for item in carried_structural_weaknesses(teacher)}
    first, second = (_ledger_key(debts[key]) for key in ("fresh:1", "fresh:2"))
    selection.visit.projection = N(teacher_state=teacher)
    monkeypatch.setattr(teacher_lineage, "restore_teacher_lineage",
                        lambda state: N(teacher=lambda: state))

    controls = ({"weakness_class_matches": {first: ["delivered:1"]},
                 "weakness_targets_delivered": 1,
                 "priority_weakness_targets_delivered": 1,
                 "weakness_unavailable": {second: "NO_MATCH_IN_BUDGET"}},)
    action = describe(teacher["strategies"]["policy"], candidate_steps=1,
                      batch_size=4, policy_controls=controls,
                      guidance_applied_steps=0, enrichment_examples=0)
    rejected = signed(outcome(teacher, capability=CAPABILITY),
                      realized_action=action, weakness_delivery=weakness_delivery_facts(controls))
    credited = apply_outcome(teacher, rejected)
    assert credited["structural_weaknesses"]["classes"][first]["exposure_count"] == 1
    assert "exposure_count" not in credited["structural_weaknesses"]["classes"][second]
    assert apply_outcome(credited, rejected) == credited

    # A perfect provisional candidate cannot close debt when it is rejected.
    eval_reject, rejected_decision, _ = _issued(witness)
    assert scored.live_resolution_proofs(selection, eval_reject, rejected_decision) == []

    # The same source row IDs are not fresh-equivalent evidence for closure.
    context, pair, instruments, original = witness
    eligible = replace(original, status=DecisionStatus.ELIGIBLE,
                       reason="PAIRED_SCREEN_WITHIN_BUDGET")
    observed = scored.observe_retained_target(context, CAPABILITY, pair, instruments, eligible)
    assert observed.missed_count == 0
    from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
    evaluation = _raw_issue_owner_evaluation(
        eligible, "9" * 64, "8" * 64, None,
        baseline_ledger=BaselineLedger.from_optional_record(None),
        target_weakness_observation=observed)
    decision = issue_factory_retention_decision(evaluation)
    assert scored.live_resolution_proofs(selection, evaluation, decision) == []

    # New, correct class-equivalent scored rows close only the matching debt.
    cases, contexts = _cases(CAPABILITY, "Z", 1, "new")
    row = {**instruments[1].source_row, "id": cases[0].case_id,
           "gold": str(cases[0].gold.value)}
    new_instrument = type(instruments[0])(row, cases[0])
    cohort = replace(pair.parent.cohort, cases=cases,
                     expected_case_digest=case_census_digest(cases))
    new_pair = AssessmentPair(
        evaluate_capabilities(_solver(contexts, set()), cohort, PARENT),
        evaluate_capabilities(_solver(contexts, {cases[0].case_id}), cohort, CANDIDATE))
    observed = scored.observe_retained_target(
        context, CAPABILITY, new_pair, (new_instrument,), eligible)
    assert observed.status == "OBSERVED_NO_MISSES"
    evaluation = _raw_issue_owner_evaluation(
        eligible, "9" * 64, "8" * 64, None,
        baseline_ledger=BaselineLedger.from_optional_record(None),
        target_weakness_observation=observed)
    decision = issue_factory_retention_decision(evaluation)
    selection.visit.projection = N(teacher_state=credited)
    proofs = scored.live_resolution_proofs(selection, evaluation, decision)
    assert len(proofs) == 1 and proofs[0]["debt_key"] == first
    retained = outcome(credited, ordinal=2, retained=True, capability=CAPABILITY)
    retained["context"].update(selection.metadata["how_context"])
    retained["decision"] = decision.to_record()
    retained = signed(retained, weakness_resolutions=proofs)
    closed = apply_outcome(credited, retained)
    assert closed["structural_weaknesses"]["classes"][first]["state"] == "RESOLVED"
    assert closed["structural_weaknesses"]["classes"][first]["exposure_count"] == 1
    assert [_ledger_key(item["weakness"]) for item in carried_structural_weaknesses(closed)] == [second]
    assert apply_outcome(closed, retained) == closed
    assert apply_outcome(closed, rejected) == closed
