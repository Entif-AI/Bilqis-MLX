"""Source-domain adapter registry used by the generic factory/runtime boundary.

The registry keys adapters by declared generator contract, never by grade letter.
Current A/B/C implementation functions are compatibility providers while callers
migrate; they are not consulted by generic control flow through grade identity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .autonomy import SupplementalEvidenceSpec
from .model import SourceAdapter


Draw = Callable[..., tuple[dict, ...]]
Enrich = Callable[..., tuple[dict, ...]]
Check = Callable[..., bool]
Witness = Callable[..., bool]
Dependencies = Callable[..., tuple[SupplementalEvidenceSpec, ...]]


@dataclass(frozen=True)
class RegisteredSourceAdapter:
    descriptor: SourceAdapter
    draw: Draw
    check: Check
    enrich: Enrich | None = None
    witness: Witness | None = None
    dependencies: Dependencies | None = None


class SourceAdapterRegistry:
    def __init__(self, adapters=()):
        self._by_generator: dict[str, RegisteredSourceAdapter] = {}
        for adapter in adapters:
            self.register(adapter)

    def register(self, adapter: RegisteredSourceAdapter) -> None:
        if not isinstance(adapter, RegisteredSourceAdapter):
            raise TypeError("FACTORY_INVALID_REGISTERED_SOURCE_ADAPTER")
        if (not callable(adapter.draw) or not callable(adapter.check) or
                (adapter.enrich is not None and not callable(adapter.enrich)) or
                (adapter.witness is not None and not callable(adapter.witness)) or
                (adapter.dependencies is not None and
                 not callable(adapter.dependencies))):
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

    def obligation_witness(self, course, *, capability: str, row: dict,
                           obligation, source_root, graph, release=None) -> bool:
        """Ask the source dialect whether one row proves a semantic obligation.

        Direct evidence needs no dialect-specific interpretation. Structural
        obligations do: the source adapter must certify that the row actually
        exercises the requested prerequisite/composition edge.
        """
        if release is None:
            cap = course.capability_map.get(capability)
            if cap is None:
                raise ValueError("FACTORY_EVIDENCE_UNKNOWN_CAPABILITY:" + str(capability))
            adapter = self.require(cap.lesson_generator, cap.independent_oracle)
            witness_course = course
        else:
            binding = release.source_bindings.by_capability.get(capability)
            if capability not in release.execution_plan.capability_map or binding is None:
                raise ValueError("FACTORY_EVIDENCE_UNKNOWN_CAPABILITY:" + str(capability))
            adapter = self.require(binding.generator_id, binding.oracle_id)
            witness_course = release.curriculum
        kind = getattr(getattr(obligation, "kind", None), "value", None)
        if kind == "DIRECT":
            return True
        if adapter.witness is None:
            raise ValueError("FACTORY_EVIDENCE_WITNESS_ADAPTER_REQUIRED")
        result = adapter.witness(
            row, obligation,
            source_root=source_root, graph=graph, course=witness_course)
        if type(result) is not bool:
            raise ValueError("FACTORY_EVIDENCE_WITNESS_RESULT_INVALID")
        return result

    def evidence_dependencies(
        self, course, *, release=None,
    ) -> tuple[SupplementalEvidenceSpec, ...]:
        """Collect provider-owned proof metadata without altering Course."""
        result = []
        if release is not None:
            active = set(release.execution_plan.capability_map)
            for execution in release.execution_plan.capabilities:
                binding = release.source_bindings.by_capability[execution.capability_id]
                adapter = self.require(binding.generator_id, binding.oracle_id)
                if adapter.dependencies is None:
                    continue
                supplied = adapter.dependencies(course=course, capability=execution.capability_id)
                for item in supplied:
                    if (not isinstance(item, SupplementalEvidenceSpec) or
                            item.capability_id != execution.capability_id):
                        raise ValueError("FACTORY_EVIDENCE_DEPENDENCY_SCOPE_DRIFT")
                    if set(item.requires_capabilities) <= active:
                        result.append(item)
            return tuple(result)
        for grade in course.grades:
            for cap in grade.capabilities:
                adapter = self.require(
                    cap.lesson_generator, cap.independent_oracle)
                if adapter.dependencies is None:
                    continue
                supplied = adapter.dependencies(
                    course=course, capability=cap.id)
                if any(not isinstance(item, SupplementalEvidenceSpec)
                       for item in supplied):
                    raise ValueError(
                        "FACTORY_EVIDENCE_DEPENDENCY_RESULT_INVALID")
                if any(item.capability_id != cap.id for item in supplied):
                    raise ValueError(
                        "FACTORY_EVIDENCE_DEPENDENCY_SCOPE_DRIFT")
                result.extend(supplied)
        identities = [
            (item.capability_id, item.kind, item.key) for item in result]
        if len(set(identities)) != len(identities):
            raise ValueError("FACTORY_EVIDENCE_DEPENDENCY_DUPLICATE")
        return tuple(result)
