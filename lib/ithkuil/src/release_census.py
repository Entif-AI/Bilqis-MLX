"""Reference existing domain/frontier receipts in a release-level row census (#94)."""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys

from .ingestion_semantic import _conformance_artifact, _file_sha, _frontier
from .skos.conformance import write_evidence
from .skos.corpus import SOURCE_TABLES, source_census
from .skos.errors import ProfileError
from .skos.no_omission import SourceRowIdentity, validate_no_omission
from .skos.publication import json_bytes

VERSION = '1.0.0'
DOMAINS = frozenset(row[0] for row in SOURCE_TABLES)


def aggregate(revision: str, coverage: dict, rows, frontier: dict, refs: dict) -> dict:
    if set(coverage['domains']) != DOMAINS:
        raise ProfileError('RELEASE_CENSUS_DOMAIN_SET_MISMATCH')
    duplicates = Counter((row.table, row.key) for row in rows)
    if any(count != 1 for count in duplicates.values()):
        raise ProfileError('RELEASE_CENSUS_DOMAIN_OVERLAP')
    if coverage['canonical_rdf'] != refs['canonical_rdf']:
        raise ProfileError('RELEASE_CENSUS_CANONICAL_MISMATCH')
    accounting = validate_no_omission(rows, coverage).as_dict()
    domains = {}
    for name, body in sorted(coverage['domains'].items()):
        domains[name] = {
            'receipt': {**refs['coverage'], 'pointer': '/domains/' + name},
            'owners': sorted({row['owner'] for row in body['rows']}),
            'source_rows': body['source_rows'], 'dispositions': body['dispositions'],
            'source_tables': dict(sorted(Counter(row['table'] for row in body['rows']).items())),
            'semantic_counts': body['semantic_counts'], 'notation_counts': body['notation_counts'],
            'frontier_debt': body['frontier_debt'],
        }
    return {
        'schema': 'bilqis.ithkuil.release-census/v1', 'version': VERSION,
        'release_revision': revision, 'compiler': coverage['compiler'],
        'accounting_complete': accounting['complete'],
        'semantic_coverage_status': coverage['build_status'],
        'full_new_ithkuil_coverage': frontier['claims']['full_new_ithkuil_coverage'],
        'canonical_rdf': coverage['canonical_rdf'], 'references': refs,
        'counting_unit': 'One stable source/IR row, keyed by (domain, table, key). Tables and row identities are disjoint across domains. Semantic-resource counts are not summed.',
        'domains': domains,
        'totals': {'source_rows': accounting['source_rows'], 'accounted_rows': accounting['accounted_rows'],
                   'dispositions': accounting['dispositions']},
        'remaining_frontier': {
            'unparsed_artifact_ids': frontier['aggregates']['unparsed_artifact_ids'],
            'debt_by_reason': frontier['aggregates']['debt']['by_reason'],
            'counting_note': 'Source-owner observation/debt categories can overlap; do not add them to semantic row totals.',
        },
    }


