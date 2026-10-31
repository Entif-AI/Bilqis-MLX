"""Structural feedback golden and active tied identity gradients."""
from dataclasses import replace
import unittest
import hashlib
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.atlas_readout import ControlAction
from bilqis_mlx.learning.atlas_readout.decoder.feedback import encode_value, occurrence_vector, role_vector
from bilqis_mlx.learning.atlas_readout.decoder.math import prepare_memory, decision_state
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class DecoderFeedbackTests(unittest.TestCase):
    def test_structural_hash_has_literal_signed_768_byte_golden(self):
        _, _, plan, semantics, params = case()
        actual = encode_value(ControlAction.EMIT_VALUE, semantics, plan, params)
        # Independent compact typed-Enum JSON / 24-block SHA expansion golden.
        fingerprint = hashlib.sha256(np.asarray(actual).astype('<f4').tobytes()).hexdigest()
        self.assertEqual(fingerprint,
            '4982770d588b1c00a0eab736e839fb164ad57015550a103bff8f13b5348312bd')

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
