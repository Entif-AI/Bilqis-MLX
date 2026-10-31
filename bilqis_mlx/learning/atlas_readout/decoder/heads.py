"""Legal-decision heads reuse the existing B10.1/2 parameter owners."""
import mlx.core as mx
from bilqis_mlx.learning.frame_embeddings.banks import semantic_logits
from bilqis_mlx.semantics.frame_schema import ConceptRef
from ..control import control_logits
from ..decisions import allowed_values
from ..frames import can_end_frame
from ..plan import DecisionKind
from ..roles import role_logits
from .feedback import encode_value


def decision_logits(z,decision,state,semantics,parameters):
    values=allowed_values(state,decision.decision_id)
    if decision.kind is DecisionKind.CONTROL:
        head=control_logits(z,parameters,semantic_release=semantics.features.semantic_release,
                            can_end=can_end_frame(state))
        indices=tuple(head.candidates.index(value.value) for value in values)
        return values,head.logits[mx.array(indices)]
    if decision.kind is DecisionKind.ROLE:
        head=role_logits(z,state.plan.allowed_output_schema,decision.occurrence,
                         parameters,semantics.features)
        indices=tuple(head.candidates.index(value) for value in values)
        return values,head.logits[mx.array(indices)]
    if decision.kind is DecisionKind.EPISTEMIC:
        binding=semantics.epistemic_binding
        indices=mx.array([binding.values.index(value) for value in values])
        logits=z@parameters['readout.epistemic'].T+parameters['readout.epistemic_bias']
        return values,logits[indices]
    if type(values[0]) is ConceptRef:
        head=semantic_logits(z,semantics.banks)
        indices=mx.array([head.indices.index(value.abi_index) for value in values])
        return values,head.logits[indices]
    vectors=mx.stack(tuple(encode_value(value,semantics,state.plan,parameters) for value in values))
    return values,(z@vectors.T)/(768**.5)
