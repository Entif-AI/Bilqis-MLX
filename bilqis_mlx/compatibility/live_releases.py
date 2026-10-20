"""Compatibility providers for the currently admitted A/B/C source releases.

Generic runtime code may depend on this release-provider boundary. It MUST NOT
import the historical ``live_grade_*`` constructor modules directly. Those
modules remain source-domain implementations while their callers are migrated.
"""
from __future__ import annotations

from dataclasses import dataclass

from ..factory.model import FactoryRelease
from ..factory.release import compile_factory_release
from .source_adapters import historical_source_registry
from ..live_grade_a import (
    GENERATOR as _INITIAL_GENERATOR,
    RELEASE as INITIAL_RELEASE,
    generator_source_digest as _initial_digest,
    live_course as _initial_course,
)
from ..live_grade_b import (
    GENERATOR as _BOOLEAN_GENERATOR,
    RELEASE as BOOLEAN_RELEASE,
    constructor_digest as _boolean_digest,
    live_course as _boolean_course,
)
from ..boolean_composite import (
    GENERATOR as _BOOLEAN_COMPOSITE_GENERATOR,
    RELEASE as BOOLEAN_COMPOSITE_RELEASE,
    build_course as _boolean_composite_course,
    constructor_digest as _boolean_composite_digest,
)
from ..boolean_identification import (
    GENERATOR as _BOOLEAN_IDENTIFICATION_GENERATOR,
    RELEASE as BOOLEAN_IDENTIFICATION_RELEASE,
    answer_heads as _boolean_identification_answer_heads,
    build_course as _boolean_identification_course,
    constructor_digest as _boolean_identification_digest,
)
from ..live_grade_c import (
    REGISTRY_COUNTING_TARGET,
    RELEASE as NUMERIC_RELEASE,
    answer_heads as _numeric_answer_heads,
    constructor_digest as _numeric_digest,
    prepare_course as _prepare_numeric_course,
    registry_graph as numeric_registry_graph,
)
from ..numeric_staircase import (
    RELEASE as NUMERIC_STAIRCASE_RELEASE,
    build_course as _build_staircase_course,
    constructor_digest as _staircase_digest,
)
from ..minimal_grade_b import (
    GENERATOR as _MINIMAL_BOOLEAN_GENERATOR,
    RELEASE as MINIMAL_BOOLEAN_RELEASE,
    answer_heads as _minimal_boolean_answer_heads,
    build_course as _minimal_boolean_course,
    constructor_digest as _minimal_boolean_digest,
)


KNOWN_RELEASES = (
    INITIAL_RELEASE,
    BOOLEAN_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
    MINIMAL_BOOLEAN_RELEASE,
    NUMERIC_RELEASE,
    NUMERIC_STAIRCASE_RELEASE,
)

FULL_BOOLEAN_RELEASES = (
    BOOLEAN_RELEASE,
    BOOLEAN_COMPOSITE_RELEASE,
    BOOLEAN_IDENTIFICATION_RELEASE,
)


@dataclass(frozen=True)
class SuccessorPlan:
    successor: object
    transition: str


SAME_GRAPH_TRANSITION = "SAME_GRAPH"
SAME_GRADE_TRANSITION = "SAME_GRADE"
GRAPH_GROWTH_TRANSITION = "GRAPH_GROWTH"


def initial_course(accepted):
    return _initial_course(accepted)


def boolean_successor(previous, source_root):
    return _boolean_course(previous, source_root)


def minimal_boolean_successor(previous, source_root):
    return _minimal_boolean_course(previous, source_root)


def default_resume_replacement(current_course, grade_a_course, source_root,
                               *, full_grade_b: bool = False):
    """Return the default neural-inert profile replacement for an existing run."""
    if full_grade_b or current_course.version == MINIMAL_BOOLEAN_RELEASE:
        return None
    if current_course.version in FULL_BOOLEAN_RELEASES:
        if (len(current_course.grades) != len(grade_a_course.grades) + 1 or
                current_course.grades[:-1] != grade_a_course.grades):
            raise ValueError("MINIMAL_GRADE_B_REPLACEMENT_REQUIRES_DIRECT_SUCCESSOR")
        return minimal_boolean_successor(grade_a_course, source_root)
    return None


def boolean_composite_successor(previous, source_root):
    return _boolean_composite_course(previous, source_root)


def boolean_identification_successor(previous, source_root):
    return _boolean_identification_course(previous, source_root)


def boolean_identification_answer_heads(graph):
    return _boolean_identification_answer_heads(graph)


