"""Reconcile additive live owner amendments into repo mirrors and child ancestry.

Dry-run by default. Never changes GitHub; live issue bodies remain authoritative.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
from typing import Callable


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def additive_only(before: str, after: str) -> bool:
    """Every nonblank original line must survive, in its original order."""
    remaining = iter(line for line in after.splitlines() if line.strip())
    return all(any(candidate == line for candidate in remaining)
               for line in before.splitlines() if line.strip())


def fetch_issue_body(issue: int) -> bytes:
    output = subprocess.check_output(
        ['gh', 'issue', 'view', str(issue), '-R', 'Entif-AI/Bilqis-MLX',
         '--json', 'body'], text=True, timeout=30)
    return json.loads(output)['body'].encode('utf-8')


def atomic_write(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        handle.write(raw)
        temp = Path(handle.name)
    os.replace(temp, path)


def reconcile(root: Path, keys: tuple[str, ...],
              fetch: Callable[[int], bytes], *, apply: bool = False,
              preserve: Path | None = None) -> dict:
    root = root.resolve()
    if apply and (preserve is None or preserve.resolve().is_relative_to(root)):
        raise ValueError('PRIVATE_PRESERVATION_ROOT_REQUIRED')
    manifest_path = root / 'workstack.json'
    registry_path = root / 'children/registry.json'
    original_manifest = manifest_path.read_bytes()
    original_registry = registry_path.read_bytes()
    owners = {item['key']: item for item in json.loads(original_manifest)['items']}
    entries = json.loads(original_registry)['entries']
    plans = []
    for key in keys:
        if key not in owners:
            raise ValueError(f'UNKNOWN_OWNER:{key}')
        row = owners[key]
        path = root / 'issues' / f'{key}.md'
        old, live = path.read_bytes(), fetch(row['number'])
        old_sha, live_sha = digest(old), digest(live)
        manifest_sha = row['body_sha256']
        if old_sha not in (manifest_sha, live_sha):
            raise ValueError(f'LOCAL_OWNER_HASH_MISMATCH:{key}')
        if old_sha != live_sha and not additive_only(
                old.decode('utf-8'), live.decode('utf-8')):
            raise ValueError(f'NON_ADDITIVE_LIVE_CHANGE:{key}')
        descendants = [entry for entry in entries if entry['parent_key'] == key]
        if not descendants:
            raise ValueError(f'OWNER_DESCENDANTS_MISSING:{key}')
        parent_hashes = {entry['source_parent_sha256'] for entry in descendants}
        for prior in parent_hashes:
            if prior in (old_sha, manifest_sha, live_sha):
                continue
            preserved = preserve / f'{key}.before.md' if preserve else None
            if preserved is None or not preserved.is_file() or digest(
                    preserved.read_bytes()) != prior:
                raise ValueError(f'DESCENDANT_PARENT_HASH_DRIFT:{key}')
        plans.append({'key': key, 'number': row['number'], 'path': path,
                      'old': old, 'live': live, 'old_sha': old_sha,
                      'manifest_sha': manifest_sha, 'new_sha': live_sha,
                      'descendants': len(descendants), 'parent_hashes': parent_hashes})
    report = {'schema': 'bilqis.owner-mirror-reconciliation/v1',
              'applied': apply,
              'owners': [{k: p[k] for k in ('key', 'number', 'old_sha',
                         'new_sha', 'descendants')} for p in plans]}
    if not apply:
        return report
    assert preserve is not None
    # Validate all metadata edits before touching even one mirror.
    manifest_text = original_manifest.decode('utf-8')
    registry_text = original_registry.decode('utf-8')
    for p in plans:
        old_sha, new_sha = p['manifest_sha'], p['new_sha']
        if old_sha != new_sha:
            if manifest_text.count(old_sha) != 1:
                raise ValueError(f'MANIFEST_HASH_OCCURRENCE_INVALID:{p["key"]}')
            manifest_text = manifest_text.replace(old_sha, new_sha)
        for prior in p['parent_hashes']:
            if prior == new_sha:
                continue
            expected = sum(entry['source_parent_sha256'] == prior
                           for entry in entries if entry['parent_key'] == p['key'])
            if registry_text.count(prior) != expected:
                raise ValueError(f'REGISTRY_HASH_OCCURRENCE_INVALID:{p["key"]}')
            registry_text = registry_text.replace(prior, new_sha)
    preserve.mkdir(parents=True, exist_ok=True)
    for path, raw in ((preserve / 'workstack.before.json', original_manifest),
                      (preserve / 'registry.before.json', original_registry)):
        if not path.exists():
            atomic_write(path, raw)
    for p in plans:
        original_path = preserve / f'{p["key"]}.before.md'
        if not original_path.exists():
            atomic_write(original_path, p['old'])
        atomic_write(p['path'], p['live'])
    atomic_write(manifest_path, manifest_text.encode('utf-8'))
    atomic_write(registry_path, registry_text.encode('utf-8'))
    atomic_write(preserve / 'reconciliation.json',
                 (json.dumps(report, indent=2, sort_keys=True) + '\n').encode())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('docs/tasks/bamf-0.2'))
    parser.add_argument('--keys', required=True, help='Comma-separated owner keys')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--preserve', type=Path)
    args = parser.parse_args()
    result = reconcile(args.root, tuple(x.strip() for x in args.keys.split(',')),
                       fetch_issue_body, apply=args.apply, preserve=args.preserve)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
