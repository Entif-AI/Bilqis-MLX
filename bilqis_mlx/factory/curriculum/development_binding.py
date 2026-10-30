"""Bind candidate developmental intent to already executable factory releases.

The bridge is read-only.  It cannot create a Capability, SourceAdapter, oracle,
grade, or FactoryRelease.  It only verifies that an independently constructed
release actually realizes the prerequisites and understanding probes declared
by a developmental blueprint.
"""
from __future__ import annotations

from dataclasses import dataclass

from .development import DevelopmentalStaircase, DevelopmentalTarget
from .model import FactoryRelease
from .understanding import (
    UnderstandingEvidencePlan,
    autonomy_projection_inputs,
)


@dataclass(frozen=True)
class DevelopmentalBinding:
    target_id: str
    capability_id: str

    def __post_init__(self) -> None:
        if (not isinstance(self.target_id, str) or not self.target_id or
                not isinstance(self.capability_id, str) or not self.capability_id):
            raise ValueError("DEVELOPMENT_BINDING_IDENTITY_INVALID")


@dataclass(frozen=True)
class DevelopmentalFrontierItem:
    target: DevelopmentalTarget
    capability_id: str | None
    blockers: tuple[str, ...]

    @property
    def executable(self) -> bool:
        return self.capability_id is not None and not self.blockers


@dataclass(frozen=True)
class DevelopmentalReleasePlan:
    staircase: DevelopmentalStaircase
    factory_release_sha256: str
    bindings: tuple[DevelopmentalBinding, ...]
    understanding_plans: tuple[UnderstandingEvidencePlan, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.staircase, DevelopmentalStaircase) or
                not isinstance(self.factory_release_sha256, str) or
                len(self.factory_release_sha256) != 64 or
                len({item.target_id for item in self.bindings}) != len(self.bindings) or
                len({item.capability_id for item in self.bindings}) != len(self.bindings) or
                len({item.capability_id for item in self.understanding_plans}) !=
                len(self.understanding_plans)):
            raise ValueError("DEVELOPMENT_RELEASE_PLAN_INVALID")

    @property
    def binding_map(self) -> dict[str, str]:
        return {item.target_id: item.capability_id for item in self.bindings}

    @property
    def understanding_map(self) -> dict[str, UnderstandingEvidencePlan]:
        return {item.capability_id: item for item in self.understanding_plans}

    def autonomy_inputs(self):
        return autonomy_projection_inputs(self.understanding_plans)

    def frontier(
        self, evidence_complete_capabilities: tuple[str, ...],
    ) -> tuple[DevelopmentalFrontierItem, ...]:
        """Project learner evidence onto the next conceptual frontier."""
        if len(set(evidence_complete_capabilities)) != len(
                evidence_complete_capabilities):
            raise ValueError("DEVELOPMENT_FRONTIER_EVIDENCE_SCOPE_INVALID")
        complete = set(evidence_complete_capabilities)
        conceptual_complete = tuple(
            (
                *tuple(item for item in self.staircase.baseline_capabilities
                       if item in complete),
                *tuple(binding.target_id for binding in self.bindings
                       if binding.capability_id in complete),
            )
        )
        frontier = self.staircase.frontier(conceptual_complete)
        binding_map = self.binding_map
        understanding_map = self.understanding_map
        result = []
        for target in frontier:
            capability_id = binding_map.get(target.capability_id)
            blockers = []
            if capability_id is None:
                blockers.append(
                    target.capability_id + ":FACTORY_BINDING_REQUIRED")
            else:
                plan = understanding_map.get(capability_id)
                if plan is None:
                    blockers.append(
                        target.capability_id + ":UNDERSTANDING_PLAN_REQUIRED")
                else:
                    blockers.extend(plan.coverage_debt)
            result.append(DevelopmentalFrontierItem(
                target, capability_id, tuple(blockers)))
        return tuple(result)


def bind_developmental_release(
    staircase: DevelopmentalStaircase, release: FactoryRelease, *,
    bindings: tuple[DevelopmentalBinding, ...],
    understanding_plans: tuple[UnderstandingEvidencePlan, ...],
) -> DevelopmentalReleasePlan:
    """Verify a one-to-one source-backed realization of blueprint targets."""
    if (not isinstance(staircase, DevelopmentalStaircase) or
            not isinstance(release, FactoryRelease)):
        raise TypeError("DEVELOPMENT_BINDING_INVALID_INPUT")
    release.verify()
    target_map = staircase.target_map
    capability_map = {item.capability_id: item for item in release.capabilities}
    if any(item not in capability_map for item in staircase.baseline_capabilities):
        raise ValueError("DEVELOPMENT_BINDING_BASELINE_NOT_IN_RELEASE")
    if (len({item.target_id for item in bindings}) != len(bindings) or
            len({item.capability_id for item in bindings}) != len(bindings)):
        raise ValueError("DEVELOPMENT_BINDING_NOT_ONE_TO_ONE")
    for binding in bindings:
        if binding.target_id not in target_map:
            raise ValueError("DEVELOPMENT_BINDING_UNKNOWN_TARGET")
        if binding.capability_id not in capability_map:
            raise ValueError("DEVELOPMENT_BINDING_CAPABILITY_NOT_IN_RELEASE")

    binding_map = {item.target_id: item.capability_id for item in bindings}
    understanding_map = {item.capability_id: item for item in understanding_plans}
    if len(understanding_map) != len(understanding_plans):
        raise ValueError("DEVELOPMENT_BINDING_DUPLICATE_UNDERSTANDING_PLAN")

    for binding in bindings:
        target = target_map[binding.target_id]
        definition = capability_map[binding.capability_id]
        expected_prerequisites = {
            binding_map.get(item, item) for item in target.prerequisites
        }
        unresolved = {
            item for item in target.prerequisites
            if item in target_map and item not in binding_map
        }
        if unresolved:
            raise ValueError(
                "DEVELOPMENT_BINDING_PREREQUISITE_TARGET_UNBOUND:" +
                binding.target_id + ":" + ",".join(sorted(unresolved)))
        if expected_prerequisites != set(definition.prerequisites):
            raise ValueError(
                "DEVELOPMENT_BINDING_PREREQUISITE_MISMATCH:" +
                binding.target_id)

        plan = understanding_map.get(binding.capability_id)
        if plan is None:
            continue
        expected_projection_ids = {item.value for item in target.projections}
        observed_projection_ids = {item.key for item in plan.obligations}
        observed_projection_ids.update(
            debt.split(":", 2)[1] for debt in plan.coverage_debt)
        if observed_projection_ids != expected_projection_ids:
            raise ValueError(
                "DEVELOPMENT_BINDING_PROJECTION_SCOPE_MISMATCH:" +
                binding.target_id)

    extra_plans = set(understanding_map) - {
        item.capability_id for item in bindings}
    if extra_plans:
        raise ValueError("DEVELOPMENT_BINDING_UNBOUND_UNDERSTANDING_PLAN")
    return DevelopmentalReleasePlan(
        staircase, release.release_sha256, bindings, understanding_plans)
