"""C-owned bounded route execution over frozen A07/B11 protocol boundaries."""
from dataclasses import dataclass
from enum import Enum
from graphlib import CycleError, TopologicalSorter
from bilqis_mlx.semantics.domains import contract_digest
from .operator_registry import TypedValue, OperatorRegistry, CognitiveOperatorSpec
from bilqis_mlx.semantics.core import Signature


class SolveStatus(str, Enum):
    RESOLVED = 'RESOLVED'
    UNRESOLVED = 'UNRESOLVED'


class SolveReason(str, Enum):
    DECISION_BUDGET_EXHAUSTED = 'DECISION_BUDGET_EXHAUSTED'
    DEPTH_LIMIT = 'DEPTH_LIMIT'
    INVALID_CACHED_RESULT = 'INVALID_CACHED_RESULT'
    INVALID_CANDIDATE = 'INVALID_CANDIDATE'
    INVALID_CANDIDATES = 'INVALID_CANDIDATES'
    INVALID_HOLE = 'INVALID_HOLE'
    INVALID_NEURAL_BINDING = 'INVALID_NEURAL_BINDING'
    INVALID_NODE = 'INVALID_NODE'
    INVALID_OPERATOR_OUTPUT = 'INVALID_OPERATOR_OUTPUT'
    INVALID_REFERENCE_OR_ROUTE = 'INVALID_REFERENCE_OR_ROUTE'
    INVALID_TASK_OR_CONTEXT = 'INVALID_TASK_OR_CONTEXT'
    NODE_LIMIT = 'NODE_LIMIT'
    NO_APPLICABLE_OPERATOR = 'NO_APPLICABLE_OPERATOR'
    OPERATION_BUDGET_EXHAUSTED = 'OPERATION_BUDGET_EXHAUSTED'
    OPERATOR_NOT_ALLOWED = 'OPERATOR_NOT_ALLOWED'
    OPERATOR_SOURCE_HELD = 'OPERATOR_SOURCE_HELD'
    OUTPUT_SIGNATURE_MISMATCH = 'OUTPUT_SIGNATURE_MISMATCH'
    SOURCE_SCOPE_HELD = 'SOURCE_SCOPE_HELD'
    UNQUALIFIED_OPERATOR = 'UNQUALIFIED_OPERATOR'
    UNSATISFIED_SIGNATURE = 'UNSATISFIED_SIGNATURE'


@dataclass(frozen=True)
class CapabilityResult:
    status: SolveStatus
    answer: TypedValue | None
    reason: SolveReason | None
    operations: int
    decisions: int
    lookups: int
    executed_nodes: tuple
    selected_bindings: tuple


