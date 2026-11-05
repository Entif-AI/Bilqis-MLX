"""B09.2 pure per-step participation and optimizer-mask derivation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import mlx.core as mx

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.learning.atlas_engram_reads import MotifReadResult
from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.runtime.topology_v2.dimensions import FEATURE_ROWS


PARTICIPATION_SCHEMA = "bilqis.mlx.step-participation/v1"
MASK_SCHEMA = "bilqis.mlx.parameter-update-mask/v1"
ACTIVE_SCHEMA = "bilqis.mlx.active-admitted-rows/v1"
INPUT_SCHEMA = "bilqis.mlx.step-participation-inputs/v1"
DENOMINATOR_SCHEMA = "bilqis.mlx.semantic-denominator/v1"
ROLE_READ_SCHEMA = "bilqis.mlx.role-read-participation/v1"
FEATURE_TABLES = frozenset({"type", "role", "schema"})


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _pairs(value) -> bool:
    return (type(value) is tuple
            and value == tuple(sorted(set(value)))
            and all(type(item) is tuple and len(item) == 2
                    and type(item[0]) is int and item[0] >= 0
                    and type(item[1]) is int
                    and 0 <= item[1] < ModelTopologySpecV2.semantic_bank_rows
                    for item in value))


def _feature_rows(value) -> bool:
    return (type(value) is tuple
            and value == tuple(sorted(set(value)))
            and all(type(item) is tuple and len(item) == 2
                    and item[0] in FEATURE_TABLES
                    and type(item[1]) is int and 0 <= item[1] < FEATURE_ROWS
                    for item in value))


def _rows(value) -> bool:
    return (type(value) is tuple
            and value == tuple(sorted(set(value)))
            and all(type(item) is int and item >= 0 for item in value))


@dataclass(frozen=True)
class StepParticipationInputs:
    visible_identity_rows: tuple[tuple[int, int], ...] = ()
    feedback_identity_rows: tuple[tuple[int, int], ...] = ()
    visible_feature_rows: tuple[tuple[str, int], ...] = ()
    local_slot_rows: tuple[int, ...] = ()
    executed_parameter_names: tuple[str, ...] = ()
    loss_bearing_target: bool = True
    schema_version: str = INPUT_SCHEMA

    def __post_init__(self) -> None:
        if (not _pairs(self.visible_identity_rows)
                or not _pairs(self.feedback_identity_rows)
                or not _feature_rows(self.visible_feature_rows)
                or not _rows(self.local_slot_rows)
                or type(self.executed_parameter_names) is not tuple
                or self.executed_parameter_names != tuple(sorted(set(self.executed_parameter_names)))
                or any(not isinstance(name, str) or not name
                       for name in self.executed_parameter_names)
                or type(self.loss_bearing_target) is not bool
                or self.schema_version != INPUT_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class SemanticDenominator:
    identity_rows: tuple[tuple[int, int], ...] = ()
    feature_rows: tuple[tuple[str, int], ...] = ()
    schema_version: str = DENOMINATOR_SCHEMA

    def __post_init__(self) -> None:
        if (not _pairs(self.identity_rows) or not _feature_rows(self.feature_rows)
                or self.schema_version != DENOMINATOR_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class RoleReadParticipation:
    feature_rows: tuple[tuple[str, int], ...] = ()
    schema_version: str = ROLE_READ_SCHEMA

    def __post_init__(self) -> None:
        if not _feature_rows(self.feature_rows) or self.schema_version != ROLE_READ_SCHEMA:
            _invalid()


@dataclass(frozen=True)
class ActiveAdmittedRows:
    identity_rows: tuple[tuple[int, int], ...] = ()
    motif_slots: tuple[int, ...] = ()
    feature_rows: tuple[tuple[str, int], ...] = ()
    local_slot_rows: tuple[int, ...] = ()
    schema_version: str = ACTIVE_SCHEMA

    def __post_init__(self) -> None:
        if (not _pairs(self.identity_rows)
                or type(self.motif_slots) is not tuple
                or self.motif_slots != tuple(sorted(set(self.motif_slots)))
                or any(type(slot) is not int or not 0 <= slot <
                       ModelTopologySpecV2.max_motif_pages * ModelTopologySpecV2.motif_page_rows
                       for slot in self.motif_slots)
                or not _feature_rows(self.feature_rows)
                or not _rows(self.local_slot_rows)
                or self.schema_version != ACTIVE_SCHEMA):
            _invalid()


@dataclass(frozen=True)
class StepParticipation:
    identity_rows: tuple[tuple[int, int], ...]
    motif_slots: tuple[int, ...]
    feature_rows: tuple[tuple[str, int], ...]
    local_slot_rows: tuple[int, ...]
    dense_parameter_names: tuple[str, ...]
    loss_bearing_target: bool
    schema_version: str = PARTICIPATION_SCHEMA

    def __post_init__(self) -> None:
        if (not _pairs(self.identity_rows)
                or type(self.motif_slots) is not tuple
                or self.motif_slots != tuple(sorted(set(self.motif_slots)))
                or any(type(slot) is not int or slot < 0 for slot in self.motif_slots)
                or not _feature_rows(self.feature_rows)
                or not _rows(self.local_slot_rows)
                or type(self.dense_parameter_names) is not tuple
                or self.dense_parameter_names != tuple(sorted(set(self.dense_parameter_names)))
                or any(not isinstance(name, str) or not name
                       for name in self.dense_parameter_names)
                or type(self.loss_bearing_target) is not bool
                or self.schema_version != PARTICIPATION_SCHEMA):
            _invalid()


def step_participation(
    inputs: StepParticipationInputs,
    semantic_denominator: SemanticDenominator,
    motif_reads: tuple[MotifReadResult, ...],
    role_reads: RoleReadParticipation,
) -> StepParticipation:
    """Derive actual objective participation; no optimizer state is touched."""
    if (type(inputs) is not StepParticipationInputs
            or type(semantic_denominator) is not SemanticDenominator
            or type(motif_reads) is not tuple
            or any(type(item) is not MotifReadResult for item in motif_reads)
            or type(role_reads) is not RoleReadParticipation):
        _invalid()
    inputs.__post_init__()
    semantic_denominator.__post_init__()
    role_reads.__post_init__()
    if not inputs.loss_bearing_target:
        return StepParticipation((), (), (), (), (), False)
    identity = tuple(sorted(set(
        inputs.visible_identity_rows + inputs.feedback_identity_rows
        + semantic_denominator.identity_rows)))
    motif = tuple(sorted({
        slot for result in motif_reads for slot in result.participating_slots
    }))
    features = tuple(sorted(set(
        inputs.visible_feature_rows
        + semantic_denominator.feature_rows + role_reads.feature_rows)))
    return StepParticipation(
        identity, motif, features, inputs.local_slot_rows,
        inputs.executed_parameter_names, True)


@dataclass(frozen=True)
class ParameterMask:
    name: str
    whole_parameter: bool
    row_indices: tuple[int, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.name, str) or not self.name
                or type(self.whole_parameter) is not bool
                or type(self.row_indices) is not tuple
                or self.row_indices != tuple(sorted(set(self.row_indices)))
                or any(type(row) is not int or row < 0 for row in self.row_indices)
                or (self.whole_parameter and self.row_indices)):
            _invalid()


@dataclass(frozen=True)
class UpdateMask:
    parameters: tuple[ParameterMask, ...]
    participating_identity_rows: tuple[tuple[int, int], ...]
    has_loss_bearing_target: bool
    schema_version: str = MASK_SCHEMA

    def __post_init__(self) -> None:
        names = tuple(item.name for item in self.parameters)
        if (any(type(item) is not ParameterMask for item in self.parameters)
                or names != tuple(sorted(set(names)))
                or not _pairs(self.participating_identity_rows)
                or type(self.has_loss_bearing_target) is not bool
                or self.schema_version != MASK_SCHEMA):
            _invalid()

    def parameter(self, name: str) -> ParameterMask:
        item = next((item for item in self.parameters if item.name == name), None)
        if item is None:
            _invalid()
        return item


def _row_mask(name: str, participation: StepParticipation,
              active: ActiveAdmittedRows) -> tuple[int, ...] | None:
    if name.startswith("identity.bank."):
        bank = int(name.rsplit(".", 1)[-1])
        return tuple(row for candidate_bank, row in participation.identity_rows
                     if candidate_bank == bank and (candidate_bank, row) in active.identity_rows)
    if name.startswith("motif.page."):
        page = int(name.rsplit(".", 1)[-1])
        width = ModelTopologySpecV2.motif_page_rows
        return tuple(slot % width for slot in participation.motif_slots
                     if slot // width == page and slot in active.motif_slots)
    for table in FEATURE_TABLES:
        if name == f"features.{table}":
            return tuple(row for candidate_table, row in participation.feature_rows
                         if candidate_table == table
                         and (candidate_table, row) in active.feature_rows)
    if name == "features.local_slot":
        return tuple(row for row in participation.local_slot_rows
                     if row in active.local_slot_rows)
    return None


def _parameter_update_mask(group_eligible, participation: StepParticipation,
                          active_admitted: ActiveAdmittedRows) -> UpdateMask:
    """Final legal mask = candidate group × step participation × active/admitted."""
    from bilqis_mlx.learning.atlas_plasticity import GroupEligibility
    if (type(group_eligible) is not GroupEligibility
            or type(participation) is not StepParticipation
            or type(active_admitted) is not ActiveAdmittedRows):
        _invalid()
    group_eligible.__post_init__()
    participation.__post_init__()
    active_admitted.__post_init__()
    names = tuple(sorted(
        group_eligible.eligible_parameter_names + group_eligible.frozen_parameter_names))
    eligible = set(group_eligible.eligible_parameter_names)
    dense = set(participation.dense_parameter_names)
    masks = []
    for name in names:
        rows = _row_mask(name, participation, active_admitted)
        if rows is not None:
            if name.startswith("identity.bank."):
                bank = int(name.rsplit(".", 1)[-1])
                admitted = set(group_eligible.admitted_identity_rows)
                if group_eligible.mode == "FAST":
                    admitted &= set(group_eligible.fast_identity_rows)
                rows = tuple(row for row in rows if (bank, row) in admitted)
                allowed = group_eligible.mode == "FAST" or name in eligible
                masks.append(ParameterMask(name, False, rows if allowed else ()))
            else:
                masks.append(ParameterMask(name, False, rows if name in eligible else ()))
        else:
            masks.append(ParameterMask(
                name, name in eligible and name in dense and participation.loss_bearing_target, ()))
    effective_identity = tuple(sorted(
        (int(item.name.rsplit(".", 1)[-1]), row)
        for item in masks if item.name.startswith("identity.bank.")
        for row in item.row_indices))
    return UpdateMask(
        tuple(masks), effective_identity, participation.loss_bearing_target)


def parameter_update_mask(group_eligible, participation, active_admitted, *, spec, extents):
    """Validate B01 groups; upstream execution provenance remains required."""
    from bilqis_mlx.learning.atlas_participation_census import validate_group_census
    validate_group_census(group_eligible, spec, extents)
    return _parameter_update_mask(group_eligible, participation, active_admitted)


def optimizer_participation_mask(
    mask: UpdateMask,
    update_counts: Mapping[str, mx.array],
) -> dict[str, mx.array]:
    """Materialize B09 authority in the exact Boolean geometry B12 consumes.

    This is a representation bridge, not a second participation decision. A
    selected row remains selected even when its numerical gradient is zero, so
    B12 can advance moments/counts/decay from the same B09 decision.
    """
    if type(mask) is not UpdateMask or not isinstance(update_counts, Mapping):
        _invalid()
    mask.__post_init__()
    if set(update_counts) != {item.name for item in mask.parameters}:
        _invalid()
    result = {}
    for item in mask.parameters:
        count = update_counts[item.name]
        if (not isinstance(count, mx.array) or count.dtype != mx.uint64
                or count.ndim not in (0, 1)):
            _invalid()
        if count.ndim == 0:
            if item.row_indices:
                _invalid()
            result[item.name] = mx.array(
                item.whole_parameter, dtype=mx.bool_)
            continue
        if any(row >= count.shape[0] for row in item.row_indices):
            _invalid()
        values = [item.whole_parameter] * count.shape[0]
        if not item.whole_parameter:
            for row in item.row_indices:
                values[row] = True
        result[item.name] = mx.array(values, dtype=mx.bool_)
    return result


def mask_gradients(
    gradients: Mapping[str, mx.array], mask: UpdateMask,
) -> dict[str, mx.array]:
    """Apply B09 masks before clipping; B12 still owns moments/counts/AdamW."""
    if not isinstance(gradients, Mapping) or type(mask) is not UpdateMask:
        _invalid()
    mask.__post_init__()
    if set(gradients) != {item.name for item in mask.parameters}:
        _invalid()
    result = {}
    for item in mask.parameters:
        gradient = gradients[item.name]
        if not isinstance(gradient, mx.array):
            _invalid()
        if item.whole_parameter:
            result[item.name] = gradient
        elif item.row_indices:
            selected = mx.zeros_like(gradient)
            selected[item.row_indices] = gradient[item.row_indices]
            result[item.name] = selected
        else:
            result[item.name] = mx.zeros_like(gradient)
    return result
