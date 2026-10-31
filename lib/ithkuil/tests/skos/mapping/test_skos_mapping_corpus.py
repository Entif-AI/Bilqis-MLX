from lib.ithkuil.tests.paths import FIXTURES, ITHKUIL_ROOT, REPO_ROOT, TEST_ROOT
from dataclasses import replace
import json
from pathlib import Path
import unittest

from rdflib import Graph, URIRef
from rdflib.namespace import RDF, SKOS

from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.mapping import MappingClaim
from lib.ithkuil.src.skos.mapping_admission import AdmissionRule, load_policy, mapping_key, validate_policy
from lib.ithkuil.src.skos.mapping_corpus import compile_mapping_corpus, compile_mapping_rows
from lib.ithkuil.src.skos.mapping_emit import MappingEmission, ReviewedMappingRow
from lib.ithkuil.src.skos.mapping_reconcile import receipt_bytes, reconcile_mapping_records
from lib.ithkuil.src.skos.mapping_rows import load_mapping_rows, preserve_nonadmitted, source_row


ROOT = ITHKUIL_ROOT/'_data/csv'
BASE = 'https://github.com/Entif-AI/Bilqis-MLX/id/'


class MappingCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = load_mapping_rows(ROOT)
        cls.policy = load_policy()

    def admitted_fixture(self):
        raw = next(row.values for row in self.rows if row.record_kind == 'crosswalk')
        source, target = BASE+'grammar/SYNTHETIC/A', BASE+'grammar/SYNTHETIC/B'
        left, right = BASE+'scheme/synthetic-left', BASE+'scheme/synthetic-right'
        raw.update(crosswalk_id='SYNTHETIC-REVIEWED', target_kind='concept', target_id=target,
                   bilqis_pasigraphy_identity=source, relation_type='exactMatch',
                   equivalence_state='admitted_exact_equivalence', crosswalk_state='admitted_exact_equivalence')
        row = source_row('crosswalk', raw)
        rule = AdmissionRule(mapping_key('crosswalk', raw), 'EMIT_EXACT', None)
        policy = replace(self.policy, rules=self.policy.rules+(rule,))
        validate_policy(policy)
        claim = MappingClaim(source, target, left, right, 'exactMatch', 'admitted_exact_equivalence',
                             row.record_ref.key, 'synthetic:review', True, 'synthetic:proof')
        reviewed = ReviewedMappingRow(row.record_ref, claim)
        graph = Graph()
        for iri, scheme in ((source,left),(target,right)):
            graph.add((URIRef(iri),RDF.type,SKOS.Concept))
            graph.add((URIRef(iri),SKOS.inScheme,URIRef(scheme)))
            graph.add((URIRef(scheme),RDF.type,SKOS.ConceptScheme))
        return row, reviewed, graph, policy

    def test_current_552_row_domain_reconciles_with_exact_dispositions(self):
        result = compile_mapping_corpus(ROOT)
        receipt = result.receipt
        self.assertEqual(receipt['rows'], {'crosswalk':222,'bridge':330,'total':552})
        self.assertEqual(receipt['dispositions'], {'EMITTED':0,'HELD':551,'REJECTED':1,'UNSUPPORTED':0})
        self.assertEqual(receipt['predicate_triples'], {'exactMatch':0,'closeMatch':0,'broadMatch':0,'narrowMatch':0,'relatedMatch':0})
        self.assertEqual(receipt['historical_only_rows'],2)
        self.assertEqual(receipt['conflict_count'],0)
        self.assertEqual(receipt['duplicate_equivalent_assertions'],0)
        self.assertTrue(receipt['accounting_complete'])
        self.assertTrue(receipt['mapping_complete'])
        self.assertTrue(receipt['requires_semantic_review'])
        self.assertEqual(len(result.graph),0)
        self.assertEqual(len({(row['table'],row['key']) for row in receipt['entries']}),552)

    def test_injected_unaccounted_row_fails_with_exact_stable_id(self):
        held = preserve_nonadmitted(self.rows,self.policy)
        with self.assertRaises(ProfileError) as caught:
            reconcile_mapping_records(self.rows,held[1:],MappingEmission(Graph(),(),(),(),()),self.policy)
        self.assertEqual(caught.exception.code,'MAPPING_RECONCILIATION_MISMATCH')
        self.assertIn(held[0].entry.key, '|'.join(caught.exception.details))

    def test_source_reordering_keeps_the_complete_receipt_identical(self):
        forward=compile_mapping_rows(self.rows,policy=self.policy)
        reverse=compile_mapping_rows(reversed(self.rows),policy=self.policy)
        self.assertEqual(receipt_bytes(forward.receipt),receipt_bytes(reverse.receipt))

    def test_admitted_synthetic_row_requires_policy_review_and_actual_endpoints(self):
        row, reviewed, graph, policy=self.admitted_fixture()
        missing=compile_mapping_rows((row,),policy=policy)
        self.assertEqual(missing.receipt['dispositions']['UNSUPPORTED'],1)
        result=compile_mapping_rows((row,),policy=policy,endpoint_graph=graph,reviewed_rows=(reviewed,))
        self.assertEqual(result.receipt['dispositions']['EMITTED'],1)
        self.assertEqual(result.receipt['predicate_triples']['exactMatch'],2)
        self.assertTrue(result.receipt['mapping_complete'])
        self.assertEqual(len(result.graph),2)

    def test_review_does_not_override_a_current_held_source_row(self):
        _,reviewed,graph,_=self.admitted_fixture()
        row=next(row for row in self.rows if row.record_kind=='crosswalk')
        forged=replace(reviewed,record_ref=row.record_ref)
        with self.assertRaises(ProfileError) as caught:
            compile_mapping_rows((row,),policy=self.policy,endpoint_graph=graph,reviewed_rows=(forged,))
        self.assertEqual(caught.exception.code,'MAPPING_REVIEW_CANNOT_OVERRIDE_POLICY')

    def test_source_or_target_review_substitution_is_not_accepted(self):
        row,reviewed,graph,policy=self.admitted_fixture()
        for field,value,code in (
            ('source_ref','unrelated-row','MAPPING_REVIEW_SOURCE_BINDING_MISMATCH'),
            ('target_iri',BASE+'grammar/SYNTHETIC/C','MAPPING_REVIEW_TARGET_BINDING_MISMATCH'),
            ('source_iri',BASE+'grammar/SYNTHETIC/C','MAPPING_REVIEW_SOURCE_ENDPOINT_MISMATCH'),
        ):
            changed=replace(reviewed,claim=replace(reviewed.claim,**{field:value}))
            result=compile_mapping_rows((row,),policy=policy,endpoint_graph=graph,reviewed_rows=(changed,))
            self.assertFalse(result.receipt['mapping_complete'])
            self.assertIn(code,result.receipt['by_reason'])
            self.assertEqual(len(result.graph),0)

    def test_unknown_source_state_blocks_strong_output_without_losing_rows(self):
        row,reviewed,graph,policy=self.admitted_fixture()
        other=next(item for item in self.rows if item.record_kind=='bridge').values
        other['bridge_epistemic_state']='future-unreviewed'
        result=compile_mapping_rows((row,source_row('bridge',other)),policy=policy,
                                    endpoint_graph=graph,reviewed_rows=(reviewed,))
        self.assertEqual(len(result.graph),0)
        self.assertEqual(result.receipt['dispositions']['UNSUPPORTED'],2)
        self.assertTrue(result.receipt['accounting_complete'])
        self.assertFalse(result.receipt['mapping_complete'])


if __name__=='__main__':
    unittest.main()