def solve_task(task, context, generation, budget, *, registry: OperatorRegistry,
               binding_for, authorize_scope, execute_pure, is_applicable,
               lookup_qualified_cache, decode_holes, constraints_satisfied) -> CapabilityResult:
    """Execute one source-lowered task, with one structured hole-decoder request."""
    operations, decisions, lookups = 0, 0, 0
    executed, selected = [], []
    def fail(reason):
        return CapabilityResult(SolveStatus.UNRESOLVED, None, reason, operations, decisions,
                                lookups, tuple(executed), tuple(selected))
    fields = {'goal_id', 'output_signature', 'source_visible_bindings', 'expression_or_holes', 'allowed_operator_ids', 'budget'}
    required_context = {'semantic_release', 'rights_epoch', 'generation', 'causal_prefix_end'}
    if (not isinstance(task, dict) or set(task) != fields or task['budget'] != budget
            or not isinstance(context, dict) or not required_context <= set(context)
            or context['generation'] != generation or not isinstance(generation, str) or not generation
            or not isinstance(budget, dict) or set(budget) != {'operations', 'decisions'}
            or any(type(v) is not int or v < 0 for v in budget.values()) or budget['decisions'] > 64
            or not isinstance(task['source_visible_bindings'], dict)):
        return fail(SolveReason.INVALID_TASK_OR_CONTEXT)
    nodes = task['expression_or_holes']
    if not isinstance(nodes, (tuple, list)) or not 1 <= len(nodes) <= 64:
        return fail(SolveReason.NODE_LIMIT)
    def qualified(value, scope):
        if not isinstance(value, TypedValue):
            return False
        binding = binding_for(value)
        return (isinstance(binding, dict) and bool(binding.get('content_id'))
                and binding.get('semantic_release') == context['semantic_release']
                and binding.get('rights_epoch') == context['rights_epoch']
                and binding.get('generation') == generation and binding.get('scope') == scope
                and type(binding.get('visible_end')) is int
                and 0 <= binding['visible_end'] <= context['causal_prefix_end'])
    node_fields = {'node_id', 'operator_id_or_hole', 'ordered_operand_refs', 'expected_output_signature', 'scope'}
    by_id, graph, choices = {}, {}, {}
    try:
        for node in nodes:
            if (not isinstance(node, dict) or set(node) != node_fields
                    or not isinstance(node['node_id'], str) or not node['node_id'] or node['node_id'] in by_id):
                return fail(SolveReason.INVALID_NODE)
            by_id[node['node_id']] = node
        def ref_type(ref, scope):
            if not isinstance(ref, (list, tuple)) or not ref:
                raise ValueError
            if ref[0] == 'result' and len(ref) == 2:
                prior = by_id[ref[1]]
                if prior['scope'] != scope:
                    raise ValueError
                return prior['expected_output_signature']
            value = (ref[1] if ref[0] == 'literal' and len(ref) == 2 else
                     task['source_visible_bindings'][tuple(ref[1:])] if ref[0] == 'input' and len(ref) == 4 else None)
            if not qualified(value, scope):
                raise ValueError
            return value.type_name
        for identity, node in by_id.items():
            if authorize_scope(context, node['scope'], generation) is not True:
                return fail(SolveReason.SOURCE_SCOPE_HELD)
            declaration = node['operator_id_or_hole']
            if isinstance(declaration, str):
                alternatives = ({'operator_id': declaration, 'operand_refs': node['ordered_operand_refs']},)
                constraints = ()
            elif isinstance(declaration, dict) and set(declaration) == {'candidates', 'constraints'}:
                alternatives, constraints = declaration['candidates'], declaration['constraints']
            else:
                return fail(SolveReason.INVALID_HOLE)
            if not isinstance(alternatives, (tuple, list)) or not 1 <= len(alternatives) <= 64:
                return fail(SolveReason.INVALID_CANDIDATES)
            legal, dependencies = [], set()
            for candidate in alternatives:
                if not isinstance(candidate, dict) or set(candidate) != {'operator_id', 'operand_refs'}:
                    return fail(SolveReason.INVALID_CANDIDATE)
                op_id, refs = candidate['operator_id'], candidate['operand_refs']
                if op_id not in task['allowed_operator_ids'] or not isinstance(refs, (list, tuple)):
                    return fail(SolveReason.OPERATOR_NOT_ALLOWED)
                operator = registry.require(op_id)
                if (not isinstance(operator, CognitiveOperatorSpec) or not isinstance(operator.signature, Signature)
                        or operator.effect != 'PURE' or operator.kind not in ('EXACT', 'CACHED', 'NEURAL')
                        or not isinstance(operator.implementation_sha256, str) or len(operator.implementation_sha256) != 64
                        or any(c not in '0123456789abcdef' for c in operator.implementation_sha256)):
                    return fail(SolveReason.UNQUALIFIED_OPERATOR)
                op_binding = operator.source_binding
                if (op_binding.get('semantic_release') != context['semantic_release']
                        or op_binding.get('rights_epoch') != context['rights_epoch']
                        or node['scope'] not in op_binding.get('allowed_scopes', ())):
                    return fail(SolveReason.OPERATOR_SOURCE_HELD)
                input_types = tuple(ref_type(ref, node['scope']) for ref in refs)
                dependencies.update(ref[1] for ref in refs if ref[0] == 'result')
                if (operator.signature.inputs == input_types and operator.signature.output == node['expected_output_signature']
                        and constraints_satisfied(operator, refs, constraints, context) is True):
                    legal.append((operator, tuple(tuple(ref) for ref in refs)))
            if not legal:
                return fail(SolveReason.UNSATISFIED_SIGNATURE)
            choices[identity] = sorted(legal, key=lambda choice: (('EXACT', 'CACHED', 'NEURAL').index(choice[0].kind), choice[0].operator_id))
            graph[identity] = tuple(sorted(dependencies))
        order = tuple(TopologicalSorter(graph).static_order())
        depth = {}
        for identity in order:
            depth[identity] = 1 + max((depth[dep] for dep in graph[identity]), default=0)
            if depth[identity] > 8:
                return fail(SolveReason.DEPTH_LIMIT)
    except (KeyError, TypeError, ValueError, AttributeError, CycleError):
        return fail(SolveReason.INVALID_REFERENCE_OR_ROUTE)
    ambiguous = {}
    for identity, options in choices.items():
        first = options[0][0]
        preferred = tuple((op, refs) for op, refs in options if op.kind == first.kind and op.operator_id == first.operator_id)
        if isinstance(by_id[identity]['operator_id_or_hole'], dict) and len(preferred) > 1:
            ambiguous[identity] = tuple({'operator_id': op.operator_id, 'operand_refs': refs} for op, refs in preferred)
    decoded = {}
    if ambiguous:
        decisions = sum(1 + len(options[0]['operand_refs']) for options in ambiguous.values())
        if decisions > budget['decisions']:
            return fail(SolveReason.DECISION_BUDGET_EXHAUSTED)
        try:
            decoded = decode_holes(ambiguous, task['source_visible_bindings'], context, generation)
        except (KeyError, ValueError, TypeError):
            return fail(SolveReason.INVALID_NEURAL_BINDING)
        if not isinstance(decoded, dict) or set(decoded) != set(ambiguous):
            return fail(SolveReason.INVALID_NEURAL_BINDING)
    values = {}
    for identity in order:
        node, options = by_id[identity], choices[identity]
        if identity in decoded:
            choice = decoded[identity]
            if type(choice) is not int or not 0 <= choice < len(options):
                return fail(SolveReason.INVALID_NEURAL_BINDING)
            options = (options[choice],)
        found = False
        for operator, refs in options:
            args = tuple(values[ref[1]] if ref[0] == 'result' else ref[1] if ref[0] == 'literal'
                         else task['source_visible_bindings'][tuple(ref[1:])] for ref in refs)
            try:
                key = {'operator': operator.operator_id, 'implementation': operator.implementation_sha256,
                       'dependencies': tuple({'ref': ref if ref[0] != 'literal' else ('literal', binding_for(value)['content_id']),
                                              'content_id': binding_for(value)['content_id'], 'type': value.type_name}
                                             for ref, value in zip(refs, args)),
                       'semantic_release': context['semantic_release'], 'rights_epoch': context['rights_epoch'],
                       'generation': generation, 'scope': node['scope']}
                value = None
                if operator.kind == 'CACHED':
                    lookups += 1
                    value = lookup_qualified_cache(contract_digest(key), key, context)
                    if value is not None and (not qualified(value, node['scope']) or value.type_name != operator.signature.output):
                        return fail(SolveReason.INVALID_CACHED_RESULT)
                if value is None:
                    if operator.kind == 'NEURAL':
                        if decisions >= budget['decisions']:
                            return fail(SolveReason.DECISION_BUDGET_EXHAUSTED)
                        decisions += 1
                    else:
                        if operations >= budget['operations']:
                            return fail(SolveReason.OPERATION_BUDGET_EXHAUSTED)
                        operations += 1
                    if is_applicable(operator, args, context) is not True:
                        continue
                    value = execute_pure(operator.operator_id, args, {**context, 'scope': node['scope']})
                if not qualified(value, node['scope']) or value.type_name != operator.signature.output:
                    return fail(SolveReason.INVALID_OPERATOR_OUTPUT)
            except (KeyError, TypeError, ValueError, AttributeError):
                continue
            values[identity] = value
            executed.append(identity)
            selected.append((identity, operator.operator_id, refs))
            found = True
            break
        if not found:
            return fail(SolveReason.NO_APPLICABLE_OPERATOR)
    answer = values[nodes[-1]['node_id']]
    if answer.type_name != task['output_signature']:
        return fail(SolveReason.OUTPUT_SIGNATURE_MISMATCH)
    return CapabilityResult(SolveStatus.RESOLVED, answer, None, operations, decisions, lookups, tuple(executed), tuple(selected))
