"""Assertions over one captured accepted #1300 optimizer horizon."""
from __future__ import annotations

import numpy as np

from bilqis_mlx.learning.atlas_acceptance import (
    EXACT_ACCEPTANCE_SCHEMA,
    EXACT_CLOSURE_ACCEPTANCE_SCHEMA,
    EXACT_MOTIF_ACCEPTANCE_SCHEMA,
    EXACT_MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
    candidate_identity_digest,
)
from bilqis_mlx.learning.atlas_candidate import resolve_candidate
from bilqis_mlx.runtime.atlas_training_authority import (
    BamfLogicalBatchTrainingAuthority,
    BamfTrainingAuthority,
)
from bilqis_mlx.runtime.baseline.lifecycle import (
    BaselineLedger,
    BaselineLifecycleState,
)
from bilqis_mlx.runtime.bamf_bundle.feature.acceptance import accepted_generation
from bilqis_mlx.runtime.bamf_bundle.genesis.records import (
    successor_candidate_identity_digest,
)


def assert_horizon_gradients(test, capture, step) -> None:
    final = step.transaction
    terminal_index = next(
        index for index, candidate_step in enumerate(capture.steps)
        if candidate_step is step
    )
    start_index = terminal_index - final.update_steps + 1
    test.assertGreaterEqual(start_index, 0)
    horizon_steps = tuple(capture.steps[start_index:terminal_index + 1])
    test.assertEqual(
        tuple(item.transaction.update_steps for item in horizon_steps),
        tuple(range(1, final.update_steps + 1)),
    )
    test.assertTrue(all(
        item.transaction.parent is final.parent for item in horizon_steps
    ))
    test.assertTrue(all(
        item.transaction.step_proofs
        == final.step_proofs[:item.transaction.update_steps]
        for item in horizon_steps
    ))
    test.assertTrue(all(
        capture.step_gradients.get(id(item)) for item in horizon_steps
    ))
    results = []
    for candidate_step in horizon_steps:
        step_results = capture.step_gradients[id(candidate_step)]
        raw_authorities = []
        for result in step_results:
            if hasattr(result, "execution"):
                raw_authorities.append(result.execution.training_authority)
            elif hasattr(result, "executions"):
                raw_authorities.extend(
                    execution.training_authority
                    for execution in result.executions
                )
            else:
                test.fail("captured gradient execution lacks B11 authority")
        top_authority = candidate_step.transaction.training_authorities[-1]
        expected_members = (
            top_authority.members
            if type(top_authority) is BamfLogicalBatchTrainingAuthority
            else (top_authority,)
        )
        test.assertEqual(
            tuple(authority.digest for authority in raw_authorities),
            tuple(authority.digest for authority in expected_members),
        )
        results.extend(step_results)
    test.assertTrue(results)
    leaf_count = 0
    nonzero = False
    for result in results:
        for gradient in result.gradients.values():
            array = np.asarray(gradient)
            leaf_count += 1
            test.assertTrue(np.all(np.isfinite(array)))
            nonzero = nonzero or bool(np.any(array != 0))
    test.assertGreater(leaf_count, 0)
    test.assertTrue(nonzero)


