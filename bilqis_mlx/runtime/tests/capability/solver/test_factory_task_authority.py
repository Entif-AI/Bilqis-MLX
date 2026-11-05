"""Factory C04 task authority keeps evaluator truth outside source lowering."""
import unittest
from types import SimpleNamespace

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.curriculum import AnswerFamily, BINARY, BOOLEAN_OPERATORS
from bilqis_mlx.runtime.factory_task_authority import (
    FactoryTaskAuthority, _source_view,
)
from bilqis_mlx.source_adapters.answer_choice_task_goal import (
    lower_answer_choice_task_goal,
)


class FactoryTaskAuthorityTests(unittest.TestCase):
    def test_source_view_removes_evaluator_owned_fields(self):
        row = {
            "id": "case-1", "capability": "Z.C0", "tokens": [1, 2],
            "source_family_id": "fresh-family", "episode_id": "fresh-episode",
            "gold": "TRUE", "native_output": {"token_id": 2},
            "auxiliary_labels": {"role": "subject"},
            "answer": "TRUE", "label": "TRUE", "expected": "TRUE",
            "expected_answer": "TRUE", "score": 1,
            "oracle_result": {"correct": True},
        }

        visible = _source_view(row)

        self.assertEqual(visible, {
            "id": "case-1", "capability": "Z.C0", "tokens": [1, 2],
            "source_family_id": "fresh-family", "episode_id": "fresh-episode",
        })

    def test_caller_cannot_construct_factory_task_authority(self):
        with self.assertRaises(BilqisError):
            FactoryTaskAuthority()

    def test_answer_choice_lowering_is_gold_blind_and_factory_domain_bounded(self):
        binary = SimpleNamespace(
            capability_id="A.IDENTITY",
            answer_families=(AnswerFamily("binary", BINARY),),
        )
        operator = SimpleNamespace(
            capability_id="B.IDBOOLOPS",
            answer_families=(AnswerFamily("boolean_operator", BOOLEAN_OPERATORS),),
        )
        row = {"id": "row-1", "capability": "A.IDENTITY", "tokens": [1],
               "gold": "TRUE"}
        release = "a" * 64
        with self.assertRaises(ValueError):
            lower_answer_choice_task_goal(
                row, semantic_release=release, capability=binary)

        binary_goal, binary_binding = lower_answer_choice_task_goal(
            _source_view(row), semantic_release=release, capability=binary)
        self.assertEqual(binary_goal.output_signature, "Boolean")
        self.assertEqual(binary_goal.allowed_operator_ids, ("SELECT_BOOLEAN",))
        self.assertEqual(
            tuple(item.typed.value for item in binary_binding.operands),
            (False, True))

        operator_goal, operator_binding = lower_answer_choice_task_goal(
            {"id": "row-2", "capability": "B.IDBOOLOPS", "tokens": [1]},
            semantic_release=release, capability=operator)
        self.assertEqual(operator_goal.output_signature, "OperatorId")
        self.assertEqual(operator_goal.allowed_operator_ids, ("SELECT_OPERATOR_ID",))
        self.assertEqual(
            tuple(item.typed.value for item in operator_binding.operands),
            BOOLEAN_OPERATORS)

if __name__ == "__main__":
    unittest.main()
