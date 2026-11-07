"""B13 pointer durability, overlapping recovery and predecessor delivery."""
import json
import os
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from bilqis_mlx._data_plane import file_objects
from bilqis_mlx.data_plane import data_plane
import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.bamf_bundle._publication_storage as publication_storage
import bilqis_mlx.runtime.checkpoints as checkpoints
import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import load_bamf_generation, publish_bamf_generation
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    publish_candidate,
    accepted_state, candidate, parent_state, shape_patch,
)


class PublicationDurabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / 'run'
        self.environment = patch.dict(os.environ, {'BILQIS_DATA_PLANE': str(self.root / 'plane.sqlite3')})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish(self, value):
        with shape_patch(), patch.object(mlx_checkpoint, 'assert_headroom'):
            return publish_candidate(self.run, value)

    def assert_persisted_tensor_durable(self):
        current = set()
        fsync, pointer = os.fsync, publication._atomic_pointer

        def identity(path):
            state = path.stat()
            return state.st_dev, state.st_ino

        def sync(fd):
            state = os.fstat(fd)
            current.add((state.st_dev, state.st_ino))
            fsync(fd)

        def install(path, value):
            manifest = json.loads((path.parent / value['bundle'] / 'manifest.json').read_bytes())
            tensor = data_plane().require_file_object(manifest['tensors']['object_sha256'])
            self.assertIn(identity(tensor), current, 'persisted CAS inode must be durable')
            for directory in (tensor.parent, tensor.parent.parent, tensor.parent.parent.parent):
                self.assertIn(identity(directory), current, 'CAS ancestry must be durable')
            pointer(path, value)

        with patch.object(os, 'fsync', side_effect=sync), \
                patch.object(publication, '_atomic_pointer', side_effect=install):
            for name in ('initial', 'reuse'):
                current.clear()
                self.run = self.root / name
                self.publish(candidate(parent_state()))

    def test_tensor_file_is_fsynced_before_pointer_can_be_installed(self):
        self.assert_persisted_tensor_durable()

    def test_acceptance_directory_is_fsynced_before_pointer_can_be_installed(self):
        durable = set()
        synced_directories = set()
        fsync, pointer = os.fsync, publication._atomic_pointer
        sync_directory = publication_storage._fsync_directory

        def identity(path):
            state = path.stat()
            return state.st_dev, state.st_ino

        def sync(fd):
            state = os.fstat(fd)
            durable.add((state.st_dev, state.st_ino))
            fsync(fd)

        def sync_path(path):
            synced_directories.add(Path(path))
            sync_directory(path)

        def install(path, pointer_value):
            acceptance = (path.parent / 'bamf-acceptance'
                          / f"{pointer_value['manifest_sha256']}.json")
            bundle_root = path.parent / 'bamf-bundles'
            self.assertIn(identity(acceptance), durable,
                          'acceptance receipt inode must be durable')
            self.assertIn(
                identity(acceptance.parent), durable,
                'acceptance directory must be durable before pointer publication')
            self.assertIn(
                identity(bundle_root), durable,
                'bundle directory must be durable before pointer publication')
            self.assertIn(
                identity(path.parent), durable,
                'run directory must durably link custody directories before pointer publication')
            self.assertIn(
                path.parent.parent, synced_directories,
                'run parent must durably link a newly created run directory before pointer publication')
            pointer(path, pointer_value)

        with patch.object(os, 'fsync', side_effect=sync), \
                patch.object(publication_storage, '_fsync_directory', side_effect=sync_path), \
                patch.object(publication, '_atomic_pointer', side_effect=install):
            self.publish(candidate(parent_state()))

    def test_acceptance_directory_is_resynced_on_pre_pointer_retry(self):
        initial = parent_state()
        first = self.publish(candidate(initial))
        successor = candidate(accepted_state(initial), 1, first['manifest_sha256'])
        with patch.object(publication, '_atomic_pointer', side_effect=RuntimeError('crash')):
            with self.assertRaisesRegex(RuntimeError, 'crash'):
                self.publish(successor)
        self.assertEqual(
            json.loads((self.run / 'bamf-state.json').read_text()), first)

        durable = set()
        fsync, pointer = os.fsync, publication._atomic_pointer

        def sync(fd):
            state = os.fstat(fd)
            durable.add((state.st_dev, state.st_ino))
            fsync(fd)

        def install(path, pointer_value):
            acceptance_root = path.parent / 'bamf-acceptance'
            state = acceptance_root.stat()
            self.assertIn(
                (state.st_dev, state.st_ino), durable,
                'existing acceptance directory must be durable before pointer retry')
            pointer(path, pointer_value)

        with patch.object(os, 'fsync', side_effect=sync), \
                patch.object(publication, '_atomic_pointer', side_effect=install):
            second = self.publish(successor)
        self.assertEqual(second['generation'], 1)

    def test_ordering_witness_detects_unsynced_cas_inode(self):
        with patch.object(file_objects, '_fsync_file'):
            with self.assertRaisesRegex(AssertionError, 'persisted CAS inode'):
                self.assert_persisted_tensor_durable()
        self.assertEqual(self.run.name, 'reuse')
        self.assertFalse((self.run / 'bamf-state.json').exists())

    def test_ordering_witness_detects_unsynced_cas_ancestry(self):
        sync = file_objects._fsync_directory

        def omit_reuse_sync(path):
            if self.run.name != 'reuse':
                sync(path)

        with patch.object(file_objects, '_fsync_directory', side_effect=omit_reuse_sync):
            with self.assertRaisesRegex(AssertionError, 'CAS ancestry'):
                self.assert_persisted_tensor_durable()
        self.assertEqual(self.run.name, 'reuse')
        self.assertFalse((self.run / 'bamf-state.json').exists())

    def test_overlapping_cold_reader_cannot_race_outbox_reconciliation(self):
        for operation in ('publish', 'load'):
            with self.subTest(operation=operation):
                self.run = self.root / operation
                source = candidate(parent_state())
                if operation == 'load':
                    with patch.object(publication, 'reconcile_bamf_outbox', side_effect=RuntimeError('crash')):
                        with self.assertRaises(RuntimeError):
                            self.publish(source)
                entered, release = threading.Event(), threading.Event()
                guard = threading.Lock()
                calls = []
                reconcile = checkpoints._reconcile_delivery_outbox

                def pause(run, record, **kwargs):
                    with guard:
                        calls.append(1)
                        first = len(calls) == 1
                    if first:
                        entered.set()
                        if not release.wait(5):
                            raise RuntimeError('test synchronization timed out')
                    return reconcile(run, record, **kwargs)

                def writer():
                    return (self.publish(source) if operation == 'publish'
                            else load_bamf_generation(self.run / 'bamf-state.json'))

                with shape_patch(), patch.object(checkpoints, '_reconcile_delivery_outbox', side_effect=pause):
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(writer)
                        try:
                            self.assertTrue(entered.wait(5))
                            with self.assertRaises(BilqisError):
                                load_bamf_generation(self.run / 'bamf-state.json')
                        finally:
                            release.set()
                            future.result(timeout=5)
                events = [json.loads(line) for line in (self.run / 'events.jsonl').read_text().splitlines()]
                self.assertEqual(len(events), 1)
                self.assertEqual(events[0]['event'], 'FIXTURE_ACCEPTED')

    def test_successor_recovers_pending_predecessor_before_advancing_pointer(self):
        initial = parent_state()
        with patch.object(publication, 'reconcile_bamf_outbox', side_effect=RuntimeError('crash')):
            with self.assertRaises(RuntimeError):
                self.publish(candidate(initial))
        first = json.loads((self.run / 'bamf-state.json').read_text())
        self.assertFalse((self.run / 'events.jsonl').exists())
        self.publish(candidate(accepted_state(initial), 1, first['manifest_sha256']))
        with shape_patch():
            loaded = load_bamf_generation(self.run / 'bamf-state.json')
        self.assertEqual(loaded.generation, 1)
        events = [json.loads(line) for line in (self.run / 'events.jsonl').read_text().splitlines()]
        self.assertEqual([e['optimizer_step'] for e in events], [11, 12])
        self.assertEqual(len({e['event_id'] for e in events}), 2)
