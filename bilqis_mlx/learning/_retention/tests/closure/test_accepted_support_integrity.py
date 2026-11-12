import unittest
from bilqis_mlx.errors import BilqisError
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.capability_support_materialization import _verify_anchor_proofs
from bilqis_mlx.runtime.capability_support_loading import _accepted_materialization


class AcceptedSupportIntegrityTests(unittest.TestCase):
    def test_two_steps_may_use_same_authority(self):
        proof = SimpleNamespace(training_authority_sha256='a'*64, source_release_sha256='b'*64,
            training_batch_sha256='c'*64, target_capability_id='cap', source_family_id='family', episode_id='episode')
        anchor = ('cap', 'row', 'd'*64, 'family', 'episode', 'b'*64, 'c'*64,
                  'e'*64, 'a'*64, (('SOURCE', 'source:one'),))
        proof.step_index = 1
        second = SimpleNamespace(**{**vars(proof), 'step_index': 2})
        student = SimpleNamespace(retained_state=SimpleNamespace(step_proofs=(proof, second)))
        binding = SimpleNamespace(source_anchors=(anchor, anchor))
        self.assertEqual(_verify_anchor_proofs(binding, student, 'cap'), (anchor, anchor))
        bad = list(anchor); bad[3] = 'different'
        with self.assertRaises(BilqisError):
            _verify_anchor_proofs(SimpleNamespace(source_anchors=(anchor, tuple(bad))), student, 'cap')
        swapped = SimpleNamespace(retained_state=SimpleNamespace(step_proofs=(second, proof)))
        with self.assertRaises(BilqisError):
            _verify_anchor_proofs(binding, swapped, 'cap')

    def test_rehashed_anchor_mutation_rejected_against_published_pointer(self):
        import hashlib
        import json
        import tempfile
        from pathlib import Path
        from bilqis_mlx.learning._retention._atlas_acceptance_records import canonical, ACCEPTANCE_SCHEMA
        anchor = ('cap', 'row', 'd'*64, 'family', 'episode', 'b'*64, 'c'*64,
                  'e'*64, 'a'*64, (('SOURCE', 'source:one'),))
        payload = {'run_id':'run', 'generation':1, 'candidate_identity_sha256':'1'*64,
            'parent_candidate_identity_sha256':'2'*64, 'feature_sha256':'3'*64,
            'optimizer_step':1, 'retention_reason':'accepted', 'step_proof_sha256':(),
            'decision_sha256':'4'*64, 'evidence_sha256':'5'*64, 'policy_sha256':'6'*64,
            'source_anchors':(anchor,), 'source_authority_registry_sha256':None,
            'schema_version':ACCEPTANCE_SCHEMA}
        original = hashlib.sha256(canonical(payload)).hexdigest()
        altered_anchor = (*anchor[:-1], (('SOURCE', 'source:altered'),))
        changed = {**payload, 'source_anchors': (altered_anchor,)}
        record = {**changed, 'binding_sha256': hashlib.sha256(canonical(changed)).hexdigest()}
        student = SimpleNamespace(generation=1)
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory)
            (run / 'bamf-acceptance').mkdir()
            (run / 'bamf-acceptance' / f"{'a'*64}.json").write_text(json.dumps(record))
            pointer = {'manifest_sha256': 'a'*64, 'acceptance_sha256': original}
            with patch('bilqis_mlx.runtime.bamf_bundle.publication._pointer_lock') as lock, \
                 patch('bilqis_mlx.runtime.bamf_bundle.publication._read_pointer', return_value=pointer), \
                 patch('bilqis_mlx.runtime.bamf_bundle.publication._live_bundle_manifest'), \
                 patch('bilqis_mlx.runtime.bamf_bundle.codec.load_bamf_bundle', return_value=student):
                lock.return_value.__enter__.return_value = None
                with self.assertRaises(BilqisError) as failure:
                    _accepted_materialization(run, 'a'*64)
                self.assertEqual(failure.exception.context.get("reason"), "BAMF_GENERATION_ACCEPTANCE_DRIFT")
