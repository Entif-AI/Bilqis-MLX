"""Pinned dependency evidence preserves incomplete meaning without runnable credit."""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path
import re

KEY = r'[ABC]\d{2}(?:\.\d+[a-z]?)*'
SOURCE_ID = re.compile(KEY + r'\.(?:body|spec|comment-\d+|pr-\d+)\Z')
EVIDENCE_FIELDS = frozenset('schema resolution body_sha256 clause known_edges external_receipts source_records obligations unresolved'.split())
SOURCE_FIELDS = frozenset('source_id kind locator sha256 excerpt'.split())
RECEIPT_FIELDS = frozenset('number role head_sha merge_sha url source_id'.split())


class EvidenceStatus(str, Enum):
    INVALID = 'invalid'
    HELD = 'held'
    RESOLVED = 'resolved'


@dataclass(frozen=True)
class EvidenceCheck:
    status: EvidenceStatus
    known_edges: tuple[str, ...] = ()
    reason: str | None = None


def _invalid(reason):
    return EvidenceCheck(EvidenceStatus.INVALID, reason=reason)


def _name(value):
    return type(value) is str and bool(value.strip())


def _source_records(records, body, sources):
    if type(records) is not list or not records:
        return False
    seen, body_found = set(), False
    for record in records:
        if (type(record) is not dict or set(record) != SOURCE_FIELDS
                or not _name(record['source_id']) or not SOURCE_ID.fullmatch(record['source_id'])
                or record['source_id'] in seen
                or record['kind'] not in ('body', 'spec', 'comment', 'pull_request')
                or not all(_name(record[k]) for k in ('locator', 'sha256', 'excerpt'))):
            return False
        seen.add(record['source_id'])
        raw = sources.get(record['source_id'])
        if (type(raw) is not bytes or hashlib.sha256(raw).hexdigest() != record['sha256']
                or record['excerpt'] not in raw.decode('utf-8')):
            return False
        if record['kind'] == 'body':
            if raw != body:
                return False
            body_found = True
    return body_found


def _receipts(receipts, records, sources):
    if type(receipts) is not list:
        return None
    required, seen = [], set()
    for receipt in receipts:
        if (type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS
                or type(receipt['number']) is not int or receipt['number'] <= 0
                or receipt['number'] in seen
                or receipt['role'] not in ('prerequisite', 'implementation')
                or any(type(receipt[k]) is not str or not re.fullmatch('[0-9a-f]{40}', receipt[k])
                       for k in ('head_sha', 'merge_sha'))):
            return None
        seen.add(receipt['number'])
        record = next((r for r in records if r['source_id'] == receipt['source_id']), None)
        if record is None or record['kind'] != 'pull_request':
            return None
        raw = json.loads(sources[receipt['source_id']])
        if (raw['number'] != receipt['number'] or raw['state'] != 'MERGED'
                or raw['url'] != receipt['url'] or raw['headRefOid'] != receipt['head_sha']
                or raw['mergeCommit']['oid'] != receipt['merge_sha']):
            return None
        if receipt['role'] == 'prerequisite':
            required.append(receipt['number'])
    return tuple(required)


def _short_edges(text, numbers):
    text = text.split('. OPEN', 1)[0].rstrip('.')
    through = re.fullmatch('(' + KEY + ') through (' + KEY + ')', text)
    if through:
        start, end = (re.fullmatch(r'(.+\.)(\d+)', key) for key in through.groups())
        if not start or not end or start[1] != end[1]:
            return None
        first, last = int(start[2]), int(end[2])
        if first > last or last - first + 1 > len(numbers):
            return None
        return tuple(start[1] + str(n) for n in range(first, last + 1))
    if re.fullmatch(KEY + r'(?:,\s*' + KEY + ')*', text):
        return tuple(re.findall(KEY, text))
    return None


