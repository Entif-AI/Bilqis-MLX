"""B10/C04 request disposition is derived from source-owned typed goals."""
from types import SimpleNamespace
import unittest

from bilqis_mlx.runtime.refinement_request import (
    RefinementRequestKind, refinement_request_disposition,
)
from bilqis_mlx.semantics.cognitive_dag import (
    DAGBudget, DAGNode, DAGOperand, DAGProgram, RefKind, TaskGoal,
)
from bilqis_mlx.semantics.numeric import calculate, number
from bilqis_mlx.source_adapters.numeric import encode
from bilqis_mlx.source_adapters.numeric_task_goal import lower_numeric_task_goal
from bilqis_mlx.curriculum import AnswerFamily, BINARY
from bilqis_mlx.source_adapters.answer_choice_task_goal import lower_answer_choice_task_goal


RELEASE = "b" * 64


def _capability(name="ADD"):
    return SimpleNamespace(
        capability_id="C." + name,
        provider_parameters=(("numbers", tuple(str(i) for i in range(11))),),
    )


def _release(*operators):
    return SimpleNamespace(execution_plan=SimpleNamespace(capabilities=tuple(
        SimpleNamespace(capability_id="C." + item, source_anchor="school.op." + item)
        for item in operators)))


class RefinementRequestDispositionTests(unittest.TestCase):
    def test_flat_source_answer_choice_is_ordinary(self):
        capability = SimpleNamespace(
            capability_id="A.IDENTITY",
            answer_families=(AnswerFamily("binary", BINARY),),
        )
        goal, _ = lower_answer_choice_task_goal(
            {"id": "ordinary", "capability": "A.IDENTITY", "tokens": [1, 2]},
            semantic_release=RELEASE, capability=capability,
        )
        actual = refinement_request_disposition(goal)
        self.assertIs(actual.kind, RefinementRequestKind.ORDINARY)
        self.assertEqual(actual.requested_roles, ())
        self.assertFalse(actual.explicit_member_question)
        self.assertFalse(actual.unresolved_nested_query)

    def test_unresolved_root_over_prior_result_is_nested(self):
        expression = calculate("ADD", calculate("MUL", number(2), number(3)), number(4))
        row = {
            "id": "nested", "capability": "C.ADD",
            "record": {"symbols": encode(expression)}, "tokens": [1, 2, 3, 4],
        }
        goal, _ = lower_numeric_task_goal(
            row, semantic_release=RELEASE, capability=_capability(),
            release=_release("ADD", "SUB", "MUL", "DIV"),
        )
        actual = refinement_request_disposition(goal)
        self.assertIs(actual.kind, RefinementRequestKind.UNRESOLVED_NESTED)
        self.assertFalse(actual.explicit_member_question)
        self.assertTrue(actual.unresolved_nested_query)

    def test_direct_typed_frame_member_is_explicit_member(self):
        member = DAGOperand(
            RefKind.INPUT, "ConceptRef", frame_handle="frame:1",
            frame_occurrence_id="occ:1", role_id="theme", occurrence_index=0,
        )
        node = DAGNode("answer", "IDENTITY", (member,), "ConceptRef", "fixture")
        goal = TaskGoal(
            "member", "ConceptRef", (member.identity,),
            DAGProgram((node,), "answer", "fixture"), ("IDENTITY",), DAGBudget(),
            RELEASE, "fixture",
        )
        actual = refinement_request_disposition(goal)
        self.assertIs(actual.kind, RefinementRequestKind.EXPLICIT_MEMBER)
        self.assertEqual(actual.requested_roles, ("theme",))
        self.assertTrue(actual.explicit_member_question)
        self.assertFalse(actual.unresolved_nested_query)


if __name__ == "__main__":
    unittest.main()
