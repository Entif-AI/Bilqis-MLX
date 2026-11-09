"""C05 evaluation carries A05 source-tree custody into the B11 encoder input."""
from __future__ import annotations

from dataclasses import replace
import os
from pathlib import Path
import unittest

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import SourceBackboneTestBase
from bilqis_mlx.runtime.factory_evaluation_compiler import compile_factory_evaluation_batch
from bilqis_mlx.runtime.tests.capability.factory.retention.factory_retention_live_support import (
    genesis_bundle, live_factory_context,
)
from bilqis_mlx.semantics.frame_compiler import validate_partial_visible_forest


class FactoryEvaluationCustodyTests(SourceBackboneTestBase):
    def setUp(self):
        if not mx.metal.is_available():
            self.skipTest("C05 evaluation custody witness requires Apple Metal")
        artifact = os.environ.get("BILQIS_A01_ATLAS_BUNDLE")
        if not artifact or not Path(artifact).is_dir():
            self.skipTest("BILQIS_A01_ATLAS_BUNDLE fixture is not mounted")
        self.artifact = Path(artifact)
        previous_device = mx.default_device()
        mx.set_default_device(mx.gpu)
        self.addCleanup(mx.set_default_device, previous_device)
        super().setUp()
        self.root = Path.cwd()
        self.source = (self.root / "vendor/legacy-v16").resolve()
        if not self.source.is_dir():
            self.skipTest("pinned legacy source fixture is not mounted")

    def test_evaluation_batch_preserves_source_ast_and_partial_forest_receipt(self):
        source_context, _ = live_factory_context(self.root, self.source)
        candidate, _ = genesis_bundle(
            self, self.snapshot, self.schema, self.artifact)
        row = source_context.draw_rows(
            seed=46117, capability="B.IDBOOLOPS", each=1)[0]

        batch = compile_factory_evaluation_batch(
            source_context, candidate, str(self.artifact), row,
            source_seed=46117, source_each=1)
        compiled = batch.compiled

        self.assertIsNotNone(compiled.source_asts)
        self.assertIsNotNone(compiled.partial_forest_receipts)
        self.assertEqual(len(compiled.source_asts), 1)
        self.assertEqual(len(compiled.partial_forest_receipts), 1)
        ast = compiled.source_asts[0]
        config = compiled.compiler_configs[0]
        receipt = compiled.partial_forest_receipts[0]
        self.assertEqual(
            validate_partial_visible_forest(
                compiled.compiled.rows[0], ast, config,
                expected_receipt=receipt),
            receipt,
        )

        with self.assertRaises(BilqisError):
            validate_partial_visible_forest(
                compiled.compiled.rows[0],
                replace(ast, source_instance_id=ast.source_instance_id + ":foreign"),
                config, expected_receipt=receipt,
            )


if __name__ == "__main__":
    unittest.main()
