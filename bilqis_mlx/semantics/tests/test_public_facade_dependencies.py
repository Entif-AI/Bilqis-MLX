from __future__ import annotations

import dis
import importlib
import inspect
import pkgutil
import unittest
from types import CodeType
from unittest.mock import patch

from bilqis_mlx.semantics import frame_schema as public_schema
from bilqis_mlx.semantics.frame_schema import FrameSchema


FAMILIES = {
    "compiler": (
        "bilqis_mlx.semantics.frame_compiler",
        "bilqis_mlx.semantics._frame_compiler",
    ),
    "forest": (
        "bilqis_mlx.semantics.partial_visible_forest",
        "bilqis_mlx.semantics._partial_forest",
    ),
    "schema": (
        "bilqis_mlx.semantics.frame_schema",
        "bilqis_mlx.semantics._frame_schema",
    ),
    "released": (
        "bilqis_mlx.semantics.released_frame_schemas",
        "bilqis_mlx.semantics._released_schemas",
    ),
}


def _code_objects(code):
    yield code
    for constant in code.co_consts:
        if isinstance(constant, CodeType):
            yield from _code_objects(constant)


def _captured_globals(function, facade_function_ids):
    captured = []
    for code in _code_objects(function.__code__):
        for instruction in dis.get_instructions(code):
            if instruction.opname != "LOAD_GLOBAL":
                continue
            dependency = function.__globals__.get(instruction.argval)
            if (inspect.isfunction(dependency)
                    and id(dependency) in facade_function_ids
                    and dependency is not function):
                captured.append(instruction.argval)
    return tuple(captured)


def _family_routes(facade_name: str, package_name: str):
    facade = importlib.import_module(facade_name)
    facade_function_ids = {
        id(value) for value in vars(facade).values()
        if inspect.isfunction(value)
    }
    package = importlib.import_module(package_name)
    modules = [package]
    modules.extend(
        importlib.import_module(module.name)
        for module in pkgutil.walk_packages(
            package.__path__, package.__name__ + ".")
    )
    routes = []
    for module in modules:
        for function_name, function in _defined_functions(module):
            for dependency_name in _captured_globals(
                    function, facade_function_ids):
                routes.append((
                    module.__name__, function_name, dependency_name))
    return tuple(routes)


def _defined_functions(module):
    seen = set()
    for name, value in vars(module).items():
        candidates = []
        if inspect.isfunction(value):
            candidates.append((name, value))
        elif inspect.isclass(value):
            for member_name, member in vars(value).items():
                if isinstance(member, (staticmethod, classmethod)):
                    functions = (member.__func__,)
                elif isinstance(member, property):
                    functions = tuple(
                        function for function in
                        (member.fget, member.fset, member.fdel) if function)
                else:
                    functions = (member,)
                candidates.extend(
                    (f"{name}.{member_name}", function)
                    for function in functions if inspect.isfunction(function)
                )
        for qualified_name, function in candidates:
            if (function.__globals__ is module.__dict__
                    and id(function) not in seen):
                seen.add(id(function))
                yield qualified_name, function


def _negative_dependency():
    return "captured"


def _captured_negative():
    return _negative_dependency()


def _nested_captured_negative():
    return tuple(_negative_dependency() for _ in range(1))


class _DynamicFacade:
    dependency = staticmethod(_negative_dependency)


def _public():
    return _DynamicFacade


def _dynamic_positive():
    return _public().dependency()


class PublicFacadeDependencyTests(unittest.TestCase):
    def test_schema_error_hook_remains_late_bound(self):
        with patch.object(
                public_schema, "_fail",
                side_effect=RuntimeError("public schema fail injected")):
            with self.assertRaisesRegex(
                    RuntimeError, "public schema fail injected"):
                FrameSchema("", 1, "source", (), "ORDERED", "scope")

    def test_census_detects_capture_and_distinguishes_dynamic_lookup(self):
        visible = {id(_negative_dependency)}
        self.assertEqual(
            _captured_globals(_captured_negative, visible),
            ("_negative_dependency",),
        )
        self.assertEqual(
            _captured_globals(_nested_captured_negative, visible),
            ("_negative_dependency",),
        )
        self.assertEqual(_captured_globals(_dynamic_positive, visible), ())

    def test_extracted_owner_dependencies_are_late_bound(self):
        unresolved = {
            label: _family_routes(facade, package)
            for label, (facade, package) in FAMILIES.items()
        }
        unresolved = {
            label: routes for label, routes in unresolved.items() if routes
        }
        self.assertEqual(unresolved, {})


if __name__ == "__main__":
    unittest.main()
