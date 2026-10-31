"""AST scanning primitives for the operator-contract audit."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re


SYMBOL = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\Z")
STATUS_FIELDS = frozenset(("result", "status", "stop_reason", "reason", "disposition"))
EVENT_FIELDS = frozenset(("event",))
GATE_COLLECTION_NAMES = frozenset(
    ("debt", "blockers", "required_source_work", "reasons"))

# These directories are physical source compartments only. Their parent
# packages deliberately preserve the long-standing public module identities
# via package search paths / aliases, so quality debt must remain keyed to
# that canonical identity rather than being reclassified as "new" merely
# because anti-monolith governance moved the source file on disk.
LOGICAL_SOURCE_COMPARTMENTS = (
    (("bilqis_mlx", "factory", "curriculum"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "factory", "lifecycle"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "factory", "sources"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "learning", "_championship"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_engram"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_retention"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_salience"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_teaching"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "semantics", "foundation"), ("bilqis_mlx", "semantics")),
)


def logical_source_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    parts = relative.parts
    for physical, canonical in LOGICAL_SOURCE_COMPARTMENTS:
        if parts[:3] == physical:
            return Path(*canonical, *parts[3:]).as_posix()
    return relative.as_posix()


@dataclass(frozen=True)
class CodeSite:
    code: str
    kind: str
    path: str
    line: int
    owner: str


@dataclass(frozen=True)
class ContractDebt:
    path: str
    kind: str
    token: str
    owner: str
    line: int


@dataclass(frozen=True)
class SourceReport:
    codes: tuple[CodeSite, ...]
    debt: tuple[ContractDebt, ...]


def _symbol_kind(node: ast.Constant, parents: dict[ast.AST, ast.AST]) -> str:
    parent = parents.get(node)
    grandparent = parents.get(parent) if parent is not None else None
    if (isinstance(parent, ast.Call) and parent.args and
            parent.args[0] is node and isinstance(grandparent, ast.Raise)):
        return "exception"
    if (isinstance(parent, ast.Call) and parent.args and parent.args[0] is node
            and isinstance(parent.func, ast.Attribute)
            and parent.func.attr in {"append", "add"}
            and isinstance(parent.func.value, ast.Name)
            and parent.func.value.id in GATE_COLLECTION_NAMES):
        return "gate"
    child: ast.AST = node
    ancestor = parent
    while ancestor is not None:
        if isinstance(ancestor, ast.Dict):
            for key, value in zip(ancestor.keys, ancestor.values):
                if value is child and isinstance(key, ast.Constant):
                    if key.value in EVENT_FIELDS:
                        return "event"
                    if key.value in STATUS_FIELDS:
                        return "status"
        if isinstance(ancestor, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id in STATUS_FIELDS
                   for target in ancestor.targets):
                return "status"
        child = ancestor
        ancestor = parents.get(ancestor)
    return "symbol"


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    result: dict[str, str] = {}
    for statement in tree.body:
        if (isinstance(statement, ast.Assign)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)):
            for target in statement.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = statement.value.value
        elif (isinstance(statement, ast.AnnAssign)
              and isinstance(statement.target, ast.Name)
              and isinstance(statement.value, ast.Constant)
              and isinstance(statement.value.value, str)):
            result[statement.target.id] = statement.value.value
    return result


def analyze_source(path: str, source: str) -> SourceReport:
    """AST-only inventory; it never imports or executes the examined module."""
    tree = ast.parse(source, filename=path)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
    module_strings = _module_string_constants(tree)
    codes: list[CodeSite] = []
    debt: list[ContractDebt] = []
    owners: list[str] = []

    class Scanner(ast.NodeVisitor):
        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            owners.append(node.name)
            self.generic_visit(node)
            owners.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            owners.append(node.name)
            self.generic_visit(node)
            owners.pop()

        def visit_Constant(self, node: ast.Constant) -> None:
            if not isinstance(node.value, str):
                return
            kind = _symbol_kind(node, parents)
            owner = ".".join(owners) if owners else "<module>"
            if kind == "exception":
                debt.append(ContractDebt(
                    path, "literal-error-identity", node.value,
                    owner, node.lineno,
                ))
            if SYMBOL.fullmatch(node.value):
                codes.append(CodeSite(node.value, kind, path, node.lineno, owner))

        def visit_Raise(self, node: ast.Raise) -> None:
            if (isinstance(node.exc, ast.Call) and node.exc.args
                    and isinstance(node.exc.args[0], ast.Name)):
                reference = node.exc.args[0]
                token = module_strings.get(reference.id)
                if token is not None:
                    owner = ".".join(owners) if owners else "<module>"
                    debt.append(ContractDebt(
                        path, "literal-error-identity", token,
                        owner, reference.lineno,
                    ))
                    if SYMBOL.fullmatch(token):
                        codes.append(CodeSite(
                            token, "exception", path, reference.lineno, owner,
                        ))
            self.generic_visit(node)

        def _numeric_guard(self, node: ast.AST) -> None:
            owner = ".".join(owners) if owners else "<module>"
            for part in ast.walk(node.test):
                if (isinstance(part, ast.Constant)
                        and type(part.value) is int and abs(part.value) > 1):
                    debt.append(ContractDebt(
                        path, "opaque-numeric-guard", str(part.value),
                        owner, part.lineno,
                    ))

        def visit_If(self, node: ast.If) -> None:
            self._numeric_guard(node)
            self.generic_visit(node)

        def visit_While(self, node: ast.While) -> None:
            self._numeric_guard(node)
            self.generic_visit(node)

        def visit_IfExp(self, node: ast.IfExp) -> None:
            self._numeric_guard(node)
            self.generic_visit(node)

    Scanner().visit(tree)
    return SourceReport(
        tuple(sorted(codes, key=lambda x: (x.path, x.line, x.code, x.kind))),
        tuple(sorted(debt, key=lambda x: (x.path, x.line, x.kind, x.token))),
    )
