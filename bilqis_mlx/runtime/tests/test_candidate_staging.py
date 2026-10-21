from pathlib import Path
import json
import tempfile
import unittest

from bilqis_mlx.factory.tests.test_candidate_staging import CandidateStagingFixture
from bilqis_mlx.factory.jit_curriculum import ProposalDisposition
from bilqis_mlx.factory.autonomy import compile_autonomy_plan, initial_evidence_ledger
from bilqis_mlx.runtime.candidate_staging import load_staged_candidates, persist_staged_candidate


class StagedCandidateCustodyTests(CandidateStagingFixture, unittest.TestCase):
    def test_previous_provider_package_is_preserved_but_cannot_compete_with_current_code(self):
        from dataclasses import replace
        from bilqis_mlx.factory.adapters import SourceAdapterRegistry, RegisteredSourceAdapter
        staged = self.stage()
        original = self.fixture.fixture.registry.require("fixture.z-generator/v1", "fixture.z-oracle/v1")
        changed = SourceAdapterRegistry((RegisteredSourceAdapter(
            replace(original.descriptor, implementation_sha256="f" * 64),
            original.draw, original.check),))
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = persist_staged_candidate(root, staged, self.frontier, self.current)
            self.assertEqual(load_staged_candidates(root, self.frontier, self.current,
                                                   source_registry=changed), ())
            self.assertTrue(path.is_file())
            self.assertEqual(load_staged_candidates(root, self.frontier, self.current,
                source_registry=self.fixture.fixture.registry), (staged,))

    def test_cold_read_is_idempotent_and_detects_content_tampering(self):
        staged = self.stage()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = persist_staged_candidate(root, staged, self.frontier, self.current)
            self.assertEqual(persist_staged_candidate(
                root, staged, self.frontier, self.current), path)
            self.assertEqual(load_staged_candidates(
                root, self.frontier, self.current), (staged,))
            value = json.loads(path.read_text())
            value["candidate_id"] = "candidate-reserve"
            path.write_text(json.dumps(value))
            with self.assertRaisesRegex(ValueError, "CANDIDATE_STAGING_DIGEST_MISMATCH"):
                load_staged_candidates(root, self.frontier, self.current)

    def test_symlinked_autonomy_directory_cannot_receive_artifacts(self):
        staged = self.stage()
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as external:
            root = Path(temp)
            (root / "autonomy").symlink_to(external, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "CANDIDATE_STAGING_PATH_UNSAFE"):
                persist_staged_candidate(root, staged, self.frontier, self.current)
            self.assertEqual(list(Path(external).iterdir()), [])

    def test_source_frontier_handoff_loads_staged_successor(self):
        from unittest.mock import patch
        from bilqis_mlx.curriculum.scheduler import Checkpoint
        from bilqis_mlx.runtime.autonomy_live import LiveAutonomySession

        staged = self.stage()
        plan = compile_autonomy_plan(self.current)
        ledger = initial_evidence_ledger(self.current, plan=plan)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            persist_staged_candidate(root, staged, self.frontier, self.current)
            session = LiveAutonomySession(root, root, self.current, plan, ledger)
            with patch("bilqis_mlx.factory.candidate_frontier.load_candidate_frontier",
                       return_value=self.frontier), patch(
                       "bilqis_mlx.runtime.autonomy_live.live_source_registry",
                       return_value=self.fixture.fixture.registry):
                proposal, relative = session.propose_source_frontier_work(
                    Checkpoint("e" * 64, "bundles/fixture", 0, True))
            self.assertEqual(proposal.disposition, ProposalDisposition.PROPOSAL)
            self.assertEqual(json.loads((root / relative).read_text())[
                "selected_successor_sha256"], staged.successor.release_sha256)
