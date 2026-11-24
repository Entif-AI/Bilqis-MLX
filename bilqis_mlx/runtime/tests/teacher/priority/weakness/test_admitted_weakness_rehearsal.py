"""Whole source construction and exposure-priority witnesses."""
from dataclasses import replace
from types import SimpleNamespace as NS

from bilqis_mlx.factory._model.weakness import classify_weakness
from bilqis_mlx.runtime.bamf_operator.session_parts.rehearsal import (
    RehearsalPlan, _seed, materialize_rehearsal_rows,
)
from bilqis_mlx.runtime.bamf_operator.session_parts.weakness_rehearsal import (
    GroupOffer, choose_groups, delivered_weakness_controls, targeted_groups,
)
from bilqis_mlx.runtime.structural_weakness_capture import _provider_for_context
from bilqis_mlx.runtime.tests.teacher.priority.source_materialization.test_priority_lesson import (
    admitted,
)


def test_actual_numeric_rehearsal_keeps_all_views_and_credits_matching_row_only(admitted):
    capability = "C.ADD"
    execution, adapter, descriptor = _provider_for_context(admitted, capability)
    plan = RehearsalPlan(capability, "C", (), (), (),
                         "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                         weakness_capacity=3)
    seed = _seed(plan, "preservation", capability, 16)
    rows, _ = admitted.draw_bound_rows(seed=seed, capability=capability, each=6)
    wanted = classify_weakness(adapter, execution, rows[0], provider_descriptor=descriptor)
    key = "context:" + wanted.class_sha256
    plan = replace(plan, weakness_records=({
        "weakness_class": wanted.to_record(), "context": {"context_sha256": "context"},
        "historical_source_ids": ["historical"],
    },))
    result = materialize_rehearsal_rows(admitted, plan, 1)
    assert len(result.preservation) == 3
    assert len({row["source_id"] for row in result.preservation}) == 1
    assert [row["answer_kind"] for row in result.preservation] == [
        "numeric_active", "binary", "binary"]
    assert [row["gold"] for row in result.preservation[1:]] == ["TRUE", "FALSE"]
    assert result.weakness_unavailable == ()
    for row in result.preservation:
        authority = result.authorities_by_id[row["id"]]
        assert admitted.require_bound_rows((row,), authority) is authority
    actual = delivered_weakness_controls(
        admitted, capability, result.preservation, result.bindings_by_id)
    assert actual["weakness_class_matches"] == {key: [result.preservation[0]["id"]]}
    assert actual["weakness_targets_delivered"] == 1
    assert actual["priority_weakness_targets_delivered"] == 1


def test_group_allocator_skips_unavailable_debt_without_splitting_or_colliding():
    def group(name, n, key, token):
        rows = tuple({"id": f"{name}:{i}", "tokens": (token, i)} for i in range(n))
        return GroupOffer(rows, ((rows[0]["id"], key),), rows, object(), 17)

    first = group("first", 3, "least-exposed", 1)
    second = group("second", 3, "more-exposed", 2)
    collided = group("collision", 3, "least-exposed", 3)
    result, served, remaining = choose_groups(
        [second, collided, first], ("missing", "least-exposed", "more-exposed"), 3,
        reserved_rows=({"id": "collision:1", "tokens": (8,)},))
    assert result == (first,)
    assert served == {"least-exposed"}
    assert remaining == 0
    result, served, remaining = choose_groups(
        [second, first], ("more-exposed", "least-exposed"), 2)
    assert result == () and served == set() and remaining == 2


def test_shared_draw_budget_preserves_least_exposed_order(admitted):
    capability = "C.ADD"
    execution, adapter, descriptor = _provider_for_context(admitted, capability)
    plan = RehearsalPlan(capability, "C", (), (), (),
                         "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                         weakness_capacity=3)
    seed = _seed(plan, "preservation", capability, 16)
    rows, _ = admitted.draw_bound_rows(seed=seed, capability=capability, each=6)
    wanted = [classify_weakness(adapter, execution, row, provider_descriptor=descriptor)
              for row in rows[:3]]
    records = tuple({"weakness_class": item.to_record(),
                     "context": {"context_sha256": "context"},
                     "historical_source_ids": ["historical"]} for item in wanted[:2])
    keys = ["context:" + item.class_sha256 for item in wanted[:2]]
    plan = replace(plan, weakness_records=records, weakness_exposures=((keys[0], 8),))
    offers, unavailable = targeted_groups(admitted, plan, 1, _seed, 4)
    # The exact source group may serve both debts. Its less-exposed matching row
    # must be present even though the higher-exposed debt was listed first.
    assert any(key == keys[1] for offer in offers for _, key in offer.matches)
    assert keys[1] not in dict(unavailable)



def test_retention_support_keeps_actual_numeric_source_family_whole(admitted):
    from bilqis_mlx.source_adapters.lesson_geometry import geometry_for_adapter

    _, adapter, _ = _provider_for_context(admitted, "C.ADD")
    plan = RehearsalPlan("C.MUL", "C", (), ("C.ADD",), (),
                         "a" * 64, "b" * 64, "c" * 64, "d" * 64,
                         support_geometries=(("C.ADD", geometry_for_adapter(adapter)),))
    result = materialize_rehearsal_rows(admitted, plan, 1)
    assert len(result.retention_support) == 3
    assert len({row["source_id"] for row in result.retention_support}) == 1
    assert [row["answer_kind"] for row in result.retention_support] == [
        "numeric_active", "binary", "binary"]
    assert [row["gold"] for row in result.retention_support[1:]] == ["TRUE", "FALSE"]
    for row in result.retention_support:
        authority = result.authorities_by_id[row["id"]]
        assert admitted.require_bound_rows((row,), authority) is authority
