"""Prefix, source and generation validation before any decoding."""
from dataclasses import replace
import unittest
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout.decoder.inputs import validate_decoder_inputs
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class DecoderInputTests(unittest.TestCase):
    def test_actual_prefix_and_borrowed_identity_tree(self):
        memory, context, plan, semantics, params = case()
        validate_decoder_inputs(memory, context, plan, semantics, params)
        self.assertIs(semantics.banks[0].weights, params["identity.bank.0"])

    def test_wrong_generation_context_and_future_anchor_reject(self):
        memory, context, plan, semantics, params = case()
        for changes in ({"generation_binding":"foreign"},
                        {"anchors":(("value",5),)}, {"anchors":(("missing",0),)}):
            with self.subTest(changes=changes), self.assertRaises(BilqisError):
                validate_decoder_inputs(replace(memory, **changes), context, plan, semantics, params)
        with self.assertRaises(BilqisError):
            validate_decoder_inputs(memory, replace(context, schema_version="forged"),
                                    plan, semantics, params)

    def test_prefix_identity_and_unborrowed_bank_reject(self):
        memory, context, plan, semantics, params = case()
        with self.assertRaises(BilqisError):
            replace(memory, row_identities=(("forged",),)+memory.row_identities[1:])
        changed = {**params, "identity.bank.0": mx.array(params["identity.bank.0"])}
        with self.assertRaises(BilqisError):
            validate_decoder_inputs(memory, context, plan, semantics, changed)
