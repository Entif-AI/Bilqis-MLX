"""Source-derived error/status atlas and non-growing legacy-debt gate.

The atlas locates strings but does NOT invent their meaning. Only definitions
from the typed diagnostic registry carry authoritatively authored guidance.
An immutable baseline fences the pre-existing literal-error/magic-guard debt:
new opaque source constructs fail CI until expressed as domain contracts.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = "bilqis.operator-contract-debt/v1"
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
    (("bilqis_mlx", "runtime", "_admission"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_batch"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_capability"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_correction"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_custody"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_depth"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_model"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_operator"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_projection"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_source"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_teacher"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "semantics", "foundation"), ("bilqis_mlx", "semantics")),
)

LOGICAL_SOURCE_ALIASES = {
    "bilqis_mlx/runtime/_admission/atlas_lease_contracts.py":
        "bilqis_mlx/runtime/atlas_admission.py",
    "bilqis_mlx/runtime/_admission/atlas_lease_storage.py":
        "bilqis_mlx/runtime/atlas_admission.py",
    "bilqis_mlx/runtime/_batch/atlas_training_contracts.py":
        "bilqis_mlx/runtime/atlas_training_adapter.py",
    "bilqis_mlx/runtime/_batch/atlas_training_delivery.py":
        "bilqis_mlx/runtime/atlas_training_adapter.py",
    "bilqis_mlx/runtime/_batch/fixed_frontier_evidence.py":
        "bilqis_mlx/runtime/candidate_evidence.py",
    "bilqis_mlx/runtime/_batch/retention_support.py":
        "bilqis_mlx/runtime/candidate_evidence.py",
    "bilqis_mlx/runtime/_capability/capability_evaluation.py":
        "bilqis_mlx/runtime/capability_retention.py",
    "bilqis_mlx/runtime/_correction/atlas_correction_branches.py":
        "bilqis_mlx/runtime/atlas_requalification.py",
    "bilqis_mlx/runtime/_correction/atlas_requalification_contracts.py":
        "bilqis_mlx/runtime/atlas_requalification.py",
    "bilqis_mlx/runtime/_correction/atlas_stale_replay.py":
        "bilqis_mlx/runtime/atlas_temporal_revalidation.py",
    "bilqis_mlx/runtime/_correction/atlas_temporal_contracts.py":
        "bilqis_mlx/runtime/atlas_temporal_revalidation.py",
    "bilqis_mlx/runtime/_custody/championship_source_repair.py":
        "bilqis_mlx/runtime/reconciliation.py",
    "bilqis_mlx/runtime/_custody/resume_metadata.py":
        "bilqis_mlx/runtime/reconciliation.py",
    "bilqis_mlx/runtime/_depth/depth_contracts.py":
        "bilqis_mlx/runtime/block_attnres.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_contracts.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_events.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_store.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_corrections.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_contracts.py":
        "bilqis_mlx/runtime/akasha_staging.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_queries.py":
        "bilqis_mlx/runtime/akasha_staging.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_store.py":
        "bilqis_mlx/runtime/akasha_staging.py",
}


def logical_source_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    alias = LOGICAL_SOURCE_ALIASES.get(relative.as_posix())
    if alias is not None:
        return alias
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
                    path, "literal-error-identity", node.value,
                    owner, node.lineno,
                ))
            if SYMBOL.fullmatch(node.value):
                codes.append(CodeSite(node.value, kind, path, node.lineno, owner))

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


def _repository_python_files(root: Path) -> tuple[Path, ...]:
    """Scan repository state, not another worker's untracked scratch files."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached"],
            check=True, capture_output=True, text=True,
        )
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
        if ("tests" in file.relative_to(root).parts or
                file.name.startswith("test_")):
            continue
        report = analyze_source(logical_source_path(file, root), file.read_text())
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))


