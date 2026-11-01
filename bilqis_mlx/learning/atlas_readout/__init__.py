"""B10 pure heads over decoder state; bounded decoding belongs to B10.2/B10.3."""
from .records import FrameOutputDomain, RoleCandidate, TypedHeadLogits, ValueHeadBinding
from .roles import compile_frame_output, role_logits
from .values import bind_value_head, value_logits

__all__ = ('FrameOutputDomain', 'RoleCandidate', 'TypedHeadLogits',
           'ValueHeadBinding', 'compile_frame_output', 'role_logits',
           'bind_value_head', 'value_logits')

from .control import ControlAction, control_logits
from .plan import AnswerPlan, DecisionKind, DecisionSpec
from .decisions import (DecodeState, DecodeStatus, DecisionOutput, start_decoding,
                        ready_decisions, parent_outputs, allowed_values, commit_decisions)
from .frames import FrameAnswer, can_end_frame, frame_bindings, publish_frame
from .causal_training import (
    NeuralDecisionResult, NeuralDecisionStatus, commit_neural_decision,
    decision_hidden, encode_feedback_value, typed_decision_loss,
)
from .parameters import bind_readout_parameters, readout_parameter_specs

__all__ += ('ControlAction', 'control_logits', 'AnswerPlan', 'DecisionKind',
            'DecisionSpec', 'DecodeState', 'DecodeStatus', 'DecisionOutput',
            'start_decoding', 'ready_decisions', 'parent_outputs', 'allowed_values',
            'commit_decisions', 'FrameAnswer', 'can_end_frame', 'frame_bindings',
            'publish_frame', 'NeuralDecisionResult', 'NeuralDecisionStatus',
            'commit_neural_decision', 'decision_hidden', 'encode_feedback_value',
            'typed_decision_loss', 'bind_readout_parameters', 'readout_parameter_specs')

from .decoder.inputs import DecoderMemory, ReadoutSemantics
from .decoder.prediction import DecisionLogits, ModelOutput, ExecutionMode, predict_typed
from .decoder.losses import LossParts, answer_loss

__all__ += ('DecoderMemory', 'ReadoutSemantics', 'DecisionLogits', 'ModelOutput',
            'ExecutionMode', 'predict_typed', 'LossParts', 'answer_loss')
