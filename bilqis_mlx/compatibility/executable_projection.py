"""Project historical Course releases onto the canonical v2 curriculum/profile.

This module is deliberately compatibility-only.  The v2 compiler never learns
legacy release names; it receives canonical semantics plus a declarative profile.
"""
from __future__ import annotations

from dataclasses import replace

from ..boolean_composite import build_course as build_boolean_composite
from ..boolean_identification import build_course as build_boolean_identification
from ..curriculum import BOOLEAN_OPERATORS, Course, validate
from ..factory.curriculum_definition import from_legacy_course
from ..factory.execution import (
    CapabilityProfile, CurriculumProfile, GradeProfile,
)
from ..factory.executable_release import compile_executable_factory_release
from ..factory.live_answers import live_answer_registry
from ..factory.schedule import schedule_program_from_executable_release
from ..live_grade_b import live_course as build_boolean_grade
from ..live_grade_c import (
    live_course as build_numeric_grade,
    registry_graph as numeric_registry_graph,
)
from ..minimal_grade_b import build_course as build_minimal_boolean
from ..source_adapters.school import live_source_registry


def legacy_execution_metadata(course: Course) -> dict:
    """Translate historical mode identity into current profile-policy metadata."""
    from ..numeric_staircase import (
        FINAL_MAXIMUM as LEGACY_NUMERIC_SCOPE_FINAL,
        RELEASE as LEGACY_NUMERIC_STAIRCASE_RELEASE,
    )
    if course.version == LEGACY_NUMERIC_STAIRCASE_RELEASE:
        return {
            "numeric_scope_final_maximum": LEGACY_NUMERIC_SCOPE_FINAL,
        }
    return {}


def resolve_legacy_resume_course(
        accepted, source_root, saved, initial, *, pending=None):
    """Resolve a pre-v2 saved receipt through the historical release decoder."""
    from .live_releases import course_for_mode, resolve_admitted_courses
    admitted = resolve_admitted_courses(
        accepted, source_root, saved, pending=pending)
    return (
        course_for_mode(admitted, saved.get("curriculum_mode"), initial),
        admitted,
    )


def verify_legacy_resume_binding(
        receipt, course, graph, manifest, fingerprint, *,
        sealed_v1_release=None) -> None:
    """Verify historical graph and provider custody before v2 qualification.

    For a separately verified, immutable v1 admission, its old provider hash
    describes the *historical* executable source, not the current constructor
    bytes. The caller must immediately compile and qualify the new v2 source
    release before making any neural update. All other legacy paths retain the
    exact live-provider digest check.
    """
    from .live_releases import graph_matches_release, verify_release_receipt
    if sealed_v1_release is not None:
        if sealed_v1_release.course != course:
            raise ValueError("FACTORY_ADMISSION_SEALED_COURSE_MISMATCH")
    elif receipt.get("curriculum_mode") is not None:
        verify_release_receipt(receipt, course)
    if not graph_matches_release(
            receipt.get("curriculum_mode"), graph, manifest, fingerprint):
        raise ValueError("HUMAN_TRAINER_RESUME_MODEL_ADAMW_OR_SEMANTIC_DRIFT")


def preflight_sealed_v1_migration(run_dir, receipt, manifest, source_root):
    """Exercise the real v1 -> v2 authority transition without neural writes.

    This closes the old CLI preflight gap where source manifests passed even
    though the saved school could not be decoded with the runtime's curriculum.
    """
    from ..grade_a_release import accepted_grade_a
    from ..runtime.admission import _verified_legacy_upgrade_release
    from ..runtime.assessment import _verify_saved_cohort
    from ..runtime.state import _fingerprint, _state_from_json
    from .schedule_program import schedule_program_from_legacy_course
    from .live_releases import initial_course, NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE

    release = _verified_legacy_upgrade_release(run_dir, receipt)
    if release is None:
        return None
    pinned = release.course
    _state_from_json(receipt["school"], schedule_program_from_legacy_course(pinned))
    _verify_saved_cohort(run_dir, receipt, pinned, sealed_v1_release=release)
    if receipt.get("curriculum_mode") in (NUMERIC_RELEASE, NUMERIC_STAIRCASE_RELEASE):
        from ..live_grade_c import registry_graph
        graph = registry_graph()
    else:
        from ..source import read_sources
        _, _, graph, _, _ = read_sources(source_root)
    if _fingerprint(graph) != receipt["semantic_graph_sha256"]:
        raise ValueError("FACTORY_ADMISSION_SEALED_GRAPH_DRIFT")
    verify_legacy_resume_binding(
        receipt, pinned, graph, manifest, _fingerprint,
        sealed_v1_release=release)
    grade_a = initial_course(accepted_grade_a(manifest))
    successor, program, _ = compile_projected_executable_release(
        pinned, grade_a, source_root, graph)
    successor.verify_semantic_catalog(graph)
    return {
        "status": "VERIFIED_SEALED_V1_TO_SOURCE_QUALIFIED_V2",
        "saved_course_sha256": pinned.digest(),
        "source_qualified_successor_sha256": successor.release_sha256,
        "successor_schedule_sha256": program.digest(),
        "capabilities_by_grade": {
            grade.id: len(grade.capabilities) for grade in program.grades},
        "neural_updates": 0,
    }


