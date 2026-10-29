#!/usr/bin/env python3
"""Validate BAMF workstack identity, dependencies, and shared-file ownership."""
from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from graphlib import CycleError, TopologicalSorter
import json
from pathlib import Path
import re
import subprocess
import sys
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from bilqis_mlx.errors import BilqisError, ErrorBus, SCHOOL


@dataclass(frozen=True)
class BamfWorkItem:
    key: str
    issue: int
    lane: str
    depends: tuple[str, ...]
    files: tuple[str, ...]
    contract_hash: str
    status: str | None


def _issues_report(issues):
    result = []
    for issue in issues:
        reason = issue['code']
        typed = ErrorBus.report(BilqisError(SCHOOL.BAMF_WORKSTACK.VALIDATION_INVALID, {'reason': reason}))
        result.append({**{k: v for k, v in issue.items() if k != 'code'}, 'code': typed.code, 'reason': reason})
    return sorted(result, key=lambda issue: json.dumps(issue, sort_keys=True))


def validate_workstack(manifest: dict, registry: dict | None = None, issue_map: dict | None = None, mirrors: dict | None = None) -> dict:
    issues = []
    if not isinstance(manifest, dict) or manifest.get('schema') != 'bilqis.bamf.workstack/v1' or manifest.get('version') != '0.2.0':
        return {'schema': 'bilqis.bamf.workstack.validation/v1', 'status': 'invalid',
                'order': [], 'issues': _issues_report([{'code': 'SCHEMA_INVALID'}])}
    rows = manifest.get('items')
    if not isinstance(rows, list) or not rows:
        return {'schema': 'bilqis.bamf.workstack.validation/v1', 'status': 'invalid',
                'order': [], 'issues': _issues_report([{'code': 'ITEMS_INVALID'}])}
    items = []
    for row in rows:
        if not isinstance(row, dict):
            issues.append({'code': 'ITEM_INVALID'}); continue
        key, number, lane = row.get('key'), row.get('number'), row.get('lane')
        deps, paths, digest, status = row.get('deps'), row.get('paths'), row.get('body_sha256'), row.get('status')
        if (not isinstance(key, str) or not re.fullmatch(r'[ABC][0-9]{2}', key)
                or lane != key[0] or not isinstance(number, int) or isinstance(number, bool) or number < 1
                or not isinstance(deps, list) or any(not isinstance(x, str) for x in deps)
                or not isinstance(paths, list) or any(not isinstance(x, str) or not x for x in paths)
                or not isinstance(digest, str) or not re.fullmatch(r'[0-9a-f]{64}', digest)
                or (status is not None and not isinstance(status, str))):
            issues.append({'code': 'ITEM_INVALID', 'key': key if isinstance(key, str) else ''}); continue
        files = tuple(re.sub(r' \((?:new|append|scoped amendment)\)$', '', p).split(':', 1)[0] for p in paths)
        if any(p in {'.', './'} or re.match(r'^[A-Za-z]:', p) or Path(p).is_absolute() or '..' in Path(p).parts or Path(p).as_posix() != p.removesuffix('/') or p.endswith('//') or '\\' in p or '\x00' in p for p in files):
            issues.append({'code': 'FILE_PATH_INVALID', 'key': key}); continue
        items.append(BamfWorkItem(key, number, lane, tuple(deps), files, digest, status))
    by_key = {item.key: item for item in items}
    if len(by_key) != len(items): issues.append({'code': 'DUPLICATE_KEY'})
    if len({item.issue for item in items}) != len(items): issues.append({'code': 'DUPLICATE_ISSUE'})
    for item in items:
        for dep in item.depends:
            if dep not in by_key: issues.append({'code': 'MISSING_DEPENDENCY', 'item': item.key, 'dependency': dep})
    claims: dict[str, tuple[str, set[str], bool, set[str]]] = {}
    for item in items:
        for path in item.files:
            canonical = path.removesuffix('/')
            folded = unicodedata.normalize('NFC', canonical).casefold()
            previous = claims.get(folded)
            if previous is None:
                claims[folded] = (canonical, {item.lane}, path.endswith('/'), {item.key})
            else:
                previous[1].add(item.lane)
                previous[3].add(item.key)
                claims[folded] = (previous[0], previous[1], previous[2] or path.endswith('/'), previous[3])
    queues = manifest.get('shared_file_queues', [])
    if not isinstance(queues, list):
        issues.append({'code': 'SHARED_FILE_QUEUE_INVALID'})
        queues = []
    c_owned_paths = {'bilqis_mlx/learning/student_ops.py', 'bilqis_mlx/runtime/mlx_checkpoint.py',
                     'bilqis_mlx/runtime/checkpoints.py', 'bilqis_mlx/runtime/boundary_commit.py'}
    c_owned_folded = {unicodedata.normalize('NFC', p).casefold() for p in c_owned_paths}
    allowed = set()
    for queue in queues:
        if not isinstance(queue, dict):
            issues.append({'code': 'SHARED_FILE_QUEUE_INVALID'}); continue
        path, writer = queue.get('path'), queue.get('writer_lane')
        participants, proposals = queue.get('participants'), queue.get('proposal_lanes')
        folded = unicodedata.normalize('NFC', path).casefold() if isinstance(path, str) else ''
        claim = claims.get(folded)
        if (not claim or path != claim[0] or folded in allowed or not isinstance(participants, list)
                or any(not isinstance(x, str) for x in participants) or len(set(participants)) != len(participants)
                or set(participants) != claim[3] or not isinstance(proposals, list)
                or any(not isinstance(x, str) for x in proposals) or len(set(proposals)) != len(proposals)
                or not isinstance(writer, str) or writer not in {'A', 'B', 'C'}
                or (folded in c_owned_folded and writer != 'C')
                or set(proposals) != claim[1] - {writer} or not proposals):
            issues.append({'code': 'SHARED_FILE_QUEUE_INVALID', 'path': path if isinstance(path, str) else ''}); continue
        allowed.add(folded)
    for path in c_owned_paths:
        folded = unicodedata.normalize('NFC', path).casefold()
        claim = claims.get(folded)
        if claim and 'B' in claim[1] and folded not in allowed:
            issues.append({'code': 'SHARED_FILE_QUEUE_REQUIRED', 'path': path})
    for folded, (path, lanes, is_dir, _) in sorted(claims.items()):
        if len(lanes) > 1 and folded not in allowed:
            issues.append({'code': 'CROSS_LANE_FILE_OWNERSHIP', 'path': path, 'lanes': sorted(lanes)})
        for other, (_, other_lanes, _, _) in sorted(claims.items()):
            if other.startswith(folded + '/') and len(lanes | other_lanes) > 1:
                issues.append({'code': 'CROSS_LANE_FILE_OWNERSHIP', 'path': path + '/',
                               'lanes': sorted(lanes | other_lanes)})
    graph = {k: tuple(sorted(v.depends)) for k, v in sorted(by_key.items())}
    child_count = 0
    numbers = {item.key: item.issue for item in items}
    if registry is None:
        issues.append({'code': 'REGISTRY_REQUIRED'})
    if registry is not None:
        if (not isinstance(registry, dict) or registry.get('schema') != 'bilqis.bamf.all-child-registry/v1'
                or not isinstance(registry.get('entries'), list)):
            issues.append({'code': 'REGISTRY_INVALID'})
        else:
            entries = registry['entries']
            valid_entries = []
            for entry in entries:
                if (not isinstance(entry, dict) or not isinstance(entry.get('key'), str)
                        or not isinstance(entry.get('number'), int) or isinstance(entry.get('number'), bool)
                        or not isinstance(entry.get('parent_key'), str)
                        or not isinstance(entry.get('parent_number'), int)
                        or not isinstance(entry.get('deps'), list)
                        or any(not isinstance(dep, str) for dep in entry['deps'])):
                    issues.append({'code': 'REGISTRY_ITEM_INVALID'}); continue
                key = entry['key']
                if key in graph:
                    issues.append({'code': 'DUPLICATE_KEY'}); continue
                graph[key] = tuple(sorted(entry['deps']))
                valid_entries.append(entry)
                numbers[key] = entry['number']
                child_count += 1
            for entry in valid_entries:
                child_key = entry['key']
                expected_parent = child_key[:-1] if child_key[-1:].islower() else child_key.rsplit('.', 1)[0]
                if (not re.fullmatch(r'[ABC][0-9]{2}(?:\.[0-9]+[a-z]?)+', child_key)
                        or entry['parent_key'] != expected_parent
                        or numbers.get(entry['parent_key']) != entry['parent_number']):
                    issues.append({'code': 'REGISTRY_PARENT_INVALID', 'key': entry.get('key', '')})
            for entry in valid_entries:
                key = entry['key']
                raw = mirrors.get(key) if isinstance(mirrors, dict) else None
                if not isinstance(raw, bytes) or hashlib.sha256(raw).hexdigest() != entry.get('body_sha256'):
                    issues.append({'code': 'MIRROR_HASH_MISMATCH', 'key': key}); continue
                try:
                    body = raw.decode('utf-8')
                except UnicodeDecodeError:
                    issues.append({'code': 'MIRROR_INVALID', 'key': key}); continue
                match = re.search(r'(?ms)^## Direct prerequisites\n(.*?)(?=^## |^\*\*Existing owner hooks:|\Z)|^\*\*Direct work prerequisites:\*\*([^\n]*)', body)
                if not match:
                    issues.append({'code': 'MIRROR_DEPENDENCIES_MISSING', 'key': key}); continue
                line = next(value for value in match.groups() if value is not None).split('Original ')[0].split(' The parent ')[0]
                found = re.findall(r'\[([ABC]\d{2}(?:\.\d+[a-z]?)*)\s*(?::\s*)?#(\d+)\]', line)
                links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', line)
                expected_links = [(f'{dep} #{number}', f'https://github.com/Entif-AI/Bilqis-MLX/issues/{number}')
                                  for dep, number in found]
                if (len(links) != len(found) or any(link not in expected_links for link in links)
                        or len(found) != len(set(found)) or {dep for dep, _ in found} != set(entry['deps'])
                        or any(numbers.get(dep) != int(number) for dep, number in found)):
                    issues.append({'code': 'MIRROR_DEPENDENCIES_MISMATCH', 'key': key})
            for row in rows:
                if not isinstance(row, dict) or 'children' not in row: continue
                declared = row['children']
                if not isinstance(declared, list) or any(not isinstance(child, str) for child in declared):
                    issues.append({'code': 'DECLARED_CHILDREN_INVALID', 'key': row.get('key', '')}); continue
                actual = [entry['key'] for entry in valid_entries if entry['parent_key'] == row.get('key')]
                if len(set(declared)) != len(declared) or set(declared) != set(actual):
                    issues.append({'code': 'DECLARED_CHILDREN_MISMATCH', 'key': row.get('key', '')})
            hierarchy = {entry['key']: (entry['parent_key'],) for entry in valid_entries}
            try:
                tuple(TopologicalSorter(hierarchy).static_order())
            except CycleError:
                issues.append({'code': 'PARENT_CYCLE'})
            if len(set(numbers.values())) != len(numbers): issues.append({'code': 'DUPLICATE_ISSUE'})
            for key, deps in graph.items():
                for dep in deps:
                    if dep not in graph and key not in by_key:
                        issues.append({'code': 'MISSING_DEPENDENCY', 'item': key, 'dependency': dep})
    if issue_map is None:
        issues.append({'code': 'ISSUE_MAP_REQUIRED'})
    if issue_map is not None and not isinstance(issue_map, dict):
        issues.append({'code': 'ISSUE_MAP_INVALID'})
    if isinstance(issue_map, dict):
        expected = {k: v for k, v in issue_map.items() if k not in {'LANE_A', 'LANE_B', 'LANE_C'}}
        if expected != numbers:
            issues.append({'code': 'ISSUE_MAP_MISMATCH'})
    order = []
    if not any(i['code'] in {'MISSING_DEPENDENCY', 'DUPLICATE_KEY'} for i in issues):
        try:
            order = list(TopologicalSorter(graph).static_order())
        except CycleError:
            issues.append({'code': 'DEPENDENCY_CYCLE'})
    return {'schema': 'bilqis.bamf.workstack.validation/v1',
            'input_schema': 'bilqis.bamf.workstack/v1', 'input_version': '0.2.0',
            'status': 'invalid' if issues else 'valid', 'order': order,
            'recursive_registry': 'included' if registry is not None else 'not_provided', 'child_count': child_count,
            'issues': _issues_report(issues)}


