"""Two materializations and one fenced reset of a new release-only graph (#95)."""
from __future__ import annotations

import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import secrets
import uuid

from falkordb import FalkorDB
from redis import Redis
from redis.exceptions import NoPermissionError

from lib.ithkuil.src.ingestion import _bytes, _write_atomic
from lib.ithkuil.src.skos.akasha_skos import AkashaSkosClient
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.falkor_import import Importer, connect
from lib.ithkuil.src.skos.falkor_lookup import Reader, ensure_indexes
from lib.ithkuil.src.skos.falkor_receipt import build_receipt
from lib.ithkuil.src.skos.falkor_smoke import MUTATION, REQUIRED_CASES
from lib.ithkuil.src.skos.rdf_read import read_canonical_graph
from rdflib import Literal, URIRef
from rdflib.namespace import RDF, SKOS
from lib.ithkuil.src.skos.falkor_reset import plan_reset, reset_owned


def comparable_receipt(receipt):
    return {key: value for key, value in receipt.items() if key != 'timestamp'}


def fixture_preflight(graph, suite):
    cases = {case['id']: case for case in suite['queries']}
    if set(cases) != REQUIRED_CASES or len(cases) != len(suite['queries']):
        raise ProfileError('RELEASE95_FIXTURE_CASES_INVALID')
    if any(MUTATION.search(case['cypher']) for case in suite['queries']):
        raise ProfileError('FALKOR_SMOKE_MUTATION_FORBIDDEN')
    for name in ('grammar-code', 'utf8-notation'):
        case = cases[name]
        if not case['expected']:
            raise ProfileError('RELEASE95_LOOKUP_EXPECTATION_EMPTY', name)
        params = case['params']
        literal = Literal(params['lexical'], datatype=URIRef(params['datatype']), normalize=False)
        expected = [[str(s)] for s in sorted(set(graph.subjects(SKOS.notation, literal)), key=str)]
        if expected != case['expected']:
            raise ProfileError('RELEASE95_LOOKUP_NOT_CANONICAL', name)
        if any((URIRef(row[0]), RDF.type, SKOS.Concept) not in graph for row in expected):
            raise ProfileError('RELEASE95_LOOKUP_NOT_CONCEPT', name)
    relation = cases['root-sense-dimensions']
    params = relation['params']
    expected = sorted([[str(s), str(stem), str(spec)]
        for s in graph.objects(URIRef(params['root']), URIRef(params['sense']))
        for stem in graph.objects(s, URIRef(params['stem']))
        for spec in graph.objects(s, URIRef(params['spec']))])
    if not expected or expected != relation['expected']:
        raise ProfileError('RELEASE95_ADMITTED_RELATION_REQUIRED')


def save(path, value):
    _write_atomic(path, _bytes(value))


