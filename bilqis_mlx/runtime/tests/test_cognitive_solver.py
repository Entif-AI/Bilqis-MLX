"""Frozen A07/B11-shaped fixtures; concrete source implementations stay upstream."""
from dataclasses import dataclass
import unittest
from bilqis_mlx.semantics.core import Signature
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.runtime.cognitive_solver import solve_task

CONTEXT = dict(semantic_release='release-1', rights_epoch='rights-1', generation='gen-1', causal_prefix_end=10)


@dataclass(frozen=True)
class ValueFixture:
    type_name: str
    value: object
    binding: dict


def value(kind, data, **changes):
    binding = {**CONTEXT, 'scope': 'public', 'visible_end': 1,
               'content_id': contract_digest((kind, data))}
    return ValueFixture(kind, data, {**binding, **changes})


@dataclass(frozen=True)
class OperatorFixture:
    operator_id: str
    signature: Signature
    kind: str = 'EXACT'
    implementation_sha256: str = 'a' * 64
    effect: str = 'PURE'
    source_binding: dict = None
    def __post_init__(self):
        if self.source_binding is None:
            object.__setattr__(self, 'source_binding', {'semantic_release': 'release-1', 'rights_epoch': 'rights-1', 'allowed_scopes': ('public',)})


class RegistryFixture:
    def __init__(self, operators):
        self.operators = {op.operator_id: op for op in operators}
    def require(self, identity):
        return self.operators[identity]


def node(identity, operator, refs, result='Integer'):
    return dict(node_id=identity, operator_id_or_hole=operator, ordered_operand_refs=refs,
                expected_output_signature=result, scope='public')


