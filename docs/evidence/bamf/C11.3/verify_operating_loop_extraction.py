"""One-off source-order witness against the preserved pre-extraction commit."""
import ast
import copy
import subprocess
from pathlib import Path

source = subprocess.check_output(['git', 'show', 'a5232e1240e47cb8d5910e67821b9742e9e5ea3e:bilqis_mlx/runtime/operating_loop.py'], text=True)
operate = next(x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef) and x.name == 'operate')
lock = next(x for x in operate.body if isinstance(x, ast.With) and x.lineno == 193)
loop = next(x for x in lock.body if isinstance(x, ast.While))
root = Path('bilqis_mlx/runtime/operator_session')
class InlinePhases(ast.NodeTransformer):
    def __init__(self):
        self.helpers = {}
        for path in root.glob('*.py'):
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.FunctionDef) and node.name.startswith('_'):
                    self.helpers[node.name] = node.body

    def expanded(self, call, trim=False):
        body = copy.deepcopy(self.helpers[call.func.id])
        if trim:
            body = body[:-1]
        if call.func.id == '_hold_autonomy':
            class RecordAlias(ast.NodeTransformer):
                def visit_Name(self, node):
                    if node.id == 'record':
                        return ast.parse('_runtime_checkpoints._record', mode='eval').body
                    return node
            body = [RecordAlias().visit(node) for node in body]
        return body

    def visit_Return(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id in self.helpers:
            return self.expanded(node.value)
        return self.generic_visit(node)

    def visit_Assign(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id in self.helpers:
            return self.expanded(node.value, trim=True)
        return self.generic_visit(node)

    def visit_Expr(self, node):
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name) and node.value.func.id in self.helpers:
            return self.expanded(node.value)
        return self.generic_visit(node)


def function(name):
    node = next(x for x in ast.parse((root / f'operator_{name}.py').read_text()).body if isinstance(x, ast.FunctionDef))
    return InlinePhases().visit(node)

def dump(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False)
class RestoreControl(ast.NodeTransformer):
    def visit_Return(self, node):
        if isinstance(node.value, ast.Tuple) and isinstance(node.value.elts[0], ast.Attribute):
            mode = node.value.elts[0].attr
            if mode == 'STOP': return ast.Break()
            if mode == 'CONTINUE': return ast.Continue()
        return node
checks = (
    ('stagnation', [x for x in lock.body if 285 <= x.lineno <= 363], 1),
    ('finish', [x for x in lock.body if x.lineno >= 753], 0),
    ('visit', [x for x in loop.body if x.lineno >= 642], 1),
    ('iteration', [x for x in loop.body if 366 <= x.lineno <= 443], 1),
    ('autonomy', next(x for x in loop.body if x.lineno == 444).body, 1),
)
for name, original, drop in checks:
    body = function(name).body
    if drop: body = body[:-drop]
    body = [RestoreControl().visit(node) for node in body]
    equal = dump(original) == dump(body)
    print(f'{name}: {"PASS" if equal else "FAIL"}')
    assert equal

setup_functions = [x for x in ast.parse((root / 'operator_setup.py').read_text()).body if isinstance(x, ast.FunctionDef)]
new_operate = next(x for x in ast.parse(Path('bilqis_mlx/runtime/operating_loop.py').read_text()).body if isinstance(x, ast.FunctionDef) and x.name == 'operate')
new_lock = next(x for x in new_operate.body if isinstance(x, ast.With) and any(isinstance(y, ast.Assign) and isinstance(y.value, ast.Call) and isinstance(y.value.func, ast.Attribute) and y.value.func.attr == '_ensure_executable_release' for y in x.body))
ensure = next(x for x in new_lock.body if isinstance(x, ast.Assign) and isinstance(x.value, ast.Call) and isinstance(x.value.func, ast.Attribute) and x.value.func.attr == '_ensure_executable_release')
actual = setup_functions[0].body[:-1] + [ensure] + setup_functions[1].body[:-1]
original = [x for x in lock.body if 198 <= x.lineno <= 284]
equal = dump(original) == dump(actual)
print(f'setup: {"PASS" if equal else "FAIL"}')
assert equal

class RestoreAliases(ast.NodeTransformer):
    aliases = {'paths': '_paths', 'experiment_runs': '_runtime_experiment_runs',
               'admission': '_runtime_admission', 'state_dag': '_state_dag',
               'disk': '_runtime_disk', 'timing_trace': '_runtime_timing_trace'}

    def visit_Name(self, node):
        node.id = self.aliases.get(node.id, node.id)
        return node

original = [x for x in operate.body if 130 <= x.lineno < 180]
actual = RestoreAliases().visit(ast.Module(body=function('preflight').body, type_ignores=[])).body
assert dump(original) == dump(actual)
print('preflight: PASS')
original = [x for x in loop.body if 631 <= x.lineno < 642]
actual = RestoreAliases().visit(ast.Module(body=function('disk').body[:-1], type_ignores=[])).body
actual[1].body = ast.parse('reason = "DISK_RESERVE_REACHED"\nbreak').body
assert dump(original) == dump(actual)
print('disk: PASS (Boolean return restores the original loop stop)')
original_functions = {x.name: x for x in ast.parse(source).body if isinstance(x, ast.FunctionDef)}
profiles = ast.parse((root / 'operator_profiles.py').read_text())
for current in (x for x in profiles.body if isinstance(x, ast.FunctionDef)):
    assert dump(original_functions['_' + current.name].body) == dump(current.body)
print('profiles: PASS')
assert ast.dump(operate.args, include_attributes=False) == ast.dump(new_operate.args, include_attributes=False)
print('human entrypoint signature: PASS')
