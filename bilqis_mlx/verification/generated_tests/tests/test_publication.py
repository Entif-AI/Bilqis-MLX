"""Immutable generated releases recover from interrupted pointer publication."""
import hashlib
import unittest
from unittest.mock import patch
from bilqis_mlx.verification.generated_tests import publication
from bilqis_mlx.verification.generated_tests.tests.helpers import boolean_release_fixture, publish


class PublicationTests(unittest.TestCase):
    def test_exact_pre_refactor_artifact_bytes_and_idempotent_restart(self):
        with boolean_release_fixture() as (parity, root):
            manifest = publish(parity, root)
            first = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in root.rglob('*.json')}
            self.assertEqual(first, {
                'current.json': '783d800fa4ca869a17e01fde770f341bd72b511643c785fdc641a631d5194f04',
                'releases/4b0cbf0f5e8d722ea58203d12765dceeb837fd9456ddcead66c26fd7f2c295f3/manifest.json':
                    '77341dbf16dd08fc557ebfa22a7573775f64c083bb63f0327b545c04d5fa4d1b',
                'releases/4b0cbf0f5e8d722ea58203d12765dceeb837fd9456ddcead66c26fd7f2c295f3/suites/boolean.constants.json':
                    '51ae566791ad9bc66925ed0fc146ef3dddcc76e9513ab5716041773bfd9e4f08'})
            self.assertEqual(publish(parity, root), manifest)
            self.assertEqual({str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in root.rglob('*.json')}, first)

    def test_failed_pointer_replace_preserves_prior_release_and_retry_converges(self):
        with boolean_release_fixture() as (parity, root):
            first = publish(parity, root)
            pointer = (root / 'current.json').read_bytes()
            with patch.object(publication.os, 'replace', side_effect=OSError('injected-pointer-failure')):
                with self.assertRaisesRegex(OSError, 'injected-pointer-failure'):
                    publish(parity, root, seed=98)
            self.assertEqual((root / 'current.json').read_bytes(), pointer)
            later = publish(parity, root, seed=98)
            self.assertNotEqual(later['release_sha256'], first['release_sha256'])
            self.assertEqual(publication.status(parity, root,
                selector='family:boolean.constants')['release_sha256'], later['release_sha256'])
