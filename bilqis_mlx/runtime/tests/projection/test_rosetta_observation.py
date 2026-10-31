"""Opt-in native Rosetta owner consumption; no service or graph writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from dataclasses import replace

from bilqis_mlx.runtime.rosetta_observation import RosettaRuntime, project_rosetta_observation
from bilqis_mlx.runtime.tests.projection.test_bamf_projection import _contract, _projected, _event
from bilqis_mlx.errors import BilqisError


class RosettaObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get('BILQIS_ROSETTA_CONTRACT_ROOT')
        if not configured:
            raise unittest.SkipTest('explicit Rosetta contract workspace required')
        root = Path(configured)
        cls.root = root
        cls.directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.directory.cleanup)
        cls.bundle = Path(cls.directory.name) / 'bridge.cjs'
        cls.revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
        if cls.revision != 'ce41904be268a9bfd6b7095e79a5cb83b6c5e8b3':
            raise AssertionError('Rosetta owner revision drift requires requalification')
        subprocess.run(['git', 'diff', '--exit-code', 'HEAD', '--',
            'packages/rosetta-core', 'packages/rosetta-canon', 'packages/rosetta-cid'],
            cwd=root, check=True, capture_output=True)

        subprocess.run([str(root / 'node_modules/.bin/esbuild'),
            str(Path(__file__).resolve().parents[4] / 'scripts/operations/c10_rosetta_owner_bridge.ts'),
            '--bundle', '--platform=node', '--format=cjs', '--conditions=@entif-ai/source',
            '--alias:@entif-ai/rosetta-core=' + str(root / 'packages/rosetta-core/src/index.ts'),
            '--define:__ROSETTA_SOURCE_REVISION__=' + repr(cls.revision).replace("'", '"'),
            '--outfile=' + str(cls.bundle)], cwd=root, check=True, capture_output=True)
        cls.runtime = RosettaRuntime('node', cls.bundle,
            hashlib.sha256(cls.bundle.read_bytes()).hexdigest(), cls.revision)

    def test_native_owner_identity_rebuild_and_compact_private_safe_payload(self):
        event = _projected(_event('private:subject:not-for-signal'), _contract(Path('/unused/outbox')))
        result = project_rosetta_observation(event, self.runtime, created_at='2026-10-29T12:00:00.000Z')
        repeated = project_rosetta_observation(event, self.runtime, created_at='2026-10-29T12:00:00.000Z')
        self.assertEqual(result, repeated)
        self.assertTrue(result.tile['cid'].startswith('cidv1-sha256-'))
        self.assertEqual(result.tile['kind'], 'rosetta.observation')
        self.assertEqual(result.tile['createdAt'], '2026-10-29T12:00:00.000Z')
        self.assertEqual(result.tile['parents'], [])
        self.assertNotIn('private:subject:not-for-signal', result.tile['canonical'])
        changed = project_rosetta_observation(replace(event, rights_digest='f' * 64), self.runtime,
            created_at='2026-10-29T12:00:00.000Z')
        self.assertNotEqual(result.tile['cid'], changed.tile['cid'])

    def test_runtime_integrity_timestamp_and_unsafe_integer_reject(self):
        event = _projected(_event('capability:one'), _contract(Path('/unused/outbox')))
        with self.assertRaises(BilqisError):
            project_rosetta_observation(event, replace(self.runtime, bridge_sha256='0' * 64),
                created_at='2026-10-29T12:00:00.000Z')
        for stamp in ('invalid', '2026-99-99T00:00:00Z'):
            with self.subTest(stamp=stamp), self.assertRaises(BilqisError):
                project_rosetta_observation(event, self.runtime, created_at=stamp)
        with self.assertRaises(BilqisError):
            project_rosetta_observation(replace(event, as_of=2**53), self.runtime,
                created_at='2026-10-29T12:00:00.000Z')

    def test_native_integrity_rejects_tamper_and_adapter_rejects_wrong_output(self):
        event = _projected(_event('capability:one'), _contract(Path('/unused/outbox')))
        result = project_rosetta_observation(event, self.runtime, created_at='2026-10-29T12:00:00.000Z')
        probe = Path(self.directory.name) / 'verify.ts'
        probe.write_text("import {verifyTileIntegrity} from '@entif-ai/rosetta-core';\n"
                         "import {readFileSync} from 'node:fs';\n"
                         "process.stdout.write(JSON.stringify(verifyTileIntegrity(JSON.parse(readFileSync(0,'utf8'))).ok));\n")
        executable = probe.with_suffix('.cjs')
        subprocess.run([str(self.root / 'node_modules/.bin/esbuild'), str(probe), '--bundle',
            '--platform=node', '--format=cjs', '--conditions=@entif-ai/source',
            '--alias:@entif-ai/rosetta-core=' + str(self.root / 'packages/rosetta-core/src/index.ts'),
            '--outfile=' + str(executable)], cwd=self.root, check=True, capture_output=True)
        tile = result.tile
        tile['payload']['signal'] = 'tampered'
        output = subprocess.check_output(['node', str(executable)], input=json.dumps(tile), text=True)
        self.assertEqual(output, 'false')
        response = dict(schema='bilqis.c10.rosetta-observation-response/v1',
            owner_revision=self.revision, verified=True, tile=result.tile)
        response['tile']['payload']['source'] = 'wrong-binding'
        bad = Path(self.directory.name) / 'bad.cjs'
        bad.write_text('process.stdout.write(' + json.dumps(json.dumps(response)) + ');')
        runtime = replace(self.runtime, bridge_path=bad, bridge_sha256=hashlib.sha256(bad.read_bytes()).hexdigest())
        with self.assertRaises(BilqisError):
            project_rosetta_observation(event, runtime, created_at='2026-10-29T12:00:00.000Z')