def minimal_boolean_answer_heads(graph):
    return _minimal_boolean_answer_heads(graph)


def numeric_answer_heads(graph, maximum, *, prior_heads=None):
    heads = _numeric_answer_heads(graph, maximum)
    if prior_heads and "boolean_operator" in prior_heads:
        prior = prior_heads["boolean_operator"]
        labels = list(prior.get("values") or ())
        token_ids = list(prior.get("token_ids") or ())
        if len(labels) < 2 or len(labels) != len(token_ids):
            raise ValueError("FACTORY_PRIOR_BOOLEAN_OPERATOR_HEAD_INVALID")
        heads["boolean_operator"] = {"values": labels, "token_ids": token_ids}
    return heads


def rebind_same_grade_config(version: str, config: dict, graph: dict) -> dict:
    """Provider-owned metadata changes for neural-inert same-grade revisions."""
    if version == BOOLEAN_IDENTIFICATION_RELEASE:
        if not isinstance(graph, dict):
            raise ValueError("FACTORY_TYPED_SAME_GRADE_REVISION_REQUIRES_GRAPH")
        return {**config, "answer_heads": _boolean_identification_answer_heads(graph)}
    if version == MINIMAL_BOOLEAN_RELEASE:
        if not isinstance(graph, dict):
            raise ValueError("FACTORY_TYPED_SAME_GRADE_REVISION_REQUIRES_GRAPH")
        return {**config, "answer_heads": _minimal_boolean_answer_heads(graph)}
    return config


def numeric_successor(previous, *, maximum=None):
    return _prepare_numeric_course(previous, maximum=maximum)


def staircase_successor(previous, *, maximum):
    return _build_staircase_course(previous, numeric_registry_graph(), maximum=maximum)


def graph_matches_release(version: str | None, graph: dict, manifest: dict,
                          fingerprint) -> bool:
    """Release-owned graph policy; generic runtime never keys this by grade."""
    if version in (NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE):
        return graph == numeric_registry_graph()
    if version in (None, INITIAL_RELEASE, BOOLEAN_RELEASE, BOOLEAN_COMPOSITE_RELEASE,
                   BOOLEAN_IDENTIFICATION_RELEASE, MINIMAL_BOOLEAN_RELEASE):
        from ..semantics.abi import HISTORICAL_PREFIX_SIZE
        return (len(graph["tokens"]) == HISTORICAL_PREFIX_SIZE and
                fingerprint(graph) == manifest["parent_student"]["full_student_graph_sha256"])
    raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))


