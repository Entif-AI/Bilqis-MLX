"""Behavioral tests for exact, complete source-group selection."""

import pytest

from bilqis_mlx.learning.native_lesson_selection import (
    LessonCapacityError, LessonGroup, select_group_lesson,
)


def group(name, size, *, gold="TRUE", stratum="required", kind="binary"):
    return LessonGroup(({"id": name, "tokens": [ord(name)] * size,
                         "answer_kind": kind, "gold": gold},), stratum)


def select(base, pool, *, seed=17, deep=False, contrast=False):
    return select_group_lesson(base, pool, seed=seed, deep=deep, contrast=contrast)


def test_depth_increases_tokens_without_changing_mandatory_slot_census():
    a = group("a", 1, stratum="TRUE")
    b = group("b", 4, stratum="TRUE")
    c = group("c", 1, gold="FALSE", stratum="FALSE")
    d = group("d", 5, gold="FALSE", stratum="FALSE")
    base, pool = (a, c), (a, b, c, d)
    low, high = select(base, pool), select(base, pool, deep=True)
    assert tuple(row["id"] for row in high.rows) == ("b", "d")
    assert high.token_count == 9
    assert high.depth_control == "SOURCE_TOKEN_LENGTH_PROXY"
    assert low.token_count < high.token_count
    assert low.depth_control == "UNBIASED_SOURCE_GROUPS"
    assert [g.stratum for g in high.groups] == ["TRUE", "FALSE"]
    assert all(any(row is source for g in pool for source in g.rows)
               for row in high.rows)


def test_contrast_changes_whole_group_signature_census_not_row_family_census():
    def pair(name, golds):
        rows = tuple({"id": f"{name}-{i}", "tokens": [ord(name), i],
                      "answer_kind": "numeric_active", "gold": gold}
                     for i, gold in enumerate(golds))
        return LessonGroup(rows, "numeric-pair")
    a, b, c = pair("a", ("A", "B")), pair("b", ("A", "B")), pair("c", ("A", "A"))
    low = select((a, b), (a, b, c), seed=5)
    high = select((a, b), (a, b, c), seed=5, contrast=True)
    assert low.signature_count == 1
    assert high.signature_count == 2
    assert {row["gold"] for row in high.rows} == {row["gold"] for row in low.rows} == {"A", "B"}
    assert high.contrast_control == "SOURCE_GROUP_DIVERSITY"
    assert low.contrast_control == "SOURCE_GROUP_RANDOM"
    assert len(high.rows) == len(low.rows) == 4
    assert high.depth_control is None


def test_ineffective_controls_return_identical_rows_and_no_credit():
    pool = (group("a", 2), group("b", 2), group("c", 2))
    baseline = pool[:2]
    low = select(baseline, pool)
    assert select(baseline, pool, deep=True, contrast=True) == low
    assert low.depth_control is low.contrast_control is None
    assert select(baseline, pool) == low


@pytest.mark.parametrize("duplicate", ["id", "tokens"])
def test_rejects_collisions_across_groups(duplicate):
    a, b = group("a", 1), group("b", 2)
    b.rows[0][duplicate] = a.rows[0][duplicate]
    with pytest.raises(ValueError, match="duplicate"):
        select((a,), (a, b))
    with pytest.raises(ValueError, match="duplicate"):
        select((a, b), (a,))


def test_identical_baseline_pool_and_strict_token_prefix_are_legal():
    a = group("a", 1)
    b = LessonGroup(({"id": "b", "tokens": [ord("a"), 3], "gold": "TRUE"},), "required")
    result = select((a, b), (a, b), deep=True)
    assert {row["id"] for row in result.rows} == {"a", "b"}
    assert result.depth_control is None


def test_pool_capacity_cannot_replace_required_stratum_or_group_size():
    a, b = group("a", 1), group("b", 2, stratum="other")
    with pytest.raises(LessonCapacityError):
        select((a,), (b,))
    pair = LessonGroup((a.rows[0], group("c", 1).rows[0]), a.stratum)
    with pytest.raises(LessonCapacityError):
        select((pair,), (a,))


def test_empty_or_malformed_rows_are_not_eligible():
    for bad in (LessonGroup((), "s"), LessonGroup(({"id": "a"},), "s")):
        with pytest.raises(ValueError):
            select((bad,), (bad,))


@pytest.mark.parametrize("gold", [1, True, None, ["TRUE"]])
def test_nonstring_gold_is_rejected(gold):
    a = group("a", 1, gold=gold)
    with pytest.raises(ValueError, match="invalid lesson row"):
        select((a,), (a,))


def test_aggregate_stratum_capacity_cannot_hide_missing_group_size():
    a, b, c = group("a", 1), group("b", 1), group("c", 1)
    pair = LessonGroup((a.rows[0], b.rows[0]), a.stratum)
    with pytest.raises(LessonCapacityError):
        select((pair, c), (a, b, c))


def test_both_high_earns_no_axis_when_either_alone_delivers_same_effect():
    a = group("a", 4, gold="A", kind="numeric_active")
    b = group("b", 1, gold="A", kind="numeric_active")
    c = group("c", 4, gold="B", kind="numeric_active")
    base, pool = (a, b), (a, b, c)
    depth = select(base, pool, seed=5, deep=True)
    contrast = select(base, pool, seed=5, contrast=True)
    both = select(base, pool, seed=5, deep=True, contrast=True)
    assert tuple(row["id"] for row in both.rows) == ("a", "c")
    assert both.groups == depth.groups == contrast.groups
    assert both.depth_control is both.contrast_control is None
    assert depth.depth_control == "SOURCE_TOKEN_LENGTH_PROXY"
    assert contrast.contrast_control == "SOURCE_GROUP_DIVERSITY"


def test_both_high_preserves_interaction_contrast_gain_on_token_tie():
    a = group("a", 1, gold="A", kind="numeric_active", stratum="X")
    b = group("b", 2, gold="B", kind="numeric_active", stratum="X")
    c = group("c", 1, gold="B", kind="numeric_active", stratum="Y")
    d = group("d", 1, gold="C", kind="numeric_active", stratum="Y")
    base, pool = (a, c, b), (a, b, c, d)
    low = select(base, pool, seed=9)
    both = select(base, pool, seed=9, deep=True, contrast=True)
    assert tuple(row["id"] for row in both.rows) == ("b", "d", "a")
    assert both.token_count == low.token_count == 4
    assert both.signature_count == 3
    assert both.depth_control is None
    assert both.contrast_control == "SOURCE_GROUP_DIVERSITY"
