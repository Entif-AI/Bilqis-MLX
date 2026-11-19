"""Cold-resume binding for generation-zero foundation Factory authority."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.bamf_bundle import accepted_runtime as _accepted_runtime  # noqa: F401
from bilqis_mlx.runtime.bamf_bundle.accepted_execution_cache import (
    _require_initial_foundation_authority,
)
from bilqis_mlx.runtime.bamf_bundle.publication.factory_release import (
    _require_release_root_shape,
)


class FoundationColdResumeTests(TestCase):
    def test_lineage_with_run_identity_verifies_pinned_release_and_foundation(self):
        student = SimpleNamespace(run_identity=SimpleNamespace(
            factory_release_sha256="1" * 64))
        signed_foundation = Mock(return_value=("A.ONE", "A.TWO"))
        release = SimpleNamespace(
            require_foundation_capability_ids=signed_foundation)
        run_dir = Path("fixture-run")
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.publication.factory_release."
                "require_initial_factory_release",
                return_value=release) as require_release:
            _require_initial_foundation_authority(run_dir, student)
        require_release.assert_called_once_with(run_dir, student)
        signed_foundation.assert_called_once_with()

    def test_historical_bundle_without_run_identity_remains_readable_only(self):
        student = SimpleNamespace(run_identity=None)
        with patch(
                "bilqis_mlx.runtime.bamf_bundle.publication.factory_release."
                "require_initial_factory_release") as require_release:
            _require_initial_foundation_authority(Path("fixture-run"), student)
        require_release.assert_not_called()

    def test_cold_resume_allows_successor_release_artifacts_but_genesis_stays_strict(self):
        initial = "1" * 64
        successor = "2" * 64
        with TemporaryDirectory() as temporary:
            run_dir = Path(temporary)
            root = run_dir / "factory-releases"
            root.mkdir()
            (root / f"{initial}.json").write_text("{}")
            (root / f"{successor}.json").write_text("{}")
            _require_release_root_shape(
                run_dir, initial, allow_other_releases=True)
            with self.assertRaises(BilqisError):
                _require_release_root_shape(run_dir, initial)
