"""Admitted finite-world, Boolean and numeric source adapters and independent checks."""
from __future__ import annotations

from ..factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from ..factory.autonomy import SupplementalEvidenceSpec
from ..factory.model import SourceAdapter
from ..curriculum import BOOLEAN_OPERATORS
from ..factory.verification import (
    check_boolean_composite, check_connective, check_numeric, check_predicate,
)
from .structure import inspect_boolean_identification, inspect_source_query

from ..grade_a_oracle import VERSION as A_ORACLE


from ..live_grade_a import (GENERATOR as A_COHORT_GENERATOR, RELEASE as A_RELEASE,
                            draw_predicates, generator_source_digest)


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
    REPRESENTATION_VARIATION as B_IDBOOLOPS_REPRESENTATION_VARIATION,
    RELEASE as B_IDBOOLOPS_RELEASE,
    constructor_digest as b_idboolops_digest,
    draw_identification,
)


from ..live_grade_b import (
    GENERATOR as B_COHORT_GENERATOR,
    OUTER_LANDMARK_VARIATION as B_OUTER_LANDMARK_VARIATION,
    RELEASE as B_RELEASE,
    draw_connectives,
    constructor_digest as b_digest,
)


from ..live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                            PLANS, constructor_digest as c_digest)


from ..numeric_curriculum import ORACLE as C_ORACLE, draw_numeric


from ..numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest

from ..boolean_association import (
    VERSION as BOOLEAN_ASSOCIATION_OPTION,
    draw_b_grade_bridges,
)


BOOLEAN_RUNTIME_SAMPLER = "bilqis.mlx.grade-b-u7c-runtime-sampler/v3"








def draw_a(*, source_root, graph, course, capability, seed, each):
    return draw_predicates(source_root, graph, seed=seed,
                           capability=capability, each=each)


def draw_b(*, source_root, graph, course, capability, seed, each):
    del course
    rows = draw_connectives(source_root, graph, seed=seed,
                            capability=capability, each=each)
    return tuple({**row, "runtime_sampler": BOOLEAN_RUNTIME_SAMPLER}
                 for row in rows)


def _boolean_profile_operators(
        profile_parameters, *, capability, scoped_capabilities) -> tuple[str, ...]:
    parameters = profile_parameters or {}
    if set(parameters) - {"operators"}:
        raise ValueError("FACTORY_BOOLEAN_PROFILE_PARAMETER_UNKNOWN")
    if parameters and capability not in scoped_capabilities:
        raise ValueError("FACTORY_BOOLEAN_PROFILE_PARAMETER_SCOPE_DRIFT")
    return tuple(parameters.get("operators", BOOLEAN_OPERATORS))


def draw_b_composite_release(*, source_root, graph, course, capability, seed, each,
                             profile_parameters=None):
    operators = _boolean_profile_operators(
        profile_parameters, capability=capability,
        scoped_capabilities={B_COMPOSITE_CAPABILITY})
    if capability == B_COMPOSITE_CAPABILITY:
        return draw_composite(source_root, graph, seed=seed,
                              capability=capability, each=each,
                              operators=operators)
    return draw_b(source_root=source_root, graph=graph, course=course,
                  capability=capability, seed=seed, each=each)


def check_b_composite_release(row, **kwargs):
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


def draw_b_idboolops_release(*, source_root, graph, course, capability, seed, each,
                             profile_parameters=None):
    operators = _boolean_profile_operators(
        profile_parameters, capability=capability,
        scoped_capabilities={B_COMPOSITE_CAPABILITY, B_IDBOOLOPS_CAPABILITY})
    if capability == B_IDBOOLOPS_CAPABILITY:
        return draw_identification(source_root, graph, seed=seed,
                                   capability=capability, each=each,
                                   operators=operators)
    if capability == B_COMPOSITE_CAPABILITY:
        return draw_composite(source_root, graph, seed=seed,
                              capability=capability, each=each,
                              operators=operators)
    return draw_b(source_root=source_root, graph=graph, course=course,
                  capability=capability, seed=seed, each=each)


def check_b_idboolops_release(row, **kwargs):
    if row.get("capability") == B_IDBOOLOPS_CAPABILITY:
        from ..boolean_identification import encode_record
        from ..boolean_identification_oracle import evaluate
        return (
            evaluate(row["record"], row["capability"]) == row["gold"] and
            encode_record(
                row["record"], kwargs["source_root"], kwargs["graph"]) ==
            row["tokens"])
    if row.get("capability") == B_COMPOSITE_CAPABILITY:
        return check_boolean_composite(row, **kwargs)
    return check_connective(row, **kwargs)


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


def enrich_boolean(*, source_root, graph, course, capability, seed, option_id):
    if option_id != BOOLEAN_ASSOCIATION_OPTION:
        raise ValueError("FACTORY_UNKNOWN_BOOLEAN_TEACHING_OPTION")
    cap = course.capability_map[capability]
    if cap.lesson_generator != "bilqis_mlx.live_grade_b.draw_connectives":
        return ()
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


