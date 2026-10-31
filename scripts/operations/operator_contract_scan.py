"""AST scanning for source-derived operator contracts and legacy debt."""
from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
import subprocess

from operations.operator_contract_paths import logical_source_path


SYMBOL = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\Z")
STATUS_FIELDS = frozenset(("result", "status", "stop_reason", "reason", "disposition"))
EVENT_FIELDS = frozenset(("event",))
GATE_COLLECTION_NAMES = frozenset(
    ("debt", "blockers", "required_source_work", "reasons"))


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


def analyze_source(path: str, source: str) -> SourceReport:
    """AST-only inventory; it never imports or executes the examined module."""
    tree = ast.parse(source, filename=path)
    parents = {child: parent for parent in ast.walk(tree)
               for child in ast.iter_child_nodes(parent)}
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
                    path, "literal-error-identity", node.value, owner, node.lineno))
            if SYMBOL.fullmatch(node.value):
                codes.append(CodeSite(node.value, kind, path, node.lineno, owner))

        def _numeric_guard(self, node: ast.AST) -> None:
            owner = ".".join(owners) if owners else "<module>"
            for part in ast.walk(node.test):
                if (isinstance(part, ast.Constant)
                        and type(part.value) is int and abs(part.value) > 1):
                    debt.append(ContractDebt(
                        path, "opaque-numeric-guard", str(part.value),
                        owner, part.lineno))

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


def _repository_python_files(root: Path) -> tuple[Path, ...]:
    """Scan repository state, not another worker's untracked scratch files."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached"],
            check=True, capture_output=True, text=True)
    except (OSError, subprocess.CalledProcessError):
        return tuple(sorted((root / "bilqis_mlx").rglob("*.py")))
    files = []
    for relative in result.stdout.splitlines():
        path = Path(relative)
        candidate = root / path
        if (path.suffix == ".py" and path.parts and path.parts[0] == "bilqis_mlx"
                and not candidate.is_symlink()):
            files.append(candidate)
    return tuple(sorted(files))


def scan_tree(root: Path) -> SourceReport:
    sites: list[CodeSite] = []
    debt: list[ContractDebt] = []
    for file in _repository_python_files(root):
        if "tests" in file.relative_to(root).parts or file.name.startswith("test_"):
            continue
        report = analyze_source(logical_source_path(file, root), file.read_text())
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))


def scan_git_tree(root: Path, ref: str) -> SourceReport:
    """Scan one committed tree using today's canonical owner mapping."""
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", ref],
        check=True, capture_output=True, text=True)
    sites: list[CodeSite] = []
    debt: list[ContractDebt] = []
    for row in listed.stdout.splitlines():
        metadata, raw_relative = row.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        relative = Path(raw_relative)
        if (relative.suffix != ".py" or not relative.parts
                or relative.parts[0] != "bilqis_mlx" or mode == "120000"
                or "tests" in relative.parts or relative.name.startswith("test_")):
            continue
        shown = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{relative.as_posix()}"],
            check=True, capture_output=True, text=True)
        report = analyze_source(
            logical_source_path(root / relative, root), shown.stdout)
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))
