"""Source-domain adapter registry used by the generic factory/runtime boundary.

The registry keys adapters by declared generator contract, never by grade letter.
Current A/B/C implementation functions are compatibility providers while callers
migrate; they are not consulted by generic control flow through grade identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .model import SourceAdapter


Draw = Callable[..., tuple[dict, ...]]


@dataclass(frozen=True)
class RegisteredSourceAdapter:
    descriptor: SourceAdapter
    draw: Draw


class SourceAdapterRegistry:
    def __init__(self, adapters=()):
        self._by_generator: dict[str, RegisteredSourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: RegisteredSourceAdapter) -> None:
        if not isinstance(adapter, RegisteredSourceAdapter):
            raise TypeError("FACTORY_INVALID_REGISTERED_SOURCE_ADAPTER")
        key = adapter.descriptor.generator_id
        if key in self._by_generator:
            raise ValueError("FACTORY_DUPLICATE_GENERATOR_ADAPTER:" + key)
        self._by_generator[key] = adapter

    def require(self, generator_id: str, oracle_id: str) -> RegisteredSourceAdapter:
        adapter = self._by_generator.get(generator_id)
        if adapter is None:
            raise ValueError("FACTORY_SOURCE_ADAPTER_MISSING:" + str(generator_id))
        if oracle_id not in adapter.descriptor.accepted_oracle_ids:
            raise ValueError("FACTORY_SOURCE_ORACLE_NOT_ADAPTER_OWNED:" + str(oracle_id))
        return adapter

    def descriptors_for(self, course) -> tuple[SourceAdapter, ...]:
        result = []
        seen = set()
        for grade in course.grades:
            for capability in grade.capabilities:
                item = self.require(capability.lesson_generator,
                                    capability.independent_oracle).descriptor
                if item.adapter_id not in seen:
                    seen.add(item.adapter_id)
                    result.append(item)
        return tuple(result)


def live_source_registry() -> SourceAdapterRegistry:
    """Compatibility bindings for the currently admitted source domains.

    All grade-neutral runtime callers consume this registry. These imports stay
    isolated here until the underlying source functions are moved into their
    final source-adapter packages.
    """
    from ..grade_a_oracle import VERSION as A_ORACLE
    from ..live_grade_a import (GENERATOR as A_COHORT_GENERATOR, RELEASE as A_RELEASE,
                                draw_predicates, generator_source_digest)
    from ..grade_b_oracle import VERSION as B_ORACLE
    from ..live_grade_b import (GENERATOR as B_COHORT_GENERATOR, RELEASE as B_RELEASE,
                                draw_connectives, constructor_digest as b_digest)
    from ..live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                                PLANS, constructor_digest as c_digest)
    from ..numeric_curriculum import ORACLE as C_ORACLE, draw_numeric
    from ..numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest

    def draw_a(*, source_root, graph, course, capability, seed, each):
        return draw_predicates(source_root, graph, seed=seed,
                               capability=capability, each=each)

    def draw_b(*, source_root, graph, course, capability, seed, each):
        return draw_connectives(source_root, graph, seed=seed,
                                capability=capability, each=each)

    def draw_c(*, source_root, graph, course, capability, seed, each):
        cap = course.capability_map[capability]
        numeric = next((family for family in cap.answer_families
                        if family.kind == "numeric_active"), None)
        if numeric is None:
            raise ValueError("FACTORY_NUMERIC_CAPABILITY_HAS_NO_ACTIVE_DOMAIN")
        maximum = len(numeric.values) - 1
        return draw_numeric(PLANS, graph, seed=seed, maximum=maximum,
                            capability=capability, each=each)

    return SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.predicates/v1", "bilqis_mlx.grade_a_probe.make_record",
            (A_ORACLE,), generator_source_digest(),
            cohort_generator_id=A_COHORT_GENERATOR,
            cohort_releases=((A_RELEASE, generator_source_digest()),)), draw_a),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-connectives/v1", "bilqis_mlx.live_grade_b.draw_connectives",
            (B_ORACLE,), b_digest(), cohort_generator_id=B_COHORT_GENERATOR,
            cohort_releases=((B_RELEASE, b_digest()),)), draw_b),
        RegisteredSourceAdapter(SourceAdapter(
            "source.finite-numeric/v1", "bilqis_mlx.numeric_curriculum.draw_numeric",
            (C_ORACLE,), c_digest(), cohort_generator_id=C_COHORT_GENERATOR,
            cohort_releases=((C_RELEASE, c_digest()),
                             (STAIRCASE_RELEASE, staircase_digest()))), draw_c),
    ))
