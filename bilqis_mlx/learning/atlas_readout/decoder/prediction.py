"""Causal bounded prediction and explicit source-validation fallback."""
from dataclasses import dataclass
from enum import Enum
import mlx.core as mx
from bilqis_mlx.errors import BilqisError
from ..control import ControlAction
from ..decisions import (
    DecisionOutput, DecodeStatus, start_decoding, ready_decisions,
    parent_outputs, commit_decisions,
)
from ..frames import FrameAnswer, publish_frame
from ..plan import AnswerPlan, DecisionKind
from ..records import invalid
from .inputs import validate_decoder_inputs
from .execution import validate_execution
from .math import prepare_memory, decision_state
from .heads import decision_logits


class ExecutionMode(str,Enum):
    INFERENCE='INFERENCE'
    TEACHER_FORCED='TEACHER_FORCED'


@dataclass(frozen=True)
class DecisionLogits:
    decision_id: str
    kind: DecisionKind
    candidates: tuple
    logits: mx.array

    def __post_init__(self):
        if (type(self.decision_id) is not str or not self.decision_id
                or type(self.kind) is not DecisionKind or type(self.candidates) is not tuple
                or not self.candidates or len(set(self.candidates))!=len(self.candidates)
                or not isinstance(self.logits,mx.array) or self.logits.dtype!=mx.float32
                or self.logits.shape!=(len(self.candidates),)
                or not bool(mx.all(mx.isfinite(self.logits)))):
            invalid()


@dataclass(frozen=True)
class ModelOutput:
    plan: AnswerPlan
    decisions: tuple[DecisionLogits,...]
    committed: tuple[DecisionOutput,...]
    status: DecodeStatus
    execution_mode: ExecutionMode
    frame: FrameAnswer|None
    fallback_requested: bool
    schema_version: str='bilqis.mlx.model-output/v1'

    def __post_init__(self):
        if (self.schema_version!='bilqis.mlx.model-output/v1' or type(self.plan) is not AnswerPlan
                or type(self.decisions) is not tuple or type(self.committed) is not tuple
                or any(type(d) is not DecisionLogits for d in self.decisions)
                or any(type(o) is not DecisionOutput for o in self.committed)
                or type(self.status) is not DecodeStatus or type(self.execution_mode) is not ExecutionMode
                or type(self.fallback_requested) is not bool
                or self.frame is not None and type(self.frame) is not FrameAnswer):
            invalid()

        self.plan.__post_init__()
        ids={d.decision_id for d in self.plan.decisions}
        if (len({d.decision_id for d in self.decisions})!=len(self.decisions)
                or not {d.decision_id for d in self.decisions}<=ids
                or len({o.decision_id for o in self.committed})!=len(self.committed)
                or not {o.decision_id for o in self.committed}<=ids
                or (self.status is DecodeStatus.COMPLETE)!=(self.frame is not None)
                or self.fallback_requested!=(self.status is not DecodeStatus.COMPLETE)):
            invalid()
        for record in (*self.decisions,*self.committed):
            record.__post_init__()
        if self.frame is not None:
            self.frame.__post_init__()
            if self.frame.plan!=self.plan:
                invalid()

        validate_execution(self)

    @property
    def generation_binding(self):
        return self.plan.generation_binding


def _targets(teacher_targets,plan):
    if teacher_targets is None:
        return {}
    if (type(teacher_targets) is not tuple
            or any(type(t) is not DecisionOutput for t in teacher_targets)
            or len({t.decision_id for t in teacher_targets})!=len(teacher_targets)):
        invalid()
    lookup={d.decision_id:d for d in plan.decisions}
    for target in teacher_targets:
        target.__post_init__()
        if target.decision_id not in lookup or not any(
                type(target.value) is type(value) and target.value==value
                for value in lookup[target.decision_id].legal_values):
            invalid()
    return {t.decision_id:t.value for t in teacher_targets}


def _ready_outputs(memory,state,semantics,parameters,prepared,targets):
    records,outputs=[],[]
    for decision in ready_decisions(state):
        z=decision_state(memory,decision,state,semantics,parameters,prepared)
        if not bool(mx.all(mx.isfinite(z))):
            return tuple(records),()
        try:
            candidates,logits=decision_logits(z,decision,state,semantics,parameters)
            records.append(DecisionLogits(decision.decision_id,decision.kind,candidates,logits))
        except BilqisError:
            return tuple(records),()
        value=targets.get(decision.decision_id,candidates[int(mx.argmax(logits).item())])
        if not any(type(value) is type(v) and value==v for v in candidates):
            invalid()
        outputs.append(DecisionOutput(decision.decision_id,value))
    end=tuple(o for o in outputs if o.value is ControlAction.END_FRAME)
    return tuple(records),(end[:1] if end else tuple(outputs))


def predict_typed(memory,eligible_context,answer_plan,active_semantics,readout_params,
                  teacher_targets=None):
    validate_decoder_inputs(memory,eligible_context,answer_plan,active_semantics,readout_params)
    targets=_targets(teacher_targets,answer_plan)
    prepared=prepare_memory(memory,readout_params,active_semantics)
    state=start_decoding(answer_plan)
    records=[]
    while state.status is DecodeStatus.ACTIVE:
        batch,outputs=_ready_outputs(memory,state,active_semantics,readout_params,prepared,targets)
        if not outputs:
            return ModelOutput(answer_plan,tuple(records),state.committed,DecodeStatus.UNRESOLVED,
                ExecutionMode.TEACHER_FORCED if teacher_targets is not None else ExecutionMode.INFERENCE,
                None,True)
        try:
            state=commit_decisions(state,outputs)
        except BilqisError:
            return ModelOutput(answer_plan,tuple(records),state.committed,DecodeStatus.UNRESOLVED,
                ExecutionMode.TEACHER_FORCED if teacher_targets is not None else ExecutionMode.INFERENCE,
                None,True)
        committed_ids={o.decision_id for o in outputs}
        records.extend(record for record in batch if record.decision_id in committed_ids)
    status,frame=state.status,None
    if status is DecodeStatus.COMPLETE:
        try:
            frame=publish_frame(state)
        except BilqisError:
            status=DecodeStatus.UNRESOLVED
    return ModelOutput(answer_plan,tuple(records),state.committed,status,
        ExecutionMode.TEACHER_FORCED if teacher_targets is not None else ExecutionMode.INFERENCE,
        frame,status is not DecodeStatus.COMPLETE)
