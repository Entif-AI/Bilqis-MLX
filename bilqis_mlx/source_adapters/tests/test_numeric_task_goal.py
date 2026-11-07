"""The numeric source owner lowers gold-blind C04 goals from admitted structure."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.source_adapters.numeric import encode
from bilqis_mlx.source_adapters.numeric_task_goal import lower_numeric_task_goal
from bilqis_mlx.semantics.numeric import calculate, number


def _capability(name="ADD"):
    return SimpleNamespace(
        capability_id="C." + name,
        provider_parameters=(("numbers", tuple(str(i) for i in range(11))),),
    )


def _release(*operators):
    items = tuple(SimpleNamespace(
        capability_id="C." + item,
        source_anchor="school.op." + item)
                  for item in operators)
    return SimpleNamespace(execution_plan=SimpleNamespace(capabilities=items))


class NumericTaskGoalTests(unittest.TestCase):
    def test_source_visible_addition_becomes_bounded_admitted_operator_hole(self):
        expression = calculate("ADD", number(2), number(3))
        row = {
            "id": "numeric-case-1", "capability": "C.ADD",
            "record": {"symbols": encode(expression)}, "tokens": [1, 2, 3, 4],
        }

        goal, binding = lower_numeric_task_goal(
            row, semantic_release="b" * 64, capability=_capability(),
            release=_release("ADD", "SUB", "MUL", "DIV"))

        root = goal.expression_or_holes.nodes[-1]
        self.assertEqual(root.operator_id, None)
        self.assertEqual(root.candidate_operator_ids, ("ADD", "DIV", "MUL", "SUB"))
        self.assertNotIn("MOD", root.candidate_operator_ids)
        self.assertEqual(goal.semantic_release, "b" * 64)
        self.assertEqual(binding.task.scope, "C.ADD")
        self.assertEqual(len(binding.operands), 2)

    def test_evaluator_gold_is_forbidden_at_lowering_boundary(self):
        expression = calculate("ADD", number(2), number(3))
        row = {
            "id": "numeric-case-1", "capability": "C.ADD", "gold": "5",
            "record": {"symbols": encode(expression)}, "tokens": [1, 2, 3, 4],
        }
        with self.assertRaises(BilqisError) as raised:
            lower_numeric_task_goal(
                row, semantic_release="b" * 64, capability=_capability(),
                release=_release("ADD", "SUB"))
        self.assertEqual(
            raised.exception.context["reason"],
            "BAMF_C04_NUMERIC_SOURCE_VIEW_INVALID")


if __name__ == "__main__":
    unittest.main()