def resolve_admitted_courses(historical_course, source_root, saved: dict,
                             *, pending: dict | None = None,
                             include_prospective: bool = True) -> dict[str, object]:
    """Reconstruct every release that may be referenced by saved/pending state."""
    from ..compatibility.historical_live_release import resume_grade_courses

    course_a, course_b = resume_grade_courses(historical_course, source_root, saved)
    courses = {course_a.version: course_a}
    modes = {saved.get("curriculum_mode")}
    if pending is not None:
        modes.add(pending.get("curriculum_mode"))
    if (BOOLEAN_RELEASE in modes or BOOLEAN_COMPOSITE_RELEASE in modes or
            BOOLEAN_IDENTIFICATION_RELEASE in modes or
            NUMERIC_RELEASE in modes or
            NUMERIC_STAIRCASE_RELEASE in modes or
            (include_prospective and
             saved.get("school", {}).get("stage") == "AWAITING_NEXT_GRADE")):
        course_b = course_b or boolean_successor(course_a, source_root)
        courses[course_b.version] = course_b
    minimal_b = None
    parent_digest = saved.get("grade_c_parent_course_digest")
    if (MINIMAL_BOOLEAN_RELEASE in modes or parent_digest is not None or
            (include_prospective and
             saved.get("school", {}).get("stage") == "AWAITING_NEXT_GRADE" and
             saved.get("curriculum_mode") == INITIAL_RELEASE)):
        minimal_b = minimal_boolean_successor(course_a, source_root)
        courses[minimal_b.version] = minimal_b
    composite_b = None
    if (BOOLEAN_COMPOSITE_RELEASE in modes or BOOLEAN_IDENTIFICATION_RELEASE in modes or
            saved.get("grade_c_parent_course_digest") is not None or
            (include_prospective and saved.get("curriculum_mode") == BOOLEAN_RELEASE)):
        course_b = course_b or boolean_successor(course_a, source_root)
        composite_b = boolean_composite_successor(course_b, source_root)
        courses[composite_b.version] = composite_b
    identified_b = None
    if (BOOLEAN_IDENTIFICATION_RELEASE in modes or
            saved.get("grade_c_parent_course_digest") is not None or
            (include_prospective and
             saved.get("curriculum_mode") == BOOLEAN_COMPOSITE_RELEASE)):
        course_b = course_b or boolean_successor(course_a, source_root)
        composite_b = composite_b or boolean_composite_successor(course_b, source_root)
        courses[composite_b.version] = composite_b
        identified_b = boolean_identification_successor(composite_b, source_root)
        courses[identified_b.version] = identified_b
    if (NUMERIC_RELEASE in modes or NUMERIC_STAIRCASE_RELEASE in modes or
            (include_prospective and saved.get("curriculum_mode") == BOOLEAN_IDENTIFICATION_RELEASE and
             saved.get("school", {}).get("stage") == "AWAITING_NEXT_GRADE")):
        parent_b = course_b
        if composite_b is None and parent_digest is not None:
            composite_b = boolean_composite_successor(course_b, source_root)
            courses[composite_b.version] = composite_b
        if identified_b is None and parent_digest is not None:
            identified_b = boolean_identification_successor(composite_b, source_root)
            courses[identified_b.version] = identified_b
        if minimal_b is not None and parent_digest == minimal_b.digest():
            parent_b = minimal_b
        elif identified_b is not None and (
                parent_digest == identified_b.digest() or
                saved.get("curriculum_mode") == BOOLEAN_IDENTIFICATION_RELEASE):
            parent_b = identified_b
        elif composite_b is not None and parent_digest == composite_b.digest():
            parent_b = composite_b
        elif saved.get("curriculum_mode") == BOOLEAN_COMPOSITE_RELEASE:
            parent_b = composite_b
        pinned_maximum = (REGISTRY_COUNTING_TARGET
                          if NUMERIC_STAIRCASE_RELEASE in modes
                          else saved.get("numeric_maximum"))
        if (pending or {}).get("curriculum_mode") == NUMERIC_RELEASE and pinned_maximum is None:
            pinned_maximum = pending.get("numeric_maximum")
        course_c, _ = numeric_successor(parent_b, maximum=pinned_maximum)
        courses[course_c.version] = course_c
        if NUMERIC_STAIRCASE_RELEASE in modes:
            active = pending if (pending or {}).get("curriculum_mode") == NUMERIC_STAIRCASE_RELEASE else saved
            staircase = staircase_successor(parent_b, maximum=active["numeric_maximum"])
            courses[staircase.version] = staircase
    return courses


def course_for_mode(courses: dict[str, object], mode: str | None, historical_course):
    if mode is None:
        return historical_course
    try:
        return courses[mode]
    except KeyError as exc:
        raise ValueError("FACTORY_RELEASE_COURSE_NOT_LOADED:" + str(mode)) from exc


def predecessor_course(courses: dict[str, object], current_course):
    """Find the unique admitted release whose grade prefix owns current_course."""
    if len(current_course.grades) < 2:
        raise ValueError("FACTORY_RELEASE_HAS_NO_PREDECESSOR")
    prefix = current_course.grades[:-1]
    matches = [course for course in courses.values()
               if course.grades == prefix]
    unique = {course.digest(): course for course in matches}
    if len(unique) != 1:
        raise ValueError("FACTORY_RELEASE_PREDECESSOR_AMBIGUOUS")
    return next(iter(unique.values()))


def next_successor_plan(current_course, source_root, *, full_grade_b: bool = False) -> SuccessorPlan | None:
    """Provider-owned successor declaration for the current admitted release."""
    if current_course.version == INITIAL_RELEASE:
        successor = (boolean_successor(current_course, source_root) if full_grade_b
                     else minimal_boolean_successor(current_course, source_root))
        return SuccessorPlan(successor, SAME_GRAPH_TRANSITION)
    if current_course.version == BOOLEAN_RELEASE:
        return SuccessorPlan(
            boolean_composite_successor(current_course, source_root),
            SAME_GRADE_TRANSITION)
    if current_course.version == BOOLEAN_COMPOSITE_RELEASE:
        return SuccessorPlan(
            boolean_identification_successor(current_course, source_root),
            SAME_GRADE_TRANSITION)
    if current_course.version == BOOLEAN_IDENTIFICATION_RELEASE:
        successor, _ = numeric_successor(current_course)
        return SuccessorPlan(successor, GRAPH_GROWTH_TRANSITION)
    if current_course.version == MINIMAL_BOOLEAN_RELEASE:
        successor, _ = numeric_successor(current_course)
        return SuccessorPlan(successor, GRAPH_GROWTH_TRANSITION)
    return None