def journey(importer, receipt, bundle, suite_path, session):
    """Use a graph-scoped RO credential; never record the ephemeral password."""
    import os
    admin = Redis(host=session['host'], port=session['port'],
                  username=os.environ.get('BILQIS_FALKOR_USERNAME'),
                  password=os.environ.get('BILQIS_FALKOR_PASSWORD'))
    user = 'release95_ro_' + uuid.uuid4().hex
    password = secrets.token_urlsafe(32)
    suite = json.loads(suite_path.read_text())
    cases = {item['id']: item for item in suite['queries']}
    before = importer.status()
    try:
        admin.acl_setuser(user, enabled=True, passwords=['+' + password], keys=[importer.name],
                          commands=['+ping', '+info', '+graph.ro_query', '+graph.list', '+client|setinfo'])
        db = FalkorDB(host=session['host'], port=session['port'], username=user, password=password,
                      socket_timeout=15, socket_connect_timeout=5)
        client = AkashaSkosClient(db, importer.name, importer.owner, receipt, bundle, suite_path)
        lookup = cases['grammar-code']
        response = client.read(lookup['params']['lexical'], lookup['params']['datatype'],
                               expected_iri=lookup['expected'][0][0])
        assert response['families'] and response['schemes']
        relation = cases['root-sense-dimensions']
        actual = Reader(client._importer).query(relation['cypher'], relation['params'])
        assert actual == relation['expected'] and actual
        denied = {}
        for name, operation in (
                ('semantic_write', lambda: db.select_graph(importer.name).query('CREATE (:Release95ForbiddenWrite)')),
                ('unrelated_graph', lambda: db.select_graph(importer.name + '_unrelated').ro_query('RETURN 1'))):
            try:
                operation()
            except NoPermissionError:
                denied[name] = 'NoPermissionError'
            else:
                raise AssertionError('RELEASE_READ_ONLY_BOUNDARY_FAILED:' + name)
        try:
            AkashaSkosClient(db, importer.name + '_unrelated', importer.owner, receipt, bundle, suite_path)
        except ProfileError as error:
            assert error.code == 'AKASHA_SKOS_PROJECTION_MISMATCH'
            denied['projection_mismatch'] = error.code
        else:
            raise AssertionError('RELEASE_PROJECTION_FALLBACK')
        result = {'akasha': response, 'admitted_relation': {'source_iri': relation['params']['root'],
                  'predicate_iri': relation['params']['sense'], 'expected': relation['expected'], 'actual': actual},
                  'credential': {'graph_scoped': True, 'read_only': True}, 'denials': denied}
    finally:
        admin.acl_deluser(user)
    assert not admin.acl_getuser(user)
    assert importer.status() == before
    result['credential']['removed_after_proof'] = True
    result['projection_marker_unchanged'] = True
    return result


