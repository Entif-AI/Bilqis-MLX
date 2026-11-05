"""B11 receipt provenance binds the executed tensor's shape and dtype."""
from copy import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest import skipUnless
from unittest.mock import patch

import mlx.core as mx

from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.source_atoms.backbone_receipts import (
    _issue_from_producer, receipt_projection,
)
from bilqis_mlx.runtime.backbone_group_numerical import _content_digest
from bilqis_mlx.runtime.block_attnres import depth_select
from bilqis_mlx.semantics.domains import contract_digest
from bilqis_mlx.source_adapters.tests.atoms.helpers import REAL_BUNDLE
from bilqis_mlx.learning.source_atoms.tests.backbone_test_support import SourceBackboneTestBase


@skipUnless(REAL_BUNDLE, "real pinned A01 artifact not mounted")
class BackboneReceiptLayoutTests(SourceBackboneTestBase):
    def test_h0_and_group_receipts_round_trip_with_executed_layout(self):
        producer = self.producer()
        group = producer.advance()
        for receipt in (producer.receipts[0], group):
            with self.subTest(source=receipt.source_id):
                self.assertEqual(receipt.output_shape, (1, 2, 768))
                self.assertEqual(receipt.output_dtype, "mlx.core.float32")
                self.assertEqual(replace(receipt).receipt_digest, receipt.receipt_digest)
                values = dict(receipt.__dict__)
                for field, changed in (("output_shape", (2, 1, 768)),
                                       ("output_dtype", "mlx.core.float16")):
                    with self.subTest(field=field):
                        altered = dict(values, **{field: changed})
                        self.assertNotEqual(
                            contract_digest(receipt_projection(altered)),
                            receipt.receipt_digest)

    def test_same_byte_rank_three_reshape_is_rejected(self):
        producer = self.producer()
        group = producer.advance()
        reshaped = group.hidden.reshape(2, 1, 768)
        self.assertEqual(_content_digest(reshaped), group.output_digest)
        with self.assertRaises(BilqisError):
            replace(group, hidden=reshaped)

    def test_dtype_substitution_is_rejected(self):
        group = self.producer().advance()
        with self.assertRaises(BilqisError):
            replace(group, hidden=group.hidden.astype(mx.float16))
        forged = copy(group)
        object.__setattr__(forged, "output_dtype", "mlx.core.float16")
        object.__setattr__(forged, "receipt_digest",
                           contract_digest(receipt_projection(forged.__dict__)))
        with self.assertRaises(BilqisError):
            forged._validate_contents()

    def test_same_byte_reshape_of_execution_result_rejects_issuance(self):
        producer = self.producer()
        producer.advance()
        result = producer._session.results[-1]
        forged = replace(result, hidden=result.hidden.reshape(2, 1, 768))
        fake = object.__new__(type(producer))
        fake.__dict__.update(producer.__dict__)
        fake._session = SimpleNamespace(results=(forged,))
        with self.assertRaises(BilqisError):
            _issue_from_producer(fake, forged)

    def test_recomputed_reshape_receipt_cannot_replace_executed_group(self):
        producer = self.producer()
        group = producer.advance()
        forged = copy(group)
        object.__setattr__(forged, "hidden", group.hidden.reshape(2, 1, 768))
        object.__setattr__(forged, "output_shape", (2, 1, 768))
        object.__setattr__(forged, "receipt_digest",
                           contract_digest(receipt_projection(forged.__dict__)))
        forged._validate_contents()
        features, view = self.depth_inputs(self.parameters)
        producer._receipts = (producer.receipts[0], forged)
        with patch("bilqis_mlx.runtime.depth_selection._depth_components") as compute:
            with self.assertRaises(BilqisError):
                depth_select(producer, features, view)
        compute.assert_not_called()
