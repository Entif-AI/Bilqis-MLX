"""Real C05 acceptance and B13/C09 cold support for a disposable C06 step."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import time

from bilqis_mlx import state_dag
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.learning.atlas_retention_decision import issue_factory_retention_decision
from bilqis_mlx.learning.tests.test_atlas_salience import _KEY, _OWNER
from bilqis_mlx.runtime.accepted_corrections import (
    AcceptedRuntimeHost, _reset_accepted_correction_runtime_for_tests,
)
from bilqis_mlx.runtime.atlas_capability_support_owner import load_capability_support_owner
from bilqis_mlx.runtime.atlas_revalidation import CorrectionEvent
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, bind_accepted_execution_cache, derive_motif_successor_bundle,
    derive_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.factory_retention_owner import evaluate_factory_retention_candidate
from bilqis_mlx.runtime.tests.capability.factory.retention.owner_live_support import _fixed_school
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


def assert_retained_publication_witness(
        testcase, run_dir, source_context, parent, result, artifact_path, capability):
    """Run the production fixed-school gate; publish only its real accepted result.

    The run directory must be disposable and remain alive throughout this witness.
    A rejection is a test failure with the owner's exact reason, not a skipped gate.
    """
    run_dir = Path(run_dir)
    transaction = result.transaction
    testcase.assertEqual(transaction.update_steps, 1)
    authority = transaction.training_authorities[0]
    proof = transaction.step_proofs[0]
    testcase.assertTrue(authority.artifact_nodes)
    testcase.assertEqual(proof.training_authority_sha256, authority.digest)
    testcase.assertEqual(proof.artifact_closure_sha256, authority.artifact_closure_sha256)
    cache = bind_accepted_execution_cache(run_dir)
    testcase.assertEqual(cache.generation, parent.generation)

    started = time.monotonic()
    print('C06_RETENTION fixed_school_started', flush=True)
    fixed = _fixed_school(run_dir, source_context, cache.accepted_manifest_sha256)
    state_dag.persist(run_dir, {
        'generation': parent.generation,
        'factory_release_sha256': source_context.release.release_sha256,
        'last_exam': fixed,
    })
    print('C06_RETENTION owner_screen_started', flush=True)
    evaluation = evaluate_factory_retention_candidate(
        source_context, transaction, str(artifact_path), capability, run_dir=run_dir)
    decision = issue_factory_retention_decision(evaluation)
    if not decision.accepted:
        raise AssertionError(
            'C06 Factory C05 rejected labeled candidate: '
            f'reason={decision.reason}; evidence={decision.evidence_sha256}; '
            f'policy={decision.policy_sha256}; '
            f'blocking_capability={evaluation.decision.blocking_capability}')

    retained = resolve_candidate(transaction, accepted=True)
    events = ({'event': 'BAMF_GENERATION_ACCEPTED',
               'optimizer_step': retained.optimizer_step},)
    if transaction.motif_transition is None:
        successor = derive_successor_bundle(
            parent, retained, parent_manifest_sha256=cache.accepted_manifest_sha256,
            delivery_events=events)
        expected_schema = 'bilqis.mlx.accepted-candidate-binding/v7'
    else:
        successor = derive_motif_successor_bundle(
            parent, transaction, parent_manifest_sha256=cache.accepted_manifest_sha256,
            delivery_events=events)
        expected_schema = 'bilqis.mlx.accepted-candidate-binding/v8'
    published = accept_and_publish(
        run_dir, successor, retained, decision=decision,
        feature_sha256=successor.extents.factor_map_digest,
        training_authorities=transaction.training_authorities, reserve_gib=0.0)
    acceptance_path = run_dir / 'bamf-acceptance' / f"{published['manifest_sha256']}.json"
    acceptance = json.loads(acceptance_path.read_text(encoding='utf-8'))
    testcase.assertEqual(acceptance['schema_version'], expected_schema)
    testcase.assertEqual(acceptance['artifact_closures'][0]['artifact_closure_sha256'],
                         proof.artifact_closure_sha256)
    testcase.assertEqual(acceptance['artifact_closures'][0]['training_authority_sha256'],
                         authority.digest)
    cold = load_accepted_generation(run_dir)
    testcase.assertEqual(cold.generation, parent.generation + 1)
    testcase.assertEqual(cold.retained_state.step_proofs[0].digest, proof.digest)
    owner = load_capability_support_owner(run_dir, capability)
    testcase.assertEqual(owner.support.retained_generation_sha256, published['manifest_sha256'])
    indexed = {node.artifact_id: node for node in owner.index.nodes}
    for node in authority.artifact_nodes:
        testcase.assertEqual(indexed[node.artifact_id], node)
    owner.require(capability)

    source_fact = next((ref for node in authority.artifact_nodes
                        for ref in node.immediate_dependencies
                        if ref.kind is DependencyKind.SOURCE
                        and ref.key.startswith('salience-fact:')), None)
    testcase.assertIsNotNone(source_fact)
    event = CorrectionEvent(
        event_id='fixture:c06-accepted-source-correction', dependency=source_fact,
        source_owner=_OWNER, source_receipt_sha256='f' * 64,
        old_evidence_sha256='a' * 64, new_evidence_sha256='b' * 64,
        source_time=1, effective_time=2, observed_at=3, recorded_at=4,
        reason_code='FIXTURE_SOURCE_CORRECTION', source_signature_hex='0' * 128)
    event = replace(event, source_signature_hex=_KEY.sign(event.signing_bytes()).hex())
    host = AcceptedRuntimeHost(run_dir)
    event_id = host.record_correction(event)
    with testcase.assertRaises(BilqisError) as before_restart:
        owner.require(capability)
    testcase.assertIn(before_restart.exception.context.get('reason'), (
        'BAMF_C09_ARTIFACT_HELD', 'BAMF_C09_ARTIFACT_DEPENDENCY_HELD',
        'BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_REQUIRED'))
    _reset_accepted_correction_runtime_for_tests()
    recovered = load_capability_support_owner(run_dir, capability)
    with testcase.assertRaises(BilqisError) as after_restart:
        recovered.require(capability)
    testcase.assertIn(after_restart.exception.context.get('reason'), (
        'BAMF_C09_ARTIFACT_HELD', 'BAMF_C09_ARTIFACT_DEPENDENCY_HELD',
        'BAMF_C09_CAPABILITY_SUPPORT_REQUALIFICATION_REQUIRED'))
    receipt = {
        'schema': 'bilqis.c06.retained-publication-witness/v1',
        'acceptance_schema': expected_schema,
        'accepted_manifest_sha256': published['manifest_sha256'],
        'proof_sha256': proof.digest,
        'closure_sha256': authority.artifact_closure_sha256,
        'correction_event_id': event_id,
        'correction_hold_recovered': True,
        'elapsed_seconds': round(time.monotonic() - started, 3),
    }
    print('C06_RETENTION accepted_cold_support ' + json.dumps(receipt, sort_keys=True), flush=True)
    return receipt
