"""Deterministic closure-to-session and route-body preservation witness."""
import ast
import copy
import json
import hashlib
import importlib.util
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
BASE = "702cc1b2270ec1347db6e18551de661d3613c345"
OWNER = "bilqis_mlx/runtime/_cognitive_solver/"
TESTS = "bilqis_mlx/runtime/tests/capability/solver/"
FIELDS = frozenset((
    "task", "context", "generation", "budget", "binding", "source_digest",
    "receipts", "remaining_operations", "reserved_operations",
    "local_refinement_calls", "fallback_reason", "ordered_cache",
    "unresolved_answer", "unresolved_signature", "neural_calls"))
METHODS = frozenset(("evaluate", "decode", "result", "qualified", "execute_proposal"))


def old(path):
    return ast.parse(subprocess.check_output(
        ["git", "show", f"{BASE}:{path}"], cwd=ROOT, text=True))


def current(path):
    return ast.parse((ROOT / path).read_text())


def definition(tree, name):
    return next(n for n in tree.body if getattr(n, "name", None) == name)


class NormalizeSession(ast.NodeTransformer):
    def visit_Attribute(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Name) and node.value.id in ("self", "session")
                and node.attr in FIELDS | METHODS):
            return ast.copy_location(ast.Name(node.attr, node.ctx), node)
        return node

    def visit_Nonlocal(self, node):
        return None

    def visit_Return(self, node):
        if isinstance(node.value, ast.Name) and node.value.id == "_CONTINUE":
            return ast.copy_location(ast.Continue(), node)
        return self.generic_visit(node)


def canonical(node):
    return ast.dump(NormalizeSession().visit(copy.deepcopy(node)), include_attributes=False)


def verify_methods(previous, session):
    for name in METHODS:
        before = definition(previous, name)
        after = copy.deepcopy(definition(session, name))
        assert after.args.args.pop(0).arg == "self"
        assert canonical(before) == canonical(after), name
    return len(METHODS)


def verify_initializers(previous, session):
    before = {n.targets[0].id: n for n in previous.body
              if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)}
    init = definition(session, "__init__")
    after = {n.targets[0].attr: n for n in init.body
             if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Attribute)}
    state_names = FIELDS - {"task", "context", "generation", "budget", "binding", "source_digest"}
    for name in state_names:
        assert canonical(before[name]) == canonical(after[name]), name
    return len(state_names)


def verify_routes(previous):
    loop = next(n for n in previous.body if isinstance(n, ast.For))
    branch = loop.body[0]
    routes = current(OWNER + "routes.py")
    driver = definition(current(OWNER + "execution.py"), "_solve_task")
    dispatch = next(n for n in driver.body if isinstance(n, ast.For)).body[0]
    for name in ("exact", "cached", "neural", "fallback"):
        assert canonical(branch.test) == canonical(dispatch.test), name
        after = definition(routes, name).body
        assert isinstance(after[-1], ast.Return) and after[-1].value.id == "_CONTINUE"
        assert canonical(ast.Module(body=branch.body, type_ignores=[])) == canonical(
            ast.Module(body=after[:-1], type_ignores=[])), name
        branch = branch.orelse[0] if isinstance(branch.orelse[0], ast.If) else branch
        dispatch = dispatch.orelse[0] if isinstance(dispatch.orelse[0], ast.If) else dispatch
    assert canonical(ast.Module(body=branch.orelse, type_ignores=[])) == canonical(
        ast.Module(body=dispatch.orelse, type_ignores=[]))
    before_prefix = previous.body[:next(i for i, n in enumerate(previous.body)
        if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
        and n.targets[0].id == "receipts")]
    assert canonical(ast.Module(body=before_prefix, type_ignores=[])) == canonical(
        ast.Module(body=driver.body[:len(before_prefix)], type_ignores=[]))
    assert canonical(previous.body[-1]) == canonical(driver.body[-1])
    return 4


def verify_tests():
    before = {}
    for name in ("execution", "execution_replay", "policy", "results"):
        case = definition(old(TESTS + "test_" + name + ".py"), "CognitiveSolverTests")
        before.update({n.name: n for n in case.body if isinstance(n, ast.FunctionDef)})
    after = {}
    for path in (ROOT / TESTS).glob("test_*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                assert node.name not in after, node.name
                after[node.name] = node
    for name, node in before.items():
        assert ast.dump(node, include_attributes=False) == ast.dump(
            after[name], include_attributes=False), name
    return len(before)


def import_census(before):
    pending = ["bilqis_mlx.runtime.cognitive_solver"]
    seen = set()
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        path = ROOT.joinpath(*name.split(".")).with_suffix(".py")
        if not path.is_file():
            path = ROOT.joinpath(*name.split("."), "__init__.py")
        if not path.is_file():
            continue
        seen.add(name)
        pending.extend(".".join(name.split(".")[:i]) for i in range(1, len(name.split("."))))
        package = name if path.name == "__init__.py" else name.rpartition(".")[0]
        tree = old(OWNER + "execution.py") if before and name == (
            "bilqis_mlx.runtime._cognitive_solver.execution") else ast.parse(path.read_text())
        for node in ast.walk(tree):
            imports = ()
            if isinstance(node, ast.Import):
                imports = tuple(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                base = importlib.util.resolve_name("." * node.level + (node.module or ""), package)
                imports = (base, *(base + "." + a.name for a in node.names))
            pending.extend(n for n in imports if n.startswith("bilqis_mlx."))
    forbidden = ("bilqis_mlx.verification", "bilqis_mlx.source_adapters",
                 "bilqis_mlx.generated_assessment", "bilqis_mlx.assessment", "bilqis_mlx.factory")
    return tuple(sorted(n for n in seen if n.startswith(forbidden) or n.endswith("_oracle")))


def main():
    previous = definition(old(OWNER + "execution.py"), "_solve_task")
    session = definition(current(OWNER + "session.py"), "_SolveSession")
    before_imports, after_imports = import_census(True), import_census(False)
    assert before_imports == after_imports
    print(json.dumps({"base": BASE,
        "existing_forbidden_imports": len(after_imports),
        "forbidden_import_set_sha256": hashlib.sha256(
            json.dumps(after_imports, separators=(",", ":")).encode()).hexdigest(),
        "normalized_nested_methods": verify_methods(previous, session),
        "state_initializers": verify_initializers(previous, session),
        "normalized_route_bodies": verify_routes(previous),
        "unchanged_existing_tests": verify_tests()}, sort_keys=True))


if __name__ == "__main__":
    main()
