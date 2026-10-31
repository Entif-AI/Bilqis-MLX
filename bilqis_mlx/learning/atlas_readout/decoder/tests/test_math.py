"""Independent numerical decoder equation and structural feedback golden."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.atlas_readout import ControlAction
from bilqis_mlx.learning.atlas_readout.decoder.feedback import encode_value, occurrence_vector, role_vector
from bilqis_mlx.learning.atlas_readout.decoder.math import prepare_memory, decision_state
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class DecoderMathTests(unittest.TestCase):
    def test_numpy_equation_and_future_rows_are_never_read(self):
        memory, _, plan, semantics, params = case()
        decision = plan.decisions[1]
        parents = (ControlAction.EMIT_VALUE,)
        prepared = prepare_memory(memory, params, semantics)
        actual = decision_state(memory, decision, parents, semantics, plan, params, prepared)
        p = {k:np.asarray(v) for k,v in params.items()}
        def norm(x,g): return x/np.sqrt(np.mean(x*x)+1e-5)*g
        feedback = np.asarray(encode_value(parents[0],semantics,plan,params))
        state = norm(np.asarray(memory.hidden[4])+np.asarray(role_vector(decision,semantics,params))
                     +np.asarray(occurrence_vector(0))+p['readout.feedback']@feedback,
                     p['readout.state_norm'])
        h = np.asarray(memory.hidden[:5])
        scores = (state@p['readout.query'].T)@(h@p['readout.key'].T).T/np.sqrt(192)
        weights = np.exp(scores-np.max(scores));weights/=weights.sum()
        expected = norm(state+(weights@(h@p['readout.value'].T))@p['readout.output'].T,
                        p['readout.output_norm'])
        np.testing.assert_allclose(np.asarray(actual),expected,rtol=2e-5,atol=2e-6)
        changed = replace(memory, hidden=mx.concatenate((memory.hidden[:5],mx.full((2,768),float('nan'),dtype=mx.float32))))
        later = decision_state(changed,decision,parents,semantics,plan,params,
                               prepare_memory(changed,params,semantics))
        np.testing.assert_array_equal(np.asarray(actual),np.asarray(later))
