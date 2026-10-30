"""Immutable dependency-ready commits for the bounded typed decoder."""
from dataclasses import dataclass
from enum import Enum
from bilqis_mlx.semantics.frame_schema import BindingState, ConceptRef, RoleOccurrence
from .control import ControlAction
from .plan import AnswerPlan, DecisionKind
from .records import RoleCandidate, invalid
from .frames import _can_end, _frame_bindings


OUTPUT_SCHEMA = 'bilqis.mlx.decision-output/v1'
STATE_SCHEMA = 'bilqis.mlx.decode-state/v1'


class DecodeStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    COMPLETE = 'COMPLETE'
    PARTIAL = 'PARTIAL'
    UNRESOLVED = 'UNRESOLVED'


@dataclass(frozen=True)
class DecisionOutput:
    decision_id: str
    value: object
    schema_version: str = OUTPUT_SCHEMA

    def __post_init__(self):
        if (self.schema_version != OUTPUT_SCHEMA
                or type(self.decision_id) is not str or not self.decision_id
                or type(self.value) not in (ControlAction, ConceptRef, RoleOccurrence, RoleCandidate, str)
                or type(self.value) is str and not self.value):
            invalid()
        if type(self.value) in (ConceptRef, RoleOccurrence, RoleCandidate):
            self.value.__post_init__()


def _ended(outputs):
    return any(output.value is ControlAction.END_FRAME for output in outputs)


def _allowed_values(plan, committed, decision):
    previous = {o.decision_id: o.value for o in committed}
    if not set(decision.depends_on) <= set(previous):
        return ()
    values = decision.legal_values
    if decision.kind is DecisionKind.CONTROL:
        return tuple(v for v in values if v is not ControlAction.END_FRAME or _can_end(plan, committed))
    if decision.kind is DecisionKind.VALUE:
        lookup = {d.decision_id: d for d in plan.decisions}
        parent = next(key for key in decision.depends_on
                      if lookup[key].kind is DecisionKind.CONTROL
                      and (lookup[key].role_id, lookup[key].occurrence) ==
                      (decision.role_id, decision.occurrence))
        return tuple(v for v in values if previous[parent] is (
            ControlAction.EMIT_ALTERNATIVES if type(v) is RoleOccurrence
            and v.state is BindingState.ALTERNATIVES else ControlAction.EMIT_VALUE))
    return values


@dataclass(frozen=True)
class DecodeState:
    plan: AnswerPlan
    committed: tuple[DecisionOutput, ...] = ()
    schema_version: str = STATE_SCHEMA

    def __post_init__(self):
        if (self.schema_version != STATE_SCHEMA or type(self.plan) is not AnswerPlan
                or type(self.committed) is not tuple
                or len(self.committed) > self.plan.position_budget
                or any(type(o) is not DecisionOutput for o in self.committed)):
            invalid()
        self.plan.__post_init__()
        lookup = {d.decision_id: d for d in self.plan.decisions}
        previous = ()
        for output in self.committed:
            output.__post_init__()
            if (_ended(previous) or output.decision_id not in lookup
                    or output.decision_id in {o.decision_id for o in previous}):
                invalid()
            legal = _allowed_values(self.plan, previous, lookup[output.decision_id])
            if not any(type(output.value) is type(v) and output.value == v for v in legal):
                invalid()
            previous += (output,)
        _frame_bindings(self.plan, self.committed)

    @property
    def remaining_capacity(self):
        return self.plan.position_budget - len(self.committed)

    @property
    def status(self):
        if _ended(self.committed):
            return DecodeStatus.COMPLETE
        if self.remaining_capacity == 0:
            return DecodeStatus.PARTIAL
        return DecodeStatus.ACTIVE if ready_decisions(self) else DecodeStatus.UNRESOLVED


def start_decoding(plan):
    return DecodeState(plan)


def ready_decisions(state):
    if type(state) is not DecodeState:
        invalid()
    if _ended(state.committed) or state.remaining_capacity == 0:
        return ()
    previous = {o.decision_id for o in state.committed}
    ready = tuple(sorted((d for d in state.plan.decisions if d.decision_id not in previous
                          and _allowed_values(state.plan, state.committed, d)),
                         key=lambda d: d.decision_id))
    return ready[:state.remaining_capacity]


def parent_outputs(state, decision_id):
    if type(state) is not DecodeState:
        invalid()
    decision = next((d for d in state.plan.decisions if d.decision_id == decision_id), None)
    previous = {o.decision_id: o.value for o in state.committed}
    if decision is None or not set(decision.depends_on) <= set(previous):
        invalid()
    return tuple(previous[key] for key in decision.depends_on)


def allowed_values(state, decision_id):
    if type(state) is not DecodeState:
        invalid()
    decision = next((d for d in ready_decisions(state) if d.decision_id == decision_id), None)
    if decision is None:
        invalid()
    return _allowed_values(state.plan, state.committed, decision)


def commit_decisions(state, outputs):
    if (type(state) is not DecodeState or type(outputs) is not tuple or not outputs
            or any(type(o) is not DecisionOutput for o in outputs)
            or len({o.decision_id for o in outputs}) != len(outputs)
            or len(outputs) > 1 and any(o.value is ControlAction.END_FRAME for o in outputs)):
        invalid()
    ready = {d.decision_id for d in ready_decisions(state)}
    if any(output.decision_id not in ready for output in outputs):
        invalid()
    # One ready batch is simultaneous; descendants cannot join their parent batch.
    ordered = tuple(sorted(outputs, key=lambda output: output.decision_id))
    return DecodeState(state.plan, state.committed + ordered)
