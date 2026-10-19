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
Enrich = Callable[..., tuple[dict, ...]]
Check = Callable[..., bool]


@dataclass(frozen=True)
class RegisteredSourceAdapter:
    descriptor: SourceAdapter
    draw: Draw
    check: Check
    enrich: Enrich | None = None


class SourceAdapterRegistry:
    def __init__(self, adapters=()):
        self._by_generator: dict[str, RegisteredSourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: RegisteredSourceAdapter) -> None:
        if not isinstance(adapter, RegisteredSourceAdapter):
            raise TypeError("FACTORY_INVALID_REGISTERED_SOURCE_ADAPTER")
        if not callable(adapter.draw) or not callable(adapter.check):
            raise ValueError("FACTORY_SOURCE_CONSTRUCTOR_AND_CHECKER_REQUIRED")
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

    def teaching_rows(self, course, *, capability: str, option_id: str,
                      source_root, graph, seed: int) -> tuple[dict, ...]:
        cap = course.capability_map.get(capability)
        if cap is None:
            raise ValueError("FACTORY_TEACHING_UNKNOWN_CAPABILITY:" + str(capability))
        adapter = self.require(cap.lesson_generator, cap.independent_oracle)
        if option_id not in adapter.descriptor.teaching_option_ids:
            return ()
        if adapter.enrich is None:
            raise ValueError("FACTORY_TEACHING_OPTION_HAS_NO_IMPLEMENTATION:" + option_id)
        rows = adapter.enrich(
            source_root=source_root, graph=graph, course=course,
            capability=capability, seed=seed, option_id=option_id)
        if any(row.get("capability") != capability for row in rows):
            raise ValueError("FACTORY_TEACHING_ENRICHMENT_SCOPE_DRIFT:" + capability)
        return tuple(rows)

    def optional_teaching_rows(self, course, *, capability: str,
                               source_root, graph, seed: int,
                               enabled: bool) -> tuple[dict, ...]:
        """Run every adapter-declared optional enrichment for one capability."""
        if not enabled:
            return ()
        cap = course.capability_map.get(capability)
        if cap is None:
            raise ValueError("FACTORY_TEACHING_UNKNOWN_CAPABILITY:" + str(capability))
        adapter = self.require(cap.lesson_generator, cap.independent_oracle)
        rows = []
        for option_id in adapter.descriptor.teaching_option_ids:
            rows.extend(self.teaching_rows(
                course, capability=capability, option_id=option_id,
                source_root=source_root, graph=graph, seed=seed))
        return tuple(rows)

    def teaching_option_ids(self, course, capability: str) -> tuple[str, ...]:
        cap = course.capability_map.get(capability)
        if cap is None:
            raise ValueError("FACTORY_TEACHING_UNKNOWN_CAPABILITY:" + str(capability))
        return self.require(
            cap.lesson_generator, cap.independent_oracle).descriptor.teaching_option_ids
