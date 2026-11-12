"""C16.3 persistent BAMF operator routing contracts."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session import (
    _execution_context, _visit, operate_bamf,
)


class BamfOperatorRoutingTests(unittest.TestCase):
    def test_execution_context_uses_accepted_release_without_requiring_c07_lease(self):
        parent = object()
        context = object()
        host = SimpleNamespace(source_context=lambda **_kwargs: context)
        receipt = SimpleNamespace(
            source_atlas_bundle_id="atlas",
            source_release_sha256="release",
            source_source_bundle_id="source",
        )
        accepted = SimpleNamespace(receipt=receipt, construction_predecessor="predecessor")
        selection = SimpleNamespace(path="/atlas")
        authenticated = SimpleNamespace(features="features")
        feature = SimpleNamespace(path="/feature")
        with patch(
                "bilqis_mlx.runtime.bamf_operator.session.load_accepted_generation",
                return_value=parent), patch(
                "bilqis_mlx.runtime.bamf_operator.session.AcceptedRuntimeHost",
                return_value=host), patch(
                "bilqis_mlx.runtime.bamf_operator.session.read_accepted_generation_feature_context",
                return_value=accepted), patch(
                "bilqis_mlx.runtime.bamf_operator.session.AtlasArtifactIdentity",
                return_value="identity"), patch(
                "bilqis_mlx.runtime.bamf_operator.session.resolve_atlas_artifact_selection",
                return_value=selection), patch(
                "bilqis_mlx.runtime.bamf_operator.session.authenticate_bamf_execution_feature_context",
                return_value=authenticated), patch(
                "bilqis_mlx.runtime.bamf_operator.session.persist_feature_manifest",
                return_value=feature):
            self.assertEqual(
                _execution_context(Path("/run")),
                (parent, context, "/atlas", "/feature"))

    def test_priority_hold_never_counts_as_a_neural_visit(self):
        with TemporaryDirectory() as temporary:
            current = SimpleNamespace(
                generation=4, retained_state=SimpleNamespace(optimizer_step=11))
            with patch(
                    "bilqis_mlx.runtime.bamf_operator.session._visit",
                    return_value="HELD") as visit, patch(
                    "bilqis_mlx.runtime.bamf_operator.session.load_accepted_generation",
                    return_value=current):
                result = operate_bamf(
                    temporary, minutes=1, max_visits=3, reserve_gib=0.0)
        self.assertEqual(result.status, "PRIORITY_HOLD")
        self.assertEqual(result.visits, 0)
        self.assertEqual(result.accepted, 0)
        self.assertEqual(result.rejected, 0)
        visit.assert_called_once()

    def test_no_admissible_priority_selection_never_executes_candidate(self):
        parent = SimpleNamespace()
        context = SimpleNamespace(release=object())
        held = SimpleNamespace(status="NO_ADMISSIBLE_TEACHING")
        with patch(
                "bilqis_mlx.runtime.bamf_operator.session._execution_context",
                return_value=(parent, context, "atlas", "feature")), patch(
                "bilqis_mlx.runtime.bamf_operator.session.schedule_program_from_executable_release",
                return_value="program"), patch(
                "bilqis_mlx.runtime.bamf_operator.session.accepted_priority_school",
                return_value="school"), patch(
                "bilqis_mlx.runtime.bamf_operator.session.select_foundation_priority_visit",
                return_value=held), patch(
                "bilqis_mlx.runtime.bamf_operator.session.execute_accepted_priority_candidate",
                side_effect=AssertionError("optimizer candidate must not run")):
            self.assertEqual(_visit("/run", 0.0), "HELD")


if __name__ == "__main__":
    unittest.main()
