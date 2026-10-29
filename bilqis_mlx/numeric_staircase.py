"""Warm-start numeric scope changes using the existing course and state owners."""
from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
from pathlib import Path

from .generated_assessment import digest
from .live_grade_c import REGISTRY_COUNTING_TARGET, answer_heads, live_course
from .semantics.foundation.core import Literal
from .semantics.foundation.numeric import evaluate
from .source_adapters.numeric import decode

RELEASE = 'bilqis.mlx.numeric-staircase/20261017-v1'
INITIAL_MAXIMUM = 4
FULL_OPERATION_MAXIMUM = 4
PREVIOUS_FINAL_MAXIMUM = 6
FINAL_MAXIMUM = REGISTRY_COUNTING_TARGET
FOUNDATIONS = ('C.COUNT', 'C.NUMBER', 'C.SUCCESSOR', 'C.ADD', 'C.SUB')


def constructor_digest():
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def build_course(previous, graph, *, maximum=INITIAL_MAXIMUM):
    if type(maximum) is not int or not INITIAL_MAXIMUM <= maximum <= FINAL_MAXIMUM:
        raise ValueError('NUMERIC_STAIRCASE_SCOPE_INVALID')
    base = live_course(previous, graph, maximum=maximum)
    seal = digest({'base_course': base.digest(), 'staircase': constructor_digest(),
                   'initial_maximum': INITIAL_MAXIMUM, 'final_maximum': FINAL_MAXIMUM})
    grade = replace(base.grades[-1], assessment_sha256=seal)
    return replace(base, version=RELEASE, grades=(*base.grades[:-1], grade),
                   assessment_manifest_sha256=seal)


def row_in_scope(row, maximum):
    """Keep wider unresolved mistakes available, but out of narrower lessons."""
    if not row['capability'].startswith('C.'):
        return True
    symbols = row['record']['symbols']
    if any(int(s.removeprefix('school.number.')) > maximum
           for s in symbols if s.startswith('school.number.')):
        return False

    def bounded(node):
        if node.type_name == 'Number' and evaluate(node) > maximum:
            return False
        if isinstance(node, Literal):
            return True
        return all(bounded(child) for child in node.arguments)

    return bounded(decode(symbols))


def scope_advance_due(receipt, course):
    school = receipt['school']
    exam = receipt.get('last_exam') or {}
    scores = exam.get('scores', {})
    expected = dict(course.grades[-1].exam_item_counts)
    return (receipt.get('curriculum_mode') == RELEASE and
            receipt['numeric_maximum'] < FINAL_MAXIMUM and
            school['active_grades'][school['grade_index']] == 'C' and
            school['stage'] == 'MAIN' and school['introduction_stage'] == len(FOUNDATIONS) and
            exam.get('student_sha256') == school['current_student']['sha256'] and
            exam.get('optimizer_step') == school['current_student']['optimizer_step'] and
            all(scores.get(cap, {}).get('correct') == expected[cap]
                and scores.get(cap, {}).get('total') == expected[cap]
                for cap in FOUNDATIONS))


