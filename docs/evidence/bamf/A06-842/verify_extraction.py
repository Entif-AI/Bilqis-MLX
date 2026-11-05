"""Compare bounded extraction against its reviewed unified source."""
import ast
import inspect
import hashlib
import json
import pickle
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
BASE = 'e58dd31574a6ee2ce0b3e35f92293a09befd15c1'
OWNER = 'bilqis_mlx/factory/execution.py'
TEST = 'bilqis_mlx/factory/tests/test_execution_plan.py'


def original(path):
    return ast.parse(subprocess.check_output(
        ['git', 'show', f'{BASE}:{path}'], cwd=ROOT, text=True))


def definitions(tree):
    return {n.name: n for n in tree.body
            if isinstance(n, (ast.ClassDef, ast.FunctionDef))}


source = original(OWNER)
names = set(definitions(source))
for node in source.body:
    if isinstance(node, ast.Import):
        names.update(a.asname or a.name.split('.')[0] for a in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module != '__future__':
        names.update(a.asname or a.name for a in node.names)


class NormalizeFacade(ast.NodeTransformer):
    def visit_Attribute(self, node):
        self.generic_visit(node)
        if (isinstance(node.value, ast.Name) and node.value.id == '_api'
                and node.attr in names):
            return ast.copy_location(ast.Name(node.attr, node.ctx), node)
        return node


def dump(node):
    return ast.dump(node, include_attributes=False)


extracted = {}
for path in (ROOT / 'bilqis_mlx/factory/_execution').glob('*.py'):
    for name, node in definitions(ast.parse(path.read_text())).items():
        assert name not in extracted, name
        extracted[name] = NormalizeFacade().visit(node)
assert extracted.keys() == definitions(source).keys()
for name, node in definitions(source).items():
    assert dump(node) == dump(extracted[name]), name

old_tests = definitions(original(TEST))
new_tests = ROOT / 'bilqis_mlx/factory/tests/execution_plan'
fixtures = definitions(ast.parse((new_tests / 'fixtures.py').read_text()))
old_fixtures = {name: node for name, node in old_tests.items()
                if isinstance(node, ast.FunctionDef)}
assert fixtures.keys() == old_fixtures.keys()
for name, node in old_fixtures.items():
    assert dump(node) == dump(fixtures[name]), name
old_methods = {n.name: n for n in old_tests['ExecutionPlanTests'].body
               if isinstance(n, ast.FunctionDef)}
new_methods = {}
for path in new_tests.glob('test_*.py'):
    for case in definitions(ast.parse(path.read_text())).values():
        if isinstance(case, ast.ClassDef) and case.name == 'ExecutionPlanTests':
            for method in case.body:
                if isinstance(method, ast.FunctionDef):
                    assert method.name not in new_methods, method.name
                    new_methods[method.name] = method
assert old_methods.keys() == new_methods.keys()
for name, node in old_methods.items():
    assert dump(node) == dump(new_methods[name]), name

import bilqis_mlx.factory.execution as execution
from bilqis_mlx.factory.tests.execution_plan.fixtures import (
    _synthetic_course, _synthetic_registry,
)

baseline = json.loads(Path(__file__).with_name('baseline.json').read_text())
for name, expected in baseline['metadata'].items():
    value = getattr(execution, name)
    actual = {'module': value.__module__, 'qualname': value.__qualname__,
              'annotations': getattr(value, '__annotations__', {})}
    if inspect.isfunction(value):
        actual['signature'] = str(inspect.signature(value))
    assert actual == expected, name
plan = execution.compile_execution_plan(
    _synthetic_course(), execution.CurriculumProfile.full(), _synthetic_registry())
assert plan.digest() == baseline['objects']['full']['json_sha256']
payload = pickle.dumps(plan, protocol=4)
assert hashlib.sha256(payload).hexdigest() == baseline['objects']['full']['pickle_sha256']
assert pickle.loads(payload) == plan
paths = [ROOT / OWNER, ROOT / TEST,
         *(ROOT / 'bilqis_mlx/factory/_execution').glob('*.py'),
         *new_tests.glob('*.py')]
for path in paths:
    assert len(path.read_text().splitlines()) < 240, path
print(json.dumps({'base': BASE, 'source_definitions': len(extracted),
                  'unchanged_test_methods': len(new_methods),
                  'unchanged_fixtures': len(fixtures),
                  'public_metadata': len(baseline['metadata']),
                  'files_below_240': len(paths)}, sort_keys=True))
