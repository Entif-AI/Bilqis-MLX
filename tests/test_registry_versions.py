"""Model-safe semantic registry versioning and external approval boundaries."""
from dataclasses import replace
import copy
import unittest

from bilqis_mlx.registry_versions import (
    ProposedRevision, revision_row, reconcile_live_ledger, review_proposal,
    approved_revision, materialize_approved_mapping, REVIEW_COLUMNS)
from bilqis_mlx.token_atlas import COLUMNS, rows_for_graph
from tests.test_vocabulary_growth import root_graph


class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.graph=root_graph()
        self.rows=[list(COLUMNS)]+rows_for_graph(self.graph)
        self.proposal=ProposedRevision(
            revision_id='TOKEN-RV-0001',parent_version='legacy/v1',token_id=1,
            token_symbol='old.math',legacy_identity='legacy:old.math',
            old_description=self.rows[2][3],
            proposed_description='Source-specified numerical concept pending confirmation',
            proposed_bridge='NI-LX-009',change_kind='PARTIAL_OR_RELATED',
            primary_url='https://ithkuil.net/New_Ithkuil_Lexicon.pdf',
            primary_locus='6.4',reasoning='Related, not proven equal.')

    def test_native_column_reordering_preserves_identity_validation(self):
        order = tuple(reversed(range(len(COLUMNS))))
        native = [[row[i] for i in order] for row in self.rows]
        state = reconcile_live_ledger(self.graph, native, pinned_version='legacy/v1')
        self.assertFalse(state['identity_conflicts'])
        self.assertFalse(state['pending_reviews'])
        native[1][native[0].index('Bilqis token symbol')] = 'swapped'
        self.assertTrue(reconcile_live_ledger(self.graph, native,
            pinned_version='legacy/v1')['identity_conflicts'])

    def test_copyediting_live_ledger_does_not_invalidate_model(self):
        live=copy.deepcopy(self.rows)
        live[2][3]='Improved description'
        live[2][11]='NI-LX-009'
        state=reconcile_live_ledger(self.graph,live,pinned_version='legacy/v1')
        self.assertEqual(state['disposition'],'CONTINUE_PINNED_MODEL')
        self.assertEqual(len(state['pending_reviews']),2)
        self.assertFalse(state['neural_checkpoint_invalidated'])
        self.assertFalse(state['can_promote_new_semantic_version'])

    def test_identity_and_length_conflicts_do_not_mutate_old_student(self):
        altered=copy.deepcopy(self.rows)
        altered[2][2]='evil:new-concept'
        state=reconcile_live_ledger(self.graph,altered,pinned_version='legacy/v1')
        self.assertTrue(state['identity_conflicts'])
        self.assertEqual(state['disposition'],'CONTINUE_PINNED_MODEL_HOLD_NEW_ALLOCATIONS')
        self.assertFalse(state['neural_checkpoint_invalidated'])
        shortened=reconcile_live_ledger(self.graph,self.rows[:-1],pinned_version='legacy/v1')
        self.assertEqual(shortened['missing_or_extra_rows'],1)
        self.assertFalse(shortened['neural_checkpoint_invalidated'])

    def test_staged_proposal_cannot_self_approve(self):
        state=review_proposal(self.proposal,pinned_version='legacy/v1',graph=self.graph)
        self.assertEqual(state['disposition'],'PENDING_HUMAN_REVIEW')
        self.assertEqual(state['neural_updates'],0)
        with self.assertRaisesRegex(ValueError,'NOT_TRACEABLE'):
            review_proposal(replace(self.proposal,old_description='bogus'),
                            pinned_version='legacy/v1',graph=self.graph)
        with self.assertRaisesRegex(ValueError,'NOT_TRACEABLE'):
            review_proposal(replace(self.proposal,disposition='APPROVED'),
                            pinned_version='legacy/v1',graph=self.graph)
        with self.assertRaisesRegex(ValueError,'EVIDENCE_REQUIRED'):
            approved_revision(self.proposal,reviewer='',authority_reference='',
                              next_version='v2',verified_authority_digest='')
        approved=approved_revision(self.proposal,reviewer='human operator',
            authority_reference='https://example.org/verified-human-approval',
            next_version='ledger-v2',verified_authority_digest='a'*64)
        self.assertEqual(approved['disposition'],'APPROVED_COMPATIBLE_ANNOTATION')
        self.assertTrue(approved['old_neural_checkpoint_still_valid'])
        changing=approved_revision(replace(self.proposal,change_kind='MEANING_CHANGE_REQUIRES_RETEACH'),
            reviewer='human operator',authority_reference='https://example.org/verified-human-approval',
            next_version='ledger-v2',verified_authority_digest='a'*64)
        self.assertEqual(changing['disposition'],'APPROVED_NEW_INSTRUCTION_REQUIRED')
        self.assertEqual(changing['pinned_model_version'],'legacy/v1')

    def test_versioned_review_row_preserves_complete_provenance(self):
        self.assertEqual(len(REVIEW_COLUMNS),16)
        row=revision_row(self.proposal)
        self.assertEqual(len(row),16)
        self.assertEqual(row[12],'PROPOSED_REVIEW')
        self.assertEqual(row[13:],["","",""])

    def test_approved_mapping_materializes_edited_ledger_view_without_mutating_old(self):
        approval=approved_revision(self.proposal,reviewer='human operator',
            authority_reference='https://example.org/verified-human-approval',
            next_version='ledger-v2',verified_authority_digest='b'*64)
        base=copy.deepcopy(self.rows)
        new,evidence=materialize_approved_mapping(self.graph,base,self.proposal,approval)
        self.assertEqual(self.rows,base)
        self.assertEqual(new[2][2],base[2][2])
        self.assertEqual(new[2][3],base[2][3])
        self.assertEqual(new[2][11],'NI-LX-009')
        self.assertTrue(evidence['source_graph_unmodified'])
        pinned=reconcile_live_ledger(self.graph,new,pinned_version='legacy/v1',
            approved_annotations={'1':{11:new[2][11],14:new[2][14],15:new[2][15]}})
        self.assertEqual(len(pinned['pending_reviews']),0)
        self.assertFalse(pinned['neural_checkpoint_invalidated'])
        newer=replace(self.proposal,revision_id='TOKEN-RV-0002',
                      parent_version='ledger-v2',
                      proposed_bridge='NI-LX-011')
        next_approval=approved_revision(newer,reviewer='human operator',
            authority_reference='https://example.org/verified-human-approval-two',
            next_version='ledger-v3',verified_authority_digest='c'*64)
        twice,step=materialize_approved_mapping(self.graph,new,newer,next_approval)
        self.assertEqual(twice[2][11],'NI-LX-011')
        self.assertEqual(step['to_version'],'ledger-v3')
        self.assertEqual(twice[2][2],base[2][2])
        bad=approved_revision(replace(self.proposal,change_kind='MEANING_CHANGE_REQUIRES_RETEACH'),
            reviewer='human',authority_reference='https://example.org/verified-human-approval',
            next_version='ledger-v2',verified_authority_digest='b'*64)
        with self.assertRaisesRegex(ValueError,'COMPATIBLE_APPROVAL'):
            materialize_approved_mapping(self.graph,base,self.proposal,bad)


if __name__=='__main__': unittest.main()
