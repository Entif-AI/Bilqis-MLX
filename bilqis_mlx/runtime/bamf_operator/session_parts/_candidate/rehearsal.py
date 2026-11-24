"""Authority-bounded R14 rehearsal planning for native BAMF lessons."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.structural_weakness_ledger import _ledger_key
from .rehearsal_allocation import (
    reserve_preservation as _reserve_preservation, scheduled_pairs, valid_allocation,
)
from .weakness_rehearsal import _draw_size, targeted_groups
from bilqis_mlx.source_adapters.lesson_geometry import (
    LessonGeometry, complete_groups, distinct_groups, geometry_for_adapter,
)
from bilqis_mlx.runtime.factory_retention_owner import require_current_retention_plan
from bilqis_mlx.runtime.priority_rejection_replay import current_structural_weaknesses
from bilqis_mlx.semantic_sampling import DEFAULT_BINARY_BALANCE
from bilqis_mlx.semantics.domains import contract_digest


_SOURCE_DRAW_EACH = DEFAULT_BINARY_BALANCE.minimum_total


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_CURRICULUM.INVALID, reason=reason)


@dataclass(frozen=True)
class RehearsalPlan:
    target_capability_id: str
    target_grade_id: str
    prior_capability_ids: tuple[str, ...]
    retention_support_capability_ids: tuple[str, ...]
    weakness_records: tuple[dict, ...]
    protection_plan_sha256: str
    active_grade_definition_sha256: str
    active_grade_activation_sha256: str
    identity: str
    weakness_exposures: tuple[tuple[str, int], ...] = ()
    weakness_capacity: int = 0
    support_geometries: tuple[tuple[str, LessonGeometry | None], ...] = ()
    preservation_allocation: dict | None = None


@dataclass(frozen=True)
class RehearsalRows:
    prior: tuple[dict, ...] = ()
    preservation: tuple[dict, ...] = ()
    retention_support: tuple[dict, ...] = ()
    bindings: tuple[dict, ...] = ()
    authorities: tuple[tuple[str, object], ...] = ()
    weakness_unavailable: tuple[tuple[str, str], ...] = ()

    @property
    def by_id(self) -> dict[str, str]:
        return {
            **{row["id"]: "prior" for row in self.prior},
            **{row["id"]: "preservation" for row in self.preservation},
            **{row["id"]: "retention_support" for row in self.retention_support},
        }

    @property
    def bindings_by_id(self) -> dict[str, dict]:
        return {item["row_id"]: item for item in self.bindings}

    @property
    def authorities_by_id(self) -> dict[str, object]:
        return dict(self.authorities)


def _seed(plan: RehearsalPlan, role: str, capability: str, ordinal: int) -> int:
    digest = hashlib.sha256(
        f"{plan.identity}|{role}|{capability}|{ordinal}".encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _support_geometry(source_context, capability):
    from bilqis_mlx.runtime.structural_weakness_capture import _provider_for_context

    _, adapter, _ = _provider_for_context(source_context, capability)
    return geometry_for_adapter(adapter)


def reserve_preservation(source_context, offer, pool, protection, target, teacher, scope):
    return _reserve_preservation(
        source_context, offer, pool, protection, target, teacher, scope,
        geometry_for_capability=_support_geometry)


def reserve_visit_preservation(source_context, parent, cache, offer, pool, teacher, scope):
    """Bind the allocation to the already-accepted student's protection scope."""
    from bilqis_mlx.runtime.bamf_bundle.execution_cache import AcceptedExecutionCache
    from bilqis_mlx.runtime.factory_retention_owner import bind_current_retention_protection_plan

    if type(cache) is not AcceptedExecutionCache:
        return pool, None
    protection = bind_current_retention_protection_plan(source_context, parent, cache)
    return reserve_preservation(
        source_context, offer, pool, protection,
        protection.for_target(offer.capability_id), teacher, scope)


