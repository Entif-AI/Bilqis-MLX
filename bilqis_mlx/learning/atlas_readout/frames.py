"""Validate structured predictions through the existing source frame rules."""
from dataclasses import dataclass
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.semantics.frame_schema import BindingState, ConceptRef, RoleOccurrence, validate_frame_bindings
from .control import ControlAction
from .output_sources import require_active_value
from .plan import AnswerPlan, DecisionKind
from .records import invalid


FRAME_ANSWER_SCHEMA = 'bilqis.mlx.frame-answer/v1'


def _frame_bindings(plan, outputs):
    decisions = {d.decision_id: d for d in plan.decisions}
    result = {}
    for output in outputs:
        decision, binding = decisions[output.decision_id], None
        if decision.kind is DecisionKind.VALUE:
            binding = (RoleOccurrence(decision.role_id, decision.occurrence, concept=output.value)
                       if type(output.value) is ConceptRef else output.value)
        elif decision.kind is DecisionKind.CONTROL and output.value is ControlAction.EMIT_UNKNOWN:
            binding = RoleOccurrence(decision.role_id, decision.occurrence, state=BindingState.UNKNOWN)
        if binding is not None:
            if type(binding) is not RoleOccurrence or binding.key in result:
                invalid()
            binding.__post_init__()
            result[binding.key] = binding
    rank = {r.role_id: i for i, r in enumerate(plan.allowed_output_schema.schema.roles)}
    return tuple(sorted(result.values(), key=lambda b: (rank[b.role_id], b.occurrence_index)))


def _validate_bindings(plan, bindings):
    for binding in bindings:
        require_active_value(plan.snapshot, binding)
    return validate_frame_bindings(
        plan.allowed_output_schema.schema, plan.snapshot, bindings=bindings,
        source_span=plan.source_span, causal_prefix_end=plan.input_prefix_end,
        declared_scope=plan.allowed_output_schema.schema.scope)


def _can_end(plan, outputs):
    try:
        _validate_bindings(plan, _frame_bindings(plan, outputs))
    except BilqisError:
        return False
    return True


def frame_bindings(state):
    from .decisions import DecodeState
    if type(state) is not DecodeState:
        invalid()
    return _frame_bindings(state.plan, state.committed)


def can_end_frame(state):
    from .decisions import DecodeState
    if type(state) is not DecodeState:
        invalid()
    return _can_end(state.plan, state.committed)


@dataclass(frozen=True)
class FrameAnswer:
    plan: AnswerPlan
    bindings: tuple[RoleOccurrence, ...]
    schema_version: str = FRAME_ANSWER_SCHEMA

    def __post_init__(self):
        if (self.schema_version != FRAME_ANSWER_SCHEMA or type(self.plan) is not AnswerPlan
                or type(self.bindings) is not tuple
                or any(type(b) is not RoleOccurrence for b in self.bindings)):
            invalid()
        self.plan.__post_init__()
        validated = _validate_bindings(self.plan, self.bindings)
        if validated != self.bindings:
            invalid()

    @property
    def schema_id(self):
        return self.plan.allowed_output_schema.schema.schema_id

    @property
    def revision(self):
        return self.plan.allowed_output_schema.schema.revision

    @property
    def semantic_release(self):
        return self.plan.snapshot.release_sha256

    @property
    def generation_binding(self):
        return self.plan.generation_binding


def publish_frame(state):
    from .decisions import DecodeState, DecodeStatus
    if type(state) is not DecodeState or state.status is not DecodeStatus.COMPLETE:
        invalid()
    return FrameAnswer(state.plan, frame_bindings(state))
