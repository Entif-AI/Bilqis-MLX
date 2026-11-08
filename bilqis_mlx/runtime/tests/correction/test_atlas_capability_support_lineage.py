"""H3 lineage regression for accepted capability-support correction ancestry."""
from __future__ import annotations

from dataclasses import replace
import os
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import bilqis_mlx.runtime.mlx_checkpoint as mlx_checkpoint
from bilqis_mlx.runtime.accepted_corrections import (
    _RUNTIME_OWNER, accepted_correction_id, record_accepted_correction,
)
from bilqis_mlx.runtime.accepted_correction_ledger import read_records
from bilqis_mlx.runtime.atlas_capability_support_owner import (
    load_capability_support_owner,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    accept_and_publish,
)
from bilqis_mlx.runtime.capability_support_journal import journal_path, read_journal
from bilqis_mlx.runtime.tests.correction.capability_support_owner_support import (
    SOURCE_ROW, TARGET, source_qualified_state,
)
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import (
    candidate, retention_decision, shape_patch, with_source_authority_registry,
)
from bilqis_mlx.runtime.tests.test_atlas_revalidation import (
    AUTHORITY, _event, _ref, _sign_event,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind


class CapabilitySupportLineageTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory()
        self.root = self.temporary.name
        from pathlib import Path
        self.run = Path(self.root) / "run"
        self.environment = patch.dict(
            os.environ, {"BILQIS_DATA_PLANE": str(Path(self.root) / "plane.sqlite3")})
        self.environment.start()

    def tearDown(self):
        self.environment.stop()
        self.temporary.cleanup()

    def publish_support(self):
        parent, transaction, retained, authority = source_qualified_state()
        bundle = with_source_authority_registry(candidate(retained), AUTHORITY)
        decision = retention_decision(parent=parent, retained=retained)
        with shape_patch(), patch.object(mlx_checkpoint, "assert_headroom"):
            published = accept_and_publish(
                self.run, bundle, retained, decision=decision,
                feature_sha256=bundle.extents.factor_map_digest,
                training_authorities=transaction.training_authorities)
        return published, authority

    def load_support(self, authority_registry=None):
        with shape_patch():
            if authority_registry is not None:
                from bilqis_mlx.runtime.bamf_bundle.admission import bind_accepted_execution_cache
                cache = bind_accepted_execution_cache(self.run)
                self.assertEqual(cache._correction_registry, authority_registry)
            return load_capability_support_owner(self.run, TARGET)

    def test_cold_rehydrated_correction_remains_branch_ancestor_for_supersession(self):
        published, _authority = self.publish_support()
        live = self.load_support(AUTHORITY)
        first = _event(_ref(DependencyKind.SOURCE, SOURCE_ROW))
        with shape_patch():
            accepted_id = record_accepted_correction(self.run, first)
        self.assertEqual(live.queue.event.event_id, first.event_id)
        manifest = published["manifest_sha256"]
        hold_path = journal_path(self.run, manifest, TARGET)
        hold = read_journal(
            hold_path, capability_id=TARGET, manifest_sha256=manifest,
            artifact_id="capability-support:" + TARGET)
        self.assertEqual(hold["state"], "HELD")
        self.assertEqual(accepted_correction_id(manifest, first), accepted_id)
        self.assertEqual(
            tuple(item["event_id"] for item in read_records(self.run, manifest)),
            (accepted_id,),
        )

        _RUNTIME_OWNER.clear()
        reloaded = self.load_support(AUTHORITY)
        self.assertEqual(reloaded.queue.event.event_id, first.event_id)
        target = reloaded._accepted_correction_target
        self.assertIn(accepted_id, target.seen)
        self.assertEqual(
            tuple(branch.event.event_id for branch in target.branches[first.dependency].branches),
            (first.event_id,),
        )

        second = _sign_event(replace(
            first,
            event_id="correction:capability-support:2",
            source_receipt_sha256="e" * 64,
            new_evidence_sha256="d" * 64,
            supersedes_event_ids=(first.event_id,),
        ))
        with shape_patch():
            record_accepted_correction(self.run, second)

        branches = target.branches[first.dependency]
        self.assertEqual(
            {branch.event.event_id for branch in branches.branches},
            {first.event_id, second.event_id},
        )
        self.assertEqual(
            tuple(branch.event.event_id for branch in branches.active),
            (second.event_id,),
        )


if __name__ == "__main__":
    unittest.main()
