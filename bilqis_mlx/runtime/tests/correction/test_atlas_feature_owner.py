"""C09 Atlas-feature dependency custody for FeatureSchema transforms."""
import unittest

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_artifact_owner import AtlasFeatureArtifactOwner
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    _SOURCE_OWNER, _TEST_PUBLIC, _event, _result,
)
from bilqis_mlx.semantics.atlas_features import (
    FEATURE_MANIFEST_OPERATOR_ID,
    AtlasFeatures,
    FeatureSchema,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


_ADAPTER_ID = "source.micro.boolean-connectives/v1"
_SCHEMA_ID = "frame:urn:concept:A"


def _features() -> AtlasFeatures:
    return AtlasFeatures(
        semantic_release="a" * 64,
        atlas_bundle_id="b" * 64,
        source_bundle_id="c" * 64,
        predecessor_digest=None,
        type_map=(),
        role_map=(("left", 1), ("right", 2)),
        schema_map=((_SCHEMA_ID, 1),),
        concepts=(),
        held_reasons=(),
    )


def _schema() -> FeatureSchema:
    return FeatureSchema(
        ("left", "right"),
        (_SCHEMA_ID,),
        source_bindings=((_SCHEMA_ID, _ADAPTER_ID),),
    )


def _operator_authority() -> SourceAuthorityRegistry:
    return SourceAuthorityRegistry((SourceAuthorityKey(
        _SOURCE_OWNER,
        _TEST_PUBLIC,
        tuple(sorted((
            SourceAuthorityScope(DependencyKind.ARTIFACT, "atlas-feature:"),
            SourceAuthorityScope(DependencyKind.OPERATOR, "operator:"),
        ), key=lambda scope: (scope.kind.value, scope.key_prefix))),
    ),))


class AtlasFeatureArtifactOwnerTests(unittest.TestCase):
    def _assert_operator_correction_holds_then_equal_revalidation_stops(
        self, dependency: DependencyRef,
    ) -> None:
        features = _features()
        owner = AtlasFeatureArtifactOwner(features, _schema())
        self.assertIn(dependency, owner.current_node.immediate_dependencies)

        authority = _operator_authority()
        event = _event(dependency)
        queue = owner.apply_correction(event, authority)
        self.assertEqual(
            queue.held_artifact_ids,
            (owner.current_node.artifact_id,),
        )
        with self.assertRaises(BilqisError) as caught:
            owner.require(features)
        self.assertEqual(
            caught.exception.context["reason"],
            "BAMF_C09_ARTIFACT_HELD",
        )

        node = owner.current_node
        progress = owner.advance(
            _result(
                node,
                digest=node.content_digest,
                correction=event,
            ),
            authority,
        )
        self.assertEqual(progress.queue.pending, ())
        self.assertEqual(progress.queue.held_artifact_ids, ())
        self.assertIs(owner.require(features), owner.current_node)

    def test_manifest_operator_correction_holds_then_equal_revalidation_stops(self):
        self._assert_operator_correction_holds_then_equal_revalidation_stops(
            DependencyRef(
                DependencyKind.OPERATOR,
                "operator:" + FEATURE_MANIFEST_OPERATOR_ID,
            ),
        )

    def test_source_binding_operator_correction_holds_then_equal_revalidation_stops(self):
        adapter = DependencyRef(
            DependencyKind.OPERATOR,
            "operator:" + _ADAPTER_ID,
        )
        owner = AtlasFeatureArtifactOwner(_features(), _schema())
        operator_dependencies = tuple(
            ref for ref in owner.current_node.immediate_dependencies
            if ref.kind is DependencyKind.OPERATOR
        )

        self.assertIn(adapter, operator_dependencies)
        self.assertTrue(any(
            ref.key.startswith("operator:atlas-feature-schema:")
            for ref in operator_dependencies
        ))
        self._assert_operator_correction_holds_then_equal_revalidation_stops(adapter)


if __name__ == "__main__":
    unittest.main()