class CognitiveSolverTest(unittest.TestCase):
    def setUp(self):
        self.registry = RegistryFixture((
            OperatorFixture('ADD', Signature(('Integer', 'Integer'), 'Integer')),
            OperatorFixture('MUL', Signature(('Integer', 'Integer'), 'Integer')),
            OperatorFixture('NEURAL', Signature(('Integer', 'Integer'), 'Integer'), kind='NEURAL'),
            OperatorFixture('LOOKUP', Signature(('Actor',), 'Integer'), kind='CACHED'),
        ))
        self.nodes = (node('mul', 'MUL', (('literal', value('Integer', 2)), ('literal', value('Integer', 3)))),
                      node('add', 'ADD', (('result', 'mul'), ('literal', value('Integer', 4)))))
        self.execution_count = 0

    def execute(self, identity, args, binding):
        self.execution_count += 1
        numbers = [item.value for item in args]
        if identity == 'ADD': return value('Integer', sum(numbers))
        if identity == 'MUL': return value('Integer', numbers[0] * numbers[1])
        if identity == 'LOOKUP': return value('Integer', {'alice': 2, 'bob': 7}[numbers[0]])
        raise ValueError('unsupported fixture')

    def solve(self, nodes=None, budget=None, inputs=None, cache=None, decoder=None, execute=None):
        budget = budget or {'operations': 2, 'decisions': 64}
        task = dict(goal_id='fixture', output_signature='Integer', source_visible_bindings=inputs or {},
                    expression_or_holes=self.nodes if nodes is None else nodes,
                    allowed_operator_ids=tuple(self.registry.operators), budget=budget)
        return solve_task(task, CONTEXT, 'gen-1', budget, registry=self.registry,
            binding_for=lambda item: item.binding, authorize_scope=lambda context, scope, generation: scope == 'public',
            execute_pure=execute or self.execute, is_applicable=lambda op, args, ctx: True,
            lookup_qualified_cache=cache or (lambda *args: None),
            decode_holes=decoder or (lambda holes, *args: {identity: 0 for identity in holes}),
            constraints_satisfied=lambda *args: True)

    def test_exact_two_node_composition(self):
        result = self.solve()
        self.assertEqual(result.status, 'RESOLVED')
        self.assertEqual(result.answer.value, 10)
        self.assertEqual((result.operations, result.decisions), (2, 0))
        self.assertEqual(result.executed_nodes, ('mul', 'add'))

    def test_exact_route_ignores_unused_neural_budget(self):
        refs = (('literal', value('Integer', 2)), ('literal', value('Integer', 3)))
        hole = {'candidates': ({'operator_id': 'ADD', 'operand_refs': refs}, {'operator_id': 'NEURAL', 'operand_refs': refs}), 'constraints': ()}
        result = self.solve(nodes=(node('answer', hole, ()),), budget={'operations': 1, 'decisions': 0})
        self.assertEqual(result.answer.value, 5)
        self.assertEqual((result.operations, result.decisions), (1, 0))

    def test_dependent_operator_and_operand_binding_from_one_decoder(self):
        refs = ((('input', 'frame', 'actor', 0),), (('input', 'frame', 'actor', 1),))
        hole = {'candidates': tuple({'operator_id': 'LOOKUP', 'operand_refs': ref} for ref in refs), 'constraints': ('qualified-actor',)}
        calls = []
        def decode(holes, visible, context, generation):
            calls.append(holes)
            return {'answer': 1}
        result = self.solve(nodes=(node('answer', hole, ()),),
            inputs={('frame', 'actor', 0): value('Actor', 'alice'), ('frame', 'actor', 1): value('Actor', 'bob')},
            decoder=decode)
        self.assertEqual(result.answer.value, 7)
        self.assertEqual(result.decisions, 2)
        self.assertEqual(len(calls), 1)
        self.assertEqual(result.selected_bindings[0][2], refs[1])

    def test_cache_is_keyed_and_never_executes_at_zero_compute_cost(self):
        actor = value('Actor', 'bob')
        refs = (('input', 'frame', 'actor', 0),)
        expected = {'operator': 'LOOKUP', 'implementation': 'a' * 64,
            'dependencies': ({'ref': refs[0], 'content_id': actor.binding['content_id'], 'type': 'Actor'},),
            'semantic_release': 'release-1', 'rights_epoch': 'rights-1', 'generation': 'gen-1', 'scope': 'public'}
        entries = {contract_digest(expected): value('Integer', 7)}
        result = self.solve(nodes=(node('answer', 'LOOKUP', refs),), inputs={('frame', 'actor', 0): actor},
            budget={'operations': 0, 'decisions': 0}, cache=lambda digest, key, context: entries.get(digest))
        self.assertEqual(result.answer.value, 7)
        self.assertEqual((result.operations, result.lookups, self.execution_count), (0, 1, 0))
        result = self.solve(nodes=(node('answer', 'LOOKUP', refs),), inputs={('frame', 'actor', 0): actor},
            budget={'operations': 0, 'decisions': 0})
        self.assertEqual(result.reason, 'OPERATION_BUDGET_EXHAUSTED')

    def test_stale_private_and_future_inputs_fail_before_execution(self):
        for change in ({'semantic_release': 'old'}, {'rights_epoch': 'revoked'}, {'generation': 'old'}, {'scope': 'private'}, {'visible_end': 11}):
            with self.subTest(change=change):
                bad = value('Integer', 2, **change)
                result = self.solve(nodes=(node('answer', 'ADD', (('literal', bad), ('literal', value('Integer', 3)))),))
                self.assertEqual(result.status, 'UNRESOLVED')
                self.assertEqual(self.execution_count, 0)

    def test_operator_failure_and_invalid_output_are_explicit(self):
        def broken(*args): raise KeyError('missing source')
        result = self.solve(execute=broken)
        self.assertEqual(result.status, 'UNRESOLVED')
        result = self.solve(execute=lambda *args: value('Boolean', True))
        self.assertEqual(result.reason, 'INVALID_OPERATOR_OUTPUT')

    def test_cycle_depth_and_budget_are_bounded(self):
        result = self.solve(budget={'operations': 1, 'decisions': 64})
        self.assertEqual(result.reason, 'OPERATION_BUDGET_EXHAUSTED')
        cycle = (node('a', 'ADD', (('result', 'b'), ('literal', value('Integer', 1)))),
                 node('b', 'ADD', (('result', 'a'), ('literal', value('Integer', 1)))))
        self.assertEqual(self.solve(nodes=cycle).status, 'UNRESOLVED')
        nodes = tuple(node(str(i), 'ADD', (('literal', value('Integer', 0)) if i == 0 else ('result', str(i-1)),
                                               ('literal', value('Integer', 1)))) for i in range(9))
        self.assertEqual(self.solve(nodes=nodes).reason, 'DEPTH_LIMIT')


if __name__ == '__main__': unittest.main()
