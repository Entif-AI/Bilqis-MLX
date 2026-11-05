"""Prove preparation and execution closure/state decomposition against source."""
import ast
import copy
import json
from verify_contract import OWNER, PACKAGE, old, current, definitions, canonical

PREP_FIELDS = frozenset(("goal", "binding", "budget", "by_id", "approved",
    "prepared", "visible", "selected", "unresolved", "decisions", "binding_checks"))
RUN_FIELDS = frozenset(("goal", "binding", "memo", "operation_limit", "order",
    "prepared", "visible", "selected", "unresolved", "program", "compute_limit",
    "release", "source_digest", "output_type", "computed", "lookups", "hits",
    "executed", "results", "lineage"))


def block(nodes):
    return ast.Module(body=nodes, type_ignores=[])


def method(owner, name):
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


def field_name(node):
    target = node.targets[0] if isinstance(node, ast.Assign) else node.target
    return target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else None


def verify_initializers(before, state, fields, param_names):
    init = method(state, "__init__")
    assert len(init.body) == len(before) + len(param_names) + (state.name == "_Execution")
    assignments = {field_name(n): n for n in init.body if isinstance(n, (ast.Assign, ast.AnnAssign))}
    for name in param_names:
        assert ast.unparse(assignments[name].value) == name, name
    for node in before:
        name = field_name(node)
        assert canonical(node, fields) == canonical(assignments[name], fields), name
    return len(before)


def verify_closures(before, state, fields):
    nested = [n for n in before.body if isinstance(n, ast.FunctionDef)]
    names = frozenset(n.name for n in nested)
    for node in nested:
        after = copy.deepcopy(method(state, node.name))
        assert after.args.args.pop(0).arg == "self"
        assert canonical(node, fields, names) == canonical(after, fields, names), node.name
    return names


def verify_preparation():
    before = definitions(old(OWNER))["_prepare"]
    after = definitions(current(PACKAGE + "/preparation.py"))["_prepare"]
    state = definitions(current(PACKAGE + "/preparation_state.py"))["_Preparation"]
    names = verify_closures(before, state, PREP_FIELDS)
    first = next(i for i, n in enumerate(before.body) if isinstance(n, ast.Assign) and field_name(n) == "prepared")
    assert canonical(block(before.body[:first])) == canonical(block(after.body[:first]))
    assert ast.unparse(after.body[first].value) == "_Preparation(goal, binding, budget, by_id, approved)"
    nested_start = next(i for i, n in enumerate(before.body) if isinstance(n, ast.FunctionDef))
    count = verify_initializers(before.body[first:nested_start], state, PREP_FIELDS,
                                ("goal", "binding", "budget", "by_id", "approved"))
    loop = next(n for n in before.body if isinstance(n, ast.For))
    opened = next(n for n in loop.body if isinstance(n, ast.If) and any(
        isinstance(x, ast.Name) and x.id == "viable" for x in ast.walk(n)))
    index = loop.body.index(opened)
    candidates = method(state, "candidates").body
    assert ast.unparse(candidates[-1]) == "return matches"
    assert canonical(block(loop.body[:index]), PREP_FIELDS, names) == canonical(
        block(candidates[:-1]), PREP_FIELDS, names)
    assert isinstance(opened.body[-1], ast.Continue)
    assert canonical(block(opened.body[:-1]), PREP_FIELDS, names) == canonical(
        block(method(state, "bind_open").body), PREP_FIELDS, names)
    assert canonical(block(loop.body[index + 1:]), PREP_FIELDS, names) == canonical(
        block(method(state, "bind_fixed").body), PREP_FIELDS, names, True)
    assert canonical(block(before.body[before.body.index(loop) + 1:]), PREP_FIELDS, names) == canonical(
        block(method(state, "finish").body), PREP_FIELDS, names)
    expected = ast.parse('''for node in order:
    matches = state.candidates(node)
    if any(ref is None for ref in node.operands):
        state.bind_open(node, matches)
        continue
    state.bind_fixed(node, matches)
return state.finish(order)
''')
    assert canonical(block(after.body[first + 1:])) == canonical(expected)
    return dict(preparation_closures=len(names), preparation_initializers=count, preparation_phases=4)


def verify_execution():
    before = definitions(old(OWNER))["execute_dag"]
    after = definitions(current(PACKAGE + "/execution.py"))["execute_dag"]
    state = definitions(current(PACKAGE + "/execution_state.py"))["_Execution"]
    names = verify_closures(before, state, RUN_FIELDS)
    first = next(i for i, n in enumerate(before.body) if isinstance(n, ast.Assign) and field_name(n) == "program")
    assert canonical(block(before.body[:first])) == canonical(block(after.body[:first]))
    assert ast.unparse(after.body[first].value) == (
        "_Execution(goal, binding, memo, operation_limit, (order, prepared, visible, selected, unresolved))")
    nested = [n for n in before.body if isinstance(n, ast.FunctionDef)]
    loop = next(n for n in before.body if isinstance(n, ast.For))
    initial = before.body[first:before.body.index(nested[0])]
    initial += [n for n in before.body[before.body.index(nested[-1]) + 1:before.body.index(loop)]
                if isinstance(n, ast.AnnAssign)]
    count = verify_initializers(initial, state, RUN_FIELDS,
                                ("goal", "binding", "memo", "operation_limit"))
    unpack = method(state, "__init__").body[4]
    assert canonical(unpack, RUN_FIELDS) == canonical(ast.parse(
        "order, prepared, visible, selected, unresolved = preparation").body[0])
    cut = next(i for i, n in enumerate(loop.body) if isinstance(n, ast.Assign) and field_name(n) == "dependencies")
    step = method(state, "step").body
    compute = method(state, "compute").body
    assert ast.unparse(step[-1]) == "return self.compute(node, spec, refs, numeric, inputs)"
    assert canonical(block(loop.body[:cut]), RUN_FIELDS, names) == canonical(block(step[:-1]), RUN_FIELDS, names)
    assert ast.unparse(compute[-1]) == "return _CONTINUE"
    assert canonical(block(loop.body[cut:]), RUN_FIELDS, names) == canonical(block(compute[:-1]), RUN_FIELDS, names)
    unresolved = next(n for n in before.body if isinstance(n, ast.If) and ast.unparse(n.test) == "unresolved is not None")
    assert canonical(unresolved, RUN_FIELDS, names) == canonical(after.body[first + 1], RUN_FIELDS, names)
    expected_loop = ast.parse('''for node in order:
    result = state.step(node)
    if result is not _CONTINUE:
        return result
''').body[0]
    assert canonical(after.body[first + 2]) == canonical(expected_loop)
    assert canonical(before.body[-1], RUN_FIELDS, names) == canonical(after.body[-1], RUN_FIELDS, names)
    return dict(execution_closures=len(names), execution_initializers=count, execution_phases=2)


def main():
    result = verify_preparation()
    result.update(verify_execution())
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
