"""CPU-only controlled route and numerical witnesses, not learner evidence."""
import unittest
from types import SimpleNamespace as NS

import mlx.core as mx
import numpy as np
from bilqis_mlx.runtime.atlas_optimizer import _adamw_update
from bilqis_mlx.runtime.atlas_optimizer_contracts import (
    AdamWHyperparameters, AdamWStateTree,
)
from bilqis_mlx.runtime.atlas_optimizer_preflight import (
    _masked_clipped_gradients,
)
from bilqis_mlx.runtime.microbatch.route_evidence import (
    _compact_loss_participation,
)
from bilqis_mlx.learning.atlas_readout import DecisionKind
from bilqis_mlx.semantics.frame_schema import ConceptRef
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2

mx.set_default_device(mx.cpu)

HP = AdamWHyperparameters(.0007, (.88, .97), 1e-7, .03)

def tree(values, dtype=mx.float32):
    return {k: mx.array(v, dtype=dtype) for k, v in values.items()}

def independent_step(p, m, v, n, g, enabled, decay):
    """Independent scalar expression for participating coordinates."""
    if not enabled:
        return p, m, v, n
    b1, b2 = HP.betas
    m = b1*m + (1-b1)*g
    v = b2*v + (1-b2)*g*g
    n += 1
    return (p*(1-HP.learning_rate*HP.weight_decay*decay)
            - HP.learning_rate*(m/(1-b1**n))
            / (np.sqrt(v/(1-b2**n))+HP.eps), m, v, n)

class NativeNumericalDiagnostic(unittest.TestCase):
    def test_actual_global_clip_and_complete_update(self):
        p = {'table': [[2., -1.], [3., 4.]], 'dense': [2.]}
        m = {'table': [[.1, -.2], [.9, -.8]], 'dense': [-.2]}
        v = {'table': [[.2, .4], [.7, .6]], 'dense': [.01]}
        n = {'table': [10, 19], 'dense': 3}
        raw = {'table': [[3., 4.], [1000., -1000.]], 'dense': [12.]}
        mask = tree({'table': [True, False], 'dense': True}, mx.bool_)
        parent = AdamWStateTree(tree(p), tree(m), tree(v), tree(n, mx.uint64))
        gradients = tree(raw)
        clipped, norm = _masked_clipped_gradients(parent, gradients, mask, max_norm=2.)
        mx.eval(norm, *clipped.values())
        self.assertAlmostEqual(float(norm), 13., places=5)
        factor = 2./(13.+1e-6)
        np.testing.assert_allclose(np.array(clipped['table']), [[3*factor,4*factor],[0,0]], atol=1e-6)
        np.testing.assert_allclose(np.array(clipped['dense']), [12*factor], atol=1e-6)
        decay = {'table': True, 'dense': False}
        authority = {'table': (False, (0,)), 'dense': (True, ())}
        for learning_first in (False, True):
            result = _adamw_update(parent, gradients, mask, HP, decay=decay,
                                   max_norm=2., participation_authority=authority,
                                   learning_first=learning_first)
            for name, rows in (('table', [(0, True),(1,False)]), ('dense', [(0, True)])):
                actual = [np.array(getattr(result, k)[name]) for k in ('parameters','m','v','update_counts')]
                for i, active in rows:
                    if name == 'table':
                        for j in range(2):
                            exp = independent_step(p[name][i][j],m[name][i][j],v[name][i][j],n[name][i],
                                                   raw[name][i][j]*factor,active,decay[name])
                            for arr, val in zip(actual[:3],exp[:3]):
                                self.assertAlmostEqual(float(arr[i,j]),val,places=6)
                            self.assertEqual(int(actual[3][i]),exp[3])
                    else:
                        exp=independent_step(p[name][0],m[name][0],v[name][0],n[name],
                                             raw[name][0]*factor,active,decay[name])
                        for arr,val in zip(actual[:3],exp[:3]):
                            self.assertAlmostEqual(float(arr[0]),val,places=6)
                        self.assertEqual(int(actual[3]),exp[3])
            np.testing.assert_array_equal(np.array(result.parameters['table'])[1],p['table'][1])

    def test_zero_gradient_is_not_zero_participation(self):
        parent=AdamWStateTree(tree({'x': [[1.],[1.]]}),tree({'x': [[.5],[.5]]}),
                              tree({'x': [[.25],[.25]]}),tree({'x':[9,9]},mx.uint64))
        result=_adamw_update(parent,tree({'x':[[0.],[0.]]}),tree({'x':[True,False]},mx.bool_),
                            HP,decay={'x':False},participation_authority={'x':(False,(0,))},
                            learning_first=True)
        self.assertLess(float(result.parameters['x'][0,0]),1.)
        self.assertEqual(float(result.parameters['x'][1,0]),1.)
        np.testing.assert_array_equal(np.array(result.update_counts['x']),[10,9])
        self.assertAlmostEqual(float(result.m['x'][0,0]),.44,places=6)
        self.assertAlmostEqual(float(result.m['x'][1,0]),.5,places=6)

    def test_route_ancestry_includes_denominator_and_only_relevant_feedback(self):
        width=ModelTopologySpecV2.semantic_bank_rows
        def concept(i):
            return ConceptRef('fixture:'+str(i),'a'*64,i,('Fixture',),'fixture')
        def decision(name, values, parents=()):
            return NS(decision_id=name,kind=DecisionKind.VALUE,legal_values=values,
                      depends_on=parents,role_id=None)
        parent,unused,positive,negative=map(concept,[2,3,width+4,width+5])
        plan=NS(decisions=(decision('parent',(parent,unused)),
                           decision('answer',(positive,negative),('parent',)),
                           decision('unrelated',(unused,))))
        route={'parent':parent,'answer':positive,'unrelated':unused}
        got=_compact_loss_participation(plan,(NS(decision_id='answer'),),
                                        {'answer':True},route,NS(role_map=(('NONE',0),)))
        self.assertEqual(got,(((0,2),),((1,4),(1,5)),(),(('role',0),)))
        # The denominator includes a negative candidate, not just the selected answer.
        # The unrelated route and unselected ancestor choice do not acquire authority.
        self.assertNotIn((0,3),got[0]+got[1])

if __name__ == '__main__':
    unittest.main()