def _explicit_clause(clause, numbers):
    prefix = '**Direct prerequisites:** '
    if clause.startswith(prefix):
        edges = _short_edges(clause[len(prefix):], numbers)
        return None if edges is None else (edges, ())
    if clause.startswith('## Direct prerequisites\n'):
        links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', clause)
        if not links:
            return None
        edges = []
        for label, url in links:
            match = re.fullmatch('(' + KEY + r')\s*#(\d+)', label)
            if (not match or numbers.get(match[1]) != int(match[2])
                    or url != 'https://github.com/Entif-AI/Bilqis-MLX/issues/' + match[2]):
                return None
            edges.append(match[1])
        return tuple(edges), ()
    match = re.match(r'Direct prerequisites: merged #(\d+)/#(\d+); exact qualified #(\d+)/#(\d+) receipts for final composition turn-in; existing (' + KEY + r'(?:/' + KEY + r')*) source interfaces\.', clause)
    if match:
        return tuple(match[5].split('/')), tuple(int(match[i]) for i in range(1, 5))
    return None


def check_dependency_evidence(entry, body, issue_map, sources):
    """Check a caller-supplied pinned matrix, not independent source authentication."""
    try:
        evidence = entry['dependency_evidence']
        if type(evidence) is not dict or set(evidence) != EVIDENCE_FIELDS:
            return _invalid('bad-record')
        matrix = json.loads(sources['reviewed-packets'])
        matches = [p for p in matrix['packets'] if p['key'] == entry['key']]
        if (matrix['schema'] != 'bilqis.bamf.registry-expansion-review/v1'
                or len(matches) != 1 or matches[0]['dependency_evidence'] != evidence):
            return _invalid('source-drift')
        edges = evidence['known_edges']
        if (evidence['schema'] != 'bilqis.bamf.dependency-evidence/v1'
                or evidence['resolution'] not in ('resolved', 'held')
                or type(edges) is not list or not all(_name(e) for e in edges)
                or len(edges) != len(set(edges)) or edges != entry['deps']
                or type(evidence['obligations']) is not list
                or not all(_name(o) for o in evidence['obligations'])):
            return _invalid('bad-record')
        if any(edge not in issue_map for edge in edges):
            return _invalid('unknown-edge')
        if (type(body) is not bytes or hashlib.sha256(body).hexdigest() != evidence['body_sha256']
                or evidence['body_sha256'] != entry['body_sha256']
                or not _name(evidence['clause']) or evidence['clause'] not in body.decode('utf-8')
                or not _source_records(evidence['source_records'], body, sources)):
            return _invalid('source-drift')
        receipts = _receipts(evidence['external_receipts'], evidence['source_records'], sources)
        if receipts is None:
            return _invalid('bad-receipt')
        if evidence['resolution'] == 'held':
            if not _name(evidence['unresolved']):
                return _invalid('bad-record')
            return EvidenceCheck(EvidenceStatus.HELD, tuple(edges), evidence['unresolved'])
        if evidence['unresolved'] is not None:
            return _invalid('bad-record')
        parsed = _explicit_clause(evidence['clause'], issue_map)
        if parsed is None:
            return _invalid('unsupported-clause')
        if parsed != (tuple(edges), receipts) or len(parsed[0]) != len(set(parsed[0])):
            return _invalid('clause-mismatch')
        return EvidenceCheck(EvidenceStatus.RESOLVED, tuple(edges))
    except (KeyError, TypeError, ValueError, RecursionError):
        return _invalid('bad-record')


def load_dependency_sources(manifest_directory, registry):
    """Read fixed local evidence paths without interpreting arbitrary source locators."""
    entries = registry.get('entries', []) if isinstance(registry, dict) else []
    if not isinstance(entries, list) or not any(isinstance(e, dict) and 'dependency_evidence' in e for e in entries):
        return {}
    root = Path(manifest_directory) / 'dependency-evidence'
    matrix, source_root = root / 'reviewed-packets.json', root / 'sources'
    if (root.is_symlink() or source_root.is_symlink() or matrix.is_symlink()
            or not matrix.is_file()):
        raise ValueError('Dependency evidence storage is not a regular local tree')
    sources = {'reviewed-packets': matrix.read_bytes()}
    for entry in entries:
        evidence = entry.get('dependency_evidence') if isinstance(entry, dict) else None
        records = evidence.get('source_records') if isinstance(evidence, dict) else None
        if not isinstance(records, list):
            continue
        for record in records:
            source_id = record.get('source_id') if isinstance(record, dict) else None
            if isinstance(source_id, str) and SOURCE_ID.fullmatch(source_id):
                path = source_root / (source_id + '.txt')
                if path.is_file() and not path.is_symlink():
                    sources[source_id] = path.read_bytes()
    return sources
