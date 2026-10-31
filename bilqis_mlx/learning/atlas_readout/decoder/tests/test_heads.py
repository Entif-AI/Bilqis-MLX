"""Explicit released classifier roster and supplied auxiliary labels only."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.learning.atlas_readout import (
    predict_typed,answer_loss,DecisionSpec,DecisionKind,DecisionOutput,
)
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


class AuxiliaryTests(unittest.TestCase):
    def test_missing_epistemic_binding_rejects_before_decoding(self):
        memory,context,plan,semantics,params=case()
        decision=DecisionSpec('epistemic',None,0,DecisionKind.EPISTEMIC,('fixture:unknown',),('value',))
        plan=replace(plan,decisions=(*plan.decisions[:2],decision,
                                    replace(plan.decisions[2],depends_on=('epistemic',))))
        with self.assertRaises(BilqisError):
            predict_typed(memory,context,plan,semantics,params)

    def test_released_five_roster_is_masked_and_unlabelled_loss_is_zero(self):
        memory,context,plan,semantics,params=case(epistemic=True)
        labels=semantics.epistemic_binding.values
        decision=DecisionSpec('epistemic',None,0,DecisionKind.EPISTEMIC,labels[:2],('value',))
        plan=replace(plan,decisions=(*plan.decisions[:2],decision,
                                    replace(plan.decisions[2],depends_on=('epistemic',))))
        params={**params,'readout.epistemic_bias':mx.array([0.,1.,9.,90.,900.])}
        output=predict_typed(memory,context,plan,semantics,params)
        record=next(d for d in output.decisions if d.decision_id=='epistemic')
        self.assertEqual(record.candidates,labels[:2])
        self.assertEqual(float(answer_loss(output,(),{'epistemic':True}).epistemic),0)
        target=(DecisionOutput('epistemic',labels[0]),)
        actual=answer_loss(output,target,{'epistemic':True}).epistemic
        expected=.1*(mx.logsumexp(record.logits)-record.logits[0])
        self.assertAlmostEqual(float(actual),float(expected),places=7)
        def objective(bias):
            result=predict_typed(memory,context,plan,semantics,
                                 {**params,'readout.epistemic_bias':bias})
            return answer_loss(result,target,{'epistemic':True}).total
        gradient=mx.grad(objective)(params['readout.epistemic_bias'])
        self.assertGreater(float(mx.sum(mx.abs(gradient[:2]))),0)
        np.testing.assert_array_equal(np.asarray(gradient[2:]),0)
        binding=semantics.epistemic_binding
        shorter=replace(binding,values=binding.values[:4],identities=binding.identities[:4],
                        abi_indices=binding.abi_indices[:4])
        with self.assertRaises(BilqisError):
            predict_typed(memory,context,plan,replace(semantics,epistemic_binding=shorter),params)

    def test_same_release_foreign_source_or_artifact_binding_rejects(self):
        memory,context,plan,semantics,params=case(epistemic=True)
        binding=semantics.epistemic_binding
        decision=DecisionSpec('epistemic',None,0,DecisionKind.EPISTEMIC,binding.values,('value',))
        plan=replace(plan,decisions=(*plan.decisions[:2],decision,
                                    replace(plan.decisions[2],depends_on=('epistemic',))))
        for field in ('bundle_id','source_bundle_id'):
            snapshot=replace(binding.snapshot,**{field:'f'*64})
            with self.subTest(field=field),self.assertRaises(BilqisError):
                predict_typed(memory,context,plan,
                    replace(semantics,epistemic_binding=replace(binding,snapshot=snapshot)),params)
