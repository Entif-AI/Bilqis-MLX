"""Non-admitting family program records and behavior registry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable
from bilqis_mlx.semantics.foundation.core import Signature
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
class FamilyProgramKey:
    """Behavior-selection key derived from source-qualified capability meaning."""

    family_id: str
    signature: Signature
    answer_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.family_id, str) or not self.family_id
                or type(self.signature) is not Signature
                or not isinstance(self.answer_kinds, tuple)
                or not self.answer_kinds
                or self.answer_kinds != tuple(sorted(set(self.answer_kinds)))
                or any(not isinstance(item, str) or not item
                       for item in self.answer_kinds)):
            _fail("BAMF_FAMILY_PROGRAM_KEY_INVALID")

    @property
    def canonical(self) -> tuple:
        return (self.family_id, self.signature.inputs,
                self.signature.output, self.answer_kinds)


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
    rule_profile: object | None = None
    source_validator: Callable[..., object] | None = None
    program_keys: tuple[FamilyProgramKey, ...] = ()

    def __post_init__(self) -> None:
        if (not self.family_id
                or not self.accepted_source_adapter_ids
                or self.accepted_source_adapter_ids
                   != tuple(sorted(set(self.accepted_source_adapter_ids)))
                or not self.constructor_ref or not self.checker_ref
                or not callable(self.construct) or not callable(self.check)
                or (self.invoke_bound is not None and not callable(self.invoke_bound))
                or (self.source_validator is not None
                    and not callable(self.source_validator))
                or not isinstance(self.program_keys, tuple)
                or any(type(key) is not FamilyProgramKey
                       or key.family_id != self.family_id
                       for key in self.program_keys)
                or len({key.canonical for key in self.program_keys})
                   != len(self.program_keys)
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
    semantic_operator_id: str | None = None
    program_key: FamilyProgramKey | None = None
    stable_semantic_id: str | None = None

    def __post_init__(self) -> None:
        if (not all(isinstance(item, str) and item for item in (
                self.family_id, self.capability_id, self.source_adapter_id,
                self.generator_id, self.oracle_id, self.constructor_ref,
                self.checker_ref))
                or self.implementation_status != PROGRAM_BOUND
                or self.learning_state != LEARNING_UNVERIFIED
                or type(self.semantic_roots) is not tuple
                or any(type(root) is not str or not root for root in self.semantic_roots)
                or (self.semantic_operator_id is not None
                    and (type(self.semantic_operator_id) is not str
                         or not self.semantic_operator_id))
                or (self.program_key is None) != (self.stable_semantic_id is None)
                or (self.program_key is not None
                    and (type(self.program_key) is not FamilyProgramKey
                         or self.program_key.family_id != self.family_id
                         or not isinstance(self.stable_semantic_id, str)
                         or not self.stable_semantic_id))
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
                or self.implementation_status not in {
                    IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND}
                or (self.implementation_status == IMPLEMENTATION_UNCOVERED
                    and not self.reason)
                or (self.implementation_status == PROGRAM_BOUND
                    and self.reason is not None)
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
        existing_keys = {
            key.canonical for registered in self._programs.values()
            for key in registered.program_keys}
        if any(key.canonical in existing_keys for key in program.program_keys):
            _fail("BAMF_FAMILY_PROGRAM_KEY_DUPLICATE")
        self._programs[program.family_id] = program

    def require(self, family_id: str) -> RegisteredFamilyProgram:
        program = self._programs.get(family_id)
        if program is None:
            _fail("BAMF_FAMILY_PROGRAM_MISSING")
        return program

    def require_key(self, key: FamilyProgramKey) -> RegisteredFamilyProgram:
        if type(key) is not FamilyProgramKey:
            _fail("BAMF_FAMILY_PROGRAM_KEY_INVALID")
        matches = tuple(
            program for program in self._programs.values()
            if any(item.canonical == key.canonical
                   for item in program.program_keys))
        if len(matches) != 1:
            _fail("BAMF_FAMILY_PROGRAM_KEY_MISSING")
        return matches[0]

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

for _record in (FamilyProgramKey, RegisteredFamilyProgram, BoundFamilyProgram, FamilyCoverageDisposition, FamilyProgramCoverage, FamilyProgramRegistry, FactoryReleaseFamilyBindings,):
    _record.__module__ = "bilqis_mlx.factory.skos_curriculum.registry"
