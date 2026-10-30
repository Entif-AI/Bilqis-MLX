"""Human option parsing and the actual unleased frontier routing seam."""
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bilqis_mlx import cli
from bilqis_mlx.runtime import operating_loop, release_adoption
from bilqis_mlx.runtime.atlas_admission import stage_unleased_atlas_proposal
from bilqis_mlx.runtime.tests.admission.test_atlas_admission import _lease
from bilqis_mlx.runtime.tests import test_jit_adoption as native_fixture
from dataclasses import asdict


class AtlasAdmissionCommandTests(unittest.TestCase):
    def test_cli_request_rejects_before_topology_or_learner_initialization(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            scope = root / 'scope.json'
            scope.write_text(json.dumps(asdict(_lease())))
            args = cli.parse_args(['train', '--human-run', '--admission-policy', 'atlas-release',
                                   '--atlas-admission-scope', str(scope), '--run-dir', str(root / 'run')])
            self.assertEqual(args.admission_policy, 'atlas-release')
            with patch('bilqis_mlx.runtime.topology_lifecycle.topology_from_file',
                       side_effect=AssertionError('learner topology entered')), redirect_stderr(StringIO()) as log:
                self.assertEqual(cli._main(args), 2)
            self.assertIn('BAMF_ATLAS_ADMISSION', log.getvalue())
            self.assertFalse((root / 'run').exists())
            self.assertEqual(cli.parse_args(['train']).admission_policy, 'staged')

    def test_actual_frontier_helper_stages_idempotently_without_native_adopter(self):
        fixture = native_fixture.JitAdoptionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.addCleanup(fixture.fixture.doCleanups)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            saved = root / 'state.json'
            saved.write_text('{"fixture":"unchanged"}')
            before = saved.read_bytes()
            records = []
            with patch.object(release_adoption, '_adopt_jit_proposal',
                              side_effect=AssertionError('unleased adoption')):
                reason = operating_loop._stage_atlas_frontier_attempt(root, {'generation': 1},
                    fixture.proposal, 'autonomy/proposals/fixture.json',
                    record=lambda path, event: records.append(event))
            first = stage_unleased_atlas_proposal(root, fixture.proposal)
            second = stage_unleased_atlas_proposal(root, fixture.proposal)
            self.assertEqual(first, second)
            self.assertEqual(reason, 'ATLAS_ADMISSION_STAGED')
            self.assertEqual(records[0]['proposal_sha256'], fixture.proposal.proposal_sha256)
            self.assertEqual(records[0]['actual_neural_updates'], 0)
            self.assertEqual(saved.read_bytes(), before)
            self.assertEqual(len(tuple((root / 'autonomy/atlas-admission/staged').glob('*.json'))), 1)
