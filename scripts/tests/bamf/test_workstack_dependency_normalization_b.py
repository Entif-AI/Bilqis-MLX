"""Focused C01 dependency-normalization evidence regressions."""
from copy import deepcopy
import hashlib
import json
import unittest

from scripts.bamf.workstack_dependencies import check_dependency_evidence, EvidenceStatus
from scripts.tests.bamf.test_workstack_dependencies import packet, pinned_matrix


class DependencyNormalizationTests(unittest.TestCase):
    def test_b02_child_handle_clause_requires_a05_compiler_receipt(self):
            clause = (
                '## Dependency / handoff\n'
                'Consumes B01 parameter/feature authority, actual A05 compiled child handles, and the A05.4 partial-visible-forest contract. '
                'Completion unblocks the neural half of B03.3 #444.\n\n'
                'No source admission, ABI allocation, or durable training is authorized by this issue.'
            )
            args = packet(clause, edges=('B01', 'A05.4'))
            args[2].update({'B01': 346, 'A05.4': 575})
            evidence = args[0]['dependency_evidence']
            for number, is_gating in ((546, True), (592, False)):
                source_id = 'C01.1.pr-' + str(number)
                url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/' + str(number)
                raw = json.dumps(dict(number=number, url=url, state='MERGED',
                    headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
                args[3][source_id] = raw
                evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
                    locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
                if is_gating:
                    evidence['external_receipts'].append(dict(number=number, role='prerequisite',
                        head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
            args[3]['reviewed-packets'] = pinned_matrix(args[0])
            result = check_dependency_evidence(*args)
            self.assertIs(result.status, EvidenceStatus.RESOLVED)
            self.assertEqual(result.known_edges, ('B01', 'A05.4'))

            missing = deepcopy(args)
            missing[0]['dependency_evidence']['external_receipts'] = []
            missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
            self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)

            no_a05_audit = deepcopy(args)
            no_a05_audit[0]['dependency_evidence']['source_records'] = [
                item for item in no_a05_audit[0]['dependency_evidence']['source_records']
                if item['source_id'] != 'C01.1.pr-592'
            ]
            no_a05_audit[3].pop('C01.1.pr-592', None)
            no_a05_audit[3]['reviewed-packets'] = pinned_matrix(no_a05_audit[0])
            self.assertIs(check_dependency_evidence(*no_a05_audit).status, EvidenceStatus.RESOLVED)

            changed = deepcopy(args)
            changed[0]['dependency_evidence']['clause'] = clause.replace(
                'actual A05 compiled child handles', 'A05 child handles')
            changed[3]['reviewed-packets'] = pinned_matrix(changed[0])
            self.assertIs(check_dependency_evidence(*changed).status, EvidenceStatus.INVALID)

    def test_b11_cycle_clause_requires_numerical_selector_and_source_ingress_receipts(self):
            clause = (
                '## Dependency-cycle rule\n'
                'This child is deliberately carved out of B11.1 so it can precede B05 parent acceptance. '
                'It consumes the accepted B01 topology/parameter registry, reviewed B04 attention/block primitives, '
                'and the already-implemented B05 numerical selector contract as a downstream numerical operation. '
                'It **must not depend on B05.4 provenance acceptance** or B13 final generation custody. '
                'Full B11.1 remains responsible for complete model assembly after the surrounding owners are accepted.'
            )
            args = packet(clause, edges=('B01', 'B04', 'A05.5'))
            args[2].update({'B01': 346, 'B04': 350, 'A05.5': 594})
            evidence = args[0]['dependency_evidence']
            for number in (552, 618):
                source_id = 'C01.1.pr-' + str(number)
                url = 'https://github.com/Entif-AI/Bilqis-MLX/pull/' + str(number)
                raw = json.dumps(dict(number=number, url=url, state='MERGED',
                    headRefOid='a'*40, mergeCommit={'oid': 'b'*40})).encode()
                args[3][source_id] = raw
                evidence['source_records'].append(dict(source_id=source_id, kind='pull_request',
                    locator=url, sha256=hashlib.sha256(raw).hexdigest(), excerpt='b'*40))
                evidence['external_receipts'].append(dict(number=number, role='prerequisite',
                    head_sha='a'*40, merge_sha='b'*40, url=url, source_id=source_id))
            amendment_id = 'B11.1a.comment-6505193864'
            amendment_raw = (
                b'Source-owner blocker formalized: new Lane A child #594 (A05.5) owns source-visible SourceAtom -> admitted A01 semantic ABI binding. '
                b'Current A05 atoms carry token/index/reference but no source-attested semantic identity; B03 accepts supplied atom vectors, so #586 cannot truthfully issue an h0 producer receipt. '
                b'Spec committed/pushed in Lane A at `ff2857c207d279526dc0f00c73682e296951fab9`. #590 has an explicit fail-closed bridge; '
                b'#594 must provide real source-positive/rights/prefix proof and reach unified before #586 producer acceptance. B08 no-hit remains separately held. No B05 admission.'
            )
            args[3][amendment_id] = amendment_raw
            evidence['source_records'].append(dict(source_id=amendment_id, kind='comment',
                locator='https://github.com/Entif-AI/Bilqis-MLX/issues/586#issuecomment-6505193864',
                sha256=hashlib.sha256(amendment_raw).hexdigest(), excerpt=amendment_raw.decode()))
            args[3]['reviewed-packets'] = pinned_matrix(args[0])
            result = check_dependency_evidence(*args)
            self.assertIs(result.status, EvidenceStatus.RESOLVED)
            self.assertEqual(result.known_edges, ('B01', 'B04', 'A05.5'))

            for missing_number in (552, 618):
                missing = deepcopy(args)
                missing[0]['dependency_evidence']['external_receipts'] = [
                    item for item in missing[0]['dependency_evidence']['external_receipts']
                    if item['number'] != missing_number
                ]
                missing[3]['reviewed-packets'] = pinned_matrix(missing[0])
                with self.subTest(missing_number=missing_number):
                    self.assertIs(check_dependency_evidence(*missing).status, EvidenceStatus.INVALID)

            missing_amendment = deepcopy(args)
            missing_amendment[0]['dependency_evidence']['source_records'] = [
                item for item in missing_amendment[0]['dependency_evidence']['source_records']
                if item['source_id'] != amendment_id
            ]
            missing_amendment[3].pop(amendment_id, None)
            missing_amendment[3]['reviewed-packets'] = pinned_matrix(missing_amendment[0])
            self.assertIs(check_dependency_evidence(*missing_amendment).status, EvidenceStatus.INVALID)

            relabelled = deepcopy(args)
            forged = b'unrelated comment text relabelled as the amendment'
            relabelled[3][amendment_id] = forged
            amendment_record = next(item for item in relabelled[0]['dependency_evidence']['source_records']
                                    if item['source_id'] == amendment_id)
            amendment_record['sha256'] = hashlib.sha256(forged).hexdigest()
            amendment_record['excerpt'] = forged.decode()
            relabelled[3]['reviewed-packets'] = pinned_matrix(relabelled[0])
            self.assertIs(check_dependency_evidence(*relabelled).status, EvidenceStatus.INVALID)

            changed = deepcopy(args)
            changed[0]['dependency_evidence']['clause'] = clause.replace(
                'already-implemented B05 numerical selector contract',
                'accepted B05.4 selector contract')
            changed[3]['reviewed-packets'] = pinned_matrix(changed[0])
            self.assertIs(check_dependency_evidence(*changed).status, EvidenceStatus.INVALID)

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
