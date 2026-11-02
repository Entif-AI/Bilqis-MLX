"""Two real local nodes exchange immutable packages without executing payloads."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.cognitive_package import export_capability, PackageKind
from bilqis_mlx.runtime.cognitive_package.exchange import publish_package, receive_package
from bilqis_mlx.runtime.cognitive_package.tests.fixtures import (
    PackageAssertions, digest, snapshot,
)


class ExchangeTests(PackageAssertions, unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.sender = self.root / 'node-a'
        self.receiver = self.root / 'node-b'
        source, rights = snapshot()
        self.package = export_capability(source, source.signature, rights)

    def receive(self, **overrides):
        args = dict(sender=self.sender, receiver=self.receiver,
                    package_digest=self.package.digest, binding=self.package.binding,
                    max_wire_bytes=16384)
        return receive_package(**{**args, **overrides})

    def test_two_nodes_preserve_exact_package_and_source_bytes(self):
        sent = publish_package(self.package, self.sender)
        before = sent.stat()
        staged = self.receive()
        self.assertEqual(staged.plan.disposition, 'EXACT_BINDING')
        self.assertEqual(staged.package, self.package)
        self.assertEqual(staged.path.read_bytes(), self.package.canonical_json.encode())
        self.assertEqual(staged.path.name, self.package.digest + '.json')
        self.assertEqual(staged.package.artifacts[0].payload, b'x + 1')
        self.assertEqual(sent.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(sorted(p.name for p in self.receiver.iterdir()), [sent.name])

    def test_retries_leave_existing_receiver_bytes_and_mtime_unchanged(self):
        publish_package(self.package, self.sender)
        first = self.receive()
        before = first.path.stat()
        second = self.receive()
        self.assertEqual(first, second)
        self.assertEqual(second.path.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(len(list(self.receiver.iterdir())), 1)

    def test_heterogeneous_exact_package_is_teaching_only(self):
        publish_package(self.package, self.sender)
        binding = replace(self.package.binding, topology_digest=digest('other topology'))
        staged = self.receive(binding=binding)
        self.assertEqual(staged.plan.disposition, 'TEACHING_ONLY')
        self.assertEqual(staged.package.artifacts[1].payload, b'1 -> 2')

    def test_incompatible_delta_never_creates_receiver(self):
        source, rights = snapshot(PackageKind.ADAPTER_DELTA)
        self.package = export_capability(source, source.signature, rights)
        publish_package(self.package, self.sender)
        binding = replace(self.package.binding, motif_key_map_digest=digest('other motif'))
        with self.assertPackageError('identical receiver binding'):
            self.receive(binding=binding)
        self.assertFalse(self.receiver.exists())

    def test_tampered_wire_does_not_create_receiver(self):
        sent = publish_package(self.package, self.sender)
        sent.write_bytes(sent.read_bytes() + b' ')
        with self.assertPackageError('digest'):
            self.receive()
        self.assertFalse(self.receiver.exists())

    def test_symlink_source_and_receiver_entries_are_refused(self):
        sent = publish_package(self.package, self.sender)
        target = self.root / 'target'
        sent.rename(target)
        sent.symlink_to(target)
        with self.assertPackageError('regular'):
            self.receive()
        sent.unlink()
        target.rename(sent)
        self.receiver.mkdir()
        (self.receiver / sent.name).symlink_to(sent)
        with self.assertPackageError('regular'):
            self.receive()
        self.assertEqual(sent.read_bytes(), self.package.canonical_json.encode())

    def test_wire_limit_fails_before_receiver_mutation(self):
        publish_package(self.package, self.sender)
        with self.assertPackageError('wire limit'):
            self.receive(max_wire_bytes=10)
        self.assertFalse(self.receiver.exists())

    def test_correct_hash_does_not_make_noncanonical_wire_valid(self):
        self.sender.mkdir()
        raw = self.package.canonical_json.encode() + b'\n'
        address = sha256(raw).hexdigest()
        (self.sender / (address + '.json')).write_bytes(raw)
        with self.assertPackageError('invalid package wire record'):
            self.receive(package_digest=address)
        self.assertFalse(self.receiver.exists())

    def test_concurrent_publication_converges_without_temporary_files(self):
        with ThreadPoolExecutor(max_workers=4) as pool:
            paths = list(pool.map(lambda _: publish_package(self.package, self.sender), range(8)))
        self.assertTrue(all(path == paths[0] for path in paths))
        self.assertEqual(paths[0].read_bytes(), self.package.canonical_json.encode())
        self.assertEqual([p.name for p in self.sender.iterdir()], [paths[0].name])

    def test_failed_file_flush_does_not_publish_and_can_retry(self):
        with patch('bilqis_mlx.runtime.cognitive_package.exchange.os.fsync',
                   side_effect=OSError('injected flush interruption')):
            with self.assertRaisesRegex(OSError, 'injected flush interruption'):
                publish_package(self.package, self.sender)
        self.assertEqual(list(self.sender.iterdir()), [])
        path = publish_package(self.package, self.sender)
        self.assertEqual(path.read_bytes(), self.package.canonical_json.encode())

    def test_directory_flush_failure_leaves_complete_retryable_publication(self):
        with patch('bilqis_mlx.runtime.cognitive_package.exchange._sync_directory',
                   side_effect=OSError('injected directory flush interruption')):
            with self.assertRaisesRegex(OSError, 'injected directory flush interruption'):
                publish_package(self.package, self.sender)
        published = self.sender / (self.package.digest + '.json')
        before = published.stat()
        self.assertEqual(published.read_bytes(), self.package.canonical_json.encode())
        self.assertEqual([p.name for p in self.sender.iterdir()], [published.name])
        self.assertEqual(publish_package(self.package, self.sender), published)
        self.assertEqual(published.stat().st_mtime_ns, before.st_mtime_ns)

    def test_failed_publication_leaves_no_partial_package_or_temporary_file(self):
        with patch('bilqis_mlx.runtime.cognitive_package.exchange.os.link',
                   side_effect=OSError('injected publish interruption')):
            with self.assertRaisesRegex(OSError, 'injected publish interruption'):
                publish_package(self.package, self.sender)
        self.assertEqual(list(self.sender.iterdir()), [])

    def test_conflicting_receiver_file_is_preserved(self):
        publish_package(self.package, self.sender)
        self.receiver.mkdir()
        existing = self.receiver / (self.package.digest + '.json')
        existing.write_bytes(b'existing unrelated bytes')
        before = existing.stat()
        with self.assertPackageError('conflict'):
            self.receive()
        self.assertEqual(existing.read_bytes(), b'existing unrelated bytes')
        self.assertEqual(existing.stat().st_mtime_ns, before.st_mtime_ns)

    def test_received_package_decodes_in_independent_process(self):
        publish_package(self.package, self.sender)
        staged = self.receive()
        script = '''
import sys
sys.path.insert(0,sys.argv[1])
from pathlib import Path
from bilqis_mlx.runtime.cognitive_package import CognitivePackage
p=CognitivePackage.from_canonical_json(Path(sys.argv[2]).read_text())
print(p.digest)
print(p.artifacts[0].payload.decode())
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
            str(Path(__file__).resolve().parents[4]), str(staged.path)],
            capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [self.package.digest, 'x + 1'])
