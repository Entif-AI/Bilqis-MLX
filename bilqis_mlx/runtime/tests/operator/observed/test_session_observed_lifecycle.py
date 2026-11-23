from pathlib import Path
from contextlib import nullcontext
import json
from tempfile import TemporaryDirectory
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch


def _complete_observed_step(observer):
    observer.complete_step(
        candidate_step=1, candidate_optimizer_step=8, candidate_step_wall_seconds=0.5,
        pre_neural_source_compile_wall_seconds=0.1, currentness_binding_wall_seconds=0.01,
        accepted_currentness_refresh_wall_seconds=0.001,
        accepted_parent_currentness_wall_seconds=0.001,
        lawful_frontier_currentness_wall_seconds=0.002,
        teacher_visit_currentness_wall_seconds=0.002, source_currentness_wall_seconds=0.001,
        candidate_binding_wall_seconds=0.003, b11_preflight_wall_seconds=0.1,
        b11_autodiff_wall_seconds=0.2, optimizer_admission_wall_seconds=0.05,
        motif_staging_wall_seconds=0.0, evidence_capture_wall_seconds=0.01,
        candidate_terminal_step=True, c08_gradient_launches=1,
        c08_vectorized_microbatches=1, c08_materialization_barriers=1,
        c08_scalar_fallback_rows=0, c08_logical_batch_wall_seconds=0.3,
        c08_rows_per_gradient_launch=4.0, b11_provider_draw_count=4,
        b11_atlas_reload_count=1, logical_rows=4, compiled_positions=32,
    )


@patch("bilqis_mlx.runtime.bamf_operator.session._training_memory_context", nullcontext)
class SessionObservationTests(unittest.TestCase):
    def setUp(self):
        patched = patch('bilqis_mlx.runtime.outcomes.issuance.build_outcome', return_value={})
        patched.start()
        self.addCleanup(patched.stop)

    def test_disposable_operator_witness_spans_planning_training_retention_and_publication(self):
        from bilqis_mlx.runtime.bamf_bundle.publication.instrumentation import (
            PublicationMetrics,
        )
        from bilqis_mlx.runtime.bamf_operator.session import operate_bamf

        parent = NS(generation=0, retained_state=NS(optimizer_step=7))
        prepared = NS(status='ACCEPTED', parent=parent, selection=object(),
                      step=NS(transaction=NS(training_authorities=())),
                      decision=NS(accepted=True), retained=object(), capability='A.IDENTITY',
                      successor=NS(extents=NS(factor_map_digest='x')))
        snapshots = []

        def capture(run_dir):
            snapshots.append(json.loads(
                (Path(run_dir) / 'trainer-observed.json').read_text())['visits'][-1])

        def prepare(_run_dir, *, observer=None, **_kwargs):
            observer.bind_parent(parent)
            observer.update(
                phase='SELECTING',
                activity='planner: compiling semantic curriculum')
            capture(_run_dir)
            observer.update(
                phase='TRAINING', capability_id='A.IDENTITY',
                candidate_step=0, candidate_horizon=1,
                candidate_optimizer_step=7)
            observer.begin_step(1, 8)
            _complete_observed_step(observer)
            capture(_run_dir)
            observer.update(
                phase='RETENTION', retention_completed=0, retention_total=2,
                retention_subject='A.IDENTITY', retention_role='parent')
            observer.update(
                retention_completed=1, retention_total=2,
                retention_subject='A.IDENTITY', retention_role='candidate')
            capture(_run_dir)
            return prepared

        def publish(run_dir, *_args, publication_observer=None, **_kwargs):
            capture(run_dir)
            if publication_observer is not None:
                publication_observer(PublicationMetrics(1, 2, 3, 4, 5))

        prefix = 'bilqis_mlx.runtime.bamf_operator.session.'
        with TemporaryDirectory() as tmp:
            run_dir = Path(tmp)
            (run_dir / 'bamf-state.json').write_text(json.dumps({
                'run_id': 'operator-witness', 'manifest_sha256': 'a' * 64,
            }))
            with patch(prefix + 'prepare_bamf_visit', side_effect=prepare), patch(
                    prefix + 'accept_and_publish', side_effect=publish), patch(
                    prefix + 'load_accepted_generation', return_value=NS(
                        generation=1, retained_state=NS(optimizer_step=8))):
                result = operate_bamf(
                    run_dir, minutes=1, max_visits=1, reserve_gib=0,
                    source_prefetch_workers=0)
            final = json.loads(
                (run_dir / 'trainer-observed.json').read_text())['visits'][-1]

        self.assertEqual((result.accepted, result.rejected), (1, 0))
        self.assertEqual((snapshots[0]['phase'], snapshots[0]['activity']),
                         ('SELECTING', 'planner: compiling semantic curriculum'))
        # complete_step is deliberately nonblocking; heartbeat/finalization
        # persists the completed step after this immediate file snapshot.
        self.assertEqual((snapshots[1]['phase'], snapshots[1]['candidate_step']),
                         ('TRAINING', 0))
        self.assertEqual((snapshots[2]['phase'], snapshots[2]['retention_completed'],
                          snapshots[2]['retention_total']), ('RETENTION', 1, 2))
        # Ordinary publishing is staged for heartbeat/finalization rather than
        # forcing another synchronous telemetry write on the accepted hot path.
        self.assertEqual((snapshots[3]['phase'], snapshots[3]['outcome']),
                         ('RETENTION', 'RUNNING'))
        self.assertEqual((final['phase'], final['outcome']),
                         ('COMPLETED', 'ACCEPTED'))
        # Strict-only progress strings are not republished by ordinary mode.
        self.assertEqual(final['activity'], 'planner: compiling semantic curriculum')
        self.assertEqual(final['candidate_step'], 1)
        self.assertEqual(final['candidate_steps'][-1]['candidate_step'], 1)
        self.assertEqual((final['retention_completed'], final['retention_total']),
                         (1, 2))
        self.assertEqual(
            (final['retention_subject'], final['retention_role']),
            ('A.IDENTITY', 'candidate'))
        # Publication performance accounting remains strict-only.  Ordinary
        # observability restores semantics without reopening that proof/timing lane.
        for field in (
                'publication_parent_bundle_loads', 'publication_child_bundle_loads',
                'publication_tensor_bytes_read', 'publication_write_bytes',
                'publication_fsync_bytes'):
            self.assertNotIn(field, final)
