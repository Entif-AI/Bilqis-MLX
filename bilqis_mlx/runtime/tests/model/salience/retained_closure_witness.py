"""Non-authorizing cold proof and correction diagnostic for a real Factory step."""
from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import CandidateStepProof
from bilqis_mlx.learning.tests.test_atlas_salience import _KEY, _OWNER, _REGISTRY
from bilqis_mlx.runtime.atlas_revalidation import CorrectionEvent
from bilqis_mlx.runtime.atlas_revalidation_runtime import apply_correction, read_artifact
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.semantics.cognitive_dependencies import DependencyIndex, DependencyKind
from bilqis_mlx.semantics.dependencies.closure import (
    closure_digest, decode_closure_nodes, encode_closure_nodes,
)


def assert_non_authorizing_closure_witness(testcase, run_dir, parent, result):
    """Cold-read exact executed B09 proof; do not issue or imply C05 acceptance.

    The correction uses the public synthetic fixture key in a fresh in-memory C09
    index. It proves transitive hold semantics without writing the accepted ledger.
    """
    run_dir = Path(run_dir)
    transaction = result.transaction
    testcase.assertEqual(transaction.update_steps, 1)
    testcase.assertEqual(len(transaction.step_proofs), 1)
    testcase.assertEqual(len(transaction.training_authorities), 1)
    authority = transaction.training_authorities[0]
    proof = transaction.step_proofs[0]
    testcase.assertIs(authority, result.gradient_execution.execution.training_authority)
    testcase.assertEqual(proof.step_index, 1)
    testcase.assertEqual(proof.training_authority_sha256, authority.digest)
    testcase.assertEqual(proof.artifact_closure_sha256, authority.artifact_closure_sha256)
    testcase.assertTrue(authority.artifact_nodes)
    testcase.assertEqual(closure_digest(authority.artifact_nodes), proof.artifact_closure_sha256)

    with TemporaryDirectory(prefix='c06-nonauthorizing-', dir=run_dir) as directory:
        path = Path(directory) / 'executed-closure.json'
        payload = {'proof': proof.to_record(), 'nodes': encode_closure_nodes(authority.artifact_nodes)}
        path.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')), encoding='utf-8')
        restored = json.loads(path.read_text(encoding='utf-8'))
        cold_proof = CandidateStepProof.from_record(restored['proof'])
        nodes = decode_closure_nodes(restored['nodes'])
    testcase.assertEqual(cold_proof, proof)
    testcase.assertEqual(nodes, authority.artifact_nodes)
    testcase.assertEqual(closure_digest(nodes), cold_proof.artifact_closure_sha256)
    index = DependencyIndex(nodes)
    roots = tuple(ref.key for ref in authority.immediate_dependencies
                  if ref.kind is DependencyKind.ARTIFACT
                  and ref.key.startswith('salience-labels:'))
    testcase.assertEqual(len(roots), 1)
    root = roots[0]
    index.node(root)
    source_fact = next((ref for node in index.nodes for ref in node.immediate_dependencies
                        if ref.kind is DependencyKind.SOURCE
                        and ref.key.startswith('salience-fact:')), None)
    testcase.assertIsNotNone(source_fact)
    unsigned = CorrectionEvent(
        event_id='fixture:c06-cold-closure-correction', dependency=source_fact,
        source_owner=_OWNER, source_receipt_sha256='f' * 64,
        old_evidence_sha256='a' * 64, new_evidence_sha256='b' * 64,
        source_time=1, effective_time=2, observed_at=3, recorded_at=4,
        reason_code='FIXTURE_SOURCE_CORRECTION', source_signature_hex='0' * 128)
    event = replace(unsigned, source_signature_hex=_KEY.sign(unsigned.signing_bytes()).hex())
    queue = apply_correction(event, index, _REGISTRY)
    testcase.assertTrue(queue.held_artifact_ids)
    testcase.assertNotIn(root, queue.held_artifact_ids)
    with testcase.assertRaises(BilqisError):
        read_artifact(index, queue, root)
    testcase.assertEqual(load_accepted_generation(run_dir).generation, parent.generation)
    return {'status': 'NON_AUTHORIZING_COLD_PROOF', 'proof_sha256': proof.digest,
            'closure_sha256': proof.artifact_closure_sha256,
            'correction_dependency': source_fact.key, 'accepted_generation_unchanged': True}