def generate(repo: Path, csv_root: Path, bundle: Path, proof_path: Path) -> dict:
    proof = json.loads(proof_path.read_text())
    if (proof.get('schema') != 'bilqis.ithkuil.release93-proof/v1' or proof.get('status') != 'passed'
            or proof.get('fixture_only') is not False or proof['runs']['one'] != proof['runs']['two']):
        raise ProfileError('RELEASE_CENSUS_CLEANROOM_PROOF_REQUIRED')
    expected = proof['runs']['one']
    for name, artifact in expected['published_source_artifacts'].items():
        if name.startswith('_data/csv/'):
            path = csv_root / name.removeprefix('_data/csv/')
            if _file_sha(path) != artifact['sha256']:
                raise ProfileError('RELEASE_CENSUS_SOURCE_DRIFT', name)
    report = json.loads((bundle / 'conformance.json').read_text())
    if report['status'] != 'complete' or any(g['status'] != 'passed' for g in report['gates']):
        raise ProfileError('RELEASE_CENSUS_CONFORMANCE_REQUIRED')
    report['evidence'] = {'path': str(bundle.resolve()), 'bundle_id': bundle.name}
    artifact = _conformance_artifact(bundle.parent, report)
    pinned = expected['semantic_artifacts']['full']
    if (artifact['bundle_id'] != pinned['bundle_id']
            or artifact['canonical']['sha256'] != pinned['files']['canonical']['sha256']):
        raise ProfileError('RELEASE_CENSUS_RELEASE_BINDING_MISMATCH')
    frontier_path = csv_root / 'sources/extraction_frontier.json'
    frontier, frontier_sha, receipt_sha = _frontier(frontier_path, csv_root, repo)
    if frontier.get('schema') != 'bilqis.ithkuil.extraction-frontier/v1':
        raise ProfileError('RELEASE_CENSUS_PRODUCTION_FRONTIER_REQUIRED')
    rows = source_census(csv_root)
    recorded = tuple(SourceRowIdentity(**row) for row in json.loads((bundle / 'source-rows.json').read_text()))
    if tuple(sorted(rows)) != tuple(sorted(recorded)):
        raise ProfileError('RELEASE_CENSUS_SOURCE_CENSUS_DRIFT')
    refs = {
        'cleanroom_proof': {'repository_file': 'lib/ithkuil/evidence/release-93.json', 'sha256': _file_sha(proof_path)},
        'source_manifest': {'file': 'sources/source_manifest.csv', 'sha256': _file_sha(csv_root / 'sources/source_manifest.csv')},
        'frontier': {'file': 'sources/extraction_frontier.json', 'sha256': frontier_sha, 'receipt_sha256': receipt_sha},
        'canonical_rdf': {k: artifact['canonical'][k] for k in ('sha256', 'triple_count')},
        'coverage': {'bundle_id': artifact['bundle_id'], 'file': 'coverage.json', 'sha256': artifact['coverage']['sha256']},
        'source_rows': {'bundle_id': artifact['bundle_id'], 'file': 'source-rows.json', 'sha256': artifact['source_rows']['sha256']},
        'conformance': {'bundle_id': artifact['bundle_id'], 'file': 'conformance.json', 'sha256': artifact['conformance']['sha256'], 'status': artifact['status']},
    }
    coverage = json.loads((bundle / 'coverage.json').read_text())
    return aggregate(proof['candidate_revision'], coverage, rows, frontier, refs)


def render_markdown(value: dict) -> str:
    lines = ['# Release corpus census', '', f"Candidate: `{value['release_revision']}`.",
             f"Canonical RDF: `{value['canonical_rdf']['sha256']}` ({value['canonical_rdf']['triple_count']} triples).", '',
             f"Declared-scope accounting complete: {value['accounting_complete']}.",
             f"Semantic coverage: **{value['semantic_coverage_status']}**.",
             f"Full New Ithkuil coverage: {value['full_new_ithkuil_coverage']}.", '',
             '| Domain | Source rows | EMITTED | HELD | REJECTED | UNSUPPORTED | IR_ONLY |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for name, domain in value['domains'].items():
        counts = domain['dispositions']
        cells = [name, domain['source_rows'], *(counts[k] for k in ('EMITTED', 'HELD', 'REJECTED', 'UNSUPPORTED', 'IR_ONLY'))]
        lines.append('| ' + ' | '.join(map(str, cells)) + ' |')
    totals = value['totals']
    cells = ['Total', totals['source_rows'], *(totals['dispositions'][k] for k in ('EMITTED', 'HELD', 'REJECTED', 'UNSUPPORTED', 'IR_ONLY'))]
    lines.append('| ' + ' | '.join(map(str, cells)) + ' |')
    lines.extend(['', value['counting_unit'], '', 'Unparsed source artifacts:', ''])
    lines.extend('- `' + item + '`' for item in value['remaining_frontier']['unparsed_artifact_ids'])
    lines.extend(['', 'Source-frontier debt (owner observation units; categories are not additive):', ''])
    lines.extend(f'- `{code}`: {count}' for code, count in sorted(value['remaining_frontier']['debt_by_reason'].items()))
    lines.extend(['', 'Domain receipt references and exact source-to-domain table counts are in `release-census.json`.',
                  'This census grants no curriculum, neural, graph-write, merge or publication authority.', ''])
    return '\n'.join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('repo', 'csv-root', 'bundle', 'proof', 'output-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    try:
        value = generate(args.repo.resolve(), args.csv_root.resolve(), args.bundle.resolve(), args.proof.resolve())
        evidence = write_evidence({'release-census.json': json_bytes(value),
                                   'RELEASE_CENSUS.md': render_markdown(value).encode()}, args.output_root)
        print(json.dumps({'status': 'passed', 'evidence': evidence, 'canonical_rdf': value['canonical_rdf']}, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({'status': 'failed', 'code': getattr(error, 'code', 'RELEASE_CENSUS_INPUT_INVALID'),
                          'details': str(error)}, sort_keys=True))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