def compile_rehearsal_plan(run_dir, parent, cache, source_context, selection) -> RehearsalPlan:
    """Compile WHAT to rehearse from R05/R13 authority without choosing curriculum."""
    capability = selection.offer.capability_id
    protection, target = require_current_retention_plan(
        cache, source_context.release, capability)
    execution = source_context.release.execution_plan.capability_map[capability]
    if target.target_grade_id != execution.grade_id:
        _invalid("BAMF_REHEARSAL_GRADE_AUTHORITY_DRIFT")
    from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
    active = read_active_generated_grade(Path(run_dir), repair=False)
    if capability not in active.member_capability_ids:
        _invalid("BAMF_REHEARSAL_TARGET_OUTSIDE_ACTIVE_GRADE")
    from bilqis_mlx.runtime.retention.protection_plan import ProtectionReason
    prior_reasons = {ProtectionReason.PREREQUISITE, ProtectionReason.CONSTITUENT}
    prior = tuple(sorted({
        edge.capability_id for edge in target.affected_edges
        if edge.reason in prior_reasons
        and edge.capability_id in set(target.protected_capability_ids)
    }))
    support = tuple(
        item for item in target.protected_capability_ids if item not in set(prior))
    geometries = tuple((cap, _support_geometry(source_context, cap)) for cap in support)
    weaknesses = current_structural_weaknesses(
        run_dir, parent, cache, source_context, selection, capability)
    scored = tuple(item for item in weaknesses
                   if item["weakness"].get("evidence_kind") == "SCORED_PARENT_MISS")
    weakness_records = tuple(item["weakness"] for item in scored)
    exposures = tuple(sorted((_ledger_key(item["weakness"]), item.get("exposure_count", 0))
                             for item in scored))
    capacity = selection.offer.source_each if scored else 0
    allocation = (getattr(selection, "metadata", None) or {}).get("preservation_allocation")
    if allocation is not None and not valid_allocation(
            allocation, protection.digest, target.protected_capability_ids,
            selection.offer.source_each):
        _invalid("BAMF_REHEARSAL_ALLOCATION_AUTHORITY_DRIFT")
    payload = {
        **({"preservation_allocation": allocation} if allocation is not None else {}),
        "schema": "bilqis.bamf.rehearsal-plan/v2",
        # A rejected candidate leaves generation and protection identity
        # unchanged. Bind fresh rehearsal to the actual issued visit as well.
        "teacher_visit_id": selection.visit.identity.visit_id,
        "target_capability_id": capability,
        "target_grade_id": target.target_grade_id,
        "prior_capability_ids": prior,
        "retention_support_capability_ids": support,
        "support_geometries": tuple((cap, asdict(geometry) if geometry else None)
                                    for cap, geometry in geometries),
        "weakness_evidence_sha256": tuple(
            item["weakness_evidence_sha256"] for item in weakness_records),
        **({"weakness_exposures": exposures, "weakness_capacity": capacity}
           if scored else {}),
        "protection_plan_sha256": protection.digest,
        "active_grade_definition_sha256": active.definition.definition_sha256,
        "active_grade_activation_sha256": active.activation_sha256,
    }
    return RehearsalPlan(
        capability, target.target_grade_id, prior, support, weakness_records,
        protection.digest, active.definition.definition_sha256,
        active.activation_sha256, contract_digest(payload), exposures, capacity, geometries,
        allocation)


def _binding(source_context, row, authority, *, role, capability, seed, each):
    execution = source_context.execution_for(capability)
    family = row.get("source_family_id")
    if not isinstance(family, str) or not family:
        family = contract_digest({
            "schema": "bilqis.mlx.source-draw-family/v1",
            "provider": execution.provider_id,
            "implementation": execution.provider_implementation_sha256,
            "capability": capability,
        })
    episode = row.get("episode_id")
    if not isinstance(episode, str) or not episode:
        episode = row["id"]
    if (authority.capability_id != capability or authority.seed != seed
            or authority.each != each or authority.source_family_id != family):
        _invalid("BAMF_REHEARSAL_SOURCE_AUTHORITY_DRIFT")
    return {
        "row_id": row["id"], "role": role, "capability": capability,
        "seed": seed, "each": each, "source_family_id": family,
        "episode_id": episode,
    }


