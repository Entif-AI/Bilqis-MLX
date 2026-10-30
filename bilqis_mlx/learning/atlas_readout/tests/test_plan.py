"""Plans validate exact schema coordinates and dependency graphs before execution."""
from dataclasses import replace
import unittest
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.control import ControlAction as C
from bilqis_mlx.learning.atlas_readout.plan import DecisionKind as K, DecisionSpec as D
from bilqis_mlx.learning.atlas_readout.records import RoleCandidate
from bilqis_mlx.learning.atlas_readout.tests.plan_helpers import plan, concept


def standard_decisions():
    return (D('control', 'agent', 0, K.CONTROL, (C.EMIT_VALUE, C.EMIT_UNKNOWN)),
            D('value', 'agent', 0, K.VALUE, (concept(),), ('control',)),
            D('end', None, 0, K.CONTROL, (C.END_FRAME,), ('value',)))


class PlanTests(unittest.TestCase):
    def test_topology_order_is_stable(self):
        source = standard_decisions()
        first = plan(source)
        other = plan(source[::-1])
        self.assertEqual(first.execution_order, ('control', 'value', 'end'))
        self.assertEqual(first.execution_order, other.execution_order)

    def test_cycles_missing_parents_and_duplicate_ids_reject(self):
        base = standard_decisions()
        for nodes in ((replace(base[0], depends_on=('value',)), *base[1:]),
                      (base[0], replace(base[1], depends_on=('missing',)), base[2]),
                      (*base, base[0])):
            with self.subTest(nodes=nodes), self.assertRaises(BilqisError):
                plan(nodes)

    def test_schema_occurrence_and_foreign_role_keys_reject(self):
        for occurrence in (-1, 2, True):
            with self.assertRaises(BilqisError):
                plan((D('r', 'theme', occurrence, K.ROLE,
                        (RoleCandidate('frame:fixture', 1, 'theme', 1),)),))
        with self.assertRaises(BilqisError):
            plan((D('r', 'agent', 0, K.ROLE,
                    (RoleCandidate('frame:wrong', 1, 'agent', 0),)),))

    def test_budget_generation_and_source_span_are_explicit(self):
        base = plan(standard_decisions())
        for changes in ({'maximum_decisions': 65}, {'maximum_decisions': True},
                        {'input_prefix_end': 1025}, {'generation_binding': ''},
                        {'input_prefix_end': 3}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                replace(base, **changes)

    def test_value_requires_exact_direct_control_parent(self):
        base = standard_decisions()
        for node in (replace(base[1], depends_on=()),
                     replace(base[1], role_id='theme'),
                     replace(base[1], depends_on=('end',))):
            with self.assertRaises(BilqisError):
                plan((base[0], node))
