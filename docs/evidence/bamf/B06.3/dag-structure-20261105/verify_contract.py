"""Prove public records, unchanged helpers, literal outputs and mirrored tests."""
import ast
import collections
import copy
import dataclasses
import inspect
import io
import json
from pathlib import Path
import pickle
import subprocess
import sys
import tokenize
import typing

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT))
BASE = "ce58deccb0371dc2f8ebe1adb3b36e4730c247b0"
OWNER = "bilqis_mlx/semantics/cognitive_dag.py"
PACKAGE = "bilqis_mlx/semantics/_cognitive_dag"
TEST = "bilqis_mlx/semantics/tests/test_cognitive_dag.py"
TEST_PACKAGE = "bilqis_mlx/semantics/tests/cognitive_dag"


def old(path):
    return ast.parse(subprocess.check_output(
        ["git", "show", f"{BASE}:{path}"], cwd=ROOT, text=True))


def current(path):
    return ast.parse((ROOT / path).read_text())


def definitions(tree):
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef))}


class Normalize(ast.NodeTransformer):
    def __init__(self, fields=(), methods=(), continue_return=False):
        self.names = frozenset(fields) | frozenset(methods)
        self.continue_return = continue_return

    def visit_Attribute(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
                and node.value.func.id == "_public" and not node.value.args):
            return ast.copy_location(ast.Name(node.attr, node.ctx), node)
        if (isinstance(node.value, ast.Name) and node.value.id in ("self", "state")
                and node.attr in self.names):
            return ast.copy_location(ast.Name(node.attr, node.ctx), node)
        return node

    def visit_AnnAssign(self, node):
        was_attribute = isinstance(node.target, ast.Attribute)
        self.generic_visit(node)
        if was_attribute and isinstance(node.target, ast.Name):
            node.simple = 1
        return node

    def visit_Return(self, node):
        if self.continue_return and node.value is None:
            return ast.copy_location(ast.Continue(), node)
        return self.generic_visit(node)


def canonical(node, fields=(), methods=(), continue_return=False):
    return ast.dump(Normalize(fields, methods, continue_return).visit(
        copy.deepcopy(node)), include_attributes=False)


def verify_records_and_helpers():
    original = definitions(old(OWNER))
    actual = definitions(current(OWNER))
    helpers = definitions(current(PACKAGE + "/record_validation.py"))
    classes = [n for n in original.values() if isinstance(n, ast.ClassDef)]
    for before in classes:
        after = copy.deepcopy(actual[before.name])
        for method in after.body:
            if isinstance(method, ast.FunctionDef) and method.name == "__post_init__":
                call = method.body[0].value
                expected = "validate_" + before.name.lower()
                assert len(method.body) == 1 and call.func.attr == expected
                assert isinstance(call.func.value, ast.Name) and call.func.value.id == "_validation"
                assert ast.unparse(call.args[0]) == "self" and len(call.args) == 1
                method.body = copy.deepcopy(helpers[expected].body)
        assert canonical(before) == canonical(after), before.name
    for path in (ROOT / PACKAGE).glob("*.py"):
        for name, node in definitions(ast.parse(path.read_text())).items():
            if name in original:
                assert name not in actual, name
                actual[name] = node
    unchanged = [n for n in original if n not in ("_prepare", "execute_dag")
                 and isinstance(original[n], ast.FunctionDef)]
    for name in unchanged:
        assert canonical(original[name]) == canonical(actual[name]), name
    return len(classes), len(unchanged)


def verify_metadata_and_literals():
    import bilqis_mlx.semantics.cognitive_dag as dag
    from snapshot_cases import snapshots

    baseline = json.loads(Path(__file__).with_name("baseline.json").read_text())
    for name, expected in baseline["metadata"].items():
        value = getattr(dag, name)
        actual = {"module": value.__module__, "qualname": value.__qualname__,
                  "annotations": getattr(value, "__annotations__", {})}
        if inspect.isfunction(value):
            actual["signature"] = str(inspect.signature(value))
        assert actual == expected, name
        typing.get_type_hints(value)
        if isinstance(value, type):
            assert "class " + name in inspect.getsource(value)
    for name, value in snapshots().items():
        literal = baseline["snapshots"][name]
        text = json.dumps(dataclasses.asdict(value), sort_keys=True, separators=(",", ":"))
        assert text == literal["canonical_json"], name
        payload = bytes.fromhex(literal["protocol4_pickle_hex"])
        assert pickle.dumps(value, protocol=4) == payload, name
        assert pickle.loads(payload) == value, name
    return len(baseline["metadata"]), len(baseline["snapshots"])


def verify_tests():
    before = definitions(old(TEST))
    fixtures = definitions(current(TEST_PACKAGE + "/fixtures.py"))
    helpers = {n: v for n, v in before.items() if isinstance(v, ast.FunctionDef)}
    assert helpers.keys() == fixtures.keys()
    for name in helpers:
        assert canonical(helpers[name]) == canonical(fixtures[name]), name
    methods = {n.name: n for n in before["CognitiveDAGTests"].body
               if isinstance(n, ast.FunctionDef)}
    actual = {}
    paths = [ROOT / TEST, *(ROOT / TEST_PACKAGE).glob("test_*.py")]
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                assert node.name not in actual, node.name
                actual[node.name] = node
    assert methods.keys() == actual.keys()
    for name in methods:
        assert canonical(methods[name]) == canonical(actual[name]), name
    return len(helpers), len(methods)


def verify_comments_and_sizes():
    paths = [ROOT / OWNER, ROOT / TEST, *(ROOT / PACKAGE).glob("*.py"),
             *(ROOT / TEST_PACKAGE).glob("*.py")]
    for path in paths:
        assert len(path.read_text().splitlines()) < 240, path
    def comments(text):
        return collections.Counter(t.string for t in tokenize.generate_tokens(
            io.StringIO(text).readline) if t.type == tokenize.COMMENT)
    for original, current_paths in ((OWNER, [ROOT / OWNER, *(ROOT / PACKAGE).glob("*.py")]),
                                    (TEST, [ROOT / TEST, *(ROOT / TEST_PACKAGE).glob("*.py")])):
        before = subprocess.check_output(["git", "show", f"{BASE}:{original}"], cwd=ROOT, text=True)
        after = "\n".join(p.read_text() for p in current_paths)
        assert not comments(before) - comments(after), original
    return len(paths)


def main():
    records, helpers = verify_records_and_helpers()
    metadata, snapshots = verify_metadata_and_literals()
    fixtures, tests = verify_tests()
    print(json.dumps({"base": BASE, "inlined_record_classes": records,
        "unchanged_function_asts": helpers, "public_metadata": metadata,
        "exact_serialized_snapshots": snapshots, "unchanged_test_fixtures": fixtures,
        "unchanged_test_methods": tests, "files_below_240": verify_comments_and_sizes()}, sort_keys=True))


if __name__ == "__main__":
    main()
