"""Grade-neutral A08 constructive-family registry over existing Factory identities."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.model import (
    CapabilityDefinition, ConstructionProgram, FactoryRelease,
)
from bilqis_mlx.factory.curriculum.formal_lessons import (
    check_formal_lesson, construct_formal_lesson,
)
from bilqis_mlx.source_adapters.school import live_source_registry

from .adapters import SOURCE_FAMILY_ADAPTERS
from .checkers import (
    assert_source_lesson_set_current, compile_source_constructive_lessons,
)
from .common import LEARNING_UNVERIFIED, _fail
from .curriculum import (
    LearnedFrontier, assert_curriculum_candidate_current,
    compile_semantic_curriculum,
)
from .inventory import assert_family_inventory_current, inventory_source_families
from .types import FamilyObligation, SemanticFamilyInventory


PROGRAM_BOUND = "FACTORY_PROGRAM_BOUND_UNADMITTED"
IMPLEMENTATION_UNCOVERED = "IMPLEMENTATION_UNCOVERED"
FAMILY_PROGRAM_SCHEMA = "bilqis.family-program/v1"
BOUND_FAMILY_PROGRAM_SCHEMA = "bilqis.bound-family-program/v1"
FAMILY_COVERAGE_SCHEMA = "bilqis.family-program-coverage/v1"

Construct = Callable[..., object]
Check = Callable[..., bool]


@dataclass(frozen=True)
class RegisteredFamilyProgram:
    """Behavior only. Stable capability identity remains owned by A08.2."""

    family_id: str
    accepted_source_adapter_ids: tuple[str, ...]
    constructor_ref: str
    checker_ref: str
    construct: Construct
    check: Check
    schema: str = FAMILY_PROGRAM_SCHEMA

    def __post_init__(self) -> None:
        if (not self.family_id
                or not self.accepted_source_adapter_ids
                or self.accepted_source_adapter_ids
                   != tuple(sorted(set(self.accepted_source_adapter_ids)))
                or not self.constructor_ref or not self.checker_ref
                or not callable(self.construct) or not callable(self.check)
                or self.schema != FAMILY_PROGRAM_SCHEMA):
            _fail("BAMF_FAMILY_PROGRAM_INVALID")


@dataclass(frozen=True)
class BoundFamilyProgram:
    """One existing Factory capability/program bound to family behavior."""

    family_id: str
    capability_id: str
    source_adapter_id: str
    generator_id: str
    oracle_id: str
    constructor_ref: str
    checker_ref: str
    implementation_status: str = PROGRAM_BOUND
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = BOUND_FAMILY_PROGRAM_SCHEMA

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and item for item in (
                self.family_id, self.capability_id, self.source_adapter_id,
                self.generator_id, self.oracle_id, self.constructor_ref,
                self.checker_ref))
                or self.implementation_status != PROGRAM_BOUND
                or self.learning_state != LEARNING_UNVERIFIED
                or self.schema != BOUND_FAMILY_PROGRAM_SCHEMA):
            _fail("BAMF_BOUND_FAMILY_PROGRAM_INVALID")


@dataclass(frozen=True)
class FamilyCoverageDisposition:
    obligation: FamilyObligation
    implementation_status: str
    reason: str | None
    learning_state: str = LEARNING_UNVERIFIED

    def __post_init__(self) -> None:
        if (type(self.obligation) is not FamilyObligation
                or self.implementation_status != IMPLEMENTATION_UNCOVERED
                or not self.reason
                or self.learning_state != LEARNING_UNVERIFIED):
            _fail("BAMF_FAMILY_COVERAGE_DISPOSITION_INVALID")


@dataclass(frozen=True)
class FamilyProgramCoverage:
    semantic_release: str
    census_digest: str
    dispositions: tuple[FamilyCoverageDisposition, ...]
    source_held_rows: int
    learning_state: str = LEARNING_UNVERIFIED
    schema: str = FAMILY_COVERAGE_SCHEMA

    def __post_init__(self) -> None:
        keys = tuple((item.obligation.semantic_id, item.obligation.family_id)
                     for item in self.dispositions)
        if (not self.semantic_release or not self.census_digest
                or len(keys) != len(set(keys))
                or type(self.source_held_rows) is not int
                or self.source_held_rows < 0
                or self.learning_state != LEARNING_UNVERIFIED
                or self.schema != FAMILY_COVERAGE_SCHEMA):
            _fail("BAMF_FAMILY_PROGRAM_COVERAGE_INVALID")


class FamilyProgramRegistry:
    def __init__(self, programs: tuple[RegisteredFamilyProgram, ...] = ()):
        self._programs: dict[str, RegisteredFamilyProgram] = {}
        for program in programs:
            self.register(program)

    def register(self, program: RegisteredFamilyProgram) -> None:
        if type(program) is not RegisteredFamilyProgram:
            _fail("BAMF_FAMILY_PROGRAM_TYPE_INVALID")
        if program.family_id in self._programs:
            _fail("BAMF_FAMILY_PROGRAM_DUPLICATE")
        self._programs[program.family_id] = program

    def require(self, family_id: str) -> RegisteredFamilyProgram:
        program = self._programs.get(family_id)
        if program is None:
            _fail("BAMF_FAMILY_PROGRAM_MISSING")
        return program

    @property
    def programs(self) -> tuple[RegisteredFamilyProgram, ...]:
        return tuple(self._programs[key] for key in sorted(self._programs))


@dataclass(frozen=True)
class FactoryReleaseFamilyBindings:
    factory_release_sha256: str
    semantic_release: str
    census_digest: str
    bound_programs: tuple[BoundFamilyProgram, ...]
    coverage: FamilyProgramCoverage
    learning_state: str = LEARNING_UNVERIFIED

    def __post_init__(self) -> None:
        if (not self.factory_release_sha256 or not self.semantic_release
                or self.coverage.census_digest != self.census_digest
                or self.coverage.semantic_release != self.semantic_release
                or self.learning_state != LEARNING_UNVERIFIED):
            _fail("BAMF_FACTORY_FAMILY_BINDINGS_INVALID")


def _source_draw(*args, **kwargs):
    """Dispatch through the existing source registry without inspecting grade."""
    generator_id = kwargs.pop("generator_id")
    oracle_id = kwargs.pop("oracle_id")
    return live_source_registry().require(generator_id, oracle_id).draw(*args, **kwargs)


def _source_check(row, *args, **kwargs) -> bool:
    generator_id = kwargs.pop("generator_id")
    oracle_id = kwargs.pop("oracle_id")
    return live_source_registry().require(generator_id, oracle_id).check(
        row, *args, **kwargs)


def default_family_program_registry() -> FamilyProgramRegistry:
    """Behavior registry for already-existing Factory capability identities."""
    formal_adapters = (
        "source.micro.boolean-composite/v1",
        "source.micro.boolean-connectives/v1",
        "source.micro.boolean-identification/v1",
        "source.finite-numeric/v2",
    )
    return FamilyProgramRegistry((
        RegisteredFamilyProgram(
            "boolean_composition", tuple(sorted(formal_adapters[:3])),
            "bilqis.factory.formal-lesson/v1",
            "bilqis.factory.formal-checker/v1",
            construct_formal_lesson, check_formal_lesson),
        RegisteredFamilyProgram(
            "numeric_composition", (formal_adapters[3],),
            "bilqis.factory.formal-lesson/v1",
            "bilqis.factory.formal-checker/v1",
            construct_formal_lesson, check_formal_lesson),
        RegisteredFamilyProgram(
            "source_world_fixture", ("source.ithkuil-reference-identity/v1",),
            "bilqis.factory.source-registry-draw/v1",
            "bilqis.factory.source-registry-check/v1",
            _source_draw, _source_check),
    ))


def bind_existing_family_program(
    registration: RegisteredFamilyProgram,
    capability: CapabilityDefinition,
    program: ConstructionProgram,
    source_registry: SourceAdapterRegistry,
) -> BoundFamilyProgram:
    """Attach behavior only after existing Factory identity/source checks pass."""
    if (type(registration) is not RegisteredFamilyProgram
            or type(capability) is not CapabilityDefinition
            or type(program) is not ConstructionProgram
            or capability.capability_id != program.capability_id
            or capability.prerequisites != program.prerequisites
            or capability.source_adapter_id != program.source_adapter_id):
        _fail("BAMF_FAMILY_PROGRAM_FACTORY_IDENTITY_MISMATCH")
    source = source_registry.require(program.generator_id, program.oracle_id)
    if source.descriptor.adapter_id != capability.source_adapter_id:
        _fail("BAMF_FAMILY_PROGRAM_SOURCE_ADAPTER_MISMATCH")
    if source.descriptor.adapter_id not in registration.accepted_source_adapter_ids:
        _fail("BAMF_FAMILY_PROGRAM_SOURCE_FAMILY_MISMATCH")
    return BoundFamilyProgram(
        registration.family_id, capability.capability_id,
        source.descriptor.adapter_id, program.generator_id, program.oracle_id,
        registration.constructor_ref, registration.checker_ref)


def bind_factory_release_families(
    release: FactoryRelease,
    registry: FamilyProgramRegistry,
    source_registry: SourceAdapterRegistry,
    atlas,
    learned_frontier: LearnedFrontier,
) -> FactoryReleaseFamilyBindings:
    """Production boundary: replay A08.1a before binding existing release programs.

    This proves program installation only. It does not grant A13 context rights or
    learning/admission credit; source-backed lesson execution still goes through
    ``issue_source_lesson_contexts`` / ``project_source_lesson_contexts``.
    """
    if (type(release) is not FactoryRelease
            or type(registry) is not FamilyProgramRegistry
            or type(source_registry) is not SourceAdapterRegistry
            or type(learned_frontier) is not LearnedFrontier):
        _fail("BAMF_FACTORY_FAMILY_BINDING_INPUT_INVALID")
    release.verify()
    census = inventory_source_families(atlas)
    candidate = compile_semantic_curriculum(
        atlas, SOURCE_FAMILY_ADAPTERS, learned_frontier)
    lessons = compile_source_constructive_lessons(atlas)
    assert_family_inventory_current(census, atlas)
    assert_curriculum_candidate_current(candidate, atlas, learned_frontier)
    assert_source_lesson_set_current(lessons, atlas)

    program_by_capability = {
        item.capability_id: item for item in release.construction_programs}
    bound = []
    for capability in release.capabilities:
        program = program_by_capability[capability.capability_id]
        matches = tuple(
            item for item in registry.programs
            if capability.source_adapter_id in item.accepted_source_adapter_ids)
        if len(matches) > 1:
            _fail("BAMF_FAMILY_PROGRAM_SOURCE_FAMILY_AMBIGUOUS")
        if matches:
            bound.append(bind_existing_family_program(
                matches[0], capability, program, source_registry))
    coverage = uncovered_family_obligations(census)
    return FactoryReleaseFamilyBindings(
        release.release_sha256, census.semantic_release, census.digest,
        tuple(bound), coverage)


def uncovered_family_obligations(
    census: SemanticFamilyInventory,
) -> FamilyProgramCoverage:
    """Preserve A08.1a denominator until A08.2 supplies exact identity bindings."""
    if type(census) is not SemanticFamilyInventory:
        _fail("BAMF_FAMILY_PROGRAM_CENSUS_INVALID")
    rows = tuple(FamilyCoverageDisposition(
        item, IMPLEMENTATION_UNCOVERED,
        "STABLE_CAPABILITY_IDENTITY_UNAVAILABLE")
        for item in census.obligations)
    return FamilyProgramCoverage(
        census.semantic_release, census.digest, rows,
        census.counts.source_held_rows)
