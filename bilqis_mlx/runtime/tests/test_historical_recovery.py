"""V2 retirement preserves historical evidence without entering live writers."""
from contextlib import ExitStack
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime import session
from bilqis_mlx.state_dag import read_current


class HistoricalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        bundle = self.root / 'bundles/historical'
        bundle.mkdir(parents=True)
        payload = b'disposable historical checksum witness; not a trainable model'
        (bundle / 'model-and-own-adamw.safetensors').write_bytes(payload)
        sha = hashlib.sha256(payload).hexdigest()
        (bundle / 'manifest.json').write_text(json.dumps({
            'schema': 'bilqis.mlx.fp32-adamw-bundle/v1',
            'safetensors_sha256': sha, 'optimizer_step': 23, 'source_digest': 'b' * 64}))
        self.receipt = {
            'schema': session.VERSION, 'run_id': 'historical-test', 'generation': 1,
            'model_bundle': 'bundles/historical', 'curriculum_mode': 'historical-fixture/v1',
            'semantic_graph_sha256': 'c' * 64,
            'school': {'course_digest': 'd' * 64, 'current_student': {
                'sha256': sha, 'filename': 'bundles/historical',
                'optimizer_step': 23, 'model_and_native_adamw': True}},
        }
        (self.root / 'state.json').write_text(json.dumps(self.receipt))

    def snapshot(self):
        return {str(p.relative_to(self.root)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.root.rglob('*') if p.is_file()}

    def forbidden_effects(self):
        stack = ExitStack()
        self.addCleanup(stack.close)
        owners = {
            'session._runtime_checkpoints': ('_clean_staged_bundles', '_recover_orphaned_commit',
                '_advance', '_persist', '_record', '_publish_boundary', '_reconcile_delivery_outbox'),
            'session._runtime_mlx_checkpoint': ('load_semantically_bound_bundle',),
            'session._runtime_release_adoption': ('_ensure_executable_release',),
            'session._runtime_admission': ('_factory_admission', '_executable_factory_admission'),
        }
        for owner, names in owners.items():
            target = session
            for part in owner.split('.')[1:]:
                target = getattr(target, part)
            for name in names:
                stack.enter_context(patch.object(target, name,
                    side_effect=AssertionError('historical path entered ' + name)))

    def test_historical_resume_is_repeatedly_readonly_at_both_entrypoints(self):
        before = self.snapshot()
        self.forbidden_effects()
        for _ in range(2):
            with self.assertRaisesRegex(ValueError, 'SCHOOL.STATE.HISTORICAL_NOT_RESUMABLE'):
                session._resume_admitted_student(self.root, {}, None, None, None, None)
            with self.assertRaisesRegex(ValueError, 'SCHOOL.STATE.HISTORICAL_NOT_RESUMABLE'):
                session._resume(self.root, {}, None, None, grade_a_course=None, source_root=None)
            self.assertEqual(self.snapshot(), before)
            self.assertEqual(read_current(self.root), self.receipt)

    def test_historical_inspection_exposes_only_recorded_metadata(self):
        from bilqis_mlx.compatibility.resume_migration import inspect_historical_run
        before = self.snapshot()
        report = inspect_historical_run(self.root, read_current(self.root))
        self.assertEqual(report['runtime_schema'], session.VERSION)
        self.assertEqual(report['run_id'], self.receipt['run_id'])
        self.assertEqual(report['optimizer_step'], 23)
        self.assertEqual(report['student_sha256'], self.receipt['school']['current_student']['sha256'])
        self.assertEqual(report['curriculum_mode'], 'historical-fixture/v1')
        self.assertEqual(report['payload_checksum'], 'VERIFIED')
        self.assertEqual(report['recorded_state'], self.receipt)
        self.assertEqual(self.snapshot(), before)

    def test_corrupt_payload_and_unknown_runtime_are_not_retired_valid_history(self):
        self.forbidden_effects()
        blob = self.root / 'bundles/historical/model-and-own-adamw.safetensors'
        blob.write_bytes(b'corrupt')
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID') as invalid:
            session._resume_admitted_student(self.root, {}, None, None, None, None)
        self.assertEqual(invalid.exception.context["reason"], "MLX_BUNDLE_TENSOR_FILE_CORRUPTED")
        self.assertEqual(self.snapshot(), before)
        unknown = {**self.receipt, 'schema': 'unknown/runtime'}
        (self.root / 'state.json').write_text(json.dumps(unknown))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID') as invalid:
            session._resume_admitted_student(self.root, {}, None, None, None, None)
        self.assertEqual(self.snapshot(), before)

    def test_invalid_json_retains_native_corruption_failure(self):
        self.forbidden_effects()
        (self.root / 'state.json').write_text('{broken')
        before = self.snapshot()
        with self.assertRaises(ValueError) as caught:
            session._resume_admitted_student(self.root, {}, None, None, None, None)
        self.assertNotIn('SCHOOL.STATE.HISTORICAL_NOT_RESUMABLE', str(caught.exception))
        self.assertEqual(self.snapshot(), before)

    def test_current_admission_is_not_classified_as_historical(self):
        current = {**self.receipt, 'factory_admission_v2': {'schema': 'current-fixture'}}
        with patch('bilqis_mlx.compatibility.resume_migration.inspect_historical_run',
                   side_effect=AssertionError('current state entered historical reader')):
            session._require_current_resume(self.root, current)

    def test_malformed_historical_identity_fails_without_retirement_or_writes(self):
        self.forbidden_effects()
        broken = {**self.receipt, 'model_bundle': '../outside'}
        (self.root / 'state.json').write_text(json.dumps(broken))
        before = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID') as invalid:
            session._resume_admitted_student(self.root, {}, None, None, None, None)
        self.assertEqual(self.snapshot(), before)
