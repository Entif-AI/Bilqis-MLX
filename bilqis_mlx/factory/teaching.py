"""Execute a released teaching option and preserve the delivered instruction."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json

from .generation import draw_executable_release_rows, runtime_adapter_for_release
from .adapters import validate_instructional_constituents


def content_digest(rows) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def optional_teaching_rows(source_root, graph, release, registry, *,
                           capability, seed, enabled, legacy_course=None):
    if not enabled:
        return ()
    execution = release.execution_plan.capability_map[capability]
    descriptor = next(item for item in release.source_adapters
                      if item.adapter_id == execution.provider_id)
    return tuple(row for option in descriptor.teaching_option_ids
                 for row in draw_teaching_option_rows(
                     source_root, graph, release, registry, capability=capability,
                     option_id=option, seed=seed, each=execution.exam_item_count,
                     legacy_course=legacy_course))


def draw_teaching_option_rows(source_root, graph, release, registry, *,
                              capability, option_id, seed, each, legacy_course=None):
    release.verify()
    execution = release.execution_plan.capability_map[capability]
    if option_id not in execution.teaching_option_ids:
        raise ValueError("FACTORY_TEACHING_OPTION_NOT_RELEASED")
    if option_id == "source.direct/" + capability:
        return tuple(draw_executable_release_rows(
            source_root, graph, release, registry, capability=capability,
            seed=seed, each=each, legacy_course=legacy_course))
    adapter = runtime_adapter_for_release(
        source_root, graph, release, registry, execution,
        legacy_course=legacy_course,
        drift_code="FACTORY_TEACHING_PROVIDER_DRIFT")
    if adapter.enrich is None or option_id not in adapter.descriptor.teaching_option_ids:
        raise ValueError("FACTORY_TEACHING_OPTION_HAS_NO_IMPLEMENTATION")
    rows = tuple(adapter.enrich(source_root=source_root, graph=graph,
                               course=legacy_course, capability=capability,
                               option_id=option_id, seed=seed))
    if not rows:
        raise ValueError("FACTORY_TEACHING_OPTION_EMPTY")
    allowed = {capability, *execution.prerequisites}
    for row in rows:
        constituent = release.execution_plan.capability_map.get(row.get("capability"))
        answers = ({family.kind: family.values for family in constituent.answer_families}
                   if constituent is not None else {})
        if (row.get("capability") not in allowed or constituent is None or
                constituent.provider_id != execution.provider_id or
                constituent.provider_implementation_sha256 != execution.provider_implementation_sha256 or
                not row.get("id") or
                row.get("gold") not in answers.get(row.get("answer_kind", "binary"), ()) or
                adapter.check(row, source_root=source_root, graph=graph,
                              course=legacy_course) is not True):
            raise ValueError("FACTORY_TEACHING_SOURCE_ORACLE_DISAGREEMENT")
        validate_instructional_constituents(
            row, curriculum=release.curriculum, plan=release.execution_plan,
            capability=constituent.capability_id, adapter=adapter)
    return rows


@dataclass(frozen=True)
class DeliveredTeaching:
    option_id: str
    provider_id: str
    provider_implementation_sha256: str
    variation_axes: tuple[str, ...]
    specimen_ids: tuple[str, ...]
    specimen_content_sha256: str


def describe_delivered_teaching(release, capability, option_id, rows) -> DeliveredTeaching:
    execution = release.execution_plan.capability_map[capability]
    if option_id not in execution.teaching_option_ids or not rows:
        raise ValueError("FACTORY_TEACHING_DELIVERY_UNPROVEN")
    identities = tuple(dict.fromkeys(row["id"] for row in rows))
    return DeliveredTeaching(option_id, execution.provider_id,
        execution.provider_implementation_sha256, execution.variation_axes,
        identities, content_digest(rows))
