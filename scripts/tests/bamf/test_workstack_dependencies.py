"""Source evidence cannot manufacture a complete or runnable dependency graph."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

from scripts.bamf.workstack_dependencies import check_dependency_evidence, EvidenceStatus, load_dependency_sources
from scripts.check_bamf_workstack import validate_workstack


def pinned_matrix(entry):
    reviewed = {key: deepcopy(entry[key]) for key in (
        'key', 'number', 'parent_key', 'parent_number', 'dependency_evidence')}
    return json.dumps(dict(schema='bilqis.bamf.registry-expansion-review/v1',
                           packets=[reviewed])).encode()


def packet(body='**Direct prerequisites:** A01. OPEN parent status alone is not a blocker.',
           edges=('A01',), resolution='resolved', unresolved=None):
    raw = body.encode()
    digest = hashlib.sha256(raw).hexdigest()
    evidence = dict(schema='bilqis.bamf.dependency-evidence/v1', resolution=resolution,
        body_sha256=digest, clause=body, known_edges=list(edges), external_receipts=[],
        source_records=[dict(source_id='C01.1.body', kind='body', locator='issue #486',
                             sha256=digest, excerpt=body)], obligations=[], unresolved=unresolved)
    entry = dict(key='C01.1', number=486, parent_key='C01', parent_number=347,
                 deps=list(edges), body_sha256=digest, dependency_evidence=evidence)
    sources = {'C01.1.body': raw, 'reviewed-packets': pinned_matrix(entry)}
    return entry, raw, {'C01': 347, 'C01.1': 486, 'A01': 345}, sources


class DependencyEvidenceTests(unittest.TestCase):
    def test_literal_list_resolves_only_the_declared_issue_edge(self):
        args = packet()
        result = check_dependency_evidence(*args)
        self.assertIs(result.status, EvidenceStatus.RESOLVED)
        self.assertEqual(result.known_edges, ('A01',))

    def test_range_resolves_each_known_same_parent_key(self):
        args = packet('**Direct prerequisites:** A01.1 through A01.3. OPEN parent status alone is not a blocker.',
                      edges=('A01.1', 'A01.2', 'A01.3'))
        args[2].update({'A01.1': 500, 'A01.2': 501, 'A01.3': 502})
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.RESOLVED)

    def test_b13_genesis_direct_prerequisites_require_the_exact_reviewed_clause(self):
        clause = (
            '## Direct prerequisites\n\n'
            '- B13.1 #478 immutable bundle/pointer custody interface.\n'
            '- B13.4 #481 / B01 parameter-schema and initializer authority.\n\n'
            'Open parent state alone is not a blocker when the required exact interface is already present '
            'on reviewed unified; final turn-in must record the actual consumed receipts.'
        )
        args = packet(clause, edges=('B13.1', 'B13.4'))
        args[2].update({'B13.1': 478, 'B13.4': 481, 'B01': 346})
        evidence = args[0]['dependency_evidence']
        for number in (885, 802):
            source_id = 'C01.1.pr-' + str(number)
            url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/' + str(number)
            raw = json.dumps(dict(number=number, url=url, state='MERGED',
                headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
            args[3][source_id] = raw
            evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
                locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
            evidence['external_receipts'].append(dict(number=number, role='prerequisite',
                head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.RESOLVED)
        missing = deepcopy(args)
        missing[0]['dependency_evidence']['external_receipts'] = []
        missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
        self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)
        variants = (
            clause.replace('#481', '#999'),
            clause.replace(
                '- B13.1 #478 immutable bundle/pointer custody interface.',
                '- B13.1 #478 and B13.4 #481 are both direct prerequisites.',
            ),
            clause.replace(
                '- B13.1 #478 immutable bundle/pointer custody interface.',
                '- B13.1 #478 is not a prerequisite.',
            ),
            clause.replace(
                '- B13.4 #481 / B01 parameter-schema and initializer authority.',
                '- B13.4 #481 / B01 parameter-schema and initializer authority.\n\n- B01 #346 extra prerequisite.',
            ),
        )
        for forged_clause in variants:
            with self.subTest(forged_clause=forged_clause):
                forged = packet(forged_clause, edges=('B13.1', 'B13.4'))
                forged[2].update({'B13.1': 478, 'B13.4': 481, 'B01': 346})
                self.assertIs(check_dependency_evidence(*forged).status, EvidenceStatus.INVALID)

    def test_a03_released_schema_clause_requires_the_accepted_serialization_receipt(self):
        clause = (
            '## Dependency / handoff\n'
            'Consumes A01 release identity and accepted A03/A04 schema serialization. '
            'B07.1 #456 must consume this witness together with the existing source-owned A13 grant machinery; '
            'B08.1 #460 must additionally bind complete rights/revocation/generation dependencies into its cache/read identity.\n\n'
            'No neural/source admission or training is authorized by this issue.'
        )
        args = packet(clause, edges=('A01',))
        number = 551
        source_id = 'C01.1.pr-551'
        url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/551'
        raw = json.dumps(dict(number=number, url=url, state='MERGED',
            headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
        evidence = args[0]['dependency_evidence']
        args[3][source_id] = raw
        evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
            locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
        evidence['external_receipts'].append(dict(number=number, role='prerequisite',
            head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        result = check_dependency_evidence(*args)
        self.assertIs(result.status, EvidenceStatus.RESOLVED)
        self.assertEqual(result.known_edges, ('A01',))

        missing = deepcopy(args)
        missing[0]['dependency_evidence']['external_receipts'] = []
        missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
        self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)

        changed = deepcopy(args)
        changed[0]['dependency_evidence']['clause'] = clause.replace(
            'accepted A03/A04 schema serialization', 'accepted A03/A04 schema serialization plus A13')
        changed[3]['reviewed-packets'] = pinned_matrix(changed[0])
        self.assertIs(check_dependency_evidence(*changed).status, EvidenceStatus.INVALID)

    def test_a05_partial_forest_requires_code_receipt_and_keeps_parent_audit_nongating(self):
        clause = (
            '## Dependency / handoff\n'
            'Consumes accepted A03/A04/A13 and current A05 compiler receipts. '
            'On completion, B03.3 #444 must rerun its child-only future-isolation and nested-gradient proof against this exact source contract.\n\n'
            'No live learner or durable optimizer start is authorized by this issue.'
        )
        args = packet(clause, edges=('A03', 'A04', 'A13'))
        args[2].update({'A03': 349, 'A04': 351, 'A13': 369})
        evidence = args[0]['dependency_evidence']
        for number in (546, 571):
            source_id = 'C01.1.pr-' + str(number)
            url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/' + str(number)
            raw = json.dumps(dict(number=number, url=url, state='MERGED',
                headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
            args[3][source_id] = raw
            evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
                locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
            if number == 546:
                evidence['external_receipts'].append(dict(number=number, role='prerequisite',
                    head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        result = check_dependency_evidence(*args)
        self.assertIs(result.status, EvidenceStatus.RESOLVED)
        self.assertEqual(result.known_edges, ('A03', 'A04', 'A13'))

        missing = deepcopy(args)
        missing[0]['dependency_evidence']['external_receipts'] = []
        missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
        self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)

        audit_only = deepcopy(args)
        audit_only[0]['dependency_evidence']['source_records'] = [
            item for item in audit_only[0]['dependency_evidence']['source_records']
            if item['source_id'] != 'C01.1.pr-571'
        ]
        audit_only[3].pop('C01.1.pr-571', None)
        audit_only[3]['reviewed-packets'] = pinned_matrix(audit_only[0])
        self.assertIs(check_dependency_evidence(*audit_only).status, EvidenceStatus.RESOLVED)

        changed = deepcopy(args)
        changed[0]['dependency_evidence']['clause'] = clause.replace(
            'current A05 compiler receipts', 'current A05 compiler receipt')
        changed[3]['reviewed-packets'] = pinned_matrix(changed[0])
        self.assertIs(check_dependency_evidence(*changed).status, EvidenceStatus.INVALID)

    def test_unknown_edge_or_missing_range_member_is_invalid(self):
        args = packet(edges=('A99',))
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)
        args = packet('**Direct prerequisites:** A01.1 through A01.3.',
                      edges=('A01.1', 'A01.3'))
        args[2].update({'A01.1': 500, 'A01.3': 502})
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_held_empty_edges_do_not_assert_absent_prerequisites(self):
        args = packet('Preserve source requirements; no direct list.', edges=(),
                      resolution='held', unresolved='No direct list was established.')
        result = check_dependency_evidence(*args)
        self.assertIs(result.status, EvidenceStatus.HELD)
        self.assertEqual(result.reason, 'No direct list was established.')

    def test_entry_cannot_promote_a_pinned_hold_or_remove_source_evidence(self):
        args = packet(resolution='held', unresolved='Named source receipt remains unresolved.')
        args[0]['dependency_evidence']['resolution'] = 'resolved'
        args[0]['dependency_evidence']['unresolved'] = None
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)
        args = packet()
        args[0]['dependency_evidence']['source_records'] = []
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_source_bytes_and_body_must_match_the_pinned_hash(self):
        args = packet()
        args[3]['C01.1.body'] += b' changed'
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)
        args = packet()
        self.assertIs(check_dependency_evidence(args[0], b'changed body', args[2], args[3]).status,
                      EvidenceStatus.INVALID)

    def test_entry_issue_and_parent_identity_must_match_reviewed_packet(self):
        args = packet()
        args[0]['number'] = 636
        args[2]['C01.1'] = 636
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)
        args = packet()
        args[0]['parent_number'] = 999
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_resolved_prose_without_supported_explicit_clause_is_invalid(self):
        args = packet('A01 is mentioned as context, not a direct prerequisite.')
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_prerequisite_pull_requests_remain_receipts_instead_of_issue_nodes(self):
        args = packet('Direct prerequisites: merged #619/#623; exact qualified #633/#634 receipts for final composition turn-in; existing B02/B03 source interfaces.',
                      edges=('B02', 'B03'))
        args[2].update(B02=359, B03=363)
        evidence = args[0]['dependency_evidence']
        for number in (619, 623, 633, 634):
            source_id = 'C01.1.pr-' + str(number)
            url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/' + str(number)
            raw = json.dumps(dict(number=number, url=url, state='MERGED',
                headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
            args[3][source_id] = raw
            evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
                locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
            evidence['external_receipts'].append(dict(number=number, role='prerequisite',
                head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        result = check_dependency_evidence(*args)
        self.assertIs(result.status, EvidenceStatus.RESOLVED)
        self.assertEqual(result.known_edges, ('B02', 'B03'))
        evidence['external_receipts'][0]['merge_sha'] = 'c'*40
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_implementation_receipt_is_validated_without_becoming_a_clause_prerequisite(self):
        args = packet()
        evidence = args[0]['dependency_evidence']
        number = 885
        source_id = 'C01.1.pr-885'
        url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/885'
        raw_obj = dict(number=number, url=url, state='MERGED',
            headRefOid='a'*40, mergeCommit={'oid': 'b'*40})
        raw = json.dumps(raw_obj).encode()
        args[3][source_id] = raw
        record = dict(source_id=source_id, kind='pull_request', locator=url,
            sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40)
        evidence['source_records'].append(record)
        evidence['external_receipts'].append(dict(number=number, role='implementation',
            head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.RESOLVED)

        raw_obj['state'] = 'OPEN'
        raw = json.dumps(raw_obj).encode()
        args[3][source_id] = raw
        record['sha256'] = hashlib.sha256(raw).hexdigest()
        args[3]['reviewed-packets'] = pinned_matrix(args[0])
        self.assertIs(check_dependency_evidence(*args).status, EvidenceStatus.INVALID)

    def test_loader_refuses_symlink_snapshots_and_ignores_arbitrary_locators(self):
        entry, body, numbers, sources = packet()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'dependency-evidence'
            (root / 'sources').mkdir(parents=True)
            (root / 'reviewed-packets.json').write_bytes(sources['reviewed-packets'])
            target = Path(tmp) / 'outside.txt'
            target.write_bytes(b'not an evidence source')
            (root / 'sources/C01.1.body.txt').symlink_to(target)
            loaded = load_dependency_sources(Path(tmp), {'entries': [entry]})
            self.assertNotIn('C01.1.body', loaded)
            self.assertNotIn(b'not an evidence source', loaded.values())
            self.assertIs(check_dependency_evidence(entry, body, numbers, loaded).status,
                          EvidenceStatus.INVALID)
            entry['dependency_evidence']['source_records'][0]['source_id'] = '../../outside'
            loaded = load_dependency_sources(Path(tmp), {'entries': [entry]})
            self.assertNotIn('../../outside', loaded)
            self.assertEqual(target.read_bytes(), b'not an evidence source')

    def test_held_contract_clears_the_entire_execution_order(self):
        entry, body, numbers, sources = packet('No direct list.', edges=(),
            resolution='held', unresolved='Receipt granularity is unresolved.')
        owner = dict(key='C01', number=347, lane='C', deps=[], paths=[], body_sha256='a'*64)
        report = validate_workstack(dict(schema='bilqis.bamf.workstack/v1', version='0.2.0',
            items=[owner], shared_file_queues=[]),
            dict(schema='bilqis.bamf.all-child-registry/v1', entries=[entry]),
            {'C01': 347, 'C01.1': 486}, {'C01.1': body}, evidence_sources=sources)
        self.assertEqual(report['status'], 'held')
        self.assertEqual(report['order'], [])
        self.assertEqual(report['registry_integrity'], 'valid')
        self.assertEqual(report['dependency_resolution'],
                         {'status': 'held', 'held_keys': ['C01.1']})

    def test_loader_rejects_dangling_matrix_link_without_entry_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'dependency-evidence'
            root.mkdir()
            (root / 'reviewed-packets.json').symlink_to(Path(tmp) / 'absent')
            with self.assertRaisesRegex(ValueError, 'regular local tree'):
                load_dependency_sources(Path(tmp), {'entries': []})

    def test_registry_cannot_remove_entry_evidence_or_a_pinned_child(self):
        entry, body, numbers, sources = packet(
            '## Direct prerequisites\n[A01 #345](https://github.com/Entif-AI/Bilqis-MLX/issues/345)',
            resolution='held', unresolved='An additional source obligation remains.')
        owners = [dict(key=key, number=number, lane=key[0], deps=[], paths=[], body_sha256='a'*64)
                  for key, number in [('C01', 347), ('A01', 345)]]
        del entry['dependency_evidence']
        for entries in ([entry], []):
            with self.subTest(entries=len(entries)):
                present = {'C01': 347, 'A01': 345}
                if entries:
                    present['C01.1'] = 486
                report = validate_workstack(dict(schema='bilqis.bamf.workstack/v1', version='0.2.0',
                    items=owners, shared_file_queues=[]),
                    dict(schema='bilqis.bamf.all-child-registry/v1', entries=entries),
                    present, {'C01.1': body}, evidence_sources=sources)
                self.assertEqual(report['status'], 'invalid')

    def test_actual_expanded_registry_has_integrity_but_no_runnable_order(self):
        root = Path(__file__).resolve().parents[3] / 'docs/tasks/bamf-0.2'
        manifest = json.loads((root / 'workstack.json').read_text())
        registry = json.loads((root / 'children/registry.json').read_text())
        numbers = json.loads((root / 'issue-map.json').read_text())
        mirrors = {e['key']: (root / 'children' / (e['key'] + '.md')).read_bytes()
                   for e in registry['entries']}
        report = validate_workstack(manifest, registry, numbers, mirrors,
            evidence_sources=load_dependency_sources(root, registry))
        self.assertEqual(report['child_count'], len(registry['entries']))
        self.assertEqual(report['registry_integrity'], 'valid')
        self.assertEqual(report['status'], 'held')
        self.assertEqual(report['order'], [])
        self.assertEqual(
            report['dependency_resolution']['held_keys'],
            sorted(
                entry['key'] for entry in registry['entries']
                if entry.get('dependency_evidence', {}).get('resolution') == 'held'
            ),
        )
        self.assertEqual(numbers['C14.3'], 535)
        self.assertNotIn('C14.4', numbers)
        self.assertEqual(numbers['B10.5'], 635)
        self.assertNotIn(587, numbers.values())
        self.assertNotIn(636, numbers.values())
        parent = next(e for e in registry['entries'] if e['key'] == 'B11.1')
        self.assertEqual(parent['kind'], 'leaf')
        self.assertIn('B11.1a', parent['deps'])

    def test_real_cli_exits_nonzero_for_held_registry(self):
        root = Path(__file__).resolve().parents[3]
        result = subprocess.run([sys.executable, '-B', str(root / 'scripts/check_bamf_workstack.py'),
            str(root / 'docs/tasks/bamf-0.2/workstack.json')],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'held')
        self.assertEqual(json.loads(result.stdout)['order'], [])