def witness_micro_obligation(row, obligation, *, source_root, graph, course):
    """Certify structural learner evidence in the finite-micro source dialect."""
    del source_root, graph
    required = tuple(getattr(obligation, "requires_capabilities", ()))
    if len(required) != 1:
        raise ValueError("FACTORY_MICRO_EVIDENCE_REQUIRES_ONE_PRODUCER")
    producer = course.capability_map.get(required[0])
    if producer is None or len(producer.examined_roots) != 1:
        raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_ROOT_UNRESOLVED")
    declared_producer_id = getattr(producer, "id", None)
    if declared_producer_id is None:
        declared_producer_id = getattr(producer, "capability_id", None)
    if not isinstance(declared_producer_id, str) or not declared_producer_id:
        raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_ID_UNRESOLVED")
    producer_root = producer.examined_roots[0]
    record = row.get("record")
    if not isinstance(record, dict):
        raise ValueError("FACTORY_MICRO_EVIDENCE_RECORD_MISSING")

    kind = getattr(getattr(obligation, "kind", None), "value", None)
    if kind == "PREREQUISITE":
        if record.get("task") == "identify_boolean_operator":
            shape = inspect_boolean_identification(record, row.get("root"))
        else:
            shape = inspect_source_query(record.get("query"))
        return producer_root in shape.rooted_operators

    if kind == "COMPOSITION":
        key = getattr(obligation, "key", "")
        if "@" not in key:
            if key != declared_producer_id:
                raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_KEY_DRIFT")
            if record.get("task") == "identify_boolean_operator":
                shape = inspect_boolean_identification(record, row.get("root"))
            else:
                shape = inspect_source_query(record.get("query"))
            return any(root in shape.rooted_operators
                       for root in producer.examined_roots)
        try:
            producer_id, slot_raw = key.rsplit("@", 1)
            slot = int(slot_raw)
        except (AttributeError, ValueError) as exc:
            raise ValueError("FACTORY_MICRO_EVIDENCE_COMPOSITION_KEY_INVALID") from exc
        if producer_id != declared_producer_id:
            raise ValueError("FACTORY_MICRO_EVIDENCE_PRODUCER_KEY_DRIFT")
        query = record.get("query")
        args = query.get("args") if isinstance(query, dict) else None
        if (query.get("kind") != "apply" if isinstance(query, dict) else True) or not isinstance(args, list):
            raise ValueError("FACTORY_MICRO_EVIDENCE_COMPOSITION_AST_INVALID")
        if not 0 <= slot < len(args):
            return False
        return inspect_source_query(args[slot]).root == producer_root

    raise ValueError("FACTORY_MICRO_EVIDENCE_KIND_UNSUPPORTED")


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


def boolean_evidence_dependencies(*, course, capability):
    """Declare abstraction proofs without changing released Course contracts."""
    del course
    if capability == B_COMPOSITE_CAPABILITY:
        return tuple(
            SupplementalEvidenceSpec(
                capability_id=capability,
                kind="COMPOSITION",
                key="B." + operator,
                requires_capabilities=("B." + operator,),
            )
            for operator in CONNECTIVES
        )
    if capability == B_IDBOOLOPS_CAPABILITY:
        return tuple(
            SupplementalEvidenceSpec(
                capability_id=capability,
                kind="PREREQUISITE",
                key="B." + operator,
                requires_capabilities=("B." + operator,),
            )
            for operator in CONNECTIVES
        )
    return ()



def live_source_registry() -> SourceAdapterRegistry:
    from .copular import registered_adapter as copular_adapter
    from .event_frames import registered_adapter as event_adapter
    from .event_intro import registered_adapter as event_intro_adapter
    from .event_pairs import registered_adapter as event_pairs_adapter
    return SourceAdapterRegistry((
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.predicates/v1", "bilqis_mlx.grade_a_probe.make_record",
            (A_ORACLE,), generator_source_digest(),
            cohort_generator_id=A_COHORT_GENERATOR,
            cohort_releases=((A_RELEASE, generator_source_digest()),)), draw_a, check_predicate),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-connectives/v1", "bilqis_mlx.live_grade_b.draw_connectives",
            (B_ORACLE,), b_digest(), cohort_generator_id=B_COHORT_GENERATOR,
            variation_axes=(
                "source-valid", "balanced-gold", "fresh-seed",
                B_OUTER_LANDMARK_VARIATION,
            ),
            cohort_releases=((B_RELEASE, b_digest()),),
            teaching_option_ids=(BOOLEAN_ASSOCIATION_OPTION,)), draw_b, check_connective,
            enrich_boolean, witness_micro_obligation),
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
            dependencies=boolean_evidence_dependencies),
        RegisteredSourceAdapter(SourceAdapter(
            "source.micro.boolean-identification/v1", B_IDBOOLOPS_GENERATOR,
            (B_ORACLE, B_COMPOSITE_ORACLE, B_IDBOOLOPS_ORACLE), b_idboolops_digest(),
            cohort_generator_id=B_IDBOOLOPS_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "inverse-operator-identification",
                            "balanced-operator-targets", "masked-operator-input",
                            B_IDBOOLOPS_REPRESENTATION_VARIATION,
                            B_OUTER_LANDMARK_VARIATION),
            profile_dimensions=(("operators", BOOLEAN_OPERATORS),),
            cohort_releases=((B_IDBOOLOPS_RELEASE, b_idboolops_digest()),)),
            draw_b_idboolops_release, check_b_idboolops_release,
            witness=witness_micro_obligation,
            dependencies=boolean_evidence_dependencies),
        RegisteredSourceAdapter(SourceAdapter(
            "source.finite-numeric/v1", "bilqis_mlx.numeric_curriculum.draw_numeric",
            (C_ORACLE,), c_digest(), cohort_generator_id=C_COHORT_GENERATOR,
            variation_axes=("source-valid", "fresh-seed", "typed-answer",
                            "numeric-scope", "construction-shape"),
            profile_dimensions=(("numbers", tuple(str(i) for i in range(11))),),
            cohort_releases=((C_RELEASE, c_digest()),
                             (STAIRCASE_RELEASE, staircase_digest()))), draw_c, check_numeric,
            witness=witness_numeric_obligation),
        copular_adapter(),
        event_adapter(),
        event_intro_adapter(),
        event_pairs_adapter(),
    ))

