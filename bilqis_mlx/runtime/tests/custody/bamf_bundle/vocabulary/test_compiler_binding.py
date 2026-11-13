"""A02 parameter-extension compiler authority follows the admitted Factory release."""
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.tests.executable_release.support import ReleaseTestSupport
from bilqis_mlx.runtime.bamf_bundle.records import BamfBundleCandidate
from bilqis_mlx.runtime.bamf_bundle.vocabulary.compiler_binding import (
    bind_parameter_extension_compiler_state,
    parameter_extension_inert_compiler_state,
    verify_parameter_extension_compiler_state,
)
from bilqis_mlx.runtime.state import _fingerprint


class ParameterExtensionCompilerBindingTests(ReleaseTestSupport):
    @staticmethod
    def _candidate():
        compiler = {
            "schema": "bilqis.mlx.bamf-compiler-features/v1",
            "factor_map_sha256": "f" * 64,
            "compiler_sha256": "0" * 64,
            "rights_epoch": 7,
            "correction_generation": 3,
            "factory_release_sha256": "1" * 64,
            "factory_semantic_catalog_sha256": "2" * 64,
            "factory_semantic_graph_sha256": "3" * 64,
            "factory_semantic_catalog": {"tokens": ["legacy.token"]},
            "factory_grade_ids": ["legacy-grade"],
            "feature_source": {
                "atlas_bundle_id": "4" * 64,
                "release_sha256": "5" * 64,
                "source_bundle_id": "6" * 64,
            },
            "feature_schema": {
                "role_ids": [], "schema_ids": [], "source_bindings": [],
            },
        }
        return BamfBundleCandidate(
            "run", 1, "a" * 64, "b" * 64,
            object(), object(), object(), object(), object(),
            {}, compiler, {}, {}, {}, {}, (), None,
        )

    def test_rebind_changes_only_factory_release_compiler_authority(self):
        release = self.compile()
        candidate = self._candidate()

        rebound = bind_parameter_extension_compiler_state(
            candidate, release, self.graph)

        self.assertEqual(
            parameter_extension_inert_compiler_state(rebound.compiler_features),
            parameter_extension_inert_compiler_state(candidate.compiler_features),
        )
        self.assertEqual(
            rebound.compiler_features["factory_release_sha256"],
            release.release_sha256,
        )
        self.assertEqual(
            rebound.compiler_features["factory_semantic_catalog_sha256"],
            release.semantic_catalog_sha256,
        )
        self.assertEqual(
            rebound.compiler_features["factory_semantic_graph_sha256"],
            _fingerprint(self.graph),
        )
        self.assertEqual(
            rebound.compiler_features["factory_grade_ids"],
            [grade.grade_id for grade in release.execution_plan.grades],
        )
        self.assertEqual(rebound.compiler_features["factory_semantic_catalog"], self.graph)
        self.assertIsNot(rebound.compiler_features["factory_semantic_catalog"], self.graph)
        verify_parameter_extension_compiler_state(rebound.compiler_features, release)

    def test_rebound_semantic_graph_tamper_fails_closed(self):
        release = self.compile()
        rebound = bind_parameter_extension_compiler_state(
            self._candidate(), release, self.graph)
        tampered = dict(rebound.compiler_features)
        tampered["factory_semantic_catalog"] = {"tokens": ["tampered.token"]}

        with self.assertRaises(BilqisError):
            verify_parameter_extension_compiler_state(tampered, release)


if __name__ == "__main__":
    unittest.main()
