"""Replay source authority before attaching Factory family behavior."""
from bilqis_mlx.factory.adapters import SourceAdapterRegistry
from bilqis_mlx.factory.model import CapabilityDefinition, ConstructionProgram, FactoryRelease
from ..adapters import SOURCE_FAMILY_ADAPTERS
from ..checkers import assert_source_lesson_set_current, compile_source_constructive_lessons
from ..common import _fail
from ..curriculum import LearnedFrontier, assert_curriculum_candidate_current, compile_semantic_curriculum
from ..inventory import assert_family_inventory_current, inventory_source_families
from ..types import SemanticFamilyInventory
from .contracts import (
    BoundFamilyProgram, FamilyProgramRegistry, RegisteredFamilyProgram,
    FactoryReleaseFamilyBindings, FamilyProgramCoverage, FamilyCoverageDisposition,
    IMPLEMENTATION_UNCOVERED,
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
    return BoundFamilyProgram(
        registration.family_id, capability.capability_id,
        source.descriptor.adapter_id, program.generator_id, program.oracle_id,
        registration.constructor_ref, registration.checker_ref,
        semantic_roots=semantic_roots,
        source_implementation_sha256=source.descriptor.implementation_sha256)


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
            source = source_registry.require(program.generator_id, program.oracle_id)
            if source.descriptor != release.source_adapter_map[capability.source_adapter_id]:
                _fail("BAMF_FAMILY_PROGRAM_RELEASE_PROVIDER_DRIFT")
            bound.append(bind_existing_family_program(
                matches[0], capability, program, source_registry,
                semantic_roots=release.course.capability_map[capability.capability_id].examined_roots))
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
