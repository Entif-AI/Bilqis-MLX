"""One-to-one pasigraphy accounting; no actual Bilqis optimizer updates."""
import copy
from dataclasses import replace
from pathlib import Path
import unittest

from bilqis_mlx.token_atlas import (
    COLUMNS, REGISTRY_SHEET, identity, read_historic_graph,
    role, rows_for_graph, validate_one_to_one, verify_sheet_rows)
from bilqis_mlx.vocabulary_growth import append_catalog, digest
from bilqis_mlx.registry_versions import reconcile_live_ledger
from tests.test_vocabulary_growth import admission, root_graph


class TokenAtlasTests(unittest.TestCase):
    def test_legacy_full_student_has_222_unique_catalog_identities(self):
        root=Path(__file__).resolve().parents[2]/'bilqis-triplets-v16'
        checkpoint=(root/'runs/primitive-consolidation-v16-triplets'/
                    'student-116760-7e9af4651f28.pt')
        if not checkpoint.is_file():
            self.skipTest('Historical checkpoint not mounted')
        graph=read_historic_graph(checkpoint)
        ledger=rows_for_graph(graph)
        self.assertEqual(len(ledger),222)
        self.assertEqual(len({r[1] for r in ledger}),222)
        self.assertEqual(len({r[2] for r in ledger}),222)
        self.assertEqual(ledger[0][1:3],['syntax.pad','legacy:syntax.pad'])
        self.assertEqual(ledger[-1][1:3],['school.number.100','legacy:school.number.100'])
        self.assertIn('exact integer 100',ledger[-1][3])
        self.assertEqual(ledger[-1][14],'LEGACY_MEANING_NEEDS_HUMAN_REVIEW')
        self.assertEqual({r[11] for r in ledger},{'UNMAPPED_TO_NI_NOT_ASSERTED'})
        self.assertEqual({r[13] for r in ledger},{'NO_SAME_CHECKPOINT_TOKEN_MASTERY_PROOF'})
        receipt=verify_sheet_rows(graph,[list(COLUMNS)]+ledger)
        self.assertEqual(receipt['mapped_tokens'],222)
        self.assertEqual(receipt['registry_sheet'],REGISTRY_SHEET)
        self.assertFalse(receipt['ni_compliance_claimed'])
        self.assertFalse(receipt['new_token_learning_claimed'])

    def test_registry_projection_is_exact_and_fails_on_missing_reordered_or_changed(self):
        graph=root_graph()
        expected=[list(COLUMNS)]+rows_for_graph(graph)
        verify_sheet_rows(graph,expected)
        with self.assertRaisesRegex(ValueError,'TOKEN_COUNT_MISMATCH'):
            verify_sheet_rows(graph,expected[:-1])
        reversed_rows=copy.deepcopy(expected)
        reversed_rows[1],reversed_rows[2]=reversed_rows[2],reversed_rows[1]
        with self.assertRaisesRegex(ValueError,'ROW_DRIFT'):
            verify_sheet_rows(graph,reversed_rows)
        wrong_semantics=copy.deepcopy(expected)
        wrong_semantics[1][3]='untraceable generic opaque meaning'
        with self.assertRaisesRegex(ValueError,'ROW_DRIFT'):
            verify_sheet_rows(graph,wrong_semantics)
        with self.assertRaisesRegex(ValueError,'HEADER_DRIFT'):
            verify_sheet_rows(graph,[['wrong header']]+expected[1:])

    def test_duplicate_meaning_id_and_uninterpretable_new_token_rejected(self):
        graph=root_graph()
        one=admission('new.test-one',())
        two=replace(admission('new.test-two',()),semantic_id=one.semantic_id)
        with self.assertRaisesRegex(ValueError,'SEMANTIC_IDENTITY_ALREADY_ASSIGNED'):
            append_catalog(graph,(one,two),allow_disposable_fixtures=True)
        bad=copy.deepcopy(graph)
        bad['nodes'][1]['semantic_id']='legacy:syntax.pad'
        bad['nodes'][1]['meaning']='same meaning claimed by two IDs'
        bad['nodes'][1]['source']='fixture:source'
        bad['nodes'][1]['admission_receipt']='fixture:receipt'
        bad['row_contract_sha256']['old.math']=digest(bad['nodes'][1])
        with self.assertRaisesRegex(ValueError,'DUPLICATE_SEMANTIC_IDENTITY'):
            validate_one_to_one(bad)
        unsupported=copy.deepcopy(graph)
        unsupported['nodes'][1]['signature']=''
        unsupported['row_contract_sha256']['old.math']=digest(unsupported['nodes'][1])
        with self.assertRaisesRegex(ValueError,'UNINTERPRETABLE_TOKEN'):
            validate_one_to_one(unsupported)

    def test_real_allocation_is_blocked_without_exact_spreadsheet_ledger(self):
        graph=root_graph()
        # Synthetic-only certification strings exercise the software gate;
        # this fixture cannot constitute a real instructional admission.
        candidate=replace(admission('candidate.next-concept',()),
                          semantic_id='test:formal-semantics',
                          source_locator='https://example.org/test-only')
        with self.assertRaisesRegex(ValueError,'REGISTRY_READBACK_REQUIRED'):
            append_catalog(graph,(candidate,))
        fixture_graph,_=append_catalog(graph,(candidate,),allow_disposable_fixtures=True)
        rows=[list(COLUMNS)]+rows_for_graph(fixture_graph)
        changed=copy.deepcopy(rows)
        changed[-1][2]='test:silent-relabel'
        with self.assertRaisesRegex(ValueError,'IDENTITY_CONFLICT'):
            append_catalog(graph,(candidate,),canonical_registry_rows=changed)
        admitted,_=append_catalog(graph,(candidate,),canonical_registry_rows=rows,
                                  approved_ledger_version='v1-approved-fixture',
                                  approved_admissions=(candidate.admission_receipt,))
        self.assertEqual(admitted,fixture_graph)
        change=reconcile_live_ledger(fixture_graph,changed,
                                     pinned_version='v1-approved-fixture')
        self.assertEqual(change['disposition'],'CONTINUE_PINNED_MODEL_HOLD_NEW_ALLOCATIONS')
        self.assertEqual(change['conflict_token_ids'],(3,))
        editorial=copy.deepcopy(rows)
        editorial[-1][3]='Reviewed meaning wording change'
        revised=reconcile_live_ledger(fixture_graph,editorial,
                                      pinned_version='v1-approved-fixture')
        self.assertEqual(revised['disposition'],'CONTINUE_PINNED_MODEL')
        self.assertEqual(len(revised['pending_reviews']),1)
        updated,_=append_catalog(graph,(candidate,),canonical_registry_rows=editorial,
                                 approved_ledger_version='v1-approved-fixture',
                                 approved_admissions=(candidate.admission_receipt,))
        self.assertEqual(updated,fixture_graph)


if __name__=='__main__':
    unittest.main()
