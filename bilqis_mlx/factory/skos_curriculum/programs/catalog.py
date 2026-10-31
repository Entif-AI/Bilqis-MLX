"""Default source-family constructors and independent checkers."""
from bilqis_mlx.factory.curriculum.formal_lessons import check_formal_lesson, construct_formal_lesson
from bilqis_mlx.source_adapters.copular import CAPABILITY as COPULAR_SOURCE_CAPABILITY
from .contracts import SourceFamilyBatch
from .invocation import invoke_formal, invoke_source_batch
from .contracts import FamilyProgramRegistry, RegisteredFamilyProgram

def _source_draw(source, *args, **kwargs):
    """Dispatch through the existing source registry without inspecting grade."""
    return source.draw(*args, **kwargs)


def _source_check(source, artifact, *args, capability_id, **kwargs) -> bool:
    if (type(artifact) is not SourceFamilyBatch or artifact.capability_id != capability_id
            or artifact.source_adapter_id != source.descriptor.adapter_id
            or artifact.generator_id != source.descriptor.generator_id
            or artifact.oracle_id not in source.descriptor.accepted_oracle_ids
            or type(artifact.rows) is not tuple or not artifact.rows):
        return False
    return all(type(row) is dict and row.get("capability") == artifact.native_capability_id
               and source.check(row, *args, **kwargs) is True for row in artifact.rows)


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
            construct_formal_lesson, check_formal_lesson, invoke_bound=invoke_formal),
        RegisteredFamilyProgram(
            "numeric_composition", (formal_adapters[3],),
            "bilqis.factory.formal-lesson/v1",
            "bilqis.factory.formal-checker/v1",
            construct_formal_lesson, check_formal_lesson, invoke_bound=invoke_formal),
        RegisteredFamilyProgram(
            "source_world_fixture", ("source.ithkuil-reference-identity/v1",),
            "bilqis.factory.source-registry-draw/v1",
            "bilqis.factory.source-registry-check/v1",
            _source_draw, _source_check, invoke_bound=invoke_source_batch,
            native_capability_id=COPULAR_SOURCE_CAPABILITY),
    ))
