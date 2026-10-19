"""Append-only MLX growth tests on disposable fixtures, never a real student update."""
from dataclasses import replace
import hashlib
import tempfile
from pathlib import Path
import unittest

import mlx.core as mx
import mlx.optimizers as optim
import numpy as np

from bilqis_mlx.vocabulary_growth import (
    AdmittedToken, ResearchSeed, append_catalog, candidate_examples, digest,
    extend_mlx_student)
from bilqis_mlx.runtime.mlx_checkpoint import save_new_bundle, load_bundle, load_semantically_bound_bundle
from bilqis_mlx.runtime.mlx_parity import forward
from bilqis_mlx.vocabulary_probe import probe


def root_graph():
    nodes=[{'id':id,'family':'legacy','subtype':'primitive','signature':'SemanticSymbol',
            'arity':0,'stage':0,'edges':[]} for id in ('syntax.pad','old.math','old.logic')]
    return {'version':'source-legacy-test/v1','tokens':[r['id'] for r in nodes],
            'nodes':nodes,'row_contract_sha256':{n['id']:digest(n) for n in nodes}}


def admission(token, prereqs=('old.math',)):
    return AdmittedToken(
        token_id=token, semantic_id='fixture:'+token, meaning='Fixture-only bounded meaning',
        source_kind='mathematics',representation='atomic',
        source_locator='fixture:test-math-curriculum',
        source_digest=hashlib.sha256(b'fixture source').hexdigest(),
        lesson_digest=hashlib.sha256(b'fixture teaching').hexdigest(),
        oracle_digest=hashlib.sha256(b'fixture oracle').hexdigest(),
        prerequisite_tokens=prereqs,capability_id='fixture.A',
        admission_receipt=hashlib.sha256(('admission '+token).encode()).hexdigest())


def tiny_optimizer(params,step=116760):
    o=optim.AdamW(learning_rate=.00013,betas=(.9,.95),weight_decay=.01,bias_correction=True)
    o.update(params,{k:mx.ones_like(v)*.01 for k,v in params.items()})
    mx.eval(params,o.state)
    o.state['step']=mx.array(step,dtype=mx.uint64)
    mx.eval(o.state)
    return o