def _rebind(run_dir, receipt, old_course, new_course, graph, *, introduction_stage, queue, event):
    from bilqis_mlx.runtime.checkpoints import _advance, _persist, _with_delivery_outbox, _reconcile_delivery_outbox
    from bilqis_mlx.runtime.admission import _factory_admission
    from bilqis_mlx.runtime.state import _state_from_json
    school = _state_from_json(receipt['school'], old_course)
    if school.grade != 'C' or school.revalidation_target_grade is not None:
        raise ValueError('NUMERIC_STAIRCASE_REQUIRES_ACTIVE_C')
    if receipt.get('_pending_visit_events'):
        raise ValueError('NUMERIC_STAIRCASE_REQUIRES_COMPLETE_CHECKPOINT')
    maximum = len(new_course.grades[-1].capabilities[0].answer_families[1].values)-1
    changed = replace(school, course_digest=new_course.digest(), stage='MAIN',
        introduction_stage=introduction_stage, queue=tuple(queue), first_recovery=(),
        latest_rubric_digest=None, pending_failures=(), grade_exam_epoch=school.grade_exam_epoch+1)
    history = [*receipt.get('curriculum_history', ()), {
        'release': old_course.version, 'course_digest': old_course.digest(),
        'integer_max': receipt['numeric_maximum'], 'generation': receipt['generation'],
        'state_file': f"states/{receipt['generation']:07d}.json"}]
    heads = answer_heads(graph, maximum)
    if 'boolean_operator' in receipt['config'].get('answer_heads', {}):
        prior = receipt['config']['answer_heads']['boolean_operator']
        heads['boolean_operator'] = {
            'values': list(prior['values']),
            'token_ids': list(prior['token_ids']),
        }
    updated = {**receipt, 'curriculum_mode': RELEASE, 'numeric_maximum': maximum,
        'staircase_code_sha256': constructor_digest(), 'curriculum_history': history,
        'curriculum_parent': receipt.get('curriculum_parent', receipt['school']['current_student']),
        'config': {**receipt['config'], 'answer_heads': heads},
        'live_rubric_sha256': new_course.grades[-1].assessment_sha256, 'last_exam': None}
    release, release_file, admission = _factory_admission(
        run_dir, new_course, school.current_student,
        receipt['semantic_graph_sha256'])
    updated.update(factory_release_sha256=release.release_sha256,
                   factory_release_file=release_file,
                   factory_admission=asdict(admission))
    from bilqis_mlx.learning.championship_identity import (
        build_school_identity, enforce_school_identity)
    identity = build_school_identity(
        course_sha256=new_course.digest(),
        semantic_graph_sha256=receipt['semantic_graph_sha256'],
        parameter_shapes=receipt['parameter_shapes'],
        factory_release_sha256=release.release_sha256)
    updated['championship_school_identity'] = identity
    if updated.get('mentor_epoch') is not None:
        epoch, _ = enforce_school_identity(
            updated['mentor_epoch'], identity,
            generation=receipt['generation'] + 1,
            student=asdict(school.current_student))
        updated['mentor_epoch'] = epoch
    updated.pop('qualification_cohort', None)
    record = _advance(run_dir, updated, changed, result='ACTIVE_GRADE_C', persist=False)
    delivery = {'event': event, 'grade': 'C', 'generation': record['generation'],
        'old_integer_max': receipt['numeric_maximum'], 'integer_max': maximum,
        'student_sha256': school.current_student.sha256,
        'optimizer_step': school.current_student.optimizer_step,
        'factory_release_sha256': release.release_sha256,
        'actual_neural_updates': 0}
    record = _persist(run_dir, _with_delivery_outbox(record, (delivery,)))
    _reconcile_delivery_outbox(run_dir, record)
    return new_course, record


def enroll(run_dir, receipt, old_course, previous, graph):
    from .live_grade_c import RELEASE as OLD_RELEASE
    if receipt.get('curriculum_mode') != OLD_RELEASE:
        raise ValueError('NUMERIC_STAIRCASE_REQUIRES_EXISTING_C')
    course = build_course(previous, graph)
    return _rebind(run_dir, receipt, old_course, course, graph,
        introduction_stage=0, queue=('C.COUNT',), event='SCHOOL_NUMERIC_STAIRCASE_ENROLLED')


def advance_scope(run_dir, receipt, old_course, previous, graph):
    if not scope_advance_due(receipt, old_course):
        raise ValueError('NUMERIC_STAIRCASE_FOUNDATIONS_NOT_MASTERED')
    course = build_course(previous, graph, maximum=receipt['numeric_maximum']+1)
    return _rebind(run_dir, receipt, old_course, course, graph,
        introduction_stage=4, queue=FOUNDATIONS, event='SCHOOL_NUMERIC_SCOPE_ADVANCED')
