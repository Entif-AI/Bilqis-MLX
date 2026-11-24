"""Admitted source differential witnesses for native policy-shaped offers."""
from collections import Counter
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from bilqis_mlx.factory.live_answers import live_answer_registry
from bilqis_mlx.runtime import priority_source_offer as offers
from bilqis_mlx.runtime import priority_planning_generation as planning
from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.priority_lesson import prepare_lesson_pool, shape_priority_lesson
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.tests.operator.pre_neural.pre_neural_journey_support import (
    LEGACY, historical_school_release,
)
from bilqis_mlx.source_adapters.school import live_source_registry


@pytest.fixture(scope="module")
def admitted(tmp_path_factory):
    release, graph = historical_school_release()
    return SourceExecutionContext(
        release=release, graph=graph, source_root=LEGACY,
        source_registry=live_source_registry(), answer_registry=live_answer_registry(),
        run_dir=tmp_path_factory.mktemp("lesson-offers"))


@pytest.fixture
def offer_factory(admitted):
    generation = object.__new__(planning.PriorityPlanningGeneration)
    object.__setattr__(generation, "_issuance", planning._PLANNING_ISSUER)
    cache = SimpleNamespace(accepted_manifest_sha256="a" * 64, generation_binding="b" * 64)
    authenticated = SimpleNamespace(
        receipt=SimpleNamespace(generation_manifest_sha256="a" * 64))
    parent = object()
    with evidence_mode(strict=False), patch.object(
        offers, "_require_planning_generation_identity",
        return_value=(cache, authenticated)
    ):
        def draw(capability):
            return offers.prepare_priority_source_offer(
                admitted, parent, None, capability=capability, source_seed=17,
                source_each=32, planning_generation=generation)
        yield parent, draw


@pytest.mark.parametrize("capability,rows,low_tokens,high_tokens,low_signatures,high_signatures", [
    ("A.IDENTITY", 32, 528, 544, 2, 2),
    ("A.MAPS", 32, 912, 928, 2, 2),
    ("B.AND", 32, 570, 700, 2, 2),
    ("B.COMPOSITE", 32, 365, 367, 2, 2),
    ("B.IDBOOLOPS", 32, 928, 928, 6, 6),
    ("C.ADD", 30, 526, 583, 6, 9),
    ("C.COUNT", 30, 325, 415, 10, 10),
])
def test_real_offers_realize_supported_controls(
    admitted, offer_factory, capability, rows, low_tokens, high_tokens,
    low_signatures, high_signatures,
):
    parent, draw = offer_factory
    original = draw(capability)
    before = admitted._source_preparation_metrics.provider_draws
    pool = prepare_lesson_pool(admitted, original)
    assert admitted._source_preparation_metrics.provider_draws == before + 1
    low, low_metadata = shape_priority_lesson(
        admitted, parent, original, pool, {"depth": 1, "contrast": 0})
    deep, deep_metadata = shape_priority_lesson(
        admitted, parent, original, pool, {"depth": 3, "contrast": 0})
    diverse, diverse_metadata = shape_priority_lesson(
        admitted, parent, original, pool, {"depth": 1, "contrast": 1})
    assert admitted._source_preparation_metrics.provider_draws == before + 1
    if rows == original.source_each:
        assert low is original
    else:
        assert low.rows() == original.rows()[:rows]
    assert (low_metadata["token_count"], deep_metadata["token_count"]) == (low_tokens, high_tokens)
    assert (low_metadata["signature_count"], diverse_metadata["signature_count"]) == (
        low_signatures, high_signatures)
    for offer, metadata in ((low, low_metadata), (deep, deep_metadata), (diverse, diverse_metadata)):
        delivered = offer.rows()
        assert len(delivered) == offer.source_each == metadata["delivered_rows"] == rows
        assert offer._planning_generation is original._planning_generation
        assert admitted.require_bound_rows(delivered, offer.source_authority) is offer.source_authority
        assert len({row["id"] for row in delivered}) == rows
        assert len({tuple(row["tokens"]) for row in delivered}) == rows
        assert all(row in pool.rows for row in delivered)
        if capability.startswith("C."):
            for index in range(0, rows, 3):
                active, positive, negative = delivered[index:index + 3]
                assert active["source_id"] == positive["source_id"] == negative["source_id"]
                assert active["answer_kind"] == "numeric_active"
                assert (positive["gold"], negative["gold"]) == ("TRUE", "FALSE")
        else:
            assert Counter((row.get("answer_kind", "binary"), row["gold"],
                            tuple(row.get("operand_truths", ()))) for row in delivered) == Counter(
                (row.get("answer_kind", "binary"), row["gold"],
                 tuple(row.get("operand_truths", ()))) for row in original.rows())
    assert deep_metadata["controls"]["depth_control"] == (
        "SOURCE_TOKEN_LENGTH_PROXY" if high_tokens > low_tokens else None)
    assert diverse_metadata["controls"]["contrast_control"] == (
        "SOURCE_GROUP_DIVERSITY" if high_signatures > low_signatures else None)
    if high_tokens > low_tokens:
        assert deep.rows() != low.rows()
    if high_signatures > low_signatures:
        assert diverse.rows() != low.rows()
    tampered = ({**deep.rows()[0], "tokens": [999999]}, *deep.rows()[1:])
    with pytest.raises(ValueError):
        admitted.require_bound_rows(tampered, deep.source_authority)