def assert_publication_identity(test, capture, run_dir):
    test.assertTrue(capture.steps)
    test.assertTrue(capture.publications)
    accepted = accepted_generation(run_dir / "bamf-state.json")[1]
    accepted_identity = candidate_identity_digest(accepted.retained_state)
    matches = []
    for binding, student, release_sha256 in capture.publications:
        for step in capture.steps:
            state = resolve_candidate(step.transaction, accepted=True)
            if (candidate_identity_digest(state) == binding.candidate_identity_sha256
                    == candidate_identity_digest(student.retained_state)
                    == accepted_identity):
                matches.append((binding, student, release_sha256, step, state))
    test.assertEqual(len(matches), 1)
    binding, published, release_sha256, matching_step, matching_state = matches[0]
    authorities = matching_step.transaction.training_authorities
    proofs = matching_step.transaction.step_proofs
    test.assertTrue(authorities)
    test.assertEqual(len(authorities), matching_step.transaction.update_steps)
    test.assertTrue(binding.source_anchors)
    test.assertIsNotNone(binding.source_authority_registry_sha256)
    test.assertEqual(
        tuple(proof.training_authority_sha256 for proof in proofs),
        tuple(authority.digest for authority in authorities),
    )
    test.assertTrue(all(
        type(authority) in (BamfTrainingAuthority, BamfLogicalBatchTrainingAuthority)
        for authority in authorities
    ))
    flattened = tuple(
        member for authority in authorities
        for member in (
            authority.members
            if type(authority) is BamfLogicalBatchTrainingAuthority
            else (authority,)
        )
    )
    test.assertEqual(
        tuple(anchor[8] for anchor in binding.source_anchors),
        tuple(member.digest for member in flattened),
    )
    test.assertEqual(
        {authority.release_sha256 for authority in authorities},
        {release_sha256},
    )
    test.assertEqual(
        {anchor[5] for anchor in binding.source_anchors},
        {release_sha256},
    )
    test.assertTrue(all(anchor[2] for anchor in binding.source_anchors))
    test.assertTrue(all(anchor[3] for anchor in binding.source_anchors))
    test.assertTrue(all(anchor[4] for anchor in binding.source_anchors))
    expected = candidate_identity_digest(matching_state)
    test.assertEqual(binding.candidate_identity_sha256, expected)
    test.assertEqual(candidate_identity_digest(published.retained_state), expected)
    test.assertEqual(candidate_identity_digest(accepted.retained_state), expected)
    test.assertIn(binding.schema_version, {
        EXACT_ACCEPTANCE_SCHEMA,
        EXACT_CLOSURE_ACCEPTANCE_SCHEMA,
        EXACT_MOTIF_ACCEPTANCE_SCHEMA,
        EXACT_MOTIF_CLOSURE_ACCEPTANCE_SCHEMA,
    })
    test.assertIsNotNone(binding.generation_authority_sha256)
    test.assertEqual(
        binding.generation_authority_sha256,
        successor_candidate_identity_digest(published),
    )
    test.assertEqual(accepted.topology.layers, 12)
    test.assertEqual(
        accepted.topology.digest,
        accepted.run_identity.initial_topology_digest,
    )
    return matching_step


def assert_first_baseline(test, capture, run_dir, capability_id: str) -> None:
    transitions = [
        evaluation.baseline_transition
        for evaluation in capture.evaluations
        if evaluation.baseline_transition is not None
        and evaluation.baseline_transition.measurement.comparison.capability_id
        == capability_id
    ]
    test.assertTrue(transitions)
    transition = transitions[0]
    evaluation = next(
        item for item in capture.evaluations
        if item.baseline_transition is transition
    )
    identity = transition.measurement.comparison
    final_ledger = evaluation.baseline_ledger
    test.assertEqual(final_ledger.measurements[-1], transition.measurement)
    parent_ledger = BaselineLedger(final_ledger.measurements[:-1])
    test.assertEqual(parent_ledger.digest, transition.parent_ledger_sha256)
    test.assertIs(
        parent_ledger.state_for(identity), BaselineLifecycleState.UNMEASURED)
    test.assertIs(
        final_ledger.state_for(identity), BaselineLifecycleState.BASELINE_ESTABLISHED)
    accepted = accepted_generation(run_dir / "bamf-state.json")[1]
    durable = BaselineLedger.from_optional_record(accepted.baseline_evidence)
    test.assertIn(transition.measurement, durable.measurements)
    matching_bindings = [
        binding for binding, _student, _release_sha256 in capture.publications
        if binding.candidate_identity_sha256
        == transition.measurement.accepted_candidate_sha256
    ]
    test.assertEqual(len(matching_bindings), 1)
