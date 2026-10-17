"""Current v16 bounded-acquisition rubric, with all three weak lessons fixed.

Retain the oracle-checked v15 source questions for 28 grades and replace its
premature G18 source panels with an eighteen-question, three-stage lesson of
static evidence/supersession. Never infer general tense, chronological order,
or world-state mutation from a snapshot contrast. Historic G24 remains only a
comparator. Same-checkpoint COMPLETE current scoring is mandatory for gold.
"""
from __future__ import annotations

from functools import lru_cache
import torch

from bilqis_logic.kernel import digest

from . import source_rubric_v15 as source
from . import repaired_lessons_v16 as repaired

SCHEMA = 'bilqis.v16.current-acquisition-rubric/v1'
PROGRAM = source.EXPECTED_PROGRAM
DEFERRED = {'G18:EXTENDED': repaired.HELD_G18_EXTENSIONS}
HISTORICAL_COMPARATORS = ('G11', 'G18', 'G20')


@lru_cache(maxsize=1)
def inventory():
    old, groups = source.inventory()
    active = {key: dict(entry) for key, entry in old.items()
              if not key.startswith('G18:')}
    for grade in ('G11','G20'):
        taught = repaired.current_rows(grade)
        registered = [row for key in active if key.startswith(grade + ':')
                      for row in groups[key]]
        if ({r['id'] for r in taught} != {r['id'] for r in registered} or
                len(taught) != len(registered)):
            raise ValueError('V16_REPAIRED_LESSON_AND_PROBE_DIVERGED:' + grade)
    for stage in repaired.lesson('G18')['stages']:
        key='G18:'+stage['name']
        rows=stage['rows']
        if not rows or len(set(r['id'] for r in rows)) != len(rows):
            raise ValueError('V16_G18_DUPLICATE_OR_EMPTY_STAGE')
        for row in rows:
            source._verify(row)
        active[key]={'source':'bilqis_school.current_rubric_v16/'+SCHEMA,
                     'assessment_role':'CURRENT_TAUGHT_SYLLABUS',
                     'evidence_role':'SOURCE_DEFINED_ACQUISITION_NOT_INDEPENDENT_GENERALIZATION',
                     'total':len(rows),
                     'questions_sha256':digest([[r['id'],r['gold'],r.get('answer_kind','evidence')]
                                                for r in rows])}
    if {key.split(':', 1)[0] for key in active} != set(PROGRAM):
        raise ValueError('V16_CURRENT_RUBRIC_MISSING_GRADE')
    return active


def identity():
    active = inventory()
    return {'schema': SCHEMA, 'rubric_sha256': digest(active),
            'program': PROGRAM, 'deferred': DEFERRED,
            'source': source.SCHEMA,
            'historical_comparators_not_current': HISTORICAL_COMPARATORS}


def questions(key):
    """Resolve exact versioned canonical question identities for a metric."""
    if key.startswith('G18:'):
        stage=key.split(':',1)[1]
        entries=[s for s in repaired.lesson('G18')['stages'] if s['name']==stage]
        if len(entries)!=1:raise ValueError('V16_G18_UNKNOWN_CURRENT_STAGE:'+key)
        return entries[0]['rows']
    return source.questions(key)


@torch.no_grad()
def score_current(model, graph, entries, *, device='cpu'):
    """Grade a current-rubric subset using the existing typed student ABI.

    Source rows, gold labels, total, question hash and roles are checked at
    the boundary. Neither frozen v15 rubric nor its scoring code is edited.
    """
    from . import numeric_answer_contract as numbers
    from . import spiral_staged_runner as staged
    all_entries=inventory()
    if not entries or any(key not in all_entries or all_entries[key]!=entry
                          for key,entry in entries.items()):
        raise ValueError('V16_UNKNOWN_OR_CHANGED_CURRENT_RUBRIC')
    by_kind={'numeric':[], 'evidence':[]}
    for key,entry in sorted(entries.items()):
        rows=questions(key)
        if (len(rows)!=entry['total'] or
                digest([[r['id'],r['gold'],r.get('answer_kind','evidence')]
                        for r in rows])!=entry['questions_sha256']):
            raise ValueError('V16_CURRENT_QUESTION_IDENTITY_DRIFT:'+key)
        for row in rows:
            kind=row.get('answer_kind','evidence')
            if kind not in by_kind:
                raise ValueError('V16_CURRENT_UNSUPPORTED_ANSWER_KIND:'+key)
            by_kind[kind].append((key,row))
    initial_training=model.training
    correct={key:0 for key in entries}
    model.eval()
    try:
        numeral_ids=numbers.numeric_token_ids(graph)[:4]
        for kind,rows in by_kind.items():
            for i in range(0,len(rows),24):
                block=rows[i:i+24]
                cases=[row for _,row in block]
                ids,lengths=staged._input(cases,graph,device)
                logits=numbers.readout(model,ids,lengths,
                                       answer_kind=kind,number_ids=numeral_ids)
                labels=staged._gold(cases,kind,device)
                if logits.shape!=(len(cases),len(numeral_ids) if kind=='numeric' else 5):
                    raise ValueError('V16_CURRENT_STUDENT_ANSWER_SHAPE_DRIFT')
                for (key,_),right in zip(block,(logits.argmax(-1)==labels).tolist()):
                    correct[key]+=int(right)
    finally:
        if initial_training:model.train()
    return correct


def score_snapshot(model, graph, *, optimizer_step, checkpoint_sha256,
                   device='cpu'):
    """Read-only same-student CURRENT scoring, using existing typed scorer.

    The caller MUST first load and verify its actual FP32+own-AdamW
    checkpoint. A score snapshot is not itself a golden qualification and
    should never be constructed from historical maxima or training logs.
    """
    from .triplet_scheduler_v16 import SNAPSHOT_SCHEMA

    if type(optimizer_step) is not int or optimizer_step < 0:
        raise ValueError('V16_PROBE_MISSING_STEP')
    if not isinstance(checkpoint_sha256, str) or len(checkpoint_sha256) != 64:
        raise ValueError('V16_PROBE_MISSING_CHECKPOINT_HASH')
    rubric = inventory()
    correct = score_current(model, graph, rubric, device=device)
    return {'schema': SNAPSHOT_SCHEMA,
            'optimizer_step': optimizer_step,
            'checkpoint_sha256': checkpoint_sha256,
            'current_rubric_sha256': digest(rubric),
            'metrics': {key: {
                'correct': correct[key], 'total': rubric[key]['total'],
                'optimizer_step': optimizer_step,
                'checkpoint_sha256': checkpoint_sha256}
                for key in rubric}}
