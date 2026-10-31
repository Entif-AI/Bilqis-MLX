"""Registry callbacks for the historical school source contract."""
from __future__ import annotations
from .shared import (A_COHORT_GENERATOR, A_IRRELEVANT_CONTEXT_VARIATION, A_MEMBER_CONTEXT_VARIATION, A_ORACLE, A_RELEASE, BOOLEAN_ASSOCIATION_OPTION, BOOLEAN_OPERATORS, B_COHORT_GENERATOR, B_COMPOSITE_GENERATOR, B_COMPOSITE_ORACLE, B_COMPOSITE_RELEASE, B_IDBOOLOPS_GENERATOR, B_IDBOOLOPS_ORACLE, B_IDBOOLOPS_RELEASE, B_ORACLE, B_RELEASE, C_COHORT_GENERATOR, C_ORACLE, C_RELEASE, RegisteredSourceAdapter, STAIRCASE_RELEASE, SourceAdapter, SourceAdapterRegistry, a_provider_digest, b_composite_digest, b_digest, b_idboolops_digest, c_digest, c_provider_digest, check_numeric, draw_a, numeric_semantic_footprint, staircase_digest,)
from .evidence import (boolean_evidence_dependencies, witness_micro_obligation, witness_numeric_obligation,)
from .boolean import (check_b_composite_release, check_b_idboolops_release, draw_b, draw_b_composite_release, draw_b_idboolops_release, enrich_boolean,)
from .checks import (check_connective, check_predicate, semantic_footprint,)
from .numeric import (draw_c,)


def live_source_registry() -> SourceAdapterRegistry:
    from ..copular import registered_adapter as copular_adapter
    from ..event_frames import registered_adapter as event_adapter
    from ..event_intro import registered_adapter as event_intro_adapter
    from ..event_pairs import registered_adapter as event_pairs_adapter
    return SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.predicates/v1", "bilqis_mlx.grade_a_probe.make_record",
            (A_ORACLE,), a_provider_digest(),
            cohort_generator_id=A_COHORT_GENERATOR,
            variation_axes=("source-valid", "balanced-gold", "fresh-seed",
                            A_MEMBER_CONTEXT_VARIATION, A_IRRELEVANT_CONTEXT_VARIATION),
            cohort_releases=((A_RELEASE, a_provider_digest()),)), draw_a, check_predicate,
            semantic_footprint=semantic_footprint),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-connectives/v1", "bilqis_mlx.live_grade_b.draw_connectives",
            (B_ORACLE,), b_digest(), cohort_generator_id=B_COHORT_GENERATOR,
            cohort_releases=((B_RELEASE, b_digest()),),
            teaching_option_ids=(BOOLEAN_ASSOCIATION_OPTION,)), draw_b, check_connective,
            enrich_boolean, witness_micro_obligation,
            semantic_footprint=semantic_footprint),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-composite/v1", B_COMPOSITE_GENERATOR,
            (B_ORACLE, B_COMPOSITE_ORACLE), b_composite_digest(),
            cohort_generator_id=B_COMPOSITE_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "operator-composition",
                            "runtime-answer-balance"),
            profile_dimensions=(("operators", BOOLEAN_OPERATORS),),
            cohort_releases=((B_COMPOSITE_RELEASE, b_composite_digest()),)),
            draw_b_composite_release, check_b_composite_release,
            witness=witness_micro_obligation,
            dependencies=boolean_evidence_dependencies,
            semantic_footprint=semantic_footprint),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-identification/v1", B_IDBOOLOPS_GENERATOR,
            (B_ORACLE, B_COMPOSITE_ORACLE, B_IDBOOLOPS_ORACLE), b_idboolops_digest(),
            cohort_generator_id=B_IDBOOLOPS_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "inverse-operator-identification",
                            "balanced-operator-targets", "masked-operator-input"),
            profile_dimensions=(("operators", BOOLEAN_OPERATORS),),
            cohort_releases=((B_IDBOOLOPS_RELEASE, b_idboolops_digest()),)),
            draw_b_idboolops_release, check_b_idboolops_release,
            witness=witness_micro_obligation,
            dependencies=boolean_evidence_dependencies,
            semantic_footprint=semantic_footprint),
        RegisteredSourceAdapter(SourceAdapter(
            "source.finite-numeric/v2", "bilqis_mlx.numeric_curriculum.draw_numeric",
            (C_ORACLE,), c_provider_digest(), cohort_generator_id=C_COHORT_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "typed-answer",
                            "numeric-scope", "construction-shape"),
            profile_dimensions=(("numbers", tuple(str(i) for i in range(11))),),
            cohort_releases=((C_RELEASE, c_digest()),
                             (STAIRCASE_RELEASE, staircase_digest()))), draw_c, check_numeric,
            witness=witness_numeric_obligation,
            semantic_footprint=numeric_semantic_footprint),
        copular_adapter(),
        event_adapter(),
        event_intro_adapter(),
        event_pairs_adapter(),
    ))

for _callback in (live_source_registry,):
    _callback.__module__ = "bilqis_mlx.source_adapters.school"
