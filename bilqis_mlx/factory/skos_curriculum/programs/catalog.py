"""Default source-family constructors and independent checkers."""
from bilqis_mlx.factory.curriculum.formal_lessons import check_formal_lesson, construct_formal_lesson
from bilqis_mlx.source_adapters.school import live_source_registry
from .contracts import FamilyProgramRegistry, RegisteredFamilyProgram

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
