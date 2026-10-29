"""Projection reads native immutable generation history, never pending event dicts."""
from dataclasses import asdict, replace
from pathlib import Path
import tempfile
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.state_dag import persist
from bilqis_mlx.runtime.checkpoints import _with_delivery_outbox
from bilqis_mlx.runtime.generation_projection import project_accepted_generation
from bilqis_mlx.runtime.bamf_projection import read_projection_outbox
from bilqis_mlx.runtime.tests.test_bamf_projection import _contract


class GenerationProjectionTests(unittest.TestCase):
    def test_native_committed_visit_replays_and_unknown_kind_remains_delivery_debt(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            from bilqis_mlx.runtime.tests.test_admission import _executable_fixture
            from bilqis_mlx.runtime.admission import _executable_factory_admission
            from bilqis_mlx.runtime.state import _fingerprint
            from bilqis_mlx.learning.champions import Checkpoint
            release, graph = _executable_fixture()
            student = Checkpoint('2' * 64, 'bundles/disposable', 0, True)
            _, release_file, admission = _executable_factory_admission(root, release, student, _fingerprint(graph), graph)
            domain = replace(_contract(root / 'outbox.sqlite3'), release_digest=release.release_sha256)
            record = _with_delivery_outbox(dict(run_id='fixture:run', generation=1,
                factory_release_sha256=release.release_sha256, factory_release_file=release_file,
                factory_admission_v2=asdict(admission), semantic_graph_sha256=_fingerprint(graph),
                school={'current_student': asdict(student)}), (
                {'event': 'SCHOOL_TEACHER_VISIT_COMMITTED', 'capability': 'renamed.capability',
                 'source_time': 570, 'effective_time': 575, 'observed_at': 580, 'recorded_at': 585},
                {'event': 'UNKNOWN_NATIVE_EVENT'},
                {'event': 'SCHOOL_TEACHER_VISIT_COMMITTED', 'capability': 'legacy:no-times'},))
            persist(root, record)
            before = (root / 'state.json').read_bytes()
            def project(contract=domain):
                return project_accepted_generation(root, 1, contract, graph=graph)
            first = project()
            self.assertEqual(first.projected_native_event_ids, (record['delivery_outbox'][0]['event_id'],))
            self.assertEqual(first.uncovered_native_event_ids, tuple(event['event_id'] for event in record['delivery_outbox'][1:]))
            self.assertEqual(first.receipt.appended_count, 1)
            self.assertEqual(project().receipt.duplicate_count, 1)
            events = read_projection_outbox(domain.outbox_path)
            self.assertEqual(events[0].event.kind.value, 'TEACHER_VISIT')
            self.assertEqual((root / 'state.json').read_bytes(), before)
            for key in ('release_digest', 'model_digest'):
                with self.assertRaises(BilqisError):
                    project(replace(domain, **{key: 'f' * 64}))
            with self.assertRaises(ValueError):
                project_accepted_generation(root, 1, domain, graph={**graph, 'tokens': ['foreign']})
            artifact = root / release_file
            original = artifact.read_bytes()
            artifact.unlink()
            with self.assertRaises(ValueError):
                project()
            artifact.write_bytes(original)
            self.assertEqual(project().receipt.duplicate_count, 1)


    def test_new_receiving_envelopes_reject_wrong_native_field_types(self):
        from bilqis_mlx.runtime.akasha_outbox import AkashaEvent, AkashaEventKind
        payload = dict(generation=1, run_id='fixture:run', native_event_id='b' * 64,
            native_event_type='SCHOOL_TEACHER_VISIT_COMMITTED', native_event_digest='a' * 64)
        for key, value in (('generation', False), ('run_id', {}), ('native_event_id', {}),
                           ('native_event_type', 42), ('native_event_type', 'SCHOOL_FACTORY_RELEASE_MIGRATED')):
            with self.subTest(key=key, value=value), self.assertRaises(BilqisError):
                AkashaEvent.from_payload(kind=AkashaEventKind.TEACHER_VISIT, subject_id='fixture:subject',
                    source_receipt_sha256='c' * 64, payload={**payload, key: value},
                    source_time=570, effective_time=575, observed_at=580, recorded_at=585)

    def test_native_artifact_and_admission_failures_precede_queue_creation(self):
        import json
        from bilqis_mlx.runtime.tests.test_admission import _executable_fixture
        from bilqis_mlx.runtime.admission import _executable_factory_admission
        from bilqis_mlx.runtime.state import _fingerprint
        from bilqis_mlx.learning.champions import Checkpoint
        release, graph = _executable_fixture()
        for case in ('missing', 'symlink', 'schema', 'digest', 'plan', 'graph', 'ahead', 'checkpoint', 'later'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                student = Checkpoint('2' * 64, 'bundles/disposable', 0, True)
                _, file, admission = _executable_factory_admission(root, release, student, _fingerprint(graph), graph)
                domain = replace(_contract(root / 'outbox.sqlite3'), release_digest=release.release_sha256)
                record = dict(run_id='fixture:run', generation=1,
                    factory_release_sha256=release.release_sha256, factory_release_file=file,
                    factory_admission_v2=asdict(admission), semantic_graph_sha256=_fingerprint(graph),
                    school={'current_student': asdict(student)})
                artifact = root / file
                if case == 'missing':
                    artifact.unlink()
                elif case == 'symlink':
                    moved = root / 'elsewhere.json'
                    artifact.rename(moved)
                    artifact.symlink_to(moved)
                elif case == 'schema':
                    payload = json.loads(artifact.read_text())
                    payload['schema'] = 'unknown/v1'
                    artifact.write_text(json.dumps(payload))
                elif case == 'digest':
                    record['factory_release_sha256'] = 'f' * 64
                elif case == 'plan':
                    record['factory_admission_v2']['execution_plan_sha256'] = 'f' * 64
                elif case == 'ahead':
                    record['factory_admission_v2']['optimizer_step'] = 1
                elif case in ('checkpoint', 'later'):
                    current = replace(student, sha256='3' * 64, optimizer_step=int(case == 'later'))
                    record['school']['current_student'] = asdict(current)
                    domain = replace(domain, model_digest=current.sha256)
                record = _with_delivery_outbox(record, ({'event': 'SCHOOL_TEACHER_VISIT_COMMITTED',
                    'source_time': 570, 'effective_time': 575, 'observed_at': 580, 'recorded_at': 585},))
                persist(root, record)
                supplied_graph = {**graph, 'tokens': ['foreign']} if case == 'graph' else graph
                if case == 'later':
                    result = project_accepted_generation(root, 1, domain, graph=supplied_graph)
                    self.assertEqual(result.receipt.appended_count, 1)
                else:
                    with self.assertRaises((ValueError, BilqisError)):
                        project_accepted_generation(root, 1, domain, graph=supplied_graph)
                    self.assertFalse(domain.outbox_path.exists())
