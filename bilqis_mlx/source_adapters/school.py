"""Admitted finite-world, Boolean and numeric source adapters and independent checks."""
from __future__ import annotations

from ..curriculum import BOOLEAN_SIGNATURE_OPERAND_COUNT

from bilqis_mlx.errors import ErrorBus, SOURCE

from dataclasses import dataclass as _dataclass
from typing import Callable as _Callable
from ..grade_b_oracle import _direct_truth, evaluate as grade_b_gold, operand_truth
from ..live_grade_b import _u7c_pattern_counts

from ..factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from ..factory.autonomy import SupplementalEvidenceSpec
from ..factory.model import SourceAdapter
from ..curriculum import BOOLEAN_OPERATORS
from .numeric import check_numeric, semantic_footprint as numeric_semantic_footprint
from .structure import inspect_boolean_identification, inspect_source_query

from ..grade_a_oracle import VERSION as A_ORACLE

from ..live_grade_a import (GENERATOR as A_COHORT_GENERATOR, RELEASE as A_RELEASE,
                            generator_source_digest)
from .grade_a_presentation import (
    IRRELEVANT_CONTEXT_VARIATION as A_IRRELEVANT_CONTEXT_VARIATION,
    MEMBER_CONTEXT_VARIATION as A_MEMBER_CONTEXT_VARIATION,
    constructor_digest as a_provider_digest,
    draw_a,
)

from ..grade_b_oracle import CONNECTIVES, VERSION as B_ORACLE

from ..boolean_composite import (
    CAPABILITY as B_COMPOSITE_CAPABILITY,
    GENERATOR as B_COMPOSITE_GENERATOR,
    ORACLE as B_COMPOSITE_ORACLE,
    RELEASE as B_COMPOSITE_RELEASE,
    constructor_digest as b_composite_digest,
    draw_composite,
)

from ..boolean_identification import (
    CAPABILITY as B_IDBOOLOPS_CAPABILITY,
    GENERATOR as B_IDBOOLOPS_GENERATOR,
    ORACLE as B_IDBOOLOPS_ORACLE,
    RELEASE as B_IDBOOLOPS_RELEASE,
    constructor_digest as b_idboolops_digest,
    draw_identification,
)

from ..live_grade_b import (GENERATOR as B_COHORT_GENERATOR, RELEASE as B_RELEASE,
                            draw_connectives, constructor_digest as b_digest)

from ..live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                            PLANS, constructor_digest as c_digest,
                            provider_implementation_digest as c_provider_digest)

from ..numeric_curriculum import ORACLE as C_ORACLE, draw_numeric

from ..numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest

from ..boolean_association import (
    VERSION as BOOLEAN_ASSOCIATION_OPTION,
    draw_b_grade_bridges,
)

from .school_sources.common import (
    BOOLEAN_RUNTIME_SAMPLER, TRUTH_PATTERNS, _U7C_RUNTIME_SAMPLER, _DIRECT_BOOLEAN_UNIVERSE,
)
from .school_sources.checks import (
    check_predicate,
    check_connective,
    check_boolean_composite,
    semantic_footprint,
)
from .school_sources.constructors import (
    draw_b,
    _boolean_profile_operators,
    draw_b_composite_release,
    check_b_composite_release,
    draw_b_idboolops_release,
    check_b_idboolops_release,
)
from .school_sources.evidence import (
    witness_micro_obligation,
    boolean_evidence_dependencies,
)
from .school_sources.preservation import (
    _is_direct_u7c_row,
    _preservation_pattern_counts,
    _replay_operand_pattern,
    _operand_kind,
    structural_signature,
    _fragile_row_pattern,
    _fragile_eligible,
    _fragile_verify_row,
    _fragile_structural_capability,
    _fragile_matching_keys,
    _FragileSourcePolicy,
    fragile_source_policy,
    _FRAGILE_SOURCE_POLICY,
)

def draw_c(*, source_root, graph, course, capability, seed, each,
           profile_parameters=None):
    parameters = profile_parameters or {}
    if set(parameters) - {"numbers"}:
        raise ValueError("FACTORY_NUMERIC_PROFILE_PARAMETER_UNKNOWN")
    if "numbers" in parameters:
        numbers = tuple(parameters["numbers"])
        if numbers != tuple(str(index) for index in range(len(numbers))):
            raise ValueError("FACTORY_NUMERIC_PROFILE_DOMAIN_INVALID")
        maximum = len(numbers) - 1
    else:
        cap = course.capability_map[capability]
        numeric = next((family for family in cap.answer_families
                        if family.kind == "numeric_active"), None)
        if numeric is None:
            raise ValueError("FACTORY_NUMERIC_CAPABILITY_HAS_NO_ACTIVE_DOMAIN")
        maximum = len(numeric.values) - 1
    return draw_numeric(PLANS, graph, seed=seed, maximum=maximum,
                        capability=capability, each=each)


def witness_numeric_obligation(row, obligation, *, source_root, graph, course):
    """Certify finite-numeric dependency transfer from the source lesson plan."""
    del source_root, graph
    capability = row.get("capability")
    plan = next((item for item in PLANS if item.capability == capability), None)
    if (plan is None or row.get("lesson_id") != plan.lesson_id or
            capability not in course.capability_map):
        raise ValueError("FACTORY_NUMERIC_EVIDENCE_PLAN_DRIFT")
    kind = getattr(getattr(obligation, "kind", None), "value", None)
    if kind == "PREREQUISITE":
        return getattr(obligation, "key", None) in plan.prerequisites
    if kind == "COMPOSITION":
        return getattr(obligation, "key", None) in course.capability_map[
            capability].composed_of
    raise ValueError("FACTORY_NUMERIC_EVIDENCE_KIND_UNSUPPORTED")


def enrich_boolean(*, source_root, graph, course, capability, seed, option_id):
    if option_id != BOOLEAN_ASSOCIATION_OPTION:
        raise ValueError("FACTORY_UNKNOWN_BOOLEAN_TEACHING_OPTION")
    course.capability_map[capability]
    numeric_caps = [member for member in course.capability_map.values()
                    if any(family.kind == "numeric_active"
                           for family in member.answer_families)]
    if not numeric_caps:
        raise ValueError("BOOLEAN_ASSOCIATION_REQUIRES_NUMERIC_SOURCE_ADAPTER")
    maximum = max(
        len(next(family for family in member.answer_families
                 if family.kind == "numeric_active").values) - 1
        for member in numeric_caps)
    return draw_b_grade_bridges(
        source_root, graph, seed=seed, maximum=maximum,
        per_source=4, capability=capability)


def live_source_registry() -> SourceAdapterRegistry:
    from .copular import registered_adapter as copular_adapter
    from .event_frames import registered_adapter as event_adapter
    from .event_intro import registered_adapter as event_intro_adapter
    from .event_pairs import registered_adapter as event_pairs_adapter
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


# Keep canonical callback identity and annotation resolution at the public facade.
from .school_sources import checks as _checks, constructors as _constructors
from .school_sources import evidence as _evidence, preservation as _preservation
for _module in (_checks, _constructors, _evidence, _preservation):
    for _callback in vars(_module).values():
        if getattr(_callback, "__module__", None) == _module.__name__:
            _callback.__module__ = __name__
del _module, _callback
