"""Focused C01 dependency-normalization evidence regressions."""
from copy import deepcopy
import hashlib
import json
import unittest

from scripts.bamf.workstack_dependencies import check_dependency_evidence, EvidenceStatus
from scripts.tests.bamf.test_workstack_dependencies import packet, pinned_matrix


class DependencyNormalizationTests(unittest.TestCase):
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

    def test_a08_formal_operator_clause_requires_causal_a13_1_receipt(self):
            clause = (
                '**Direct prerequisites:** A08.1a, A07.1, A07.2, A13. '
                'OPEN parent status alone is not a blocker when an exact reviewed branch receipt exists.'
            )
            args = packet(clause, edges=('A08.1a', 'A07.1', 'A07.2', 'A13'))
            args[2].update({'A08.1a': 417, 'A07.1': 413, 'A07.2': 414, 'A13': 369})
            number = 546
            source_id = 'C01.1.pr-546'
            url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/546'
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
            self.assertEqual(result.known_edges, ('A08.1a', 'A07.1', 'A07.2', 'A13'))

            missing = deepcopy(args)
            missing[0]['dependency_evidence']['external_receipts'] = []
            missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
            self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)

            changed = deepcopy(args)
            changed[0]['dependency_evidence']['clause'] = clause.replace('A13.', 'A13.1.')
            changed[3]['reviewed-packets'] = pinned_matrix(changed[0])
            self.assertIs(check_dependency_evidence(*changed).status, EvidenceStatus.INVALID)
