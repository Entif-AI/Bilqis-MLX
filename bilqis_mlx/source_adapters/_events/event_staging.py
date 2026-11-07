"""Append-only Factory staging for source-qualified event-frame successors."""
from dataclasses import replace

from ..curriculum import AnswerFamily, BINARY, GRADE_IDS
from ..factory.candidate_staging import candidate_source_anchor, compile_candidate_successor
from ..factory.curriculum_definition import CapabilitySourceBinding, CapabilitySpec, GradeSpec
from ..factory.execution import CurriculumProfile
from ..vocabulary_growth import AdmittedToken, append_catalog
from .event_authority import (
    SEMANTIC_IDS,
    SOURCE_SPECS,
    SPECS,
    SYMBOLS,
    provider_implementation_digest,
    source_contract_digest,
    source_invalid,
    source_senses,
)


GENERATOR = 'bilqis.ithkuil-event-frame-constructor/v1'
ORACLE = 'bilqis.issue349.event-frame-oracle/v1'


def capability_definition(capability):
    """Return the ordinary Factory capability declaration for one event sense."""
    spec = SOURCE_SPECS[capability]
    return CapabilitySpec(
        capability, 'finite-event-frame', (SYMBOLS[capability],), (SYMBOLS[capability],),
        spec.prerequisites, (), (AnswerFamily('binary', BINARY),),
    )


def event_grade_id(curriculum):
    """Choose the event tranche container from structure, never a named grade."""
    event_grades = tuple(
        grade.grade_id for grade in curriculum.grades
        if any(cap.capability_id in SOURCE_SPECS for cap in grade.capabilities)
    )
    if len(set(event_grades)) > 1:
        source_invalid('EVENT_FRAME_GRADE_STRUCTURE_DRIFT')
    if event_grades:
        return event_grades[0]
    used = {grade.grade_id for grade in curriculum.grades}
    available = tuple(grade_id for grade_id in GRADE_IDS if grade_id not in used)
    if not available:
        source_invalid('EVENT_FRAME_GRADE_CAPACITY_EXHAUSTED')
    return available[0]


def projected_graph(parent, capabilities):
    """Append only the requested prerequisite-closed event identities."""
    if (type(capabilities) is not tuple or not capabilities
            or len(set(capabilities)) != len(capabilities)
            or any(capability not in SOURCE_SPECS for capability in capabilities)):
        source_invalid('EVENT_FRAME_CATALOG_PROJECTION_INVALID')
    sources = source_senses()
    admissions = []
    available = set(parent.get('tokens', ()))
    for capability in capabilities:
        _, prerequisites = SPECS[capability]
        if SYMBOLS[capability] in parent['tokens']:
            available.add(SYMBOLS[capability])
            continue
        required_event_tokens = tuple(
            SYMBOLS[item] for item in prerequisites if item in SYMBOLS)
        if any(token not in available for token in required_event_tokens):
            source_invalid('EVENT_FRAME_CATALOG_PREREQUISITE_MISSING')
        row = sources[capability]
        proof = source_contract_digest(capability)
        prerequisite_tokens = (
            ('development.Event.E0',) if capability == 'D.EVENT_OCCURRENCE'
            else required_event_tokens
        )
        admissions.append(AdmittedToken(
            SYMBOLS[capability], SEMANTIC_IDS[capability],
            row['sense_summary'] +
            '; finite event observation/transition only; morphology not realized',
            'new_ithkuil', 'compositional', row['source_url'],
            row['source_text_sha256'], proof, provider_implementation_digest(),
            prerequisite_tokens, capability, proof,
            signature='Boolean*Boolean->Boolean', arity=2,
        ))
        available.add(SYMBOLS[capability])
    return (
        append_catalog(parent, tuple(admissions), allow_disposable_fixtures=True)[0]
        if admissions else parent
    )


def expanded_graph(parent):
    return projected_graph(parent, tuple(SOURCE_SPECS))


def stage_capability(
    frontier, current, parent_graph, capability, *,
    source_root, source_registry, answer_registry,
):
    """Stage exactly one prerequisite-closed event successor without admitting it."""
    spec = SOURCE_SPECS.get(capability)
    matches = [
        candidate for candidate in frontier.candidates
        if candidate.proposed_capability_id == capability
        and spec is not None and candidate.target_sense_id == spec.sense_id
    ]
    if (spec is None or capability in current.curriculum.capability_map
            or len(matches) != 1):
        source_invalid('EVENT_FRAME_EXACT_NEW_CANDIDATE_REQUIRED')
    if any(prerequisite not in current.curriculum.capability_map
           for prerequisite in spec.prerequisites):
        source_invalid('EVENT_FRAME_FACTORY_PREREQUISITE_MISSING')

    candidate_id = matches[0].candidate_id
    event_capability = capability_definition(capability)
    target_grade = event_grade_id(current.curriculum)
    grades = list(current.curriculum.grades)
    for index, grade in enumerate(grades):
        if grade.grade_id != target_grade:
            continue
        grades[index] = replace(
            grade,
            capabilities=(*grade.capabilities, event_capability),
            exam_item_counts=(*grade.exam_item_counts, (capability, 12)),
            teaching_stages=(*grade.teaching_stages, (capability,)),
        )
        break
    else:
        grades.append(
            GradeSpec(target_grade, (event_capability,), ((capability, 12),), ((capability,),))
        )
    curriculum = replace(current.curriculum, grades=tuple(grades))
    bindings = replace(
        current.source_bindings,
        bindings=(*current.source_bindings.bindings, CapabilitySourceBinding(
            capability, candidate_source_anchor(frontier, candidate_id), GENERATOR, ORACLE)),
    )
    graph = projected_graph(parent_graph, (capability,))
    staged = compile_candidate_successor(
        frontier, current, candidate_id,
        curriculum=curriculum, source_bindings=bindings,
        profile=CurriculumProfile('jit/event-frames/v1', grades=current.profile.grades),
        source_registry=source_registry, answer_registry=answer_registry,
        source_root=source_root, graph=graph, verification_seed=2026110704,
    )
    staged.successor.verify_semantic_catalog(graph)
    return staged
