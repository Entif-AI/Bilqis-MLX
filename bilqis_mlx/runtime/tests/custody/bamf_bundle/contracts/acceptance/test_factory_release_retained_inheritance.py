"""Retained descendants preserve accepted Factory-release authority."""

from types import SimpleNamespace
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint

from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_factory_release
from bilqis_mlx.runtime.bamf_bundle import (
    load_bamf_generation_authority,
    publish_bamf_generation,
)
from bilqis_mlx.runtime.bamf_bundle.admission import derive_successor_bundle
from bilqis_mlx.runtime.bamf_bundle.factory_release.admission import (
    _issue_factory_release_admission_binding,
)
from bilqis_mlx.runtime.bamf_bundle.factory_release_adoption import (
    _issue_factory_release_adoption_transition,
    derive_factory_release_adoption_candidate,
)
from bilqis_mlx.runtime.bamf_bundle.publication import (
    publish_factory_release_adoption_generation,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.contracts.acceptance._generation_acceptance_support import (
    GenerationAcceptanceFixture,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    accepted_state,
    shape_patch,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.publication.publication_helpers import (
    acceptance,
)


class FactoryReleaseRetainedInheritanceTests(
        GenerationAcceptanceFixture, unittest.TestCase):
    def test_later_retained_child_inherits_factory_release_authority(self):
        parent = self.parent()
        transition = _issue_factory_release_adoption_transition(
            predecessor_factory_release_sha256=parent.run_identity.factory_release_sha256,
            factory_release_sha256="2" * 64,
            handoff_sha256="3" * 64,
            proposal_sha256="4" * 64,
            staged_candidate_sha256="5" * 64,
            selection_receipt_sha256="6" * 64,
            lease_sha256="7" * 64,
            source_approval_sha256="8" * 64,
        )
        capability = derive_factory_release_adoption_candidate(
            parent,
            parent_manifest_sha256=self._parent_pointer["manifest_sha256"],
            transition=transition,
        )
        binding = _issue_factory_release_admission_binding(
            capability,
            parent,
            transition=transition,
        )

        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            capability_pointer = publish_factory_release_adoption_generation(
                self.run,
                capability,
                admission=binding,
                reserve_gib=0.0,
            )
            capability_child, _manifest = load_bamf_generation_authority(
                self.run / "bamf-state.json"
            )
            retained = derive_successor_bundle(
                capability_child,
                accepted_state(
                    capability_child.retained_state,
                    capability_child.extents,
                ),
                parent_manifest_sha256=capability_pointer["manifest_sha256"],
                delivery_events=({"event": "FIXTURE_RETAINED_DESCENDANT"},),
            )
            retained_pointer = publish_bamf_generation(
                self.run,
                retained,
                acceptance=acceptance(
                    retained,
                    parent=capability_child.retained_state,
                ),
                reserve_gib=0.0,
            )

        def resolve_artifact(_root, record):
            return SimpleNamespace(
                release_sha256=record["factory_release_sha256"],
            )

        with shape_patch(), patch(
                "bilqis_mlx.runtime.admission."
                "_read_executable_factory_release_artifact",
                side_effect=resolve_artifact):
            resolved = read_accepted_atlas_factory_release(self.run)

        self.assertEqual(retained_pointer["generation"], parent.generation + 2)
        self.assertEqual(resolved.release_sha256, "2" * 64)


if __name__ == "__main__":
    unittest.main()