def test_finite_boolean_pool_retains_baseline_without_false_credit(admitted, offer_factory):
    parent, draw = offer_factory
    offer = draw("B.NOT")
    pool = prepare_lesson_pool(admitted, offer)
    assert pool.reason == "baseline_only"
    selected, metadata = shape_priority_lesson(
        admitted, parent, offer, pool, {"depth": 3, "contrast": 1})
    assert selected is offer
    assert len(selected.rows()) == 32
    assert metadata["controls"]["depth_control"] is None
    assert metadata["controls"]["contrast_control"] is None



def test_primary_selection_reaches_delivery_and_realized_action(admitted, offer_factory):
    from bilqis_mlx.learning.teacher_realized_action import describe
    from bilqis_mlx.runtime.accepted_priority_candidate_execution import (
        _candidate_delivery_inputs,
    )
    from bilqis_mlx.runtime.factory_candidate_training import FactoryDeliveryObservation
    from bilqis_mlx.errors import BilqisError

    parent, draw = offer_factory
    original = draw("B.AND")
    pool = prepare_lesson_pool(admitted, original)
    policy = {"depth": 3, "contrast": 0, "lr": 0.001}
    shaped, metadata = shape_priority_lesson(admitted, parent, original, pool, policy)
    selection = SimpleNamespace(offer=shaped, metadata={"primary_lesson": metadata})
    capture = SimpleNamespace(attempt_id="attempt", selected_option="instruction",
                              delivery=lambda *args, **kwargs: None)
    observation = FactoryDeliveryObservation(capture, 1, original.rows(), 17)
    result = _candidate_delivery_inputs(
        selection, admitted, shaped.rows(), (), (), {}, {}, {}, observation)
    delivery, observed = result[-2:]
    assert tuple(delivery.specimen_ids) == tuple(row["id"] for row in shaped.rows())
    assert observed.option_rows == shaped.rows()
    assert observed.option_rows != original.rows()
    action = describe(policy, candidate_steps=1, batch_size=len(observed.option_rows),
                      policy_controls=(observed.controls,), guidance_applied_steps=0,
                      enrichment_examples=0)
    assert action["features"]["depth_controls"] == {"SOURCE_TOKEN_LENGTH_PROXY": 1}
    assert action["features"]["semantic_patterns_delivered"] == 4
    assert action["features"]["semantic_patterns_required"] == 4
    assert action["features"]["old_grade_examples_delivered"] == 0

    changed = ({**shaped.rows()[0], "tokens": [999999]}, *shaped.rows()[1:])
    with pytest.raises(BilqisError) as caught:
        _candidate_delivery_inputs(
            selection, admitted, changed, (), (), {}, {}, {}, observation)
    assert caught.value.context["reason"] == "BAMF_PRIORITY_PRIMARY_LESSON_DRIFT"


