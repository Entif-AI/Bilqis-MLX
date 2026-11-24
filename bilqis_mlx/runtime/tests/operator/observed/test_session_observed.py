from pathlib import Path
from contextlib import ExitStack, nullcontext
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session import _visit


def _run_observed_preparation_fixture(parent, selection, steps, events):
    from bilqis_mlx.runtime.bamf_operator.session import prepare_bamf_visit
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode

    def assess(*args, **kwargs):
        assert 'observer' not in kwargs
        return NS(
            candidate_state=object(),
            parent_state=parent.retained_state,
            decision=NS(outcome_scores=(('cap', 2, 3, 6),)),
        )

    prefix = 'bilqis_mlx.runtime.bamf_operator.session.'
    native_prefix = 'bilqis_mlx.runtime.bamf_operator.session_parts.native_session.'
    accepted_cache = NS(generation=1, accepted_manifest_sha256='a' * 64)
    context = NS(
        release='release',
        _accepted_runtime_host=NS(_accepted_cache=accepted_cache),
    )
    patches = {
        '_execution_context': (parent, context, 'atlas', 'feature'),
        'schedule_program_from_executable_release': 'program',
        'accepted_priority_school': 'school',
        'select_foundation_priority_visit': selection,
        '_Capture': NS(finalize=lambda **_kwargs: {
            'schema': 'bilqis.bamf.c16.3-candidate-evidence-reference/v1',
            'persistence': {'bytes_written': 1, 'file_fsyncs': 1,
                            'directory_fsyncs': 1, 'evidence_objects': 1,
                            'persistence_seconds': 0.0}}),
        'FactoryDeliveryObservation': 'delivery',
        'bind_accepted_execution_cache': accepted_cache,
        'candidate_step_horizon': 3,
        'rejection_attempt_ordinals': (1, 1),
        'prepare_candidate_evidence_root': Path('/tmp/teacher-observations/objects'),
        'issue_factory_retention_decision': NS(
            accepted=False, decision='REJECT',
            reason='PROTECTED_CAPABILITY_REGRESSION',
            evaluated_capability_ids=('cap', 'protected-cap'),
            retention_protection_plan_sha256='f' * 64,
            broad_certification_trigger=None,
            to_record=lambda: {'decision': 'REJECTED'}),
    }
    with ExitStack() as stack:
        for name, value in patches.items():
            owner = prefix if name in {
                '_execution_context', 'schedule_program_from_executable_release',
                'accepted_priority_school', 'select_foundation_priority_visit',
            } else native_prefix
            stack.enter_context(patch(owner + name, return_value=value))
        stack.enter_context(patch(
            native_prefix + 'execute_learning_first_priority_candidate',
            side_effect=steps))
        stack.enter_context(patch(
            native_prefix + 'currentness_metrics',
            side_effect=AssertionError(
                'ordinary semantic observation reopened currentness telemetry')))
        stack.enter_context(patch(
            'bilqis_mlx.runtime.bamf_operator.session_parts.learning_trace.'
            'CandidateLearningTrace',
            return_value=NS(
                delivery=lambda *_args, **_kwargs: None,
                summary=lambda: {
                    'attempt_id': 'fixture-attempt', 'candidate_steps': 3,
                    'batch_size': 1, 'policy_controls': ({}, {}, {}),
                    'guidance_applied_steps': 0, 'enrichment_examples': 0,
                })))
        stack.enter_context(patch(
            native_prefix + 'evaluate_factory_retention_candidate',
            side_effect=assess))
        stack.enter_context(patch(
            'bilqis_mlx.runtime.championship_advisers.prepare_championship_adviser_pool',
            return_value=None))
        stack.enter_context(patch(
            'bilqis_mlx.runtime.bamf_operator.evidence_parts.projection.complete_visit_evidence',
            side_effect=RuntimeError('observation readback failed')))
        observer = NS(
            bind_parent=lambda value: events.append({'bound': value}),
            update=lambda **fields: events.append(fields),
            stage=lambda **fields: events.append(fields),
            begin_step=lambda step, optimizer_step: events.append({
                'candidate_step': step,
                'candidate_optimizer_step': optimizer_step,
            }))
        with evidence_mode(strict=False):
            return prepare_bamf_visit(Path('/tmp'), observer=observer)


@patch("bilqis_mlx.runtime.bamf_operator.session._training_memory_context", nullcontext)
class SessionObservationTests(unittest.TestCase):
    def setUp(self):
        patched = patch('bilqis_mlx.runtime.outcomes.issuance.build_outcome', return_value={})
        patched.start()
        self.addCleanup(patched.stop)

    def test_publication_before_accepted_and_failure_propagates(self):
        events = []
        observer = NS(update=lambda **v: events.append(v))
        decision = NS(accepted=True)
        prepared = NS(status='ACCEPTED', parent=object(), selection=object(),
                      step=NS(transaction=NS(training_authorities=())), decision=decision,
                      retained=object(), capability='cap', successor=NS(extents=NS(factor_map_digest='x')))
        with patch('bilqis_mlx.runtime.bamf_operator.session.prepare_bamf_visit', return_value=prepared), patch(
                'bilqis_mlx.runtime.bamf_operator.session.accept_and_publish', side_effect=RuntimeError('publish')):
            with self.assertRaises(RuntimeError):
                _visit(Path('/tmp'), 0, observer=observer)
        self.assertEqual(events[0], {'phase': 'PUBLISHING'})
        self.assertGreaterEqual(events[1]['publishing_wall_seconds'], 0.0)

    def test_preparation_emits_observed_training_and_retention(self):
        events = []
        parent = NS(retained_state=NS(optimizer_step=4), optimizer_hyperparameters='hp')
        selection = NS(status='TEACHER_SELECTED', offer=NS(
            capability_id='cap', source_seed=1, rows=lambda: ({'id': 'row'},),
            _planning_generation=NS(_accepted_currentness='currentness')),
            visit=NS(identity=NS(visit_id='visit')))
        steps = [NS(
            transaction=NS(parent=NS(optimizer_step=4), update_steps=i),
            realized_cost={
                'wall_seconds': 1.0, 'optimizer_steps': 1,
                'candidate_optimizer_steps': i, 'c08_memory_budget_bytes': 1,
            }) for i in (1, 2, 3)]
        result = _run_observed_preparation_fixture(
            parent, selection, steps, events)
        self.assertEqual(result.status, 'REJECTED')
        self.assertEqual([e.get('phase') for e in events if 'phase' in e],
                         ['SELECTING', 'TRAINING', 'RETENTION'])
        self.assertIn({'visit_id': 'visit'}, events)
        self.assertIn({
            'phase': 'TRAINING', 'capability_id': 'cap', 'visit_id': 'visit',
            'candidate_step': 0, 'candidate_horizon': 3,
            'candidate_optimizer_step': 4,
        }, events)
        for i in (1, 2, 3):
            self.assertIn({'candidate_step': i, 'candidate_optimizer_step': 4 + i}, events)
        self.assertIn({
            'retention_target': {
                'state': 'MEASURED', 'before': 2, 'after': 3, 'total': 6,
            },
            'retention_protected_count': 1,
        }, events)
        self.assertFalse(any(
            'retention_protection_plan_sha256' in event for event in events))
