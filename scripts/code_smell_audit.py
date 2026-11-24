"""Read-only, dependency-free Python code hygiene inventory.

Reports candidates for review; does not assert that every flagged pattern is a
bug, rewrite source, or alter the currently hash-bound training recipe.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import time

try:
    from quality.change_scope import GOVERNANCE_ADOPTION_COMMIT, scoped_name_status
    from quality.code_smell_rules import Finding, inspect_source
    from quality.smell_inspection import SourceInspection
    from quality.verification_ledger import VerificationLedger, full_requested, ledger_path
except ModuleNotFoundError:  # dynamic test import from repository root
    from scripts.quality.change_scope import GOVERNANCE_ADOPTION_COMMIT, scoped_name_status
    from scripts.quality.code_smell_rules import Finding, inspect_source
    from scripts.quality.smell_inspection import SourceInspection
    from scripts.quality.verification_ledger import VerificationLedger, full_requested, ledger_path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIRS = tuple(sorted(
    path.name for path in ROOT.iterdir()
    if path.is_dir() and (path.name.startswith('bilqis_') or
                          path.name in ('scripts','tests'))))

PHYSICAL_OWNER_GROUPS = frozenset({
    "_projection", "_admission", "_capability", "_source", "_model", "_custody",
    "_operator", "_teacher", "_depth", "_correction", "_batch",
})
NESTED_PHYSICAL_OWNER_GROUPS = frozenset({
    ("_batch", "training"),
    ("_admission", "v2"),
    ("_admission", "jit"),
    ("_admission", "lease"),
    ("_capability", "factory"),
    ("_model", "cache"),
    ("_model", "backbone"),
    ("_correction", "owners"),
    ("_correction", "accepted"),
})
DEEP_NESTED_PHYSICAL_OWNER_GROUPS = frozenset({
    ("_capability", "factory", "_evaluation"),
    ("_capability", "factory", "_solver"),
    ("_capability", "factory", "_task"),
})


def logical_source_path(path: str) -> str:
    """Preserve established module identity across runtime physical grouping."""
    parts = Path(path).parts
    if (len(parts) >= 6
            and parts[:4] == (
                "bilqis_mlx", "runtime", "bamf_operator", "session_parts")
            and parts[4] in {"_candidate", "_lifecycle"}):
        return Path(*parts[:4], *parts[5:]).as_posix()
    if (len(parts) >= 4
            and parts[:3] == ("bilqis_mlx", "semantics", "_cognitive_dag")):
        return "bilqis_mlx/semantics/cognitive_dag.py"
    if (len(parts) >= 6 and parts[:2] == ("bilqis_mlx", "runtime")
            and tuple(parts[2:5]) in DEEP_NESTED_PHYSICAL_OWNER_GROUPS):
        return Path(*parts[:2], *parts[5:]).as_posix()
    if (len(parts) >= 5 and parts[:2] == ("bilqis_mlx", "runtime")
            and tuple(parts[2:4]) in NESTED_PHYSICAL_OWNER_GROUPS):
        return Path(*parts[:2], *parts[4:]).as_posix()
    if len(parts) >= 4 and parts[:2] == ("bilqis_mlx", "runtime") and parts[2] in PHYSICAL_OWNER_GROUPS:
        return Path(*parts[:2], *parts[3:]).as_posix()
    return Path(path).as_posix()



def _paths(user_paths):
    if user_paths is not None:
        return sorted({(ROOT / name).resolve() for name in user_paths
                       if str((ROOT/name).resolve()).startswith(str(ROOT.resolve()) + '/')})
    return sorted(path for name in DEFAULT_DIRS for path in (ROOT/name).rglob('*.py')
                  if path.is_file())


def audit(paths, inspection=None):
    records = []
    for path in paths:
        if not path.is_file() or path.suffix != '.py':
            continue
        name = logical_source_path(str(path.relative_to(ROOT)))
        if inspection is None:
            records.extend(inspect_source(name, path.read_text(encoding='utf-8')))
        else:
            records.extend(inspection.current(name, path))
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
        status=fields[0]
        if status.startswith(('R','C')):
            old,new=fields[1],fields[2]
        else:
            old=new=fields[1]
        if new.endswith('.py'):
            records.append((status,old,new))
    return records


def _staged_records():
    result=subprocess.run(['git','diff','--cached','--name-status','-M','--diff-filter=ACMR'],
                          cwd=ROOT,check=True,text=True,stdout=subprocess.PIPE)
    return 'HEAD',_records_from_name_status(result.stdout)


def _changed_records(base_ref):
    merge_base,scoped=scoped_name_status(ROOT,base_ref,diff_filter='ACMR')
    return merge_base,_records_from_name_status(scoped)


def _debt_baseline_ref(requested_base, scoped_base):
    """Use the exact PR base once governance already exists there.

    The pre-adoption boundary protects the migration that introduced this gate.
    Once the requested base already contains that governance, a later PR must be
    charged only for debt beyond its actual base, including files that merely
    moved into physical owner compartments.
    """
    result=subprocess.run(
        ['git','merge-base','--is-ancestor',GOVERNANCE_ADOPTION_COMMIT,requested_base],
        cwd=ROOT,text=True,capture_output=True)
    return requested_base if result.returncode==0 else scoped_base


def _base_findings(merge_base, records, inspection=None):
    # Preserve the existing rename and canonical-owner debt semantics.
    tree = subprocess.run(
        ['git', '--no-replace-objects', 'ls-tree', '-r', '-z', merge_base], cwd=ROOT,
        check=True, capture_output=True,
    )
    blobs = {}
    owners = defaultdict(list)
    for entry in tree.stdout.split(b'\0'):
        if not entry:
            continue
        header, raw_name = entry.split(b'\t', 1)
        _mode, kind, oid = header.decode().split()
        name = raw_name.decode('utf-8')
        if kind == 'blob':
            blobs[name] = oid
            if name.endswith('.py'):
                owners[logical_source_path(name)].append(name)
    found = []
    for status, old, new in records:
        logical = logical_source_path(new)
        if old in blobs:
            source = old
        elif logical != new and logical in blobs:
            source = logical
        elif status.startswith('R') and len(owners[logical]) == 1:
            source = owners[logical][0]
        else:
            continue
        oid = blobs[source]
        if inspection is not None:
            found.extend(inspection.committed(logical, oid))
        else:
            raw = subprocess.check_output(['git', '--no-replace-objects', 'cat-file', 'blob', oid], cwd=ROOT)
            found.extend(inspect_source(logical, raw.decode('utf-8')))
    return sorted(found, key=lambda f: (f.path, f.line, f.rule))


def _scoped_baseline(args, changed, merge_base, inspection):
    if changed is None:
        return None
    baseline_ref = merge_base if args.staged else _debt_baseline_ref(args.changed_from, merge_base)
    return {'fingerprints': [list(fingerprint(item))
                             for item in _base_findings(baseline_ref, changed, inspection)]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths',nargs='*',help='Relative Python paths, default core packages')
    scope=parser.add_mutually_exclusive_group()
    scope.add_argument('--staged',action='store_true',help='Audit staged Python files only')
    scope.add_argument('--changed-from',help='Audit Python files changed from merge-base with REF')
    parser.add_argument('--full', action='store_true', help='Recompute all scoped findings')
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
        scoped=[new for _,_,new in changed]
    elif args.changed_from:
        merge_base,changed=_changed_records(args.changed_from)
        scoped=[new for _,_,new in changed]
    else:
        scoped=args.paths
    paths=_paths(scoped if args.staged or args.changed_from else (args.paths or None))
    started = time.perf_counter()
    with VerificationLedger(ledger_path(ROOT), full=args.full or full_requested()) as ledger:
        inspection = SourceInspection(ROOT, ledger)
        found = audit(paths, inspection)
        base_findings = _scoped_baseline(args, changed, merge_base if changed is not None else None,
                                         inspection)
        ledger.report('code-smell', time.perf_counter() - started)
    if args.write_baseline:
        if args.staged or args.changed_from or args.paths:
            raise ValueError('HYGIENE_BASELINE_REQUIRES_WHOLE_CURRENT_CORE')
        output={'schema':'bilqis.code-smell-baseline/v1',
                'description':'Review findings only; not proven defects or frozen-source rewrite authority',
                'fingerprints':[list(fingerprint(item)) for item in found]}
        args.write_baseline.parent.mkdir(parents=True,exist_ok=True)
        args.write_baseline.write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
    new=[]
    if base_findings is not None:
        new = compare_to_baseline(found, base_findings)
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