LIVE_V2_VERIFICATION_SEED = 2026101905


def _canonical_boolean_course(grade_a: Course, source_root) -> Course:
    full = build_boolean_grade(grade_a, source_root)
    full = build_boolean_composite(full, source_root)
    return build_boolean_identification(full, source_root)


def _canonical_school_course(grade_a: Course, source_root) -> Course:
    boolean = _canonical_boolean_course(grade_a, source_root)
    return build_numeric_grade(
        boolean, numeric_registry_graph(), maximum=10)


def _boolean_grade_profile(current_b, canonical_b) -> GradeProfile:
    current_ids = tuple(cap.id for cap in current_b.capabilities)
    canonical_ids = tuple(cap.id for cap in canonical_b.capabilities)
    if not set(current_ids) <= set(canonical_ids):
        raise ValueError("FACTORY_COMPATIBILITY_BOOLEAN_SCOPE_UNKNOWN")
    overrides = []
    id_capability = next(
        (cap for cap in current_b.capabilities if cap.id == "B.IDBOOLOPS"), None)
    operator_values = (
        id_capability.answer_families[0].values
        if id_capability is not None else BOOLEAN_OPERATORS
    )
    if tuple(operator_values) != tuple(BOOLEAN_OPERATORS):
        if not set(operator_values) <= set(BOOLEAN_OPERATORS):
            raise ValueError("FACTORY_COMPATIBILITY_BOOLEAN_DOMAIN_UNKNOWN")
        if "B.COMPOSITE" in current_ids:
            overrides.append(CapabilityProfile(
                "B.COMPOSITE",
                provider_parameters=(("operators", tuple(operator_values)),),
            ))
        if "B.IDBOOLOPS" in current_ids:
            overrides.append(CapabilityProfile(
                "B.IDBOOLOPS",
                provider_parameters=(("operators", tuple(operator_values)),),
                answer_family_values=(
                    ("boolean_operator", tuple(operator_values)),),
            ))
    return GradeProfile(
        "B", enabled_capabilities=current_ids, capabilities=tuple(overrides))


def _numeric_grade_profile(current_c, canonical_c) -> GradeProfile:
    current_ids = tuple(cap.id for cap in current_c.capabilities)
    if not set(current_ids) <= {cap.id for cap in canonical_c.capabilities}:
        raise ValueError("FACTORY_COMPATIBILITY_NUMERIC_SCOPE_UNKNOWN")
    overrides = []
    canonical_by_id = {cap.id: cap for cap in canonical_c.capabilities}
    for capability in current_c.capabilities:
        numeric = next(
            (family for family in capability.answer_families
             if family.kind == "numeric_active"), None)
        if numeric is None:
            continue
        numbers = tuple(numeric.values)
        canonical_numeric = next(
            family for family in canonical_by_id[capability.id].answer_families
            if family.kind == "numeric_active")
        if numbers != tuple(canonical_numeric.values):
            overrides.append(CapabilityProfile(
                capability.id,
                provider_parameters=(("numbers", numbers),),
                answer_family_values=(("numeric_active", numbers),),
            ))
    return GradeProfile(
        "C", enabled_capabilities=current_ids, capabilities=tuple(overrides))


def project_legacy_course(
        course: Course, grade_a: Course, source_root, *,
        answer_kinds: tuple[str, ...]):
    """Return canonical curriculum/source bindings + profile for a v1 release."""
    if not isinstance(course, Course) or not isinstance(grade_a, Course):
        raise TypeError("FACTORY_COMPATIBILITY_COURSE_REQUIRED")

    canonical_school = _canonical_school_course(grade_a, source_root)
    current_b = next((grade for grade in course.grades if grade.id == "B"), None)
    current_c = next((grade for grade in course.grades if grade.id == "C"), None)
    if current_b is None:
        canonical_course = canonical_school
        profile = CurriculumProfile(
            "compatibility/v1-a-only",
            grades=(
                GradeProfile("B", enabled_capabilities=()),
                GradeProfile("C", enabled_capabilities=()),
            ),
        )
    else:
        canonical_course = canonical_school
        grade_profiles = [_boolean_grade_profile(
            current_b, canonical_school.grades[1])]
        if current_c is None:
            grade_profiles.append(GradeProfile("C", enabled_capabilities=()))
        else:
            grade_profiles.append(_numeric_grade_profile(
                current_c, canonical_school.grades[2]))
        profile = CurriculumProfile(
            "compatibility/v1-active-scope",
            grades=tuple(grade_profiles),
        )

    curriculum, bindings = from_legacy_course(
        canonical_course, answer_kinds=answer_kinds)
    return curriculum, bindings, profile, canonical_course