def scan_git_tree(root: Path, ref: str) -> SourceReport:
    """Scan one committed tree using today's canonical owner mapping.

    PR gates compare the candidate tree with the exact base SHA. Reading the
    base through Git avoids mutating the worktree and, importantly, preserves
    the same logical-module normalization on both sides of a physical move.
    """
    listed = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-r", ref],
        check=True, capture_output=True, text=True,
    )
    sites: list[CodeSite] = []
    debt: list[ContractDebt] = []
    for row in listed.stdout.splitlines():
        metadata, raw_relative = row.split("\t", 1)
        mode = metadata.split(" ", 1)[0]
        relative = Path(raw_relative)
        if (relative.suffix != ".py" or not relative.parts
                or relative.parts[0] != "bilqis_mlx"
                or mode == "120000"
                or "tests" in relative.parts
                or relative.name.startswith("test_")):
            continue
        shown = subprocess.run(
            ["git", "-C", str(root), "show", f"{ref}:{relative.as_posix()}"],
            check=True, capture_output=True, text=True,
        )
        report = analyze_source(
            logical_source_path(root / relative, root), shown.stdout)
        sites.extend(report.codes)
        debt.extend(report.debt)
    return SourceReport(tuple(sites), tuple(debt))


def debt_counter(debt: tuple[ContractDebt, ...]) -> Counter[tuple[str, ...]]:
    """Track opaque contracts without making safe function extraction illegal.

    Moving an existing literal into a smaller pure function is not new debt.
    Adding another occurrence of that literal, adding a new literal, or moving
    the same opaque contract into a new module still increases the counter.
    """
    return Counter((item.path, item.kind, item.token) for item in debt)


def new_debt(
    current: Counter[tuple[str, ...]], baseline: Counter[tuple[str, ...]],
) -> tuple[tuple[str, ...], ...]:
    return tuple(key for key, count in sorted(current.items())
                 for _ in range(max(0, count - baseline[key])))


def _baseline(counter: Counter[tuple[str, ...]]) -> dict:
    return {
        "schema": SCHEMA,
        "description": "Existing debt only; NOT an endorsement of magic numbers or string errors.",
        "counts": [list(key) + [count] for key, count in sorted(counter.items())],
    }


def _read_baseline(path: Path) -> Counter[tuple[str, ...]]:
    data = json.loads(path.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("INVALID_OPERATOR_CONTRACT_BASELINE_SCHEMA")
    return Counter({tuple(row[:-1]): row[-1] for row in data["counts"]})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, default=ROOT,
                        help="Root of the checkout/worktree to inspect; defaults to this checkout")
    parser.add_argument("--lookup", metavar="CODE_FRAGMENT",
                        help="Find source occurrences, including unregistered status/gate codes")
    parser.add_argument("--json", action="store_true", help="Output machine-readable atlas data")
    parser.add_argument("--check-baseline", type=Path,
                        help="Exit nonzero if any new raw error identity or opaque policy number appears")
    parser.add_argument("--write-baseline", type=Path,
                        help="Explicit bootstrap only; never refresh baseline to silence new errors")
    args = parser.parse_args(argv)
    report = scan_tree(args.source_root.resolve())
    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(
            json.dumps(_baseline(debt_counter(report.debt)), indent=2) + "\n"
        )
    introduced = ()
    if args.check_baseline:
        introduced = new_debt(
            debt_counter(report.debt), _read_baseline(args.check_baseline))
    matches = [item for item in report.codes
               if not args.lookup or args.lookup.upper() in item.code]
    if args.json:
        print(json.dumps({
            "source_files": len({item.path for item in report.codes}),
            "code_occurrences": len(report.codes),
            "distinct_codes": len({item.code for item in report.codes}),
            "results": [asdict(item) for item in matches],
            "new_debt": [list(item) for item in introduced],
        }, indent=2))
    else:
        print(f"Source-derived atlas: {len({item.code for item in report.codes})} "
              f"distinct uppercase symbols; {len(report.debt)} old-style "
              "error/numeric-guard occurrences.")
        for site in matches[:80] if args.lookup else ():
            print(f"{site.code} [{site.kind}] {site.path}:{site.line} ({site.owner})")
        if args.lookup and len(matches) > 80:
            print(f"... {len(matches) - 80} more source matches; use --json.")
        if args.check_baseline:
            print(f"New opaque-contract debt: {len(introduced)}")
            for item in introduced[:30]:
                print("NEW", *item, sep=" | ")
    return 2 if introduced else 0


if __name__ == "__main__":
    raise SystemExit(main())
