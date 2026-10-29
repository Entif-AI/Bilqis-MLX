"""Projection reads native immutable generation history, never pending event dicts."""
from dataclasses import replace
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
            domain = _contract(root / 'outbox.sqlite3')
            record = _with_delivery_outbox(dict(run_id='fixture:run', generation=1,
                factory_release_sha256=domain.release_digest,
                school={'current_student': {'sha256': domain.model_digest}}), (
                {'event': 'SCHOOL_TEACHER_VISIT_COMMITTED', 'capability': 'renamed.capability',
                 'source_time': 570, 'effective_time': 575, 'observed_at': 580, 'recorded_at': 585},
                {'event': 'UNKNOWN_NATIVE_EVENT'},
                {'event': 'SCHOOL_TEACHER_VISIT_COMMITTED', 'capability': 'legacy:no-times'},))
            persist(root, record)
            before = (root / 'state.json').read_bytes()
            def project(contract=domain):
                return project_accepted_generation(root, 1, contract)
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
