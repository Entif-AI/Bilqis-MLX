"""Admitted finite-world, Boolean and numeric source adapters and independent checks."""
from __future__ import annotations

from dataclasses import dataclass as _dataclass
from typing import Callable as _Callable
from ..grade_b_oracle import _direct_truth, evaluate as grade_b_gold, operand_truth
from ..live_grade_b import _u7c_pattern_counts

from ..factory.adapters import RegisteredSourceAdapter, SourceAdapterRegistry
from ..factory.autonomy import SupplementalEvidenceSpec
from ..factory.model import SourceAdapter
from ..curriculum import BOOLEAN_OPERATORS
from ..factory.verification import check_numeric
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
    RELEASE as B_IDBOOLOPS_RELEASE,
    constructor_digest as b_idboolops_digest,
    draw_identification,
)


from ..live_grade_b import (GENERATOR as B_COHORT_GENERATOR, RELEASE as B_RELEASE,
                            draw_connectives, constructor_digest as b_digest)


from ..live_grade_c import (GENERATOR as C_COHORT_GENERATOR, RELEASE as C_RELEASE,
                            PLANS, constructor_digest as c_digest)


from ..numeric_curriculum import ORACLE as C_ORACLE, draw_numeric


from ..numeric_staircase import RELEASE as STAIRCASE_RELEASE, constructor_digest as staircase_digest

from ..boolean_association import (
    VERSION as BOOLEAN_ASSOCIATION_OPTION,
    draw_b_grade_bridges,
)


BOOLEAN_RUNTIME_SAMPLER = "bilqis.mlx.grade-b-u7c-runtime-sampler/v3"








def check_predicate(row, *, source_root, **_):
    from ..grade_a_oracle import evaluate
    from ..grade_a_probe import read_sources
    micro, development, *_ = read_sources(source_root)
    library = micro if row["record"]["task"] == "micro" else development
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(library.encode(row["record"])) == row["tokens"])


def check_connective(row, *, source_root, graph, **_):
    from ..grade_b_oracle import evaluate
    if row["record"].get("task") == "evaluate":
        from ..live_grade_b import _encode_logic_record, _logic_source
        logic = _logic_source(source_root)
        return (evaluate(row["record"], row["capability"]) == row["gold"] and
                _encode_logic_record(logic, row["record"], graph) == row["tokens"])
    from ..grade_a_probe import read_sources
    micro, *_ = read_sources(source_root)
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(micro.encode(row["record"])) == row["tokens"])


def check_boolean_composite(row, *, source_root, graph, **_):
    from ..boolean_composite_oracle import evaluate
    if row["record"].get("task") == "evaluate":
        from ..live_grade_b import _encode_logic_record, _logic_source
        logic = _logic_source(source_root)
        return (evaluate(row["record"], row["capability"]) == row["gold"] and
                _encode_logic_record(logic, row["record"], graph) == row["tokens"])
    from ..grade_a_probe import read_sources
    micro, *_ = read_sources(source_root)
    return (evaluate(row["record"], row["capability"]) == row["gold"] and
            list(micro.encode(row["record"])) == row["tokens"])


def semantic_footprint(row: dict) -> tuple[str, ...]:
    """Inspect source operations and omit literal/entity/codec representation."""
    record = row["record"]
    if record.get("task") == "identify_boolean_operator":
        from ..boolean_identification_oracle import evaluate
        root = "cogal.operator." + evaluate(record, row["capability"])
        shape = inspect_boolean_identification(record, root)
    else:
        shape = inspect_source_query(record["query"])
    return tuple(dict.fromkeys(shape.rooted_operators))


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
    """Resolve each direct Boolean producer from the declared curriculum."""
    if capability == B_COMPOSITE_CAPABILITY:
        kind = "COMPOSITION"
    elif capability == B_IDBOOLOPS_CAPABILITY:
        kind = "PREREQUISITE"
    else:
        return ()
    result = []
    for operator in CONNECTIVES:
        root = "cogal.operator." + operator
        producers = tuple(identity for identity, producer in course.capability_map.items()
                          if producer.examined_roots == (root,))
        if len(producers) != 1:
            raise ValueError("FACTORY_BOOLEAN_EVIDENCE_PRODUCER_UNRESOLVED:" + root)
        identity = producers[0]
        result.append(SupplementalEvidenceSpec(
            capability_id=capability, kind=kind, key=identity,
            requires_capabilities=(identity,)))
    return tuple(result)



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
            cohort_releases=((A_RELEASE, generator_source_digest()),)), draw_a, check_predicate,
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




TRUTH_PATTERNS = ((False, False), (False, True), (True, False), (True, True))
_U7C_RUNTIME_SAMPLER = BOOLEAN_RUNTIME_SAMPLER
_DIRECT_BOOLEAN_UNIVERSE = "DIRECT_BOOLEAN_AST"


def _is_direct_u7c_row(row: dict) -> bool:
    record = row.get("record") if isinstance(row, dict) else None
    return (isinstance(record, dict) and record.get("task") == "evaluate" and
            row.get("runtime_sampler") == _U7C_RUNTIME_SAMPLER)


