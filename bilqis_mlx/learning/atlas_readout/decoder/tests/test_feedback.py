"""Structural feedback golden and active tied identity gradients."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.atlas_readout import ControlAction
from bilqis_mlx.learning.atlas_readout.decoder.feedback import encode_value, occurrence_vector, role_vector
from bilqis_mlx.learning.atlas_readout.decoder.math import prepare_memory, decision_state
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class DecoderFeedbackTests(unittest.TestCase):
    def test_structural_hash_has_literal_768_bit_golden(self):
        _, _, plan, semantics, params = case()
        actual = encode_value(ControlAction.EMIT_VALUE, semantics, plan, params)
        raw = bytes.fromhex(
            '3247a18fa33a761a4fe4570f88d5675fe5d52008ec283f0a8e4e8f64aabe19dc'
            'ea7a525765972a239ee65107a08ed6ededf33054c1f658440d58f8781086c4c2'
            '4dea0d8f1b951326c6e350bfe4da0129e79d54afcfe462815d7e1250e143e087')
        expected = (np.unpackbits(np.frombuffer(raw,np.uint8)).astype(np.float32)*2-1)/np.sqrt(768)
        np.testing.assert_allclose(np.asarray(actual), expected, rtol=1e-6)

    def test_active_concept_feedback_keeps_identity_gradients(self):
        memory, _, plan, semantics, params = case()
        concept = plan.decisions[1].legal_values[0]
        def objective(weights):
            bank = replace(semantics.banks[0], weights=weights)
            return mx.sum(encode_value(concept,replace(semantics,banks=(bank,)),plan,
                                      {**params,'identity.bank.0':weights}))
        gradient=mx.grad(objective)(params['identity.bank.0'])
        self.assertGreater(float(mx.sum(mx.abs(gradient[concept.abi_index]))),0)
        self.assertEqual(float(mx.sum(mx.abs(gradient[0]))),0)
