from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from bilqis_mlx.grade_a_probe import read_sources
from bilqis_mlx.live_grade_b import independent_truth
from bilqis_mlx.live_grade_c import registry_graph
from bilqis_mlx.boolean_association import draw_grade_associations, draw_b_grade_bridges
from bilqis_mlx.boolean_association import constructor_digest, VERSION
from bilqis_mlx.grade_a_trainer import (
    _association_rows_for_lesson, _extend_binary_guidance,
)


ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "vendor" / "legacy-v16"


def test_four_a_and_four_c_questions_compose_opaque_source_assertions():
    graph = registry_graph()
    rows = tuple(draw_grade_associations(
        LEGACY, graph, grade=grade, seed=2026101801, maximum=6, count=4)
        for grade in ("A", "C"))

    for grade, questions in zip(("A", "C"), rows):
        assert len(questions) == 4
        for row in questions:
            truths = tuple(row["operand_truths"])
            expected = row["gold"] == "TRUE"
            assert independent_truth(row["record"]["operator"], truths) == expected
            assert all(child["capability"].startswith(grade + ".")
                       for child in row["record"]["children"])
            assert row["tokens"][0] == graph["tokens"].index("task.evaluate")
            assert row["tokens"][1] == graph["tokens"].index(
                "cogal.operator." + row["record"]["operator"])
            assert row["tokens"][-1] == graph["tokens"].index("syntax.end")
            assert len(row["tokens"]) <= 96


def test_association_draw_is_seeded_but_not_a_fixed_question_bank():
    graph = registry_graph()
    first = draw_grade_associations(
        LEGACY, graph, grade="C", seed=17, maximum=6, count=4)
    again = draw_grade_associations(
        LEGACY, graph, grade="C", seed=17, maximum=6, count=4)
    changed = draw_grade_associations(
        LEGACY, graph, grade="C", seed=18, maximum=6, count=4)
    assert first == again
    assert {row["id"] for row in first} != {row["id"] for row in changed}


def test_association_draw_can_rehearse_every_binary_b_operator():
    graph = registry_graph()
    operators = set()
    golds = set()
    for seed in range(40):
        rows = draw_grade_associations(LEGACY, graph, grade="A", seed=seed,
                                       maximum=6, count=4)
        operators.update(row["record"]["operator"] for row in rows)
        golds.update(row["gold"] for row in rows)
    assert operators == {"AND", "OR", "XOR", "IMPLIES", "IFF"}
    assert golds == {"TRUE", "FALSE"}
    assert len(constructor_digest()) == 64
    assert VERSION.startswith("bilqis.mlx.boolean-association-bridge/")


def test_b_grade_bridge_borrows_four_a_and_four_c_without_relabeling_sources():
    graph = registry_graph()
    rows = draw_b_grade_bridges(
        LEGACY, graph, seed=2026101802, maximum=6, per_source=4)
    assert len(rows) == 8
    assert all(row["capability"].startswith("B.") for row in rows)
    assert [row["association_grade"] for row in rows].count("A") == 4
    assert [row["association_grade"] for row in rows].count("C") == 4
    assert all(all(child["capability"].startswith(row["association_grade"] + ".")
                   for child in row["record"]["children"])
               for row in rows)


def test_b_grade_bridge_targets_the_capability_currently_being_taught():
    graph = registry_graph()
    rows = draw_b_grade_bridges(
        LEGACY, graph, seed=2026101802, maximum=6, per_source=4,
        capability="B.IFF")
    assert len(rows) == 8
    assert {row["capability"] for row in rows} == {"B.IFF"}
    assert {row["record"]["operator"] for row in rows} == {"IFF"}


def test_b_grade_bridge_can_target_unary_not():
    graph = registry_graph()
    rows = draw_b_grade_bridges(
        LEGACY, graph, seed=2026101803, maximum=6, per_source=4,
        capability="B.NOT")
    assert len(rows) == 8
    assert {row["capability"] for row in rows} == {"B.NOT"}
    assert {row["record"]["operator"] for row in rows} == {"NOT"}
    assert all(len(row["operand_truths"]) == 1 for row in rows)


def test_trainer_exposes_bridge_only_during_b_lessons():
    course = SimpleNamespace(grades=tuple(
        SimpleNamespace(id=grade) for grade in ("A", "B", "C")))
    synthetic = tuple({"id": str(i)} for i in range(8))
    with patch("bilqis_mlx.grade_a_trainer.numeric_maximum", return_value=6), \
            patch("bilqis_mlx.boolean_association.draw_b_grade_bridges",
                  return_value=synthetic) as draw:
        assert _association_rows_for_lesson(None, {}, course, "A", "A.IDENTITY", seed=1,
                                            enabled=True) == ()
        assert _association_rows_for_lesson(None, {}, course, "C", "C.ADD", seed=1,
                                            enabled=True) == ()
        assert _association_rows_for_lesson(None, {}, course, "B", "B.IFF", seed=1,
                                            enabled=True) == synthetic
        draw.assert_called_once_with(
            None, {}, seed=1, maximum=6, per_source=4, capability="B.IFF")


def test_bridge_rows_receive_no_mentor_weight_when_appended_to_b_lesson():
    guidance = (np.asarray([[.2, .8], [.9, .1]], dtype=np.float32),
                np.asarray([.04, .03], dtype=np.float32))
    rows = [{"gold": "TRUE"}, {"gold": "FALSE"}]
    target, strength = _extend_binary_guidance(guidance, rows)
    assert target.shape == (4, 2)
    assert strength.shape == (4,)
    np.testing.assert_allclose(target[:2], guidance[0])
    np.testing.assert_allclose(strength[:2], guidance[1])
    np.testing.assert_allclose(strength[2:], [0., 0.])
