"""Read-only census of original facade-callable dependencies after extraction."""
from __future__ import annotations

import ast
import dis
import importlib
import json
from pathlib import Path
from types import CodeType, FunctionType


def _functions(value):
    if isinstance(value, FunctionType):
        yield value
    elif isinstance(value, type):
        for member in vars(value).values():
            if isinstance(member, (staticmethod, classmethod)):
                yield member.__func__
            elif isinstance(member, property):
                yield from (item for item in (member.fget, member.fset, member.fdel)
                            if item is not None)
            elif isinstance(member, FunctionType):
                yield member


def captured_code_routes(code, dependencies):
    """Inspect nested functions and comprehensions as well as their enclosing code."""
    loaded = {item.argval for item in dis.get_instructions(code)
              if item.opname in {"LOAD_GLOBAL", "LOAD_NAME"}}
    for name in sorted(loaded & set(dependencies)):
        yield (code.co_qualname, name)
    for value in code.co_consts:
        if isinstance(value, CodeType):
            yield from captured_code_routes(value, dependencies)


def captured_source_routes(source, dependencies):
    """Catch imports, aliases and defaults which capture a callable outside globals."""
    tree = ast.parse(source)
    names = set(dependencies)
    function_names = {item.id for node in ast.walk(tree)
                      if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                      for item in ast.walk(node)
                      if isinstance(item, ast.Name) and isinstance(item.ctx, ast.Load)}

    def dependency(value):
        if isinstance(value, ast.Name) and value.id in names:
            return value.id
        if isinstance(value, ast.Attribute) and value.attr in names:
            return value.attr
        if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id == "getattr" and len(value.args) >= 2
                and isinstance(value.args[1], ast.Constant)
                and value.args[1].value in names):
            return value.args[1].value
        return None

    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in names and (alias.asname or alias.name) in function_names:
                    yield (node.lineno, "captured-import", alias.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            for value in (*node.args.defaults, *node.args.kw_defaults):
                name = dependency(value)
                if name:
                    yield (node.lineno, "default", name)
            for child in ast.walk(node):
                if isinstance(child, ast.ImportFrom):
                    for alias in child.names:
                        if alias.name in names:
                            yield (child.lineno, "local-import", alias.name)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            name = dependency(node.value)
            if name:
                yield (node.lineno, "alias", name)


def audit_contract():
    """Audit all physical owner modules against a fixed pre-extraction name census."""
    contract = json.loads(Path(__file__).with_name("facade_contract.json").read_text())
    reports = []
    for owner in contract["owners"]:
        importlib.import_module(owner["facade"])
        package = importlib.import_module(owner["private_package"])
        root = Path(package.__file__).resolve().parent
        dependencies = owner["dependencies"]
        seen = set()
        routes = set()
        for path in sorted(root.glob("*.py")):
            module = (package if path.stem == "__init__" else
                      importlib.import_module(owner["private_package"] + "." + path.stem))
            for value in vars(module).values():
                for function in _functions(value):
                    code = function.__code__
                    key = (code.co_filename, code.co_qualname, code.co_firstlineno)
                    if (key in seen or not Path(code.co_filename).resolve().is_relative_to(root)):
                        continue
                    seen.add(key)
                    for function_name, name in captured_code_routes(
                            code, dependencies):
                        routes.add((Path(code.co_filename).relative_to(root).as_posix(),
                                    function_name, name))
            for line, kind, name in captured_source_routes(path.read_text(), dependencies):
                routes.add((path.name, f"{kind}:{line}", name))
        reports.append({"facade": owner["facade"],
                        "baseline_commit": owner["baseline_commit"],
                        "captured_routes": sorted(routes)})
    return reports


def main():
    reports = audit_contract()
    print(json.dumps(reports, indent=2))
    return int(any(report["captured_routes"] for report in reports))


if __name__ == "__main__":
    raise SystemExit(main())
