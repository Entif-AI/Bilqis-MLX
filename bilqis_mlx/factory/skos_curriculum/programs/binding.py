"""Replay source authority before attaching Factory family behavior."""
from dataclasses import replace
from bilqis_mlx.errors import BilqisError
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.model import CapabilityDefinition, ConstructionProgram, FactoryRelease
from ..adapters import SOURCE_FAMILY_ADAPTERS
from ..checkers import assert_source_lesson_set_current, compile_source_constructive_lessons
from ..common import _fail
from ..curriculum import LearnedFrontier, assert_curriculum_candidate_current, compile_semantic_curriculum
from ..inventory import assert_family_inventory_current, inventory_source_families
from ..types import SemanticFamilyInventory
from .contracts import (
    BoundFamilyProgram, FamilyProgramKey, FamilyProgramRegistry, RegisteredFamilyProgram,
    FactoryReleaseFamilyBindings, FamilyProgramCoverage, FamilyCoverageDisposition,
    IMPLEMENTATION_UNCOVERED, PROGRAM_BOUND,
)

def bind_existing_family_program(
    registration: RegisteredFamilyProgram,
    capability: CapabilityDefinition,
    program: ConstructionProgram,
    source_registry: SourceAdapterRegistry,
    *, semantic_roots: tuple[str, ...] = (),
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
    if registration.source_validator is not None:
        try:
            registration.source_validator(source)
        except (TypeError, ValueError):
            _fail("BAMF_FAMILY_PROGRAM_SOURCE_IMPLEMENTATION_MISMATCH")
    profile = registration.rule_profile
    semantic_operator_id = None
    if profile is not None:
        identity = getattr(profile, "identity", None)
        source_capabilities = getattr(profile, "source_capability_ids", ())
        source_adapter_id = getattr(profile, "source_adapter_id", None)
        if (getattr(identity, "family_id", None) != registration.family_id
                or tuple(sorted(capability.answer_kinds))
                != getattr(identity, "answer_kinds", None)
                or (source_capabilities
                    and capability.capability_id not in source_capabilities)
                or (source_adapter_id is not None
                    and source_adapter_id != capability.source_adapter_id)):
            _fail("BAMF_FAMILY_PROGRAM_SEMANTIC_RULE_MISMATCH")
        coordinates = getattr(profile, "source_coordinates", ())
        if coordinates:
            matches = tuple(
                item for item in coordinates if item[0] == capability.capability_id)
            if len(matches) != 1 or semantic_roots != (matches[0][1],):
                _fail("BAMF_FAMILY_PROGRAM_SEMANTIC_COORDINATE_MISMATCH")
            semantic_operator_id = matches[0][2]
    return BoundFamilyProgram(
        registration.family_id, capability.capability_id,
        source.descriptor.adapter_id, program.generator_id, program.oracle_id,
        registration.constructor_ref, registration.checker_ref,
        semantic_roots=semantic_roots,
        source_implementation_sha256=source.descriptor.implementation_sha256,
        semantic_operator_id=semantic_operator_id)


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
            from .catalog import default_family_program_registry
            canonical_matches = tuple(
                item for item in default_family_program_registry().programs
                if capability.source_adapter_id in item.accepted_source_adapter_ids)
            if (len(canonical_matches) == 1
                    and matches[0] != canonical_matches[0]):
                _fail("BAMF_FAMILY_PROGRAM_CANONICAL_REGISTRATION_MISMATCH")
            source = source_registry.require(program.generator_id, program.oracle_id)
            if source.descriptor != release.source_adapter_map[capability.source_adapter_id]:
                _fail("BAMF_FAMILY_PROGRAM_RELEASE_PROVIDER_DRIFT")
            provisional = bind_existing_family_program(
                matches[0], capability, program, source_registry,
                semantic_roots=release.course.capability_map[capability.capability_id].examined_roots)
            if matches[0].program_keys:
                from bilqis_mlx.factory.curriculum.capability_identity import (
                    bind_factory_release_capability_identity,
                )
                from bilqis_mlx.semantics.cognitive_operators.registry import default_registry
                provisional_bindings = FactoryReleaseFamilyBindings(
                    release.release_sha256, census.semantic_release, census.digest,
                    (provisional,), uncovered_family_obligations(census))
                try:
                    identity = bind_factory_release_capability_identity(
                        release, provisional_bindings, capability.capability_id,
                        atlas, default_registry(census.semantic_release),
                    ).stable_identity.identity
                except BilqisError as exc:
                    if exc.context.get("reason") == (
                            "FACTORY_CAPABILITY_IDENTITY_SIGNATURE_AUTHORITY_MISSING"):
                        continue
                    raise
                key = FamilyProgramKey(
                    identity.family_id, identity.signature, identity.answer_kinds)
                selected = registry.require_key(key)
                if selected != matches[0]:
                    _fail("BAMF_FAMILY_PROGRAM_TYPED_SELECTION_MISMATCH")
                provisional = replace(
                    provisional, program_key=key,
                    stable_semantic_id=identity.semantic_id)
            bound.append(provisional)
    coverage = family_program_coverage(
        census, tuple(sorted(
            (item.stable_semantic_id, item.family_id)
            for item in bound if item.stable_semantic_id is not None)))
    return FactoryReleaseFamilyBindings(
        release.release_sha256, census.semantic_release, census.digest,
        tuple(bound), coverage)


def family_program_coverage(
    census: SemanticFamilyInventory,
    supported_identities: tuple[tuple[str, str], ...],
) -> FamilyProgramCoverage:
    """Project implementation support without changing the frozen census."""
    if (type(census) is not SemanticFamilyInventory
            or type(supported_identities) is not tuple
            or supported_identities != tuple(sorted(set(supported_identities)))
            or any(type(item) is not tuple or len(item) != 2
                   or any(type(value) is not str or not value for value in item)
                   for item in supported_identities)):
        _fail("BAMF_FAMILY_PROGRAM_CENSUS_INVALID")
    supported = frozenset(supported_identities)
    rows = tuple(FamilyCoverageDisposition(
        item,
        PROGRAM_BOUND
        if (item.semantic_id, item.family_id) in supported
        else IMPLEMENTATION_UNCOVERED,
        None if (item.semantic_id, item.family_id) in supported else item.reason,
    ) for item in census.obligations)
    return FamilyProgramCoverage(
        census.semantic_release, census.digest, rows,
        census.counts.source_held_rows)


def uncovered_family_obligations(
    census: SemanticFamilyInventory,
) -> FamilyProgramCoverage:
    """Preserve the denominator when no implementation family is bound."""
    if type(census) is not SemanticFamilyInventory:
        _fail("BAMF_FAMILY_PROGRAM_CENSUS_INVALID")
    rows = tuple(FamilyCoverageDisposition(
        item, IMPLEMENTATION_UNCOVERED,
        "STABLE_CAPABILITY_IDENTITY_UNAVAILABLE")
        for item in census.obligations)
    return FamilyProgramCoverage(
        census.semantic_release, census.digest, rows,
        census.counts.source_held_rows)
