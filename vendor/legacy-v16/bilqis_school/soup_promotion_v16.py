"""Next-run frozen-teacher promotion on the *current taught syllabus*.

Never assign a weights-only soup to the causal FP32 student or claim that it
inherits the student's AdamW moments. Use the selected qualified soup as a
frozen teaching model at the next version boundary, with lineage recorded.
"""
from __future__ import annotations

from copy import deepcopy

FOCUS_DENOMINATORS={'G11':16,'G20':24,'G22':16}


def current_score(focused, bridge_correct, numeric_correct):
    """Authoritative *current* G11/G20/G22 + B84 + N4 assessment."""
    if set(focused)!=set(FOCUS_DENOMINATORS):
        raise ValueError('V16_CURRENT_SYLLABUS_INCOMPLETE')
    for grade,denominator in FOCUS_DENOMINATORS.items():
        record=focused[grade]
        if record['total']!=denominator or not 0<=record['correct']<=denominator:
            raise ValueError('V16_CURRENT_SYLLABUS_DENOMINATOR_DRIFT')
    if not 0<=bridge_correct<=84 or not 0<=numeric_correct<=4:
        raise ValueError('V16_CURRENT_DOMAIN_DENOMINATOR_DRIFT')
    focused_correct=sum(x['correct'] for x in focused.values())
    return {'focused':deepcopy(focused),
            'focused_correct':focused_correct,'focused_total':56,
            'bridge_correct':bridge_correct,'numeric_correct':numeric_correct,
            'current_macro':round(100*((focused_correct/56)+
                  (bridge_correct/84)+(numeric_correct/4))/3,6),
            'assessment':'V16_CURRENT_TAUGHT_56_B84_N4',
            'legacy_G24_included':False}


def select_teacher(incumbent,student,proposed):
    """Promote the highest CURRENT measured teacher, with stable provenance.

    incumbent and student are separate candidates. A soup must beat both
    (and itself have a frozen file) to replace the frozen teaching guidance.
    Do not silently infer candidate scores from legacy G528 measurements.
    """
    for contender in (incumbent,student,*proposed):
        scores=contender['scores']
        if scores['assessment']!='V16_CURRENT_TAUGHT_56_B84_N4':
            raise ValueError('V16_REFUSE_LEGACY_METRIC_PROMOTION')
        if not contender.get('sha256') or not contender.get('file'):
            raise ValueError('V16_PROMOTION_MISSING_FROZEN_PROVENANCE')
    baseline=max((incumbent,student),key=lambda item:item['scores']['current_macro'])
    best=max(proposed,key=lambda item:item['scores']['current_macro']) if proposed else None
    if best is not None and best['scores']['current_macro']>baseline['scores']['current_macro']:
        return {'decision':'PROMOTE_FROZEN_TEACHER_FOR_NEXT_VERSION',
                'winner':deepcopy(best),'beats_baseline':baseline['file'],
                'source_student_adamw_preserved':True}
    return {'decision':'KEEP_MEASURED_INCUMBENT_OR_STUDENT',
            'winner':deepcopy(baseline),'beats_baseline':None,
            'source_student_adamw_preserved':True}
