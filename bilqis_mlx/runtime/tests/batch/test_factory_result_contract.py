"""Cheap contract checks for C08 Factory-result assertions."""
from __future__ import annotations

import unittest
from types import SimpleNamespace

from bilqis_mlx.runtime.atlas_training_authority import (
    _issue as issue_training_authority,
    extend_training_dependencies,
)
from bilqis_mlx.runtime.atlas_training_contracts import (
    BamfDeliveryProvenance, BamfTrainingRow, _issue_training_batch,
)
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.runtime.tests.batch.training.visit_provenance_support import (
    visit_provenance,
)
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind, DependencyRef


class FactoryResultAuthorityContractTests(unittest.TestCase):
    def _prepared_authority(self):
        row = {"id": "row:test", "capability": "A.IDENTITY"}
        dependency = DependencyRef(DependencyKind.SOURCE, row["id"])
        provenance = BamfDeliveryProvenance(
            row["id"], source_content_digest((row,)), "source:test",
            "A.IDENTITY", None, (), 1, 1, None, 0,
            visit_provenance("A.IDENTITY"), "family:test", "episode:test",
            (dependency,),
        )
        training_row = BamfTrainingRow(None, None, None, provenance)
        batch = _issue_training_batch(
            "a" * 64, "b" * 64, "c" * 64, "A.IDENTITY", (training_row,))
        return issue_training_authority(
            batch, SimpleNamespace(source_row=row), provenance)

    def test_execution_authority_may_extend_prepared_dependencies(self):
        prepared = self._prepared_authority()
        learned = DependencyRef(DependencyKind.SOURCE, "execution:learned")
        execution = extend_training_dependencies(prepared, (learned,))

        self.assertNotEqual(execution.digest, prepared.digest)
        self.assertEqual(
            (
                execution.release_sha256,
                execution.generation_binding,
                execution.training_batch_sha256,
                execution.delivery_capability,
                execution.source_row_id,
                execution.source_row_sha256,
                execution.source_family_id,
                execution.episode_id,
                execution.visit_id,
            ),
            (
                prepared.release_sha256,
                prepared.generation_binding,
                prepared.training_batch_sha256,
                prepared.delivery_capability,
                prepared.source_row_id,
                prepared.source_row_sha256,
                prepared.source_family_id,
                prepared.episode_id,
                prepared.visit_id,
            ),
        )
        self.assertTrue(
            set(prepared.immediate_dependencies)
            < set(execution.immediate_dependencies)
        )


if __name__ == "__main__":
    unittest.main()
