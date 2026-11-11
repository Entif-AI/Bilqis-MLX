"""R19 generation-zero pre-seal prefix and three-lock owner witness."""
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
import unittest

from bilqis_mlx.presentation.operator_cli.tests import test_bamf_atlas_release_create as atlas_create_tests
import bilqis_mlx.runtime.bamf_bundle.publication as publication
import bilqis_mlx.runtime.bamf_bundle.publication.retry as retry
import bilqis_mlx.runtime.bamf_bundle.publication.storage as storage


class BamfPresealRetryTests(unittest.TestCase):
    def _fixture(self):
        fixture = atlas_create_tests.BamfAtlasReleaseCreateTests(methodName="runTest")
        fixture.setUp()
        return fixture

    def _create(self, fixture, target: Path):
        manifest = fixture.manifest()
        with fixture.c07_create_context(), patch(
                "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                side_effect=AssertionError("pre-seal create is neural-inert")):
            return fixture.invoke([
            "--human-run", "--model-topology", str(atlas_create_tests.TOPOLOGY),
                "--atlas-release-manifest", str(manifest),
                "--run-dir", str(target), *fixture.FOUNDATION_ARGS,
            ])

    def test_lock_only_and_lock_plus_empty_stage_are_fresh_create_retry_prefixes(self):
        for include_stage in (False, True):
            fixture = self._fixture()
            try:
                target = fixture.root / ("prefix-stage" if include_stage else "prefix-lock")
                target.mkdir()
                (target / ".bamf-pointer.lock").write_bytes(b"")
                if include_stage:
                    (target / ".bamf-staging").mkdir()
                code, output, errors = self._create(fixture, target)
                self.assertEqual((code, errors), (0, ""))
                report = fixture.output_records(output)[-1]
                self.assertEqual(report["result"], "CREATED")
                self.assertEqual(report["neural_updates"], 0)
                self.assertTrue((target / "bamf-state.json").is_file())
            finally:
                fixture.tearDown()

    def test_preseal_prefix_resume_is_classification_only(self):
        for marker in ("lock", "stage"):
            fixture = self._fixture()
            try:
                target = fixture.root / ("resume-" + marker)
                target.mkdir()
                (target / ".bamf-pointer.lock").write_bytes(b"")
                if marker == "stage":
                    (target / ".bamf-staging").mkdir()
                before = tuple(sorted(path.name for path in target.iterdir()))
                with patch(
                        "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                        side_effect=AssertionError("resume cannot recover pre-seal prefixes")):
                    code, output, errors = fixture.invoke([
                        "--human-run", "--resume", "--run-dir", str(target),
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn("BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY", errors)
                self.assertEqual(tuple(sorted(path.name for path in target.iterdir())), before)
            finally:
                fixture.tearDown()

    def test_malformed_preseal_prefixes_fail_closed(self):
        for case in ("stage-only", "nonempty-stage"):
            fixture = self._fixture()
            try:
                target = fixture.root / case
                target.mkdir()
                stage = target / ".bamf-staging"
                stage.mkdir()
                if case == "nonempty-stage":
                    (target / ".bamf-pointer.lock").write_bytes(b"")
                    (stage / "partial").write_text("x", encoding="utf-8")
                code, output, errors = self._create(fixture, target)
                self.assertEqual((code, output), (2, ""))
                self.assertIn("BLOCKED", errors)
                self.assertFalse((target / "bamf-state.json").exists())
            finally:
                fixture.tearDown()

    def test_generation_zero_owner_crosses_three_durable_pointer_lock_boundaries(self):
        fixture = self._fixture()
        try:
            target = fixture.root / "three-locks"
            entries = []
            real = storage._initial_generation_pointer_lock

            @contextmanager
            def observed(run_dir):
                with real(run_dir):
                    entries.append((Path(run_dir), (Path(run_dir) / ".bamf-pointer.lock").is_file()))
                    yield

            with patch.object(retry, "_initial_generation_pointer_lock", observed), \
                    patch.object(publication, "_initial_generation_pointer_lock", observed):
                code, _output, errors = self._create(fixture, target)
            self.assertEqual((code, errors), (0, ""))
            self.assertEqual(len(entries), 3)
            canonical_target = target.resolve()
            self.assertTrue(all(
                run.resolve() == canonical_target and durable for run, durable in entries))
        finally:
            fixture.tearDown()

    def test_real_owner_crash_prefixes_resume_reject_and_fresh_create_converges(self):
        crash_points = (
            ("after-retry-lock", "_parent_acceptance_for_publication", False),
            ("after-parent-lock", "_stage", False),
            ("after-stage", "_save_publication_bundle", True),
        )
        for label, owner, expects_stage in crash_points:
            fixture = self._fixture()
            try:
                target = fixture.root / label
                with patch.object(publication, owner, side_effect=RuntimeError(label)):
                    code, output, _errors = self._create(fixture, target)
                self.assertEqual((code, output), (2, ""))
                self.assertTrue((target / ".bamf-pointer.lock").is_file())
                self.assertEqual((target / ".bamf-staging").is_dir(), expects_stage)
                if expects_stage:
                    self.assertEqual(tuple((target / ".bamf-staging").iterdir()), ())

                with patch(
                        "bilqis_mlx.presentation.operator_cli.command._invoke_learner",
                        side_effect=AssertionError("resume cannot recover crash prefixes")):
                    code, output, errors = fixture.invoke([
                        "--human-run", "--resume", "--run-dir", str(target),
                    ])
                self.assertEqual((code, output), (2, ""))
                self.assertIn("BAMF_OPERATOR_INTERRUPTED_GENESIS_REQUIRES_CREATE_RETRY", errors)

                code, output, errors = self._create(fixture, target)
                self.assertEqual((code, errors), (0, ""))
                report = fixture.output_records(output)[-1]
                self.assertEqual(report["result"], "CREATED")
                self.assertEqual(report["neural_updates"], 0)
            finally:
                fixture.tearDown()


if __name__ == "__main__":
    unittest.main()