def check_live_owner_mirrors(manifest: dict, root: Path) -> list[dict]:
    rows = manifest['items']
    fields = ' '.join(f'q{i}: issue(number:{row["number"]}) {{ number body }}' for i, row in enumerate(rows))
    query = 'query { repository(owner:"Entif-AI",name:"Bilqis-MLX") { ' + fields + ' } }'
    response = subprocess.run(['gh', 'api', 'graphql', '-f', 'query=' + query],
                              check=True, capture_output=True, text=True, timeout=30)
    repository = json.loads(response.stdout)['data']['repository']
    findings = []
    for index, row in enumerate(rows):
        issue = repository[f'q{index}']
        if not isinstance(issue, dict) or issue.get('number') != row['number'] or not isinstance(issue.get('body'), str):
            raise ValueError('Invalid live issue response')
        live = hashlib.sha256(issue['body'].encode('utf-8')).hexdigest()
        mirror = hashlib.sha256((root / 'issues' / (row['key'] + '.md')).read_bytes()).hexdigest()
        if live != row['body_sha256'] or live != mirror:
            findings.append({'code': 'LIVE_OWNER_MIRROR_MISMATCH', 'key': row['key']})
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--registry', type=Path, help='Recursive child registry; defaults to children/registry.json beside the manifest when present.')
    parser.add_argument('--issue-map', type=Path, help='Independent issue map; defaults to issue-map.json beside the manifest.')
    parser.add_argument('--live', action='store_true', help='Compare every owner mirror and digest against live GitHub.')
    args = parser.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding='utf-8'))
        registry_path = args.registry or args.manifest.parent / 'children' / 'registry.json'
        registry = json.loads(registry_path.read_text(encoding='utf-8')) if args.registry or registry_path.exists() else None
        map_path = args.issue_map or args.manifest.parent / 'issue-map.json'
        issue_map = json.loads(map_path.read_text(encoding='utf-8')) if args.issue_map or map_path.exists() else None
        mirrors = {}
        if isinstance(registry, dict) and isinstance(registry.get('entries'), list):
            for entry in registry['entries']:
                key = entry.get('key') if isinstance(entry, dict) else None
                if isinstance(key, str) and re.fullmatch(r'[ABC][0-9]{2}(?:\.[0-9]+[a-z]?)+', key):
                    mirror = registry_path.parent / (key + '.md')
                    if mirror.is_file(): mirrors[key] = mirror.read_bytes()
        result = validate_workstack(manifest, registry, issue_map, mirrors)
        if args.live and result['status'] == 'valid':
            live_findings = check_live_owner_mirrors(manifest, args.manifest.parent)
            result['live_owner_mirrors'] = {'checked': len(manifest['items']), 'status': 'invalid' if live_findings else 'valid'}
            if live_findings:
                result['issues'] = _issues_report(live_findings)
                result['status'] = 'invalid'
        elif args.live:
            result['live_owner_mirrors'] = {'checked': 0, 'status': 'not_checked'}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
        report = ErrorBus.report(BilqisError(SCHOOL.BAMF_WORKSTACK.INPUT_INVALID, {'error_type': type(error).__name__}))
        print(json.dumps({'schema': 'bilqis.bamf.workstack.validation/v1', 'status': 'error',
                          'error': {'code': report.code, 'summary': report.summary}}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] == 'valid' else 1


if __name__ == '__main__':
    raise SystemExit(main())
