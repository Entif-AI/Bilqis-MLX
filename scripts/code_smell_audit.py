"""Read-only, dependency-free Python code hygiene inventory.

Reports candidates for review; does not assert that every flagged pattern is a
bug, rewrite source, or alter the currently hash-bound training recipe.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import subprocess

try:
    from quality.change_scope import effective_base
except ModuleNotFoundError:  # dynamic test import from repository root
    from scripts.quality.change_scope import effective_base


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRS = tuple(sorted(
    path.name for path in ROOT.iterdir()
    if path.is_dir() and (path.name.startswith('bilqis_') or
                          path.name in ('scripts','tests'))))
GRADE_BOUNDS = {'grade', 'number', 'i', 'index', 'stage'}
ALLOWED_LITERALS = {0, 1, 2, 3, 4, 8, 16, 32, 64}


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


def _paths(user_paths):
    if user_paths:
        return sorted({(ROOT / name).resolve() for name in user_paths
                       if str((ROOT/name).resolve()).startswith(str(ROOT.resolve()) + '/')})
    return sorted(path for name in DEFAULT_DIRS for path in (ROOT/name).rglob('*.py')
                  if path.is_file())


def audit(paths):
    records = []
    for path in paths:
        if not path.is_file() or path.suffix != '.py':
            continue
        name = str(path.relative_to(ROOT))
        records.extend(inspect_source(name, path.read_text(encoding='utf-8')))
    return sorted(records, key=lambda f:(f.path,f.line,f.rule))


def fingerprint(finding):
    """Ignore moved line numbers; preserve exact source-local review identity."""
    # Once a long/branchy function is acknowledged, a harmless line edit must
    # not produce a fresh fingerprint just because the displayed count moved.
    # A newly overlong function still creates a new entry and fails the gate.
    context=(finding.context.split(':',1)[0]
             if finding.rule in ('long-function','branch-density')
             else finding.context)
    return (finding.path, finding.rule, context)


def compare_to_baseline(findings, baseline):
    prior=Counter(tuple(item) for item in baseline.get('fingerprints',[]))
    seen=Counter(fingerprint(item) for item in findings)
    return [key for key,count in sorted(seen.items())
            for _ in range(max(0,count-prior[key]))]


def _records_from_name_status(text):
    records=[]
    for line in text.splitlines():
        fields=line.split('\t')
        if fields[0].startswith(('R','C')):
            old,new=fields[1],fields[2]
        else:
            old=new=fields[1]
        if new.endswith('.py'):
            records.append((old,new))
    return records


def _staged_records():
    result=subprocess.run(['git','diff','--cached','--name-status','-M','--diff-filter=ACMR'],
                          cwd=ROOT,check=True,text=True,stdout=subprocess.PIPE)
    return 'HEAD',_records_from_name_status(result.stdout)


def _changed_records(base_ref):
    merge_base=effective_base(ROOT,base_ref)
    result=subprocess.run(['git','diff','--name-status','-M','--diff-filter=ACMR',merge_base,'HEAD'],
                          cwd=ROOT,check=True,text=True,stdout=subprocess.PIPE)
    return merge_base,_records_from_name_status(result.stdout)


def _base_findings(merge_base,records):
    found=[]
    for old,new in records:
        result=subprocess.run(['git','show',f'{merge_base}:{old}'],cwd=ROOT,text=True,
                              capture_output=True)
        if result.returncode==0:
            found.extend(inspect_source(new,result.stdout))
    return sorted(found,key=lambda f:(f.path,f.line,f.rule))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='*',help='Relative Python paths, default core packages')
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--staged',action='store_true',help='Audit staged Python files only')
    scope.add_argument('--changed-from',help='Audit Python files changed from merge-base with REF')
    parser.add_argument('--json',action='store_true',help='Output machine-readable findings')
    parser.add_argument('--strict',action='store_true',help='Exit nonzero on any finding; explicit opt-in')
    parser.add_argument('--write-baseline',type=Path,
                        help='Write acknowledged current debt for reviewed core code; never changes source')
    parser.add_argument('--check-baseline',type=Path,
                        help='Fail on new findings relative to an acknowledged baseline')
    args=parser.parse_args(argv)
    changed=None
    if args.staged:
        merge_base,changed=_staged_records()
        scoped=[new for _,new in changed]
    elif args.changed_from:
        merge_base,changed=_changed_records(args.changed_from)
        scoped=[new for _,new in changed]
    else:
        scoped=args.paths
    paths=_paths(scoped)
    found=audit(paths)
    if args.write_baseline:
        if args.staged or args.changed_from or args.paths:
            raise ValueError('HYGIENE_BASELINE_REQUIRES_WHOLE_CURRENT_CORE')
        output={'schema':'bilqis.code-smell-baseline/v1',
                'description':'Review findings only; not proven defects or frozen-source rewrite authority',
                'fingerprints':[list(fingerprint(item)) for item in found]}
        args.write_baseline.parent.mkdir(parents=True,exist_ok=True)
        args.write_baseline.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    new=[]
    if args.staged or args.changed_from:
        prior={'fingerprints':[list(fingerprint(item)) for item in _base_findings(merge_base,changed)]}
        new=compare_to_baseline(found,prior)
    elif args.check_baseline:
        baseline=json.loads(args.check_baseline.read_text(encoding='utf-8'))
        if baseline.get('schema')!='bilqis.code-smell-baseline/v1':
            raise ValueError('HYGIENE_UNKNOWN_BASELINE_SCHEMA')
        new=compare_to_baseline(found,baseline)
    if args.json:
        print(json.dumps({'files':len(paths),'findings':[asdict(f) for f in found]},indent=2))
    else:
        print(f'Scanned {len(paths)} files; {len(found)} review findings (no mutations).')
        print('By rule:',dict(Counter(f.rule for f in found)))
        for item in found[:60]:
            print(f'{item.path}:{item.line} [{item.rule}] {item.context}')
        if len(found)>60:print(f'... {len(found)-60} further findings; use --json')
        if args.check_baseline or args.staged or args.changed_from:
            label='changed-file' if args.staged or args.changed_from else 'baseline-relative'
            print(f'New {label} findings: {len(new)}')
            for path,rule,context in new[:30]:print(f'NEW {path} [{rule}] {context}')
    return 2 if new else 1 if args.strict and found else 0


if __name__=='__main__':
    raise SystemExit(main())