def prove(session_path: Path, bundle: Path, suite: Path, census_path: Path, output: Path):
    session = json.loads(session_path.read_text())
    census = json.loads(census_path.read_text())
    assert session['graph'].startswith('bilqis_skos_release95_')
    assert session['owner'].startswith('codex_release95_')
    assert census['accounting_complete'] and census['canonical_rdf']['sha256'] == session['canonical_sha256']
    assert hashlib.sha256((bundle / 'canonical.nt').read_bytes()).hexdigest() == session['canonical_sha256']
    assert hashlib.sha256(suite.read_bytes()).hexdigest() == session['suite_sha256']
    assert json.loads(suite.read_text())['canonical_rdf_sha256'] == session['canonical_sha256']
    fixture_preflight(read_canonical_graph((bundle / 'canonical.nt').read_bytes()), json.loads(suite.read_text()))
    db = connect(session['host'], session['port'])
    if session['initial_state'] == 'absent':
        assert session['graph'] not in db.list_graphs(), 'RELEASE95_REQUIRES_NEW_GRAPH'
    elif session['initial_state'] == 'empty':
        previous = Importer(db, session['graph'], session['owner'])
        state = previous.require_owned()
        assert state['state'] == 'empty' and state['digest'] == '' and state['nodes'] == state['edges'] == 0
        assert previous._read('MATCH(n:RdfTerm) WHERE n.owner=$owner RETURN count(n)', {'owner': previous.owner}) == [[0]]
    else:
        raise ProfileError('RELEASE95_EMPTY_PROJECTION_REQUIRED')
    output.mkdir(parents=True, exist_ok=False)
    importer = Importer(db, session['graph'], session['owner'])

    def phase(name):
        save(output / 'state.json', {'phase': name, 'session': session})
        print(name, flush=True)

    phase('FIRST_MATERIALIZATION')
    first_import = importer.materialize(bundle)
    # Foreign data is created only inside this new test graph and stays unrelated.
    importer.graph.query("CREATE (a:Release95Foreign {key:'release95-unrelated-a'}), "
                         "(b:Release95Foreign {key:'release95-unrelated-b'}), "
                         "(a)-[:Release95Foreign {key:'release95-unrelated-edge'}]->(b)")
    ensure_indexes(importer)
    first = build_receipt(importer, bundle, suite)
    save(output / 'first-materialization.json', first)
    phase('FIRST_READ_ONLY_JOURNEY')
    first_read = journey(importer, first, bundle, suite, session)
    save(output / 'first-readback.json', first_read)

    phase('RESET_PREFLIGHT')
    plan = plan_reset(importer)
    save(output / 'reset-plan.json', plan)
    assert plan['graph'] == session['graph'] and plan['owner'] == session['owner']
    assert plan['canonical_sha256'] == session['canonical_sha256'] and not plan['blockers']
    assert (plan['owned_nodes'], plan['owned_edges']) == (first_import['nodes'], first_import['edges'])
    foreign_query = 'MATCH(n:Release95Foreign) RETURN n.key ORDER BY n.key'
    foreign = importer._read(foreign_query)
    assert foreign == [['release95-unrelated-a'], ['release95-unrelated-b']]
    phase('SCOPED_RESET_EXECUTION')
    reset = reset_owned(importer, plan)
    save(output / 'reset-result.json', reset)
    empty = importer.status()
    assert empty['state'] == 'empty' and empty['nodes'] == empty['edges'] == 0
    assert importer._read(foreign_query) == foreign
    assert importer._read('MATCH()-[r:Release95Foreign]->() RETURN r.key') == [['release95-unrelated-edge']]

    phase('SECOND_MATERIALIZATION')
    second_import = importer.materialize(bundle)
    ensure_indexes(importer)
    second = build_receipt(importer, bundle, suite)
    save(output / 'second-materialization.json', second)
    phase('SECOND_READ_ONLY_JOURNEY')
    second_read = journey(importer, second, bundle, suite, session)
    save(output / 'second-readback.json', second_read)
    assert first_import == second_import
    assert comparable_receipt(first) == comparable_receipt(second)
    assert first_read == second_read
    assert importer._read(foreign_query) == foreign
    summary = {key: value for key, value in plan.items() if key not in {'node_keys', 'edge_keys'}}
    summary['plan_sha256'] = hashlib.sha256((output / 'reset-plan.json').read_bytes()).hexdigest()
    result = {'schema': 'bilqis.ithkuil.release95-proof/v1', 'issue': 95, 'status': 'passed',
              'candidate_revision': census['release_revision'], 'authority_boundary': 'IPR-0220; no curriculum admission or neural updates',
              'graph': session['graph'], 'owner': session['owner'], 'initial_state': session['initial_state'],
              'recovery_incident': session.get('recovery_incident'),
              'canonical_rdf': census['canonical_rdf'], 'release_census_sha256': hashlib.sha256(census_path.read_bytes()).hexdigest(),
              'suite_sha256': session['suite_sha256'], 'first_import': first_import, 'second_import': second_import,
              'first_materialization': first, 'second_materialization': second,
              'first_readback': first_read, 'second_readback': second_read,
              'reset_plan': summary, 'reset_result': reset, 'reset_readback': empty,
              'unrelated_foreign_nodes_and_edge_survived': True,
              'equivalence': {'differences': [], 'excluded_materialization_fields': ['timestamp']},
              'dependencies': {name: version(name) for name in ('falkordb', 'redis', 'rdflib', 'pyshacl')},
              'execution': 'Repository code, inference-free validation and orchestration ran locally; only DB protocol traffic crossed the existing SSH tunnel.',
              'limits': ['Semantic coverage remains partial.', 'The two unrelated foreign nodes/edge are deliberate reset fixtures inside the new test namespace.', 'No unrelated graph was reset or deleted; no source/RDF/semantic mutation, training or merge.']}
    save(output / 'proof.json', result)
    phase('COMPLETE')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('session', 'bundle', 'suite', 'census', 'output-root'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prove(args.session, args.bundle, args.suite, args.census, args.output_root)