def _preservation_pattern_counts(capability: str, rows, *, each: int) -> dict:
    relevant = [row for row in rows if row.get("capability") == capability]
    if relevant and all(_is_direct_u7c_row(row) for row in relevant):
        try:
            return _u7c_pattern_counts(capability.removeprefix("B."), each)
        except ValueError as exc:
            raise ValueError("FRAGILE_PRESERVATION_U7C_PATTERN_CONTRACT_INVALID") from exc
    if any(_is_direct_u7c_row(row) for row in relevant):
        raise ValueError("FRAGILE_PRESERVATION_MIXED_REPRESENTATION")
    return {pattern: 1 for pattern in TRUTH_PATTERNS}


def _replay_operand_pattern(record: dict) -> list[bool]:
    """Recompute OR/XOR operand truth for historical worlds or direct U7C ASTs."""
    if not isinstance(record, dict):
        raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
    if record.get("task") == "evaluate":
        expression = record.get("expression")
        query = record.get("query")
        assignments = record.get("assignments")
        if (not isinstance(expression, dict) or expression != query or
                not isinstance(assignments, dict)):
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        args = expression.get("args")
        if not isinstance(args, list) or len(args) != 2:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        try:
            return [_direct_truth(arg, assignments) for arg in args]
        except ValueError as exc:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT") from exc
    if record.get("task") == "micro":
        world = record.get("world")
        query = record.get("query")
        args = query.get("args") if isinstance(query, dict) else None
        if not isinstance(world, dict) or not isinstance(args, list) or len(args) != 2:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")
        try:
            return [operand_truth(world, arg) for arg in args]
        except ValueError as exc:
            raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT") from exc
    raise ValueError("FRAGILE_REPLAY_ORACLE_OR_COMPOSITION_DRIFT")


def _operand_kind(node: dict) -> str:
    kind = node.get("kind")
    if kind == "compare":
        value = node.get("operator")
    elif kind == "relation":
        value = node.get("name")
    else:
        value = kind
    if not isinstance(value, str) or not value:
        raise ValueError("FRAGILE_PRESERVATION_OPERAND_KIND_INVALID")
    return value


def structural_signature(row: dict) -> tuple:
    """Describe the compositional shape that truth-pattern-only replay misses."""
    capability = row.get("capability")
    raw = row.get("operand_truths")
    record = row.get("record") or {}
    query = record.get("query") or {}
    args = query.get("args")
    universe = (_DIRECT_BOOLEAN_UNIVERSE if _is_direct_u7c_row(row)
                else row.get("universe_size"))
    if (not isinstance(capability, str) or not capability or
            not isinstance(raw, (list, tuple)) or len(raw) != 2 or
            any(type(value) is not bool for value in raw) or
            not isinstance(args, list) or len(args) != 2 or
            (universe != _DIRECT_BOOLEAN_UNIVERSE and
             (type(universe) is not int or universe < 1))):
        raise ValueError("FRAGILE_PRESERVATION_STRUCTURAL_SIGNATURE_INVALID")
    return (capability, tuple(raw), tuple(_operand_kind(arg) for arg in args),
            universe)



def _fragile_row_pattern(row):
    raw = row.get("operand_truths")
    if (not isinstance(raw, (list, tuple)) or len(raw) != 2 or
            any(type(value) is not bool for value in raw)):
        raise ValueError("FRAGILE_PRESERVATION_OPERAND_PATTERN_INVALID")
    pattern = tuple(raw)
    if pattern not in TRUTH_PATTERNS:
        raise ValueError("FRAGILE_PRESERVATION_SOURCE_GOLD_DRIFT")
    return pattern


def _fragile_eligible(row):
    return (isinstance(row.get("capability"), str) and
            isinstance(row.get("operand_truths"), (list, tuple)) and
            len(row.get("operand_truths")) == 2)


def _fragile_verify_row(row, capability):
    return (row.get("operand_truths") == _replay_operand_pattern(row["record"]) and
            grade_b_gold(row["record"], capability) == row["gold"] and bool(row.get("tokens")))


def _fragile_structural_capability(rows, limit):
    capabilities = {row.get("capability") for row in rows}
    if len(capabilities) != 1 or limit < 4 or limit % 2:
        raise ValueError("FRAGILE_PRESERVATION_U7C_STRUCTURAL_REQUEST_INVALID")
    return next(iter(capabilities))


def _fragile_matching_keys(signature):
    return signature, signature[:3], signature[:2]


@_dataclass(frozen=True)
class _FragileSourcePolicy:
    is_exact: _Callable[[dict], bool]
    pattern_counts: _Callable[..., dict]
    row_pattern: _Callable[[dict], tuple[bool, bool]]
    eligible: _Callable[[dict], bool]
    verify_row: _Callable[[dict, str], bool]
    signature: _Callable[[dict], tuple]
    structural_capability: _Callable[[tuple[dict, ...], int], str]
    matching_keys: _Callable[[tuple], tuple[tuple, ...]]
    answer_values: tuple[str, ...]


_FRAGILE_SOURCE_POLICY = _FragileSourcePolicy(
    _is_direct_u7c_row, _preservation_pattern_counts, _fragile_row_pattern,
    _fragile_eligible, _fragile_verify_row, structural_signature,
    _fragile_structural_capability, _fragile_matching_keys, ("TRUE", "FALSE"))


def fragile_source_policy(selector: str):
    """Resolve the existing source selector to its immutable semantic callbacks."""
    if selector != BOOLEAN_RUNTIME_SAMPLER:
        raise ValueError("FRAGILE_PRESERVATION_SOURCE_POLICY_UNKNOWN")
    return _FRAGILE_SOURCE_POLICY
