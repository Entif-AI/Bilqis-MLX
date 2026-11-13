"""Append-only Factory staging for source-qualified event-frame successors."""
from dataclasses import replace

from ..curriculum import AnswerFamily, BINARY, GRADE_IDS
from ..factory.candidate_staging import candidate_source_anchor, compile_candidate_successor
from ..factory.curriculum_definition import CapabilitySourceBinding, CapabilitySpec, GradeSpec
from ..factory.execution import CurriculumProfile
from ..vocabulary_growth import AdmittedToken, append_catalog
from bilqis_mlx.source_adapters import copular_curriculum
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


def _admission(capability, sources):
    row = sources[capability]
    proof = source_contract_digest(capability)
    _, prerequisites = SPECS[capability]
    required_event_tokens = tuple(
        SYMBOLS[item] for item in prerequisites if item in SYMBOLS)
    prerequisite_tokens = (
        ('development.Event.E0',) if capability == 'D.EVENT_OCCURRENCE'
        else required_event_tokens
    )
    return AdmittedToken(
        SYMBOLS[capability], SEMANTIC_IDS[capability],
        row['sense_summary'] +
        '; finite event observation/transition only; morphology not realized',
        'new_ithkuil', 'compositional', row['source_url'],
        row['source_text_sha256'], proof, provider_implementation_digest(),
        prerequisite_tokens, capability, proof,
        signature='Boolean*Boolean->Boolean', arity=2,
    )


def _canonical_node(entry):
    return {
        'id': entry.token_id,
        'family': entry.source_kind,
        'subtype': entry.representation,
        'signature': entry.signature,
        'arity': entry.arity,
        'stage': 0,
        'source': entry.source_locator,
        'semantic_id': entry.semantic_id,
        'meaning': entry.meaning,
        'capability_id': entry.capability_id,
        'admission_receipt': entry.admission_receipt,
        'state': entry.state,
        'edges': [
            {'kind': 'prerequisite', 'target': prerequisite}
            for prerequisite in entry.prerequisite_tokens
        ],
    }


def _allocation_base(parent):
    """Preserve the already-authorized numeric->copular allocation frontier."""
    copular = copular_curriculum.token_admission()
    if copular.token_id not in parent['tokens']:
        return copular_curriculum.proposed_graph(parent)
    index = parent['tokens'].index(copular.token_id)
    if parent['nodes'][index] != _canonical_node(copular):
        source_invalid('EVENT_FRAME_COPULAR_ALLOCATION_AUTHORITY_DRIFT')
    return parent


def projected_graph(parent, capabilities):
    """Append only the requested prerequisite-closed event identities."""
    if (type(capabilities) is not tuple or not capabilities
            or len(set(capabilities)) != len(capabilities)
            or any(capability not in SOURCE_SPECS for capability in capabilities)):
        source_invalid('EVENT_FRAME_CATALOG_PROJECTION_INVALID')
    parent = _allocation_base(parent)
    sources = source_senses()
    admissions = []
    available = set(parent.get('tokens', ()))
    for capability in capabilities:
        _, prerequisites = SPECS[capability]
        admission = _admission(capability, sources)
        if SYMBOLS[capability] in parent['tokens']:
            index = parent['tokens'].index(SYMBOLS[capability])
            if parent['nodes'][index] != _canonical_node(admission):
                source_invalid('EVENT_FRAME_EXISTING_ROW_AUTHORITY_DRIFT')
            available.add(SYMBOLS[capability])
            continue
        required_event_tokens = tuple(
            SYMBOLS[item] for item in prerequisites if item in SYMBOLS)
        if any(token not in available for token in required_event_tokens):
            source_invalid('EVENT_FRAME_CATALOG_PREREQUISITE_MISSING')
        admissions.append(admission)
        available.add(SYMBOLS[capability])
    return (
        append_catalog(parent, tuple(admissions), allow_disposable_fixtures=True)[0]
        if admissions else parent
    )


def expanded_graph(parent):
    return projected_graph(parent, tuple(SOURCE_SPECS))


def _qualified_frontier_candidate(frontier, capability):
    spec = SOURCE_SPECS.get(capability)
    matches = [
        candidate for candidate in frontier.candidates
        if candidate.proposed_capability_id == capability
        and spec is not None and candidate.target_sense_id == spec.sense_id
    ]
    if spec is None or len(matches) != 1:
        source_invalid('EVENT_FRAME_EXACT_NEW_CANDIDATE_REQUIRED')
    candidate = matches[0]
    sense = next((item for item in frontier.senses
                  if item.sense_id == spec.sense_id), None)
    source = source_senses()[capability]
    if (sense is None
            or sense.root_id != spec.root_id
            or sense.root_form != spec.root_form
            or sense.selected_target_capability != capability
            or sense.source_text_sha256 != spec.source_text_sha256
            or sense.source_text_sha256 != source['source_text_sha256']
            or tuple(item.capability_id for item in candidate.prerequisites)
               != spec.prerequisites):
        source_invalid('EVENT_FRAME_FRONTIER_SOURCE_AUTHORITY_DRIFT')
    return candidate


def stage_capability(
    frontier, current, parent_graph, capability, *,
    source_root, source_registry, answer_registry,
):
    """Stage exactly one prerequisite-closed event successor without admitting it."""
    spec = SOURCE_SPECS.get(capability)
    if spec is None or capability in current.curriculum.capability_map:
        source_invalid('EVENT_FRAME_EXACT_NEW_CANDIDATE_REQUIRED')
    candidate = _qualified_frontier_candidate(frontier, capability)
    if any(prerequisite not in current.curriculum.capability_map
           for prerequisite in spec.prerequisites):
        source_invalid('EVENT_FRAME_FACTORY_PREREQUISITE_MISSING')

    candidate_id = candidate.candidate_id
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