def test_selected_direct_authority_does_not_redraw_or_accept_foreign_content(admitted, offer_factory):
    from bilqis_mlx.factory.teaching import describe_delivered_teaching
    from bilqis_mlx.runtime.factory_training_preparation import _selected_delivery_authority
    from bilqis_mlx.errors import BilqisError

    parent, draw = offer_factory
    original = draw("C.ADD")
    pool = prepare_lesson_pool(admitted, original)
    shaped, _ = shape_priority_lesson(
        admitted, parent, original, pool, {"depth": 3, "contrast": 1})
    rows, authority = shaped.rows(), shaped.source_authority
    execution = admitted.release.execution_plan.capability_map["C.ADD"]
    delivery = describe_delivered_teaching(
        admitted.release, "C.ADD", execution.teaching_option_ids[0], rows)
    draws = admitted._source_preparation_metrics.provider_draws
    with evidence_mode(strict=True):
        assert _selected_delivery_authority(
            admitted, rows, authority, delivery, "C.ADD", 17) is authority
        with pytest.raises(BilqisError):
            _selected_delivery_authority(admitted, rows, authority, delivery, "C.ADD", 18)
        with pytest.raises(BilqisError):
            _selected_delivery_authority(admitted, rows, authority, delivery, "C.SUB", 17)
        changed = ({**rows[0], "tokens": [999999]}, *rows[1:])
        with pytest.raises(BilqisError):
            _selected_delivery_authority(admitted, changed, authority, delivery, "C.ADD", 17)
        extra = ({**rows[0], "id": "foreign"},)
        with pytest.raises(BilqisError):
            _selected_delivery_authority(
                admitted, (*rows, *extra), authority, delivery, "C.ADD", 17)
    assert admitted._source_preparation_metrics.provider_draws == draws


def test_protected_interference_reserves_real_primary_rows_and_rotates_rehearsal(
        admitted, offer_factory):
    from bilqis_mlx.runtime.bamf_operator.session_parts.rehearsal import (
        RehearsalPlan, materialize_rehearsal_rows, reserve_preservation,
    )

    parent, draw = offer_factory
    original = draw("A.PARENT")
    pool = prepare_lesson_pool(admitted, original)
    protected = ("A.IDENTITY", "A.MAPS", "A.MEMBER")
    target = SimpleNamespace(protected_capability_ids=protected)
    protection = SimpleNamespace(digest="a" * 64)
    teacher = {"causal_experiment": {"negative_archetypes": [
        {"capability": "A.PARENT", "curriculum_scope": "school",
         "fixed_reference_deltas": {"A.MAPS": -.8, "A.IDENTITY": -.2, "A.PARENT": -1}},
        {"capability": "A.EDGE", "curriculum_scope": "school",
         "fixed_reference_deltas": {"A.MEMBER": -1}},
        {"capability": "A.PARENT", "curriculum_scope": "other",
         "fixed_reference_deltas": {"A.MEMBER": -1}},
    ]}}
    reduced, allocation = reserve_preservation(
        admitted, original, pool, protection, target, teacher, "school")
    assert allocation["reserved_rows"] == 8
    shaped, _ = shape_priority_lesson(
        admitted, parent, original, reduced, {"depth": 1, "contrast": 0})
    assert shaped.source_each == 24
    assert Counter(row["gold"] for row in shaped.rows()) == {"TRUE": 12, "FALSE": 12}
    assert admitted.require_bound_rows(shaped.rows(), shaped.source_authority) is shaped.source_authority
    plan = RehearsalPlan("A.PARENT", "A", (), protected, (),
                         "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                         preservation_allocation=allocation)
    counts = Counter()
    for ordinal in range(1, 7):
        delivered = materialize_rehearsal_rows(admitted, plan, ordinal)
        rows = delivered.retention_support
        assert len(rows) + shaped.source_each == 32
        assert Counter(row["gold"] for row in rows) == {"TRUE": 4, "FALSE": 4}
        assert len({row["id"] for row in rows}) == len(rows)
        for row in rows:
            authority = delivered.authorities_by_id[row["id"]]
            assert admitted.require_bound_rows((row,), authority) is authority
            counts[row["capability"]] += 1
    assert set(counts) == set(protected)
    assert counts["A.MAPS"] > counts["A.MEMBER"]

    neutral_pool, neutral = reserve_preservation(
        admitted, original, pool, protection, target, {}, "school")
    assert neutral["reserved_rows"] == 4
    assert len(neutral_pool.baseline) == 28
    assert reduced != neutral_pool
    # No authority for a non-predicate or incomplete construction: unchanged.
    other = draw("B.AND")
    other_pool = prepare_lesson_pool(admitted, other)
    assert reserve_preservation(
        admitted, other, other_pool, protection, target, teacher, "school"
    ) == (other_pool, None)