def _draw_rehearsal(source_context, plan, role, capability, ordinal, *, pairs=0):
    seed = _seed(plan, role, capability, ordinal)
    geometry = dict(plan.support_geometries).get(capability) if role == "retention_support" else None
    each = _SOURCE_DRAW_EACH if geometry is None else _draw_size(geometry, _SOURCE_DRAW_EACH)
    if pairs:
        each = max(_SOURCE_DRAW_EACH, 2 * pairs)
    rows, parent_authority = source_context.draw_bound_rows(
        seed=seed, capability=capability, each=each)
    rows = tuple(rows)
    if (len(rows) != each
            or any(row.get("capability") != capability for row in rows)):
        _invalid("BAMF_REHEARSAL_SOURCE_DRAW_INVALID")
    if pairs:
        selected = []
        for gold in ("TRUE", "FALSE"):
            bucket = tuple(row for row in rows if row["gold"] == gold)
            if len(bucket) < pairs:
                _invalid("BAMF_REHEARSAL_BALANCED_DRAW_UNAVAILABLE")
            start = seed % len(bucket)
            selected.extend((bucket[start:] + bucket[:start])[:pairs])
        if len(selected) != 2 * pairs:
            _invalid("BAMF_REHEARSAL_BALANCED_DRAW_UNAVAILABLE")
    elif geometry is not None:
        groups = distinct_groups(complete_groups(rows, geometry))
        if not groups:
            _invalid("BAMF_REHEARSAL_SOURCE_DRAW_INVALID")
        selected = groups[seed % len(groups)].rows
    else:
        selected = (rows[seed % len(rows)],)
    result = []
    for row in selected:
        authority = source_context.bind_authorized_subset_rows(
            rows, (row,), parent_authority)
        result.append((row, _binding(
            source_context, row, authority, role=role, capability=capability,
            seed=seed, each=1), authority))
    return tuple(result)


def materialize_rehearsal_rows(source_context, plan: RehearsalPlan, ordinal: int, *,
                               reserved_rows=(), exposure_counts=None) -> RehearsalRows:
    """Materialize fresh rows for an already-compiled plan; never expand its scope."""
    allocation = plan.preservation_allocation
    if allocation is None:
        draws = dict.fromkeys((*plan.prior_capability_ids,
                               *plan.retention_support_capability_ids), 0)
    else:
        draws = scheduled_pairs(allocation, ordinal, int(plan.identity[:16], 16))
    prior_pairs = tuple(item for cap in plan.prior_capability_ids if cap in draws
                        for item in _draw_rehearsal(
                            source_context, plan, "prior", cap, ordinal, pairs=draws[cap]))
    support_pairs = tuple(item for cap in plan.retention_support_capability_ids if cap in draws
                          for item in _draw_rehearsal(
                              source_context, plan, "retention_support", cap, ordinal, pairs=draws[cap]))
    prior = tuple(row for row, _binding_record, _authority in prior_pairs)
    support = tuple(row for row, _binding_record, _authority in support_pairs)
    bindings = [record for _row, record, _authority in (*prior_pairs, *support_pairs)]
    authorities = [(row["id"], authority)
                   for row, _record, authority in (*prior_pairs, *support_pairs)]
    preservation = []
    groups, unavailable = targeted_groups(
        source_context, plan, ordinal, _seed, _SOURCE_DRAW_EACH,
        reserved_rows=(*reserved_rows, *prior, *support), exposure_counts=exposure_counts)
    for group in groups:
        matches = dict(group.matches)
        for row in group.rows:
            authority = source_context.bind_authorized_subset_rows(
                group.parent_rows, (row,), group.authority)
            binding = _binding(
                source_context, row, authority, role="preservation",
                capability=plan.target_capability_id, seed=group.seed, each=1)
            if row["id"] in matches:
                binding["weakness_debt_key"] = matches[row["id"]]
            preservation.append(row)
            bindings.append(binding)
            authorities.append((row["id"], authority))
    rows = RehearsalRows(
        prior, tuple(preservation), support, tuple(bindings), tuple(authorities), unavailable)
    ids = [row["id"] for row in (*rows.prior, *rows.preservation, *rows.retention_support)]
    if len(ids) != len(set(ids)):
        _invalid("BAMF_REHEARSAL_ROW_ID_COLLISION")
    if set(ids) != set(rows.bindings_by_id):
        _invalid("BAMF_REHEARSAL_BINDING_COVERAGE_INVALID")
    if set(ids) != set(rows.authorities_by_id):
        _invalid("BAMF_REHEARSAL_AUTHORITY_COVERAGE_INVALID")
    return rows


__all__ = (
    "RehearsalPlan", "RehearsalRows", "compile_rehearsal_plan",
    "materialize_rehearsal_rows", "reserve_preservation", "reserve_visit_preservation",
)