def compile_projected_executable_release(
        course: Course, grade_a: Course, source_root, graph: dict, *,
        predecessor=None):
    """Compile one v2 artifact from the historical live-course boundary."""
    answers = live_answer_registry()
    curriculum, bindings, profile, canonical_course = project_legacy_course(
        course, grade_a, source_root, answer_kinds=answers.kinds)
    release = compile_executable_factory_release(
        curriculum, bindings, profile,
        live_source_registry(), answers,
        source_root=source_root,
        graph=graph,
        verification_seed=LIVE_V2_VERIFICATION_SEED,
        predecessor=predecessor,
    )
    return release, schedule_program_from_executable_release(release), canonical_course


def legacy_course_for_profile(
        grade_a: Course, source_root, profile: CurriculumProfile) -> Course:
    """Temporary historical Course view for consumers not yet on v2 projections."""
    canonical = _canonical_boolean_course(grade_a, source_root)
    grade_profile = next(
        (item for item in profile.grades if item.grade_id == "B"), None)
    if grade_profile is None:
        base = canonical
    else:
        enabled = grade_profile.enabled_capabilities
        if enabled == ():
            return grade_a
        canonical_ids = tuple(cap.id for cap in canonical.grades[-1].capabilities)
        if enabled is None or enabled == canonical_ids:
            base = canonical
        elif enabled == ("B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"):
            base = build_minimal_boolean(grade_a, source_root)
        else:
            # Preserve the canonical source seal as historical provenance;
            # the admitted v2 release owns the narrowed assessment seal.
            grade = canonical.grades[-1]
            selected = tuple(cap for cap in grade.capabilities if cap.id in enabled)
            if (tuple(cap.id for cap in selected) != enabled or
                    grade_profile.capabilities):
                raise ValueError("FACTORY_COMPATIBILITY_PROFILE_VIEW_UNSUPPORTED")
            stages = tuple(tuple(cap for cap in stage if cap in enabled)
                           for stage in grade.teaching_stages)
            narrowed = replace(grade, capabilities=selected,
                exam_item_counts=tuple((cap, count) for cap, count in grade.exam_item_counts
                                       if cap in enabled),
                teaching_stages=tuple(stage for stage in stages if stage))
            base = replace(canonical, grades=(*canonical.grades[:-1], narrowed))
            validate(base)
    numeric_profile = next(
        (item for item in profile.grades
         if item.grade_id == "C" and item.enabled_capabilities not in ((), None)),
        None)
    if numeric_profile is None:
        return base
    numbers = None
    for capability in numeric_profile.capabilities:
        parameters = dict(capability.provider_parameters)
        if "numbers" in parameters:
            candidate = tuple(parameters["numbers"])
            if numbers is None:
                numbers = candidate
            elif numbers != candidate:
                raise ValueError(
                    "FACTORY_COMPATIBILITY_NUMERIC_DOMAIN_INCONSISTENT")
    if numbers is None:
        maximum = 10
    else:
        if numbers != tuple(str(index) for index in range(len(numbers))):
            raise ValueError("FACTORY_COMPATIBILITY_NUMERIC_DOMAIN_INVALID")
        maximum = len(numbers) - 1
    return build_numeric_grade(
        base, numeric_registry_graph(), maximum=maximum)


def profile_has_legacy_inventory(release, course) -> bool:
    """Keep legacy resume defaults from replacing an explicitly narrowed slice."""
    active = set(release.execution_plan.capability_map)
    boolean = {cap for cap in active if cap.startswith("B.")}
    basic = {"B." + operator for operator in BOOLEAN_OPERATORS}
    legacy_scopes = (set(), basic, basic | {"B.COMPOSITE", "B.IDBOOLOPS"},
                     {"B.AND", "B.IFF", "B.COMPOSITE", "B.IDBOOLOPS"})
    return active <= set(course.capability_map) and boolean in legacy_scopes
