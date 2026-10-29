"""B08.1 experimental exact/structural motif reads at the two B01 sites.

No slot allocation, optimizer write, checkpoint publication or depth placement
occurs here. B08.2/B11 own placement and the complete neural generation.
EGM_BLOCKED: the local schema-grant convention is caller-mintable and MUST NOT
be wired into a production reader until A03/B07.1 source-owned schema authority
and a complete cache identity are integrated. See B08.1/egm.md.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.semantics.context_eligibility import (
    ApprovedContextProjection, ContextEligibility, ContextHold,
    ContextPolicy, SourceFrontier, TaskScope, project_context,
)
from bilqis_mlx.semantics.frame_schema import AtomicFrame, FrameInstance, FrameSchema
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from .atlas_engram import (
    INITIAL_MOTIF_CAPACITY, MotifFrameInput, MotifManifest, motif_keys,
)
from .atlas_engram_parameters import MotifParameterView, SITE_COUNT


READ_SCHEMA = "bilqis.mlx.motif-read-result/v1"
POSITION_SCHEMA = "bilqis.mlx.motif-read-position/v1"
WIDTH = ModelTopologySpecV2.width
MOTIF_WIDTH = 128
READ_TENSOR_RANK = 3
FEATURE_AXIS = 2
BATCH_PREFIX_AXES = 2
DISPOSITIONS = frozenset({"EXACT", "STRUCTURAL", "MISS", "HELD", "FOREIGN_RELEASE"})
_SHA = re.compile(r"[0-9a-f]{64}\Z")


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def schema_source_handle(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _invalid()
    return f"source:motif-schema:{schema.identity}"


def schema_evidence_digest(schema: FrameSchema) -> str:
    if type(schema) is not FrameSchema:
        _invalid()
    return hashlib.sha256(schema.canonical_bytes()).hexdigest()


def _schema_grant_live(
    schema: FrameSchema, envelope: ContextEligibility,
    task: TaskScope, frontier: SourceFrontier,
) -> bool:
    grant = next(
        (item for item in frontier.grants
         if item.source_handle == schema_source_handle(schema)), None)
    return bool(
        grant is not None and not grant.revoked
        and grant.evidence_digest == schema_evidence_digest(schema)
        and grant.semantic_release == task.semantic_release
        and grant.source_regime == envelope.source_regime
        and grant.principal_id == task.principal_id
        and grant.tenant_id == task.tenant_id
        and task.purpose in grant.permitted_purposes
        and task.jurisdiction in grant.permitted_jurisdictions
        and task.scope in grant.permitted_scopes
        and grant.rights_epoch == frontier.rights_epoch
        and grant.correction_generation == frontier.correction_generation
        and grant.observed_at <= task.observed_frontier
        and grant.effective_from <= task.effective_time
        and (grant.effective_until is None
             or task.effective_time < grant.effective_until)
    )


@dataclass(frozen=True)
class MotifReadPosition:
    envelope: ContextEligibility
    schema: FrameSchema | None
    schema_version: str = POSITION_SCHEMA

    def __post_init__(self) -> None:
        if (type(self.envelope) is not ContextEligibility
                or (self.schema is not None and type(self.schema) is not FrameSchema)
                or (type(self.envelope.frame) is FrameInstance
                    and (self.schema is None
                         or self.schema.schema_id
                         != self.envelope.frame.frame_schema_id
                         or self.schema.revision
                         != self.envelope.frame.frame_schema_revision))
                or (type(self.envelope.frame) is AtomicFrame
                    and self.schema is not None)
                or self.schema_version != POSITION_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class MotifReadResult:
    hidden: mx.array
    dispositions: tuple[tuple[str, ...], ...]
    participating_slots: tuple[int, ...]
    context_digests: tuple[str | None, ...]
    schema_version: str = READ_SCHEMA

    def __post_init__(self) -> None:
        if (not isinstance(self.hidden, mx.array)
                or self.hidden.ndim != READ_TENSOR_RANK
                or self.hidden.shape[FEATURE_AXIS] != WIDTH
                or self.hidden.dtype != mx.float32
                or not isinstance(self.dispositions, tuple)
                or len(self.dispositions) != self.hidden.shape[0]
                or any(not isinstance(row, tuple)
                       or len(row) != self.hidden.shape[1]
                       or any(item not in DISPOSITIONS for item in row)
                       for row in self.dispositions)
                or not isinstance(self.participating_slots, tuple)
                or any(type(slot) is not int or slot < 0
                       for slot in self.participating_slots)
                or self.participating_slots
                != tuple(sorted(set(self.participating_slots)))
                or not isinstance(self.context_digests, tuple)
                or len(self.context_digests) != self.hidden.shape[0]
                or any(item is not None
                       and (not isinstance(item, str)
                            or not _SHA.fullmatch(item))
                       for item in self.context_digests)
                or self.schema_version != READ_SCHEMA):
            _invalid()


def _read_motif_unqualified_candidate(
    *,
    site_index: int,
    hidden: mx.array,
    features: mx.array,
    positions: tuple[tuple[MotifReadPosition | None, ...], ...],
    tasks: tuple[TaskScope, ...],
    frontiers: tuple[SourceFrontier, ...],
    policies: tuple[ContextPolicy, ...],
    manifest: MotifManifest,
    parameters: MotifParameterView,
) -> MotifReadResult:
    """Experimental numerical proof only; not a source-authorized entrypoint.

    A row is source-gated as a *set* before a slot is gathered, so a
    disallowed join cannot leak through individually eligible frames.
    Caller-supplied feature128 must be bound to B02 source features by
    the B11 integration owner; it grants no source eligibility here.
    """
    if (type(site_index) is not int or not 0 <= site_index < SITE_COUNT
            or type(manifest) is not MotifManifest
            or type(parameters) is not MotifParameterView
            or parameters.site_index != site_index
            or manifest.capacity > parameters.page_count * INITIAL_MOTIF_CAPACITY
            or not isinstance(hidden, mx.array) or hidden.ndim != READ_TENSOR_RANK
            or hidden.shape[FEATURE_AXIS] != WIDTH or hidden.dtype != mx.float32
            or not isinstance(features, mx.array)
            or features.shape != (*hidden.shape[:BATCH_PREFIX_AXES], MOTIF_WIDTH)
            or features.dtype != mx.float32
            or not isinstance(positions, tuple)
            or not isinstance(tasks, tuple)
            or not isinstance(frontiers, tuple)
            or not isinstance(policies, tuple)
            or not (len(positions) == len(tasks) == len(frontiers)
                    == len(policies) == hidden.shape[0])
            or any(not isinstance(row, tuple) or len(row) != hidden.shape[1]
                   or any(item is not None and type(item) is not MotifReadPosition
                          for item in row) for row in positions)
            or any(type(item) is not TaskScope for item in tasks)
            or any(type(item) is not SourceFrontier for item in frontiers)
            or any(type(item) is not ContextPolicy for item in policies)
            or not bool(mx.all(mx.isfinite(hidden)))
            or not bool(mx.all(mx.isfinite(features)))):
        _invalid()
    parameters.__post_init__()
    projections = {name: parameters[name] for name in (
        "projection", "norm", "gate_hidden", "gate_feature", "bias")}
    output_rows = []
    dispositions = []
    context_digests = []
    participating = set()
    any_hit = False
    for row_index, row in enumerate(positions):
        envelopes = tuple(item.envelope for item in row if item is not None)
        task, frontier, policy = tasks[row_index], frontiers[row_index], policies[row_index]
        if not envelopes:
            output_rows.append(tuple(hidden[row_index, index] for index in range(hidden.shape[1])))
            dispositions.append(("MISS",) * hidden.shape[1])
            context_digests.append(None)
            continue
        projection = project_context(envelopes, task, frontier, policy)
        if isinstance(projection, ContextHold):
            output_rows.append(tuple(hidden[row_index, index] for index in range(hidden.shape[1])))
            dispositions.append(tuple(
                "HELD" if item is not None else "MISS" for item in row))
            context_digests.append(None)
            continue
        if type(projection) is not ApprovedContextProjection:
            _invalid()
        context_digests.append(projection.digest)
        output = []
        status = []
        for index, item in enumerate(row):
            state = hidden[row_index, index]
            if item is None or type(item.envelope.frame) is AtomicFrame:
                output.append(state)
                status.append("MISS")
                continue
            if task.semantic_release != manifest.semantic_release:
                output.append(state)
                status.append("FOREIGN_RELEASE")
                continue
            if (projection.frame(item.envelope.frame_handle)
                    != item.envelope.frame):
                _invalid()
            if not _schema_grant_live(
                    item.schema, item.envelope, task, frontier):
                output.append(state)
                status.append("HELD")
                continue
            exact, structural = motif_keys(
                MotifFrameInput(item.envelope.frame, item.schema),
                manifest.semantic_release)
            slot_id = manifest.lookup(exact)
            disposition = "EXACT"
            if slot_id is None:
                slot_id = manifest.lookup(structural)
                disposition = "STRUCTURAL"
            if slot_id is None:
                output.append(state)
                status.append("MISS")
                continue
            page_index, local_index = divmod(slot_id, INITIAL_MOTIF_CAPACITY)
            slot_vector = parameters[f"page.{page_index}"][local_index]
            normalized = mx.fast.rms_norm(
                state, projections["norm"], ModelTopologySpecV2.rms_norm_epsilon)
            gate_logit = (
                mx.sum(projections["gate_hidden"] * normalized) / math.sqrt(WIDTH)
                + mx.sum(projections["gate_feature"] * features[row_index, index])
                / math.sqrt(MOTIF_WIDTH)
                + projections["bias"][0]
            )
            gate = mx.sigmoid(gate_logit)
            output.append(state + gate * (projections["projection"] @ slot_vector))
            status.append(disposition)
            participating.add(slot_id)
            any_hit = True
        output_rows.append(tuple(output))
        dispositions.append(tuple(status))
    if not any_hit:
        return MotifReadResult(
            hidden, tuple(dispositions), (), tuple(context_digests))
    return MotifReadResult(
        mx.stack(tuple(mx.stack(row) for row in output_rows)),
        tuple(dispositions), tuple(sorted(participating)),
        tuple(context_digests),
    )


def read_motif(**_unqualified: object) -> MotifReadResult:
    """Fail closed until the A03/B07.1 released-schema issuer is available.

    The experimental numerical helper above is intentionally not exposed as
    an authorized runtime read. A caller-supplied SourceGrant is insufficient
    to mint canonical source-schema authority.
    """
    _invalid()
