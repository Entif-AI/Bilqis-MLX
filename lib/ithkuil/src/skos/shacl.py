"""Independent SHACL graph validation and explicit mapping-admission check (#71)."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from pyshacl import validate
from rdflib import Graph, Namespace
from rdflib.namespace import DCTERMS, RDF, SKOS

from .canonical import canonicalize
from .errors import ProfileError
from .rdf_read import read_canonical_graph

SHAPES_PATH = Path(__file__).with_name('conformance_shapes.ttl')
SH = Namespace('http://www.w3.org/ns/shacl#')
MAPPING_PREDICATES = frozenset(SKOS[name] for name in (
    'exactMatch', 'closeMatch', 'broadMatch', 'narrowMatch', 'relatedMatch',
))


def validate_graph(graph: Graph, *, admitted_mappings=()) -> dict:
    """Validate a copy without inference or mutation; admission evidence is external.

    RDF cannot prove a row's review state. The caller supplies the exact triples
    emitted by the upstream admitted mapping projector; absence fails closed.
    """
    shapes = Graph().parse(SHAPES_PATH, format='turtle')
    conforms, report, _ = validate(
        graph, shacl_graph=shapes, inference='none', advanced=True,
        inplace=False, allow_infos=False, allow_warnings=False,
    )
    if not isinstance(report, Graph):
        raise ProfileError('SHACL_VALIDATOR_FAILURE', str(report))
    violations = []
    for result in report.subjects(RDF.type, SH.ValidationResult):
        shape = report.value(result, SH.sourceShape)
        # Property shapes inherit their owning named node shape's authority.
        owner = shape
        if not list(shapes.objects(owner, DCTERMS.identifier)):
            owner = next(shapes.subjects(SH.property, shape), shape)
        violations.append({
            'focus_node': str(report.value(result, SH.focusNode)),
            'shape': str(owner),
            'invariant': str(shapes.value(owner, DCTERMS.identifier)),
            'owners': sorted(map(str, shapes.objects(owner, DCTERMS.source))),
            'path': str(report.value(result, SH.resultPath) or ''),
            'message': sorted(map(str, report.objects(result, SH.resultMessage))),
        })
    admitted = set(admitted_mappings)
    for subject, predicate, target in graph:
        if predicate in MAPPING_PREDICATES and (subject, predicate, target) not in admitted:
            violations.append({
                'focus_node': str(subject),
                'shape': 'https://github.com/Entif-AI/Bilqis-MLX/validation/shape/MappingAdmission',
                'invariant': 'MappingAdmission',
                'owners': ['https://github.com/Entif-AI/Bilqis-MLX/issues/63',
                           'https://github.com/Entif-AI/Bilqis-MLX/issues/66'],
                'path': str(predicate), 'message': ['Mapping triple lacks upstream admitted support.'],
            })
    canonical = canonicalize(graph)
    return {
        'schema': 'bilqis.skos.shacl-report/v1',
        'conforms': bool(conforms and not violations),
        'canonical_sha256': canonical.sha256,
        'shapes_sha256': hashlib.sha256(SHAPES_PATH.read_bytes()).hexdigest(),
        'triple_count': canonical.triple_count,
        'violations': sorted(violations, key=lambda value: json.dumps(value, sort_keys=True)),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rdf', type=Path, required=True, help='Canonical N-Triples input.')
    parser.add_argument('--admitted-mappings', type=Path, help='Canonical triples from upstream admitted mapping output.')
    args = parser.parse_args(argv)
    try:
        graph = read_canonical_graph(args.rdf.read_bytes())
        admitted = read_canonical_graph(args.admitted_mappings.read_bytes()) if args.admitted_mappings else ()
        report = validate_graph(graph, admitted_mappings=admitted)
    except (ProfileError, OSError) as error:
        print(json.dumps({'status': 'failed', 'code': getattr(error, 'code', 'SHACL_IO_ERROR')}, sort_keys=True))
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0 if report['conforms'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
