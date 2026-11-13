"""Factory release composition for the admitted C13 episode-binding source family."""
from __future__ import annotations

from bilqis_mlx.curriculum import AnswerFamily
from bilqis_mlx.errors import ErrorBus, SOURCE
from bilqis_mlx.factory.curriculum_definition import (
    CapabilitySourceBinding, CapabilitySpec, CurriculumDefinition, GradeSpec,
    SourceBindingSet,
)
from bilqis_mlx.factory.executable_release import compile_executable_factory_release
from bilqis_mlx.factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile,
)
from bilqis_mlx.generated_assessment import digest

from .c13_episode import (
    ACTOR_ROOT, ADD_ROOT, CAPABILITY, GENERATOR_ID, ORACLE_ID, PROVIDER_ID,
    TIME_ROOT,
)
from .c13_episode_cases import DEPTHS, SOURCE_FAMILY


SOURCE_ATTESTATION_SCHEMA = "bilqis.c13.episode-source-attestation/v1"


def _fail(reason: str) -> None:
    ErrorBus.raise_(SOURCE.BAMF_C13_EPISODE.INVALID, reason=reason)


def source_attestation_sha256() -> str:
    """Bind the constructive family contract without claiming a new semantic root."""
    return digest({
        "schema": SOURCE_ATTESTATION_SCHEMA,
        "source_family_id": SOURCE_FAMILY,
        "provider_id": PROVIDER_ID,
        "constituent_roots": (ACTOR_ROOT, TIME_ROOT, ADD_ROOT),
        "relation_cue": "FIRST_EVENT_SUCCESSOR",
    })


def compile_episode_release(
    source_root,
    graph,
    source_registry,
    answer_registry,
    *,
    depths: tuple[int, ...] = (1,),
    verification_seed: int = 52813,
):
    """Compile the disposable C13 family from repository-owned registries."""
    if (not depths or any(type(depth) is not int or depth not in DEPTHS for depth in depths)
            or tuple(dict.fromkeys(depths)) != depths):
        _fail("BAMF_C13_EPISODE_PROFILE_INVALID")
    roots = (ACTOR_ROOT, TIME_ROOT, ADD_ROOT)
    capability = CapabilitySpec(
        CAPABILITY,
        "c13-disposable",
        roots,
        roots,
        (),
        (),
        (AnswerFamily("numeric_active", tuple(str(index) for index in range(21))),),
    )
    curriculum = CurriculumDefinition(
        "bilqis.c13.episode-curriculum/v1",
        (GradeSpec("Z", (capability,), ((CAPABILITY, 12),), ((CAPABILITY,),)),),
        program_complete=True,
    )
    bindings = SourceBindingSet(
        (CapabilitySourceBinding(
            CAPABILITY,
            "public-formal:" + SOURCE_FAMILY,
            GENERATOR_ID,
            ORACLE_ID,
        ),),
        source_attestation_sha256(),
    )
    profile = CurriculumProfile.full()
    if depths != (1,):
        profile = CurriculumProfile(
            "bamf-c13-episode/" + "-".join(str(depth) for depth in depths),
            (GradeProfile(
                "Z",
                capabilities=(CapabilityProfile(
                    CAPABILITY,
                    provider_parameters=((
                        "depths", tuple(str(depth) for depth in depths)),),
                ),),
            ),),
        )
    return compile_executable_factory_release(
        curriculum,
        bindings,
        profile,
        source_registry,
        answer_registry,
        source_root=source_root,
        graph=graph,
        verification_seed=verification_seed,
    )


__all__ = ("compile_episode_release", "source_attestation_sha256")
