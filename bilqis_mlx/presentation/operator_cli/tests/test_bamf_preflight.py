"""Real BAMF CLI configuration inspection stays held, read-only and neural-inert."""
from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx.cli import main, parse_args

ROOT = Path(__file__).resolve().parents[4]
TOPOLOGY = ROOT / 'configs/models/bamf-0.2.json'


class BamfPreflightTests(unittest.TestCase):
    def invoke(self, extra):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(['train', '--dry-run', '--model-topology', str(TOPOLOGY), *extra])
        return code, output.getvalue(), errors.getvalue()

    def test_actual_v2_dry_run_reports_topology_without_creating_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            run = Path(tmp) / 'new'
            code, output, _ = self.invoke(['--run-dir', str(run), '--source-prefetch-workers', '0'])
            self.assertEqual(code, 2)
            report = json.loads(output)
            self.assertEqual(report['schema'], 'bilqis.bamf.operator-preflight/v1')
            self.assertEqual(report['result'], 'HELD_PENDING_SOURCE_AND_GENERATION_AUTHORITY')
            self.assertEqual(report['model_topology']['schema'], 'bilqis.mlx.model-topology/v2')
            self.assertEqual(report['model_topology']['architecture_id'], 'bamf-atlas-v2')
            self.assertEqual(report['model_topology']['digest'],
                             '4ea0a04087596dc243a667ed17138ff0ffb3df8b4339759ddf533cdad7e0bd96')
            self.assertEqual(report['source_prefetch_workers'], 0)
            self.assertTrue(report['retention_enabled'])
            self.assertFalse(report['ready_for_training'])
            self.assertEqual(report['neural_updates'], 0)
            self.assertFalse(run.exists())

    def test_manifest_is_an_opaque_unqualified_reference_not_a_lease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = root / 'manifest.json'
            raw = b'{"unqualified-source-reference":true}\n'
            manifest.write_bytes(raw)
            before = manifest.stat()
            code, output, _ = self.invoke(['--run-dir', str(root / 'new'),
                '--admission-policy', 'atlas-release', '--atlas-release-manifest', str(manifest)])
            self.assertEqual(code, 2)
            report = json.loads(output)
            self.assertEqual(report['admission_policy'], 'atlas-release')
            self.assertEqual(report['atlas_release_manifest']['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(report['atlas_release_manifest']['qualification'], 'NOT_VERIFIED')
            self.assertEqual(manifest.read_bytes(), raw)
            self.assertEqual(manifest.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['manifest.json'])

    def test_missing_or_policy_conflicting_manifest_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            for extra in (['--admission-policy', 'atlas-release'],
                          ['--atlas-release-manifest', str(Path(tmp) / 'missing')]):
                with self.subTest(extra=extra):
                    code, output, errors = self.invoke(['--run-dir', tmp, *extra])
                    self.assertEqual(code, 2)
                    self.assertEqual(output, '')
                    self.assertIn('BLOCKED', errors)

    def test_saved_v1_is_never_coerced_to_v2_or_modified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = root / 'state.json'
            state.write_bytes(b'protected-v1-lineage-not-for-this-reader')
            before = state.stat()
            with patch('bilqis_mlx.presentation.operator_cli.command._invoke_learner',
                       side_effect=AssertionError('no optimizer')):
                code, _, errors = self.invoke(['--run-dir', tmp, '--resume'])
            self.assertEqual(code, 2)
            self.assertIn('BLOCKED', errors)
            self.assertEqual(state.read_bytes(), b'protected-v1-lineage-not-for-this-reader')
            self.assertEqual(state.stat().st_mtime_ns, before.st_mtime_ns)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ['state.json'])

    def test_parser_keeps_human_and_prefetch_controls(self):
        args = parse_args(['train', '--dry-run', '--human-run', '--source-prefetch-workers', '1',
                          '--atlas-release-manifest', '/manifest.json'])
        self.assertTrue(args.human_run)
        self.assertEqual(args.source_prefetch_workers, 1)
        self.assertEqual(args.atlas_release_manifest, Path('/manifest.json'))

    def test_fresh_process_can_inspect_without_mlx_or_run_writes(self):
        script = '''
import importlib.abc,sys
class NoMlx(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'mlx' or fullname.startswith('mlx.'):
            raise ModuleNotFoundError('no MLX during configuration inspection')
        return None
sys.meta_path.insert(0,NoMlx())
sys.path.insert(0,sys.argv[1])
from bilqis_mlx.cli import main
raise SystemExit(main(['train','--dry-run','--model-topology',sys.argv[2],'--run-dir',sys.argv[3]]))
'''
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-I', '-B', '-c', script,
                str(ROOT), str(TOPOLOGY), str(Path(tmp) / 'new')],
                text=True, capture_output=True, timeout=20)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)['neural_updates'], 0)
            self.assertEqual(list(Path(tmp).iterdir()), [])