def preflight_successor(current_course, source_root, manifest: dict,
                        saved: dict, *, full_grade_b: bool = False) -> dict:
    """Provider-owned, neural-inert next-release preflight for the operator CLI."""
    blockers: list[str] = []
    details: dict = {}
    if current_course.version == INITIAL_RELEASE:
        successor = (boolean_successor(current_course, source_root) if full_grade_b
                     else minimal_boolean_successor(current_course, source_root))
        details.update({
            "start_behavior": "HUMAN_RESUME_ADMIT_NEXT_GRADE_FROM_MASTERY",
            "next_grade": successor.grades[-1].id,
            "next_grade_source_checked": successor.executable,
            "next_grade_rubric_sha256": successor.grades[-1].assessment_sha256,
            "next_grade_complete_assessment_items": sum(
                count for grade in successor.grades for _, count in grade.exam_item_counts),
        })
        return {"details": details, "blockers": blockers}
    if current_course.version == BOOLEAN_RELEASE:
        successor = boolean_composite_successor(current_course, source_root)
        details.update({
            "start_behavior": "HUMAN_RESUME_REBIND_CURRENT_GRADE",
            "next_grade": "B",
            "next_capability": "B.COMPOSITE",
            "next_grade_source_checked": successor.executable,
            "next_grade_rubric_sha256": successor.grades[-1].assessment_sha256,
            "next_grade_complete_assessment_items": sum(
                count for grade in successor.grades for _, count in grade.exam_item_counts),
        })
        return {"details": details, "blockers": blockers}
    if current_course.version == BOOLEAN_COMPOSITE_RELEASE:
        successor = boolean_identification_successor(current_course, source_root)
        details.update({
            "start_behavior": "HUMAN_RESUME_REBIND_CURRENT_GRADE",
            "next_grade": "B",
            "next_capability": "B.IDBOOLOPS",
            "next_grade_source_checked": successor.executable,
            "next_grade_rubric_sha256": successor.grades[-1].assessment_sha256,
            "next_grade_complete_assessment_items": sum(
                count for grade in successor.grades for _, count in grade.exam_item_counts),
        })
        return {"details": details, "blockers": blockers}
    if current_course.version == BOOLEAN_IDENTIFICATION_RELEASE:
        from ..grade_c_preflight import qualify
        from ..live_grade_c import (
            REGISTRY_COUNTING_TARGET,
            REGISTRY_PATH,
            integer_scope,
            registry_graph,
        )
        next_grade = "C"
        details.update({
            "start_behavior": "HUMAN_RESUME_ADMIT_NEXT_GRADE_FROM_MASTERY",
            "next_grade": next_grade,
            "next_grade_policy": "SOURCE_AND_CUSTODY_CHECKS",
        })
        if REGISTRY_PATH.is_symlink():
            blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_UNSAFE_PATH")
            return {"details": details, "blockers": blockers}
        if not REGISTRY_PATH.is_file():
            blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_MISSING")
            return {"details": details, "blockers": blockers}
        details["next_grade_source"] = qualify(
            source_root, manifest, previous=current_course)
        if integer_scope(registry_graph()) != REGISTRY_COUNTING_TARGET:
            blockers.append(
                "NEXT_GRADE_REQUIRES_INTEGER_MAX=" + str(REGISTRY_COUNTING_TARGET))
        successor, _ = numeric_successor(current_course)
        details["next_grade_rubric_sha256"] = successor.grades[-1].assessment_sha256
        details["next_grade_source_checked"] = successor.executable
        return {"details": details, "blockers": blockers}
    if current_course.version == MINIMAL_BOOLEAN_RELEASE:
        from ..grade_c_preflight import qualify
        from ..live_grade_c import (
            REGISTRY_COUNTING_TARGET,
            REGISTRY_PATH,
            integer_scope,
            registry_graph,
        )
        details.update({
            "start_behavior": "HUMAN_RESUME_ADMIT_NEXT_GRADE_FROM_MASTERY",
            "next_grade": "C",
            "next_grade_policy": "SOURCE_AND_CUSTODY_CHECKS",
        })
        if REGISTRY_PATH.is_symlink():
            blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_UNSAFE_PATH")
            return {"details": details, "blockers": blockers}
        if not REGISTRY_PATH.is_file():
            blockers.append("NEXT_GRADE_NATIVE_REGISTRY_ARTIFACT_MISSING")
            return {"details": details, "blockers": blockers}
        details["next_grade_source"] = qualify(
            source_root, manifest, previous=current_course)
        if integer_scope(registry_graph()) != REGISTRY_COUNTING_TARGET:
            blockers.append(
                "NEXT_GRADE_REQUIRES_INTEGER_MAX=" + str(REGISTRY_COUNTING_TARGET))
        successor, _ = numeric_successor(current_course)
        details["next_grade_rubric_sha256"] = successor.grades[-1].assessment_sha256
        details["next_grade_source_checked"] = successor.executable
        return {"details": details, "blockers": blockers}
    return {"details": details, "blockers": blockers}


