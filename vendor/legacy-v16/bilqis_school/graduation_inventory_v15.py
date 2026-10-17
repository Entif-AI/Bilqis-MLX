"""The v15 current-source exam, independent of historical G528 maxima.

Built by source_rubric_v15 from exactly taught, oracle-backed families.
The score is acquisition coverage, not evidence of unseen generalization.
"""

CURRENT_RUBRIC_CANDIDATES = {
    'G11': {'source':'foundation_course_v15.rows', 'total':16},
    'G15': {'source':'primitive_staircase_v13.rows(EDGE)', 'total':8},
    'G20': {'source':'foundation_course_v15.rows', 'total':24},
    'G22': {'source':'foundation_course_v15.rows', 'total':16},
}

# This explicit source-backed profile replaces the incomplete placeholder.
# Setting None remains a strict HOLD. Tests can override with a fixture profile.
APPROVED_CURRENT_RUBRIC = 'SOURCE_DEFINED_V15_ACQUISITION_V1'


def questions(key):
    from .source_rubric_v15 import questions as get_questions
    return get_questions(key)


def approved_inventory(program):
    rubric=APPROVED_CURRENT_RUBRIC
    if rubric=='SOURCE_DEFINED_V15_ACQUISITION_V1':
        from .source_rubric_v15 import inventory
        rubric=inventory()[0]
    if not isinstance(rubric,dict) or not rubric:
        raise ValueError('NO_APPROVED_CURRENT_METRIC_INVENTORY')
    if len(program)!=29 or len(set(program))!=29 or set(program)!=set(
            [f'B{x:02d}' for x in range(1,8)]+[f'G{x:02d}' for x in range(1,23)]):
        raise ValueError('INVALID_CURRENT_GRADE_PROGRAM')
    grades={grade:[] for grade in program}
    for key,entry in rubric.items():
        if not isinstance(key,str) or ':' not in key or not isinstance(entry,dict):
            raise ValueError('INVALID_CURRENT_METRIC_INVENTORY')
        grade,capability=key.split(':',1)
        if (grade not in grades or not capability or type(entry.get('total')) is not int
                or entry['total']<=0 or not entry.get('source') or
                entry.get('assessment_role')!='CURRENT_TAUGHT_SYLLABUS'):
            raise ValueError('INVALID_CURRENT_METRIC_INVENTORY')
        grades[grade].append(key)
    if any(not metrics for metrics in grades.values()):
        raise ValueError('INCOMPLETE_CURRENT_METRIC_COVERAGE')
    return rubric
