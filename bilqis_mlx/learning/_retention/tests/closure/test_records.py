import copy
import unittest

from bilqis_mlx.learning._retention._atlas_candidate.proofs import CandidateStepProof
from bilqis_mlx.learning._retention._atlas_candidate.common import STEP_PROOF_SCHEMA, CLOSURE_STEP_PROOF_SCHEMA
from bilqis_mlx.learning._retention._atlas_acceptance_records import normalize_artifact_closures, require_closure_proofs
from bilqis_mlx.semantics.cognitive_dependencies import ArtifactKind, ArtifactNode, DependencyKind, DependencyRef
from bilqis_mlx.semantics.dependencies.closure import closure_digest, encode_closure_nodes


class ClosureRecordsTests(unittest.TestCase):
    def test_proof_versions_and_closure_binding(self):
        base = dict(step_index=1, provenance_sha256='1'*64, participation_sha256='2'*64,
                    mask_sha256='3'*64, parameter_names=('p',), loss_bearing=True,
                    source_release_sha256='4'*64, training_batch_sha256='5'*64,
                    target_capability_id='cap', training_authority_sha256='6'*64,
                    source_family_id='family', episode_id='episode')
        old = CandidateStepProof(**base, schema_version=STEP_PROOF_SCHEMA)
        self.assertNotIn('artifact_closure_sha256', old.to_record())
        self.assertEqual(old.digest, '3ffc161b1d2ecb787e954822345e3765b7e35a087ab1a034e1ce8a4491451daf')
        node = ArtifactNode('root', ArtifactKind.SALIENCE_EVIDENCE, '0'*64, True,
                            (DependencyRef(DependencyKind.SOURCE, 'source'),), 2, 3)
        digest = closure_digest((node,))
        proof = CandidateStepProof(**base, artifact_closure_sha256=digest,
                                   schema_version=CLOSURE_STEP_PROOF_SCHEMA)
        self.assertEqual(CandidateStepProof.from_record(proof.to_record()), proof)
        entry = {'step_index': 1, 'training_authority_sha256': '6'*64,
                 'artifact_closure_sha256': digest, 'nodes': encode_closure_nodes((node,))}
        entries = normalize_artifact_closures((entry,))
        anchor = ('cap', 'row', '0'*64, 'family', 'episode', '1'*64, '2'*64, '3'*64, '6'*64, (('ARTIFACT', 'root'),))
        binding = type('Binding', (), {'artifact_closures': entries, 'source_anchors': (anchor,)})()
        require_closure_proofs(binding, (proof,))
        changed = copy.deepcopy(entry)
        changed['training_authority_sha256'] = '7'*64
        binding.artifact_closures = normalize_artifact_closures((changed,))
        with self.assertRaises(Exception):
            require_closure_proofs(binding, (proof,))
        with self.assertRaises(Exception):
            require_closure_proofs(type('Binding', (), {})(), (proof,))

    def test_acceptance_v7_roundtrip_and_proof_validation(self):
        import hashlib
        from bilqis_mlx.learning._retention._atlas_acceptance_records import (
            CLOSURE_ACCEPTANCE_SCHEMA, MOTIF_CLOSURE_ACCEPTANCE_SCHEMA, canonical, parse_accepted_candidate_binding)
        node = ArtifactNode('root', ArtifactKind.SALIENCE_EVIDENCE, '0'*64, True,
                            (DependencyRef(DependencyKind.SOURCE, 'source'),), 2, 3)
        digest = closure_digest((node,))
        proof = CandidateStepProof(step_index=1, provenance_sha256='1'*64,
            participation_sha256='2'*64, mask_sha256='3'*64, parameter_names=('p',),
            loss_bearing=True, source_release_sha256='4'*64, training_batch_sha256='5'*64,
            target_capability_id='cap', training_authority_sha256='6'*64,
            source_family_id='family', episode_id='episode', artifact_closure_sha256=digest,
            schema_version=CLOSURE_STEP_PROOF_SCHEMA)
        anchor = ('cap', 'row', '0'*64, 'family', 'episode', '4'*64, '5'*64,
                  '7'*64, '6'*64, (('ARTIFACT', 'root'),))
        closure = {'step_index': 1, 'training_authority_sha256': '6'*64,
                   'artifact_closure_sha256': digest, 'nodes': encode_closure_nodes((node,))}
        payload = {'run_id':'run', 'generation':1, 'candidate_identity_sha256':'1'*64,
            'parent_candidate_identity_sha256':'2'*64, 'feature_sha256':'3'*64,
            'optimizer_step':1, 'retention_reason':'accepted', 'step_proof_sha256':(proof.digest,),
            'decision_sha256':'4'*64, 'evidence_sha256':'5'*64, 'policy_sha256':'6'*64,
            'source_anchors':(anchor,), 'source_authority_registry_sha256':None,
            'artifact_closures':(closure,), 'schema_version':CLOSURE_ACCEPTANCE_SCHEMA}
        record = {**payload, 'binding_sha256':hashlib.sha256(canonical(payload)).hexdigest()}
        parsed = parse_accepted_candidate_binding(record)
        require_closure_proofs(parsed, (proof,))
        self.assertEqual(parsed.to_record(), record)
        motif_payload = {**payload, 'schema_version': MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
                         'generation_authority_sha256': '9'*64}
        motif_record = {**motif_payload, 'binding_sha256': hashlib.sha256(canonical(motif_payload)).hexdigest()}
        motif = parse_accepted_candidate_binding(motif_record)
        require_closure_proofs(motif, (proof,))
        self.assertEqual(motif.to_record(), motif_record)
        altered = copy.deepcopy(record)
        altered['artifact_closures'][0]['training_authority_sha256'] = '8'*64
        altered['binding_sha256'] = hashlib.sha256(canonical({k:v for k,v in altered.items() if k != 'binding_sha256'})).hexdigest()
        with self.assertRaises(Exception):
            require_closure_proofs(parse_accepted_candidate_binding(altered), (proof,))