def release_generator(version: str) -> str:
    if version == INITIAL_RELEASE:
        return _INITIAL_GENERATOR
    if version == BOOLEAN_RELEASE:
        return _BOOLEAN_GENERATOR
    if version == BOOLEAN_COMPOSITE_RELEASE:
        return _BOOLEAN_COMPOSITE_GENERATOR
    if version == BOOLEAN_IDENTIFICATION_RELEASE:
        return _BOOLEAN_IDENTIFICATION_GENERATOR
    if version == MINIMAL_BOOLEAN_RELEASE:
        return _MINIMAL_BOOLEAN_GENERATOR
    # Numeric source identity is carried by the factory SourceAdapter. Runtime
    # telemetry only needs the historical A/B generator labels.
    raise ValueError("FACTORY_RELEASE_HAS_NO_LEGACY_GENERATOR_LABEL:" + str(version))


def release_code_digest(version: str) -> str:
    providers = {
        INITIAL_RELEASE: _initial_digest,
        BOOLEAN_RELEASE: _boolean_digest,
        BOOLEAN_COMPOSITE_RELEASE: _boolean_composite_digest,
        BOOLEAN_IDENTIFICATION_RELEASE: _boolean_identification_digest,
        MINIMAL_BOOLEAN_RELEASE: _minimal_boolean_digest,
        NUMERIC_RELEASE: _numeric_digest,
        NUMERIC_STAIRCASE_RELEASE: _staircase_digest,
    }
    try:
        return providers[version]()
    except KeyError as exc:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version)) from exc


def legacy_receipt_fields(version: str) -> dict[str, str]:
    """Return compatibility-only receipt metadata for historical readers.

    These fields MUST NOT be used by generic runtime to choose pedagogy or
    admission behavior. They exist solely so older state readers can verify
    the exact provider bytes they historically recorded.
    """
    if version == BOOLEAN_RELEASE:
        return {
            "grade_b_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == BOOLEAN_COMPOSITE_RELEASE:
        return {
            "boolean_composite_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == BOOLEAN_IDENTIFICATION_RELEASE:
        return {
            "boolean_identification_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == MINIMAL_BOOLEAN_RELEASE:
        return {
            "grade_b_minimal_code_sha256": release_code_digest(version),
            "grade_b_generator": release_generator(version),
        }
    if version == NUMERIC_RELEASE:
        return {"grade_c_code_sha256": release_code_digest(version)}
    if version == NUMERIC_STAIRCASE_RELEASE:
        return {"staircase_code_sha256": release_code_digest(version)}
    if version == INITIAL_RELEASE:
        return {}
    raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))


def verify_release_receipt(receipt: dict, course) -> None:
    """Verify historical provider fingerprints without grade-letter dispatch."""
    version = course.version
    if version == INITIAL_RELEASE:
        return
    field_by_release = {
        BOOLEAN_RELEASE: "grade_b_code_sha256",
        BOOLEAN_COMPOSITE_RELEASE: "boolean_composite_code_sha256",
        BOOLEAN_IDENTIFICATION_RELEASE: "boolean_identification_code_sha256",
        MINIMAL_BOOLEAN_RELEASE: "grade_b_minimal_code_sha256",
        NUMERIC_RELEASE: "grade_c_code_sha256",
        NUMERIC_STAIRCASE_RELEASE: "staircase_code_sha256",
    }
    field = field_by_release.get(version)
    if field is None:
        raise ValueError("FACTORY_UNKNOWN_RELEASE:" + str(version))
    if receipt.get(field) != release_code_digest(version):
        raise ValueError("FACTORY_RELEASE_PROVIDER_DIGEST_DRIFT:" + version)


def compile_live_release(course) -> FactoryRelease:
    return compile_factory_release(course, historical_source_registry())