class VocabularyTests(unittest.TestCase):
    def setUp(self):
        mx.set_default_device(mx.cpu)

    def test_research_seeds_do_not_automatically_become_tokens(self):
        roots=candidate_examples()
        self.assertEqual({r.gloss for r in roots},{'enshittification','shibboleth'})
        self.assertTrue(all(r.state=='RESEARCH_SEED_NOT_TAUGHT' for r in roots))
        self.assertTrue(all(r.suggested_representation=='atomic' for r in roots))
        with self.assertRaisesRegex(ValueError,'ADMISSION|RESEARCH'):
            append_catalog(root_graph(),roots)
        with self.assertRaisesRegex(ValueError,'ADMISSION|RESEARCH'):
            append_catalog(root_graph(),tuple())

    def test_growth_preserves_old_graph_and_rejects_duplicate_or_unattested_roots(self):
        prior=root_graph()
        before=digest(prior)
        added, receipt=append_catalog(prior,(admission('candidate.root.first'),
                                               admission('candidate.root.second',('candidate.root.first',))),
                                       allow_disposable_fixtures=True)
        self.assertEqual(digest(prior),before)
        self.assertEqual(added['tokens'][:3],prior['tokens'])
        self.assertEqual(added['tokens'][3:],['candidate.root.first','candidate.root.second'])
        self.assertEqual(receipt['old_token_count'],3)
        self.assertEqual(receipt['new_token_count'],5)
        self.assertFalse(receipt['new_semantics_mastered'])
        for token in prior['tokens']:
            self.assertEqual(added['row_contract_sha256'][token],prior['row_contract_sha256'][token])
        self.assertEqual(append_catalog(prior,(admission('candidate.root.first'),
                                          admission('candidate.root.second',('candidate.root.first',))),
                                        allow_disposable_fixtures=True)[0],added)
        with self.assertRaisesRegex(ValueError,'DUPLICATE'):
            append_catalog(prior,(admission('old.math'),),allow_disposable_fixtures=True)
        with self.assertRaisesRegex(ValueError,'ATTESTED'):
            append_catalog(prior,(replace(admission('candidate.x'),oracle_digest='not-attested'),),
                           allow_disposable_fixtures=True)
        with self.assertRaisesRegex(ValueError,'PREREQUISITE'):
            append_catalog(prior,(admission('candidate.x',('unknown.future.root',)),),
                           allow_disposable_fixtures=True)
        with self.assertRaisesRegex(ValueError,'FIXTURE_CANNOT_ENTER_REAL_CATALOG'):
            append_catalog(prior,(admission('candidate.fixture-not-real'),))

    def test_mlx_model_and_optimizer_expand_without_changing_old_model_inference(self):
        old=root_graph()
        later,receipt=append_catalog(old,(admission('candidate.new-root.one'),
                                          admission('candidate.new-root.two')),
                                     allow_disposable_fixtures=True)
        params={'embedding.weight':mx.array([[0.,0.],[.12,.2],[-.5,.9]],dtype=mx.float32),
                'position.weight':mx.array([[1.,1.],[.1,.2],[.3,.4]],dtype=mx.float32)}
        opt=tiny_optimizer(params)
        frozen={k:np.asarray(v).copy() for k,v in params.items()}
        old_moment={k:{n:np.asarray(x).copy() for n,x in opt.state[k].items()} for k in params}
        grown, grown_opt, evidence=extend_mlx_student(params,opt,old,later)
        self.assertEqual(grown['embedding.weight'].shape,(5,2))
        self.assertEqual(evidence['adamw_step'],116760)
        self.assertEqual(evidence['train_updates'],0)
        self.assertFalse(evidence['new_semantics_mastered'])
        np.testing.assert_array_equal(np.asarray(params['embedding.weight']),frozen['embedding.weight'])
        np.testing.assert_array_equal(np.asarray(grown['embedding.weight'][:3]),frozen['embedding.weight'])
        for k in params:
            for n in ('m','v'):
                np.testing.assert_array_equal(np.asarray(opt.state[k][n]),old_moment[k][n])
                np.testing.assert_array_equal(np.asarray(grown_opt.state[k][n][:params[k].shape[0]]),old_moment[k][n])
        for slot in ('m','v'):
            self.assertFalse(np.asarray(grown_opt.state['embedding.weight'][slot][3:]).any())
        self.assertEqual(int(opt.state['step'].item()),116760)
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'fixture-expanded'
            save_new_bundle(target,grown,grown_opt,
                            source_digest=receipt['expanded_graph_digest'],
                            semantic_catalog=later,reserve_gib=0)
            restored, restored_opt, manifest=load_bundle(target)
            self.assertEqual(restored['embedding.weight'].shape,(5,2))
            self.assertEqual(int(restored_opt.state['step'].item()),116760)
            np.testing.assert_array_equal(np.asarray(restored['embedding.weight'][:3]),frozen['embedding.weight'])
            bound_weights,bound_opt,bound_manifest,bound_catalog=load_semantically_bound_bundle(target)
            self.assertEqual(bound_catalog,later)
            self.assertEqual(bound_manifest['semantic_catalog']['token_count'],5)
            self.assertEqual(bound_weights['embedding.weight'].shape,(5,2))
            with (target/'semantic-catalog.json').open('a',encoding='utf-8') as output:
                output.write(' ')
            with self.assertRaisesRegex(ValueError,'CATALOG_FILE_CHANGED'):
                load_semantically_bound_bundle(target)
        with self.assertRaisesRegex(ValueError,'STRICTLY_APPEND_ONLY'):
            extend_mlx_student(params,opt,old,old)
        corrupted=root_graph()
        corrupted['nodes'][1]['subtype']='changed-meaning'
        corrupted['row_contract_sha256']['old.math']=digest(corrupted['nodes'][1])
        with self.assertRaisesRegex(ValueError,'STRICTLY_APPEND_ONLY'):
            extend_mlx_student(params,opt,old,corrupted)

    def test_synthetic_thousands_of_new_roots_are_not_a_fixed_222_token_limit(self):
        prior=root_graph()
        arrivals=tuple(admission(f'new.math.synthetic-{i:04d}',()) for i in range(3400))
        expanded,receipt=append_catalog(prior,arrivals,allow_disposable_fixtures=True)
        self.assertEqual(len(expanded['tokens']),3403)
        self.assertEqual(receipt['added_token_count'],3400)
        self.assertEqual(expanded['tokens'][:3],prior['tokens'])
        # Source attestations above are synthetic fixture hashes, not real root admissions.

    def test_complete_historical_student_in_memory_growth_is_read_only(self):
        legacy = Path(__file__).resolve().parents[3] / 'vendor' / 'legacy-v16'
        checkpoint = (legacy / 'runs/primitive-consolidation-v16-triplets' /
                      'student-116760-7e9af4651f28.pt')
        if not checkpoint.is_file():
            self.skipTest('Audited checkpoint not mounted')
        result = probe(checkpoint,legacy)
        self.assertEqual(result['original_model_token_count'],222)
        self.assertEqual(result['in_memory_fixture_extended_count'],223)
        self.assertEqual(result['max_old_logit_abs_diff'],0.0)
        self.assertTrue(result['historic_checkpoint_unchanged'])
        self.assertTrue(result['old_adamw_moments_exactly_unchanged'])
        self.assertTrue(result['adamw_step_unchanged'])
        self.assertEqual(result['neural_optimizer_updates'],0)


if __name__=='__main__':
    unittest.main()
