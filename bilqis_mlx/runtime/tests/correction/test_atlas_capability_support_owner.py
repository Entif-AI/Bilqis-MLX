"""C09 capability-support provenance and accepted-lineage tests."""
from __future__ import annotations

import json
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.runtime.atlas_capability_support_owner import CapabilitySupportArtifactOwner
from bilqis_mlx.runtime.capability_support_loading import accepted_support_census
from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
    apply_capability_support_correction,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, derive_successor_bundle, load_accepted_generation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    retention_decision, shape_patch,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _SOURCE_OWNER, _TEST_PUBLIC, _event, _ref,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef

from .capability_support_owner_support import (
    CapabilitySupportOwnerFixture, GENERATION, IMMEDIATE_DEPENDENCIES, SOURCE_ROW,
    TARGET, source_qualified_state,
)


class CapabilitySupportOwnerTests(CapabilitySupportOwnerFixture):
    def test_b13_acceptance_persists_exact_source_anchor_and_materializes_owner(self):
        published, authority = self.publish_support()
        acceptance_path = (
            self.run / "bamf-acceptance" / f"{published['manifest_sha256']}.json")
        record = json.loads(acceptance_path.read_text())
        self.assertEqual(record["source_anchors"][0][0], TARGET)
        self.assertEqual(record["source_anchors"][0][1], SOURCE_ROW)
        self.assertEqual(record["source_anchors"][0][2], authority.source_row_sha256)
        self.assertEqual(record["source_anchors"][0][8], authority.digest)
        self.assertEqual(
            tuple(map(tuple, record["source_anchors"][0][9])),
            tuple((ref.kind.value, ref.key)
                  for ref in authority.immediate_dependencies))

        owner = self.load_support()
        self.assertEqual(owner.support.source_anchor_ids, (SOURCE_ROW,))
        self.assertEqual(
            owner.support.retained_generation_sha256,
            published["manifest_sha256"])
        self.assertIn(
            DependencyRef(DependencyKind.SOURCE, SOURCE_ROW),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.SOURCE,
                "source-proof:" + authority.digest,
            ),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.RELEASE,
                "source-generation:" + GENERATION,
            ),
            owner.current_node.immediate_dependencies)
        self.assertIn(
            DependencyRef(
                DependencyKind.SOURCE,
                "training-batch:" + authority.training_batch_sha256,
            ),
            owner.current_node.immediate_dependencies)
        for dependency in IMMEDIATE_DEPENDENCIES:
            self.assertIn(dependency, owner.current_node.immediate_dependencies)
        self.assertEqual(
            self.load_support().support,
            owner.support)
        with self.assertRaises(BilqisError):
            CapabilitySupportArtifactOwner()

    def test_operator_correction_holds_lossless_learned_support(self):
        self.publish_support()
        authority = SourceAuthorityRegistry((SourceAuthorityKey(
            _SOURCE_OWNER,
            _TEST_PUBLIC,
            (SourceAuthorityScope(DependencyKind.OPERATOR, "operator:"),),
        ),))
        owner = self.load_support(authority)
        dependency = next(
            ref for ref in owner.current_node.immediate_dependencies
            if ref.kind is DependencyKind.OPERATOR)
        self.assertTrue(apply_capability_support_correction(
            owner, _event(dependency), authority))
        with self.assertRaises(BilqisError) as caught:
            owner.require(TARGET)
        self.assertEqual(
            caught.exception.context["reason"], "BAMF_C09_ARTIFACT_HELD")

    def test_retained_capability_provenance_survives_unrelated_successor_acceptance(self):
        first, _authority_a = self.publish_support()
        first_manifest = first["manifest_sha256"]
        with shape_patch():
            accepted_parent = load_accepted_generation(self.run)
        capability_b = "capability:unrelated-b"
        source_b = "source:capability-support:row-b"
        parent_state_b, transaction_b, retained_b, _authority_b = source_qualified_state(
            accepted_parent.retained_state,
            capability=capability_b,
            source_row=source_b,
            source_family="source-family:capability-support-b",
            episode="episode:capability-support-b",
            generation_binding="6" * 64,
        )
        successor = derive_successor_bundle(
            accepted_parent,
            retained_b,
            parent_manifest_sha256=first_manifest,
            delivery_events=({"event": "FIXTURE_SUCCESSOR_B"},),
        )
        decision = retention_decision(parent=parent_state_b, retained=retained_b)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            second = accept_and_publish(
                self.run, successor, retained_b, decision=decision,
                feature_sha256=successor.extents.factor_map_digest,
                training_authorities=transaction_b.training_authorities,
            )

        with shape_patch():
            ledger, _nodes = accepted_support_census(
                self.run, second["manifest_sha256"])
        self.assertEqual(
            tuple(item.capability_id for item in ledger.capabilities),
            (TARGET, capability_b),
        )
        inherited = self.load_support(AUTHORITY)
        self.assertEqual(inherited.support.source_anchor_ids, (SOURCE_ROW,))
        self.assertEqual(
            inherited.support.retained_generation_sha256,
            first_manifest,
        )
        correction = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        self.assertTrue(apply_capability_support_correction(
            inherited, correction, AUTHORITY))
        with self.assertRaises(BilqisError):
            inherited.require(TARGET)



if __name__ == "__main__":
    import unittest
    unittest.main()
