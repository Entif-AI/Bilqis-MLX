"""Run registered independent semantic-corpus conformance gates (#72)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .canonical import canonicalize
from .coverage_schema import validate_coverage_receipt
from .determinism import compare_graphs, require_equivalent
from .errors import ProfileError
from .no_omission import SourceRowIdentity, validate_no_omission
from .rdf_read import read_canonical_graph
from .shacl import validate_graph

GATES = ('coverage', 'no-omission', 'determinism', 'shacl')
GATE_VERSION = '1.0.0'


def validate_artifacts(graph, receipt, source_rows, comparison_graph, *, admitted_mappings=()) -> dict:
    canonical = canonicalize(graph)

    def coverage():
        validate_coverage_receipt(receipt)
        expected = {'sha256': canonical.sha256, 'triple_count': canonical.triple_count}
        if receipt['canonical_rdf'] != expected:
            raise ProfileError('COVERAGE_CANONICAL_RDF_MISMATCH', canonical.sha256)
        return {'canonical_rdf': expected, 'build_status': receipt['build_status']}

    def no_omission():
        return validate_no_omission(source_rows, receipt, strong_subjects={str(s) for s in graph.subjects()}).as_dict()

    def determinism():
        return require_equivalent(compare_graphs(graph, comparison_graph, scenario='independent-build')).as_dict()

    def shacl():
        return validate_graph(graph, admitted_mappings=admitted_mappings)

    implementations = {'coverage': coverage, 'no-omission': no_omission, 'determinism': determinism, 'shacl': shacl}
    if set(implementations) != set(GATES):
        raise ProfileError('CONFORMANCE_GATE_REGISTRY_MISMATCH')
    results = []
    for name in GATES:
        try:
            evidence = implementations[name]()
            passed = evidence.get('conforms', True)
            results.append({'gate': name, 'version': GATE_VERSION, 'status': 'passed' if passed else 'failed', 'evidence': evidence})
        except (OSError, ImportError) as error:
            results.append({'gate': name, 'version': GATE_VERSION, 'status': 'infrastructure-failed', 'evidence': {'code': type(error).__name__}})
        except ProfileError as error:
            results.append({'gate': name, 'version': GATE_VERSION, 'status': 'failed', 'evidence': error.as_dict()})
    failed = [value['gate'] for value in results if value['status'] != 'passed']
    infrastructure = any(value['status'] == 'infrastructure-failed' for value in results)
    return {
        'schema': 'bilqis.skos.conformance/v1', 'status': 'infrastructure-failed' if infrastructure else ('failed' if failed else 'complete'),
        'canonical_sha256': canonical.sha256, 'failed_gates': failed, 'gates': results,
        'coverage_status': receipt.get('build_status'),
    }


def write_evidence(files, output_root):
    """Keep constituent bytes under a content-derived directory; reconcile retries."""
    from .publication import json_bytes
    manifest = {name: hashlib.sha256(payload).hexdigest() for name, payload in sorted(files.items())}
    manifest_bytes = json_bytes(manifest)
    identity = hashlib.sha256(manifest_bytes).hexdigest()
    root = Path(output_root)
    if root.is_symlink():
        raise ProfileError('CONFORMANCE_EVIDENCE_SYMLINK')
    target = root / identity
    target.mkdir(parents=True, exist_ok=True)
    for name, payload in {**files, 'manifest.json': manifest_bytes}.items():
        path = target / name
        if path.is_symlink():
            raise ProfileError('CONFORMANCE_EVIDENCE_SYMLINK', name)
        try:
            with path.open('xb') as handle:
                handle.write(payload)
        except FileExistsError:
            pass
        if path.read_bytes() != payload:
            raise ProfileError('CONFORMANCE_EVIDENCE_DRIFT', name)
    return {'bundle_id': identity, 'path': str(target.resolve())}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input-root', type=Path, help='Build and validate the complete tracked corpus twice.')
    parser.add_argument('--output-root', type=Path, help='Publish immutable constituent evidence.')
    parser.add_argument('--rdf', type=Path)
    parser.add_argument('--coverage', type=Path)
    parser.add_argument('--source-rows', type=Path, help='Independent source census, never derived from coverage rows.')
    parser.add_argument('--comparison-rdf', type=Path, help='Canonical RDF from an independent rebuild.')
    parser.add_argument('--admitted-mappings', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.input_root:
            if any((args.rdf, args.coverage, args.source_rows, args.comparison_rdf, args.admitted_mappings)):
                raise ProfileError('CONFORMANCE_INPUT_MODES_CONFLICT')
            from .corpus import compile_domains, source_census
            built, admitted = compile_domains(args.input_root)
            rebuilt, _ = compile_domains(args.input_root)
            graph, receipt = built.graph, built.receipt
            reference = rebuilt.graph
            rows = source_census(args.input_root)
        else:
            if not all((args.rdf, args.coverage, args.source_rows, args.comparison_rdf)):
                raise ProfileError('CONFORMANCE_ARTIFACT_INPUTS_REQUIRED')
            graph = read_canonical_graph(args.rdf.read_bytes())
            reference = read_canonical_graph(args.comparison_rdf.read_bytes())
            receipt = json.loads(args.coverage.read_text(encoding='utf-8'))
            raw_rows = json.loads(args.source_rows.read_text(encoding='utf-8'))
            rows = tuple(SourceRowIdentity(**row) for row in raw_rows)
            admitted = read_canonical_graph(args.admitted_mappings.read_bytes()) if args.admitted_mappings else ()
        report = validate_artifacts(graph, receipt, rows, reference, admitted_mappings=admitted)
        if args.output_root:
            from .publication import json_bytes
            files = {'canonical.nt': canonicalize(graph).payload,
                     'comparison.nt': canonicalize(reference).payload,
                     'coverage.json': json_bytes(receipt),
                     'source-rows.json': json_bytes([{'domain': r.domain, 'table': r.table, 'key': r.key} for r in rows]),
                     'conformance.json': json_bytes(report)}
            for gate in report['gates']:
                files[gate['gate'] + '.json'] = json_bytes(gate)
            if args.input_root and args.output_root.resolve().is_relative_to(args.input_root.resolve()):
                raise ProfileError('CONFORMANCE_OUTPUT_INSIDE_SOURCE')
            report['evidence'] = write_evidence(files, args.output_root)
    except (OSError, ImportError) as error:
        print(json.dumps({'status': 'infrastructure-failed', 'code': type(error).__name__}, sort_keys=True))
        return 3
    except (ProfileError, ValueError, TypeError) as error:
        print(json.dumps({'status': 'failed', 'code': getattr(error, 'code', 'CONFORMANCE_INPUT_INVALID')}, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    count = sum(g['status'] == 'passed' for g in report['gates'])
    print(f"Semantic conformance: {count}/{len(GATES)} gates passed; {report['status']}; coverage={report['coverage_status']}", file=sys.stderr)
    return 0 if report['status'] == 'complete' else (3 if report['status'] == 'infrastructure-failed' else 2)


if __name__ == '__main__':
    raise SystemExit(main())
