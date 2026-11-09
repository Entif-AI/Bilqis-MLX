"""Current-generation binding for accepted C09 capability support."""
from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.atlas_capability_support_owner import (
    load_capability_support_owner,
)
from bilqis_mlx.runtime.backbone_identity import execution_generation_digest
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish, load_accepted_generation,
)
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import (
    TARGET, source_qualified_state,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, parent_state, provision_source_authority_registry,
    retention_decision, shape_patch, with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import AUTHORITY


class CapabilitySupportGenerationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.run = self.root / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(self.root / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def test_retained_update_binds_support_to_current_execution_generation(self):
        parent = parent_state()
        parent_bundle = candidate(parent)
        with shape_patch():
            parent_generation = execution_generation_digest(
                parent.optimizer.parameters,
                spec=parent_bundle.topology,
                extents=parent_bundle.extents,
            )
        parent, transaction, retained, authority = source_qualified_state(
            parent,
            generation_binding=parent_generation,
        )
        bundle = candidate(retained)
        provision_source_authority_registry(self.run, AUTHORITY)
        bundle = with_source_authority_registry(bundle, AUTHORITY)
        decision = retention_decision(parent=parent, retained=retained)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            accept_and_publish(
                self.run, bundle, retained, decision=decision,
                feature_sha256=bundle.extents.factor_map_digest,
                training_authorities=transaction.training_authorities,
            )
            accepted = load_accepted_generation(self.run)
            current_generation = execution_generation_digest(
                accepted.retained_state.optimizer.parameters,
                spec=accepted.topology,
                extents=accepted.extents,
            )
        self.assertEqual(authority.generation_binding, parent_generation)
        self.assertNotEqual(current_generation, parent_generation)
        with shape_patch():
            owner = load_capability_support_owner(self.run, TARGET)
        self.assertEqual(owner.require(TARGET, current_generation), owner.support)


if __name__ == "__main__":
    unittest.main()
