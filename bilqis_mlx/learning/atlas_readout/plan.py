"""Source-bound structured AnswerPlan/v2 and deterministic dependency order."""
from dataclasses import dataclass
from enum import Enum
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas_projection import FrozenAtlasSnapshot
from bilqis_mlx.semantics.frame_schema import BindingState, ConceptRef, RoleOccurrence, SourceSpan
from .control import ControlAction
from .output_sources import require_active_value
from .records import FrameOutputDomain, RoleCandidate, invalid


PLAN_SCHEMA = 'bilqis.mlx.answer-plan/v2'
DECISION_SCHEMA = 'bilqis.mlx.decision-spec/v1'
MAX_DECISIONS = 64
MAX_POSITIONS = ModelTopologySpecV2.context


class DecisionKind(str, Enum):
    VALUE = 'VALUE'
    ROLE = 'ROLE'
    CONTROL = 'CONTROL'
    EPISTEMIC = 'EPISTEMIC'


def _text(value):
    return type(value) is str and bool(value)


@dataclass(frozen=True)
class DecisionSpec:
    decision_id: str
    role_id: str | None
    occurrence: int
    kind: DecisionKind
    legal_values: tuple
    depends_on: tuple[str, ...] = ()
    schema_version: str = DECISION_SCHEMA

    def __post_init__(self):
        types = {DecisionKind.VALUE: (ConceptRef, RoleOccurrence),
                 DecisionKind.ROLE: (RoleCandidate,), DecisionKind.CONTROL: (ControlAction,),
                 DecisionKind.EPISTEMIC: (str,)}
        if (self.schema_version != DECISION_SCHEMA or not _text(self.decision_id)
                or (self.role_id is not None and not _text(self.role_id))
                or type(self.occurrence) is not int or self.occurrence < 0
                or type(self.kind) is not DecisionKind
                or type(self.legal_values) is not tuple or not self.legal_values
                or any(type(v) not in types[self.kind] for v in self.legal_values)
                or len({type(v) for v in self.legal_values}) != 1
                or len(set(self.legal_values)) != len(self.legal_values)
                or any(type(v) is str and not v for v in self.legal_values)
                or type(self.depends_on) is not tuple
                or any(not _text(v) for v in self.depends_on)
                or len(set(self.depends_on)) != len(self.depends_on)):
            invalid()
        for value in self.legal_values:
            if type(value) in (ConceptRef, RoleOccurrence, RoleCandidate):
                value.__post_init__()
        if self.kind is DecisionKind.VALUE:
            if self.role_id is None:
                invalid()
            for value in self.legal_values:
                if type(value) is RoleOccurrence and (
                        value.key != (self.role_id, self.occurrence)
                        or value.child_frame is not None or value.state is BindingState.UNKNOWN):
                    invalid()


def _ordered_ids(decisions):
    ids = {d.decision_id for d in decisions}
    if len(ids) != len(decisions) or any(not set(d.depends_on) <= ids for d in decisions):
        invalid()
    remaining, done = dict((d.decision_id, d) for d in decisions), []
    while remaining:
        ready = sorted(k for k, d in remaining.items() if set(d.depends_on) <= set(done))
        if not ready:
            invalid()
        done.extend(ready)
        for key in ready:
            del remaining[key]
    return tuple(done)


@dataclass(frozen=True)
class AnswerPlan:
    modality_id: str
    input_prefix_end: int
    decisions: tuple[DecisionSpec, ...]
    allowed_output_schema: FrameOutputDomain
    snapshot: FrozenAtlasSnapshot
    source_span: SourceSpan
    generation_binding: str
    maximum_decisions: int = MAX_DECISIONS
    schema_version: str = PLAN_SCHEMA

    def __post_init__(self):
        if (self.schema_version != PLAN_SCHEMA or not _text(self.modality_id)
                or not _text(self.generation_binding)
                or type(self.input_prefix_end) is not int
                or not 0 <= self.input_prefix_end <= MAX_POSITIONS
                or type(self.maximum_decisions) is not int
                or not 1 <= self.maximum_decisions <= MAX_DECISIONS
                or type(self.decisions) is not tuple or not self.decisions
                or any(type(d) is not DecisionSpec for d in self.decisions)
                or type(self.allowed_output_schema) is not FrameOutputDomain
                or type(self.snapshot) is not FrozenAtlasSnapshot
                or type(self.source_span) is not SourceSpan
                or self.source_span.end > self.input_prefix_end):
            invalid()
        domain = self.allowed_output_schema
        domain.__post_init__()
        self.source_span.__post_init__()
        manifest = domain.released_schemas.manifest
        if (self.modality_id != domain.modality_id
                or (self.snapshot.release_sha256, self.snapshot.bundle_id, self.snapshot.source_bundle_id)
                != (manifest.semantic_release, manifest.atlas_bundle_id, manifest.source_bundle_id)):
            invalid()
        for d in self.decisions:
            d.__post_init__()
        _ordered_ids(self.decisions)
        roles = {r.role_id: r for r in domain.schema.roles}
        lookup = {d.decision_id: d for d in self.decisions}
        coordinates = {kind: set() for kind in (DecisionKind.CONTROL, DecisionKind.VALUE)}
        for d in self.decisions:
            if d.role_id is not None and (d.role_id not in roles
                    or d.occurrence >= roles[d.role_id].max_cardinality):
                invalid()
            if d.kind in coordinates and d.role_id is not None:
                key = (d.role_id, d.occurrence)
                if key in coordinates[d.kind]:
                    invalid()
                coordinates[d.kind].add(key)
            if d.kind is DecisionKind.ROLE:
                for value in d.legal_values:
                    if (value.schema_id != domain.schema.schema_id or value.revision != domain.schema.revision
                            or value.role_id not in roles or value.occurrence_index != d.occurrence
                            or value.occurrence_index >= roles[value.role_id].max_cardinality):
                        invalid()
            elif d.kind is DecisionKind.CONTROL and d.role_id is None:
                if d.legal_values != (ControlAction.END_FRAME,):
                    invalid()
            elif d.kind is DecisionKind.VALUE:
                for value in d.legal_values:
                    require_active_value(self.snapshot, value)
                if len([lookup[key] for key in d.depends_on
                        if lookup[key].kind is DecisionKind.CONTROL
                        and (lookup[key].role_id, lookup[key].occurrence) == (d.role_id, d.occurrence)]) != 1:
                    invalid()

    @property
    def execution_order(self):
        return _ordered_ids(self.decisions)

    @property
    def position_budget(self):
        return min(self.maximum_decisions, MAX_POSITIONS - self.input_prefix_end)
