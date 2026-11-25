"""Deterministic source-local code smell rules."""
from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import dataclass

GRADE_BOUNDS = frozenset(('grade', 'number', 'i', 'index', 'stage'))
ALLOWED_LITERALS = frozenset((0, 1, 2, 3, 4, 8, 16, 32, 64))


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    rule: str
    context: str


def _function_nodes(tree):
    return [node for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]


def _boundary_operand(node):
    return isinstance(node, ast.Name) and node.id.lower() in GRADE_BOUNDS


def inspect_source(path: str, source: str) -> list[Finding]:
    """Inspect a single source string; no imports or code execution."""
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as error:
        return [Finding(path, error.lineno or 1, 'syntax', str(error.msg))]
    findings = []
    for node in _function_nodes(tree):
        length = node.end_lineno - node.lineno + 1
        if length > 85:
            findings.append(Finding(path, node.lineno, 'long-function',
                                    f'{node.name}: {length} lines'))
        branches = sum(isinstance(item, (ast.If, ast.IfExp, ast.For, ast.AsyncFor,
                         ast.While, ast.Try, ast.Match)) for item in ast.walk(node))
        if branches > 18:
            findings.append(Finding(path, node.lineno, 'branch-density',
                                    f'{node.name}: {branches} branches'))
    error_codes = defaultdict(list)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == 'ValueError' and node.args
                and isinstance(node.args[0], ast.Constant)
                and isinstance(node.args[0].value, str)):
            code = node.args[0].value
            if len(code) >= 8 and code.isupper() and '_' in code:
                error_codes[code].append(node.lineno)
        if (isinstance(node, ast.Compare) and any(_boundary_operand(x)
             for x in (node.left, *node.comparators))):
            for operand in (node.left, *node.comparators):
                if (isinstance(operand, ast.Constant) and type(operand.value) is int
                        and operand.value >= 10 and operand.value not in ALLOWED_LITERALS):
                    findings.append(Finding(path,node.lineno,'positional-grade-boundary',
                            f'grade-like comparison to literal {operand.value}'))
    for code,lines in error_codes.items():
        if len(lines) >= 2:
            findings.append(Finding(path, min(lines), 'duplicate-error-code',
                                    f'{code}: used {len(lines)} times'))
    for statement in tree.body:
        if isinstance(statement, (ast.Assign, ast.AnnAssign)):
            value = statement.value
            if isinstance(value, (ast.List, ast.Dict, ast.Set)):
                targets = statement.targets if isinstance(statement,ast.Assign) else [statement.target]
                for target in targets:
                    if isinstance(target, ast.Name) and not target.id.startswith('__'):
                        findings.append(Finding(path, statement.lineno,'module-mutable-literal',
                                                target.id))
    return sorted(findings, key=lambda f: (f.line,f.rule))
