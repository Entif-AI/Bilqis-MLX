"""Non-admitting family program records and behavior registry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from ..common import LEARNING_UNVERIFIED, _fail
from ..types import FamilyObligation

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
    invoke_bound: Callable[..., object] | None = None
    native_capability_id: str | None = None

    def __post_init__(self) -> None:
        if (not self.family_id
                or not self.accepted_source_adapter_ids
                or self.accepted_source_adapter_ids
                   != tuple(sorted(set(self.accepted_source_adapter_ids)))
                or not self.constructor_ref or not self.checker_ref
                or not callable(self.construct) or not callable(self.check)
                or (self.invoke_bound is not None and not callable(self.invoke_bound))
                or (self.native_capability_id is not None
                    and (type(self.native_capability_id) is not str or not self.native_capability_id))
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
    semantic_roots: tuple[str, ...] = ()
    source_implementation_sha256: str | None = None

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and item for item in (
                self.family_id, self.capability_id, self.source_adapter_id,
                self.generator_id, self.oracle_id, self.constructor_ref,
                self.checker_ref))
                or self.implementation_status != PROGRAM_BOUND
                or self.learning_state != LEARNING_UNVERIFIED
                or type(self.semantic_roots) is not tuple
                or any(type(root) is not str or not root for root in self.semantic_roots)
                or self.schema != BOUND_FAMILY_PROGRAM_SCHEMA):
            _fail("BAMF_BOUND_FAMILY_PROGRAM_INVALID")


@dataclass(frozen=True)
class SourceFamilyBatch:
    """Factory identity alongside unchanged independently checked source rows."""

    capability_id: str
    source_adapter_id: str
    native_capability_id: str
    generator_id: str
    oracle_id: str
    rows: tuple[dict, ...]
    learning_state: str = LEARNING_UNVERIFIED

    def __post_init__(self) -> None:
        if (any(type(value) is not str or not value for value in (
                self.capability_id, self.source_adapter_id, self.native_capability_id,
                self.generator_id, self.oracle_id))
                or type(self.rows) is not tuple or not self.rows
                or any(type(row) is not dict for row in self.rows)
                or self.learning_state != LEARNING_UNVERIFIED):
            _fail("BAMF_FAMILY_PROGRAM_SOURCE_BATCH_INVALID")


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

    def require(self, capability_id: str) -> BoundFamilyProgram:
        matches = tuple(
            item for item in self.bound_programs
            if item.capability_id == capability_id)
        if len(matches) != 1:
            _fail("BAMF_FACTORY_FAMILY_BINDING_MISSING")
        return matches[0]

for _record in (RegisteredFamilyProgram, BoundFamilyProgram, FamilyCoverageDisposition, FamilyProgramCoverage, FamilyProgramRegistry, FactoryReleaseFamilyBindings,):
    _record.__module__ = "bilqis_mlx.factory.skos_curriculum.registry"
