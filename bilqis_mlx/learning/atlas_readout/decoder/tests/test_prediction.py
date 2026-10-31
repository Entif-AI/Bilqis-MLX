"""Actual parent feedback, no future-gold leakage and checked publication."""
from dataclasses import replace
import unittest
import numpy as np
import mlx.core as mx
from bilqis_mlx.learning.atlas_readout import (
    predict_typed, DecisionOutput, DecisionSpec, DecisionKind, ControlAction,
    RoleCandidate, DecodeStatus,
)
from bilqis_mlx.semantics.frame_schema import BindingState, RoleOccurrence
from bilqis_mlx.learning.atlas_readout.decoder.prediction import ExecutionMode
from bilqis_mlx.learning.atlas_readout.decoder.tests.helpers import case


def role_plan(plan):
    schema=plan.allowed_output_schema.schema
    roles=tuple(RoleCandidate(schema.schema_id,schema.revision,r.role_id,0) for r in schema.roles)
    role=DecisionSpec('role','theme',0,DecisionKind.ROLE,roles,('value',))
    return replace(plan,decisions=(*plan.decisions[:2],role,
                                   replace(plan.decisions[2],depends_on=('role',))))


def logits(output,key):
    return next(d.logits for d in output.decisions if d.decision_id==key)


class PredictionTests(unittest.TestCase):
    def test_complete_output_is_source_valid_and_unassisted(self):
        memory,context,plan,semantics,params=case()
        output=predict_typed(memory,context,plan,semantics,params)
        self.assertIs(output.status,DecodeStatus.COMPLETE)
        self.assertIs(output.execution_mode,ExecutionMode.INFERENCE)
        self.assertIsNotNone(output.frame)
        self.assertFalse(output.fallback_requested)
        self.assertEqual(output.generation_binding,plan.generation_binding)

    def test_current_and_descendant_targets_never_change_earlier_logits(self):
        memory,context,plan,semantics,params=case();plan=role_plan(plan)
        actor=plan.decisions[1].legal_values
        roles=plan.decisions[2].legal_values
        first=predict_typed(memory,context,plan,semantics,params,
                            (DecisionOutput('value',actor[0]),DecisionOutput('role',roles[0])))
        second=predict_typed(memory,context,plan,semantics,params,
                             (DecisionOutput('value',actor[1]),DecisionOutput('role',roles[1])))
        np.testing.assert_array_equal(np.asarray(logits(first,'value')),np.asarray(logits(second,'value')))
        self.assertFalse(np.array_equal(np.asarray(logits(first,'role')),np.asarray(logits(second,'role'))))
        third=predict_typed(memory,context,plan,semantics,params,
                            (DecisionOutput('value',actor[0]),DecisionOutput('role',roles[1])))
        np.testing.assert_array_equal(np.asarray(logits(first,'role')),np.asarray(logits(third,'role')))
        self.assertIs(first.execution_mode,ExecutionMode.TEACHER_FORCED)

    def test_inference_parent_equals_prediction_not_future_teacher_label(self):
        memory,context,plan,semantics,params=case();plan=role_plan(plan)
        actual=predict_typed(memory,context,plan,semantics,params)
        parent=next(o.value for o in actual.committed if o.decision_id=='value')
        forced=predict_typed(memory,context,plan,semantics,params,(DecisionOutput('value',parent),))
        np.testing.assert_array_equal(np.asarray(logits(actual,'role')),np.asarray(logits(forced,'role')))
        changed=replace(memory,hidden=mx.concatenate((memory.hidden[:5],mx.full((2,768),77.))))
        later=predict_typed(changed,context,plan,semantics,params)
        for one,two in zip(actual.decisions,later.decisions):
            np.testing.assert_array_equal(np.asarray(one.logits),np.asarray(two.logits))

    def test_budget_exhaustion_never_publishes_a_frame(self):
        memory,context,plan,semantics,params=case()
        output=predict_typed(memory,context,replace(plan,maximum_decisions=1),semantics,params)
        self.assertIs(output.status,DecodeStatus.PARTIAL)
        self.assertIsNone(output.frame)
        self.assertTrue(output.fallback_requested)
        self.assertEqual(len(output.committed),1)

    def test_unknown_and_alternatives_stay_distinct(self):
        memory,context,plan,semantics,params=case()
        choices=plan.decisions[1].legal_values
        unknown=replace(plan,decisions=(
            replace(plan.decisions[0],legal_values=(ControlAction.EMIT_UNKNOWN,)),
            replace(plan.decisions[2],depends_on=('control',))))
        result=predict_typed(memory,context,unknown,semantics,params)
        self.assertIs(result.status,DecodeStatus.COMPLETE)
        self.assertIs(result.frame.bindings[0].state,BindingState.UNKNOWN)
        for state,control in ((BindingState.ALTERNATIVES,ControlAction.EMIT_ALTERNATIVES),):
            value=RoleOccurrence('agent',0,state=state,
                                  alternatives=choices if state is BindingState.ALTERNATIVES else ())
            changed=replace(plan,decisions=(
                replace(plan.decisions[0],legal_values=(control,)),
                replace(plan.decisions[1],legal_values=(value,)),plan.decisions[2]))
            output=predict_typed(memory,context,changed,semantics,params)
            self.assertIs(output.status,DecodeStatus.COMPLETE)
            self.assertIs(output.frame.bindings[0].state,state)

    def test_invalid_neural_binding_is_explicit_unresolved_fallback(self):
        memory,context,plan,semantics,params=case()
        bad=replace(plan.decisions[1].legal_values[0],type_ids=('invalid',))
        changed=replace(plan,decisions=(plan.decisions[0],
            replace(plan.decisions[1],legal_values=(bad,)),plan.decisions[2]))
        output=predict_typed(memory,context,changed,semantics,params)
        self.assertIs(output.status,DecodeStatus.UNRESOLVED)
        self.assertIsNone(output.frame)
        self.assertTrue(output.fallback_requested)

    def test_nonfinite_neural_computation_requests_fallback_without_publication(self):
        memory,context,plan,semantics,params=case()
        changed={**params,'readout.query':mx.full((192,768),1e30),
                 'readout.key':mx.full((192,768),1e30)}
        output=predict_typed(memory,context,plan,semantics,changed)
        self.assertIs(output.status,DecodeStatus.UNRESOLVED)
        self.assertTrue(output.fallback_requested)
        self.assertIsNone(output.frame)
