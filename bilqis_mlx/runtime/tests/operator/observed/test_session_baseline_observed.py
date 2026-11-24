from pathlib import Path
from contextlib import ExitStack, nullcontext
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


def _first_baseline_operator_case():
    from bilqis_mlx.runtime.tests.capability.factory.owner.adversarial.support import (
        _evaluate_foundation_owner,
        _foundation_owner_fixture,
    )
    from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
        accepted_state,
        candidate,
        parent_state,
    )

    evaluation = _evaluate_foundation_owner(*_foundation_owner_fixture())
    identity = evaluation.baseline_transition.measurement.comparison
    fixture_parent_state = parent_state()
    fixture_candidate_state = accepted_state(fixture_parent_state)
    object.__setattr__(evaluation, "parent_state", fixture_parent_state)
    object.__setattr__(evaluation, "candidate_state", fixture_candidate_state)
    successor = candidate(
        fixture_candidate_state,
        generation=1,
        parent="0" * 64,
    )
    parent = NS(
        generation=0,
        retained_state=NS(optimizer_step=0),
        optimizer_hyperparameters=None,
    )
    selection = NS(
        option_id="fixture-option",
        visit=NS(
            identity=NS(visit_id="fixture-visit", policy_key="fixture-policy"),
            projection=NS(teacher_state={})),
    )
    step = NS(transaction=NS(training_authorities=()))
    capture = NS(finalize=lambda **_kwargs: {
        "schema": "bilqis.bamf.c16.3-candidate-evidence-reference/v1",
        "persistence": {
            "bytes_written": 0,
            "file_fsyncs": 0,
            "directory_fsyncs": 0,
            "evidence_objects": 0,
            "persistence_seconds": 0.0,
        },
    }, summary=lambda: {
        "attempt_id": "fixture-attempt",
        "candidate_steps": 1,
        "batch_size": 1,
        "policy_controls": ({},),
        "guidance_applied_steps": 0,
        "enrichment_examples": 0,
    })
    cache = NS(generation=0, accepted_manifest_sha256="0" * 64)
    return evaluation, identity, successor, parent, selection, step, capture, cache


def _operate_first_baseline_case(case):
    from contextlib import ExitStack
    from tempfile import TemporaryDirectory
    from bilqis_mlx.runtime.bamf_operator.session import _emit_progress, operate_bamf
    from bilqis_mlx.runtime.bamf_operator.session_parts.native_session import retention_result

    evaluation, identity, successor, parent, selection, step, capture, cache = case
    published = []

    def prepare(run_dir, *, observer=None, **_kwargs):
        if observer is not None:
            observer.bind_parent(parent)
        return retention_result(
            run_dir, parent, NS(), "artifact", selection, identity.capability_id,
            cache, (step,), capture, 1, 1, {}, None, observer, emit_progress=_emit_progress)

    def publish(_run_dir, bound_successor, *_args, **_kwargs):
        published.append(bound_successor)

    prefix = "bilqis_mlx.runtime.bamf_operator.session."
    native_prefix = "bilqis_mlx.runtime.bamf_operator.session_parts.native_session."
    patches = (
        ('bilqis_mlx.runtime.outcomes.issuance.build_outcome', {'return_value': {}}),
        ('bilqis_mlx.runtime.outcomes.issuance.credited_visit', {'side_effect': lambda visit, outcome: visit}),
        ('bilqis_mlx.runtime.outcomes.issuance.carry_credit_to_successor', {'side_effect': lambda visit, successor, parent: successor}),
        (prefix + "prepare_bamf_visit", {"side_effect": prepare}),
        (native_prefix + "evaluate_factory_retention_candidate", {"return_value": evaluation}),
        (native_prefix + "derive_accepted_teacher_successor", {"return_value": successor}),
        (native_prefix + "_resource_observation", {"return_value": {}}),
        (native_prefix + "candidate_identity_metrics_delta", {"return_value": {}}),
        ("bilqis_mlx.runtime.bamf_operator.session_parts.retention._instruction_event",
         {"return_value": {
             "event": "BAMF_INSTRUCTION_HISTORY",
             "schema": "bilqis.bamf.instruction-history/v1",
             "state": "PARTIAL",
             "capability_ids": [identity.capability_id],
         }}),
        ("bilqis_mlx.runtime.retention.screen.candidate_identity_for_canonical_consumer",
         {"return_value": "d" * 64}),
        (prefix + "accept_and_publish", {"side_effect": publish}),
        (prefix + "load_accepted_generation", {"return_value": NS(
            generation=1, retained_state=NS(optimizer_step=1))}),
    )
    with TemporaryDirectory() as tmp, ExitStack() as stack:
        for target, kwargs in patches:
            stack.enter_context(patch(target, **kwargs))
        result = operate_bamf(
            Path(tmp), minutes=1, max_visits=1, reserve_gib=0,
            source_prefetch_workers=0)
    return result, published


@patch("bilqis_mlx.runtime.bamf_operator.session._training_memory_context", nullcontext)
class SessionObservationTests(unittest.TestCase):
    def setUp(self):
        patched = patch('bilqis_mlx.runtime.outcomes.issuance.build_outcome', return_value={})
        patched.start()
        self.addCleanup(patched.stop)

    def test_operate_bamf_carries_first_accepted_baseline_to_publication(self):
        from bilqis_mlx.runtime.baseline.lifecycle import (
            BaselineLedger,
            BaselineLifecycleState,
        )

        case = _first_baseline_operator_case()
        evaluation, identity = case[:2]
        identity = evaluation.baseline_transition.measurement.comparison
        self.assertIs(
            evaluation.baseline_ledger.state_for(identity),
            BaselineLifecycleState.BASELINE_ESTABLISHED,
        )
        result, published = _operate_first_baseline_case(case)

        self.assertEqual((result.accepted, result.rejected), (1, 0))
        self.assertEqual(len(published), 1)
        ledger = BaselineLedger.from_optional_record(published[0].baseline_evidence)
        self.assertIs(
            ledger.state_for(identity),
            BaselineLifecycleState.BASELINE_ESTABLISHED,
        )
