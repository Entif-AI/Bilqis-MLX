"""Read-only GitHub census of BAMF child registry gaps and duplicate keys.

Default audit never blocks CI or mutates issues. --strict returns nonzero on drift.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess

_KEY = re.compile(r'BAMF-0\.2\s+([ABC]\d{2}(?:\.\d+[a-z]?)*)\b')


def audit(registry: dict, workstack: dict, issues: list[dict]) -> dict:
    entries = registry['entries']
    registered_numbers = {entry['number'] for entry in entries}
    registered_keys = {entry['key'] for entry in entries}
    owner_numbers = {item['number'] for item in workstack['items']}
    candidates = []
    for issue in issues:
        match = _KEY.search(issue['title'])
        if not match or issue['number'] in owner_numbers:
            continue
        candidates.append({'key': match.group(1), 'number': issue['number'],
                           'state': issue['state'], 'title': issue['title']})
    by_key = {}
    for item in candidates:
        by_key.setdefault(item['key'], []).append(item)
    duplicates = [{'key': key, 'issues': sorted(rows, key=lambda x: x['number'])}
                  for key, rows in by_key.items() if len(rows) > 1]
    missing = [item for item in candidates if item['number'] not in registered_numbers]
    wrong_number = [{'key': entry['key'], 'number': entry['number'],
                     'live_numbers': sorted(x['number'] for x in by_key[entry['key']])}
                    for entry in entries if entry['key'] in by_key and
                    entry['number'] not in {x['number'] for x in by_key[entry['key']]}]
    unknown_registered = sorted(registered_keys - set(by_key))
    return {'schema': 'bilqis.child-registry-live-audit/v1',
            'status': 'incomplete' if missing or duplicates or wrong_number else 'complete',
            'registered_count': len(entries), 'owner_count': len(owner_numbers),
            'matched_live_count': len(candidates),
            'missing_issue_count': len(missing),
            'missing_unique_keys': len({item['key'] for item in missing}),
            'missing': sorted(missing, key=lambda x: x['number']),
            'duplicates': sorted(duplicates, key=lambda x: x['key']),
            'wrong_number': wrong_number,
            'registered_not_in_search': unknown_registered}


def fetch_live_issues(repo: str, limit: int) -> list[dict]:
    raw = subprocess.check_output(
        ['gh', 'issue', 'list', '-R', repo, '--state', 'all', '--search',
         'BAMF-0.2', '--limit', str(limit), '--json',
         'number,title,state'], text=True, timeout=60)
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('docs/tasks/bamf-0.2'))
    parser.add_argument('--repo', default='Entif-AI/Bilqis-MLX')
    parser.add_argument('--limit', type=int, default=1000)
    parser.add_argument('--issues-json', type=Path,
                        help='Offline issue-search fixture instead of GitHub')
    parser.add_argument('--strict', action='store_true')
    args = parser.parse_args()
    registry = json.loads((args.root / 'children/registry.json').read_text())
    workstack = json.loads((args.root / 'workstack.json').read_text())
    issues = (json.loads(args.issues_json.read_text()) if args.issues_json
              else fetch_live_issues(args.repo, args.limit))
    report = audit(registry, workstack, issues)
    print(json.dumps(report, sort_keys=True))
    return 1 if args.strict and report['status'] != 'complete' else 0


if __name__ == '__main__':
    raise SystemExit(main())
