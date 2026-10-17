"""Versioned v15 grade-boundary completion adapter; no neural recipe edits.

The old trainer already calls reporter after each durable grade and checks
stop_requested before scheduling the next. This adapter connects those hooks
to a SAME-CHECKPOINT current-metric producer. Without approved full rubric it
continues under human operator control and cannot certify a golden student.
"""
from __future__ import annotations

from pathlib import Path
import os
import torch
from unittest.mock import patch

from bilqis_logic.kernel import digest
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash

from . import engine, time_first_runner_v15 as trainer
from . import training_completion as completion
from . import graduation_inventory_v15 as inventory
from . import source_rubric_v15 as source_rubric

CURRENT_RUBRIC_CANDIDATES = inventory.CURRENT_RUBRIC_CANDIDATES


def score_current_metric(model,graph,key,entry):
    """Single family scorer; whole-program scoring batches calls together."""
    if entry.get('source')=='bilqis_school.source_rubric_v15/'+source_rubric.SCHEMA:
        return score_source_rubric(model,graph,{key:entry})[key]
    from . import foundation_course_v15 as foundation
    grade,concept=key.split(':',1)
    if grade=='G15' and concept=='EDGE' and entry.get('source')=='primitive_staircase_runner_v13._score':
        from . import primitive_staircase_runner_v13 as staircase
        result=staircase._score(model,graph,'cpu')['by_concept'].get('EDGE')
    elif entry.get('source')=='foundation_course_v15.measure' and grade in foundation.FOCUSED:
        result=foundation.measure(model,graph,grade,'cpu')['by_concept'].get(concept)
    else:
        raise ValueError('NO_APPROVED_EXECUTABLE_CURRENT_SCORER:'+key)
    if not result or result.get('total',result.get('questions'))!=entry['total']:
        raise ValueError('CURRENT_SCORER_QUESTION_INVENTORY_DRIFT:'+key)
    return result['correct']


@torch.no_grad()
def score_source_rubric(model,graph,rubric,*,device='cpu'):
    """Evaluate all CURRENT taught-source questions at the same model step.

    Score both numeric and semantic questions through the training ABI, with
    frozen question hashes and oracle gold. No optimizer/model writes.
    """
    from . import numeric_answer_contract as numbers
    from . import spiral_staged_runner as staged
    from . import lessons
    rows_by_kind={'numeric':[], 'evidence':[]}
    for key,entry in sorted(rubric.items()):
        if entry.get('source')!='bilqis_school.source_rubric_v15/'+source_rubric.SCHEMA:
            raise ValueError('CURRENT_SOURCE_RUBRIC_NOT_BOUND:'+key)
        questions=inventory.questions(key)
        if len(questions)!=entry['total'] or entry.get('questions_sha256')!=digest([
             [r['id'],r['gold'],r.get('answer_kind','evidence')] for r in questions]):
            raise ValueError('CURRENT_RUBRIC_QUESTION_IDENTITY_DRIFT:'+key)
        for row in questions:
            # Compilation already checked both independent symbolic oracles.
            kind=row.get('answer_kind','evidence')
            if kind not in rows_by_kind:
                raise ValueError('CURRENT_RUBRIC_BAD_ANSWER_TYPE:'+key)
            rows_by_kind[kind].append((key,row))
    was_training=model.training
    scores={key:0 for key in rubric}
    model.eval()
    try:
        numeral_ids=numbers.numeric_token_ids(graph)[:4]
        for kind,all_rows in rows_by_kind.items():
            for index in range(0,len(all_rows),24):
                block=all_rows[index:index+24]
                questions=[row for _,row in block]
                ids,lengths=staged._input(questions,graph,device)
                logits=numbers.readout(model,ids,lengths,
                                       answer_kind=kind,number_ids=numeral_ids)
                gold=staged._gold(questions,kind,device)
                if logits.shape!=(len(questions),
                                  len(numeral_ids) if kind=='numeric' else 5):
                    raise ValueError('CURRENT_RUBRIC_TYPED_READOUT_DRIFT')
                matches=(logits.argmax(-1)==gold).tolist()
                for (key,_),correct in zip(block,matches):
                    scores[key]+=int(correct)
    finally:
        if was_training:model.train()
    return scores


def screen_source_rubric(model,graph,rubric,*,previous=None):
    """Exact fail-fast qualification, not a sampled/proxy completion test.

    Every category must pass at this *same checkpoint* to graduate. Sorting
    previously failed categories first reduces cost without weakening that
    criterion. One actual wrong answer proves the entire rubric is not 100%.
    A perfect screen provides all 137 scored totals for a single receipt.
    """
    history=(previous or {}).get('metrics') or {}
    def priority(key):
        row=history.get(key) or {}
        correct=row.get('correct')
        total=row.get('total')
        ratio=(correct/total if type(correct) is int and
               type(total) is int and total>0 else 1.0)
        return ratio,key
    scores={}
    for key in sorted(rubric,key=priority):
        value=score_source_rubric(model,graph,{key:rubric[key]})[key]
        if value!=rubric[key]['total']:
            return None,{'key':key,'correct':value,
                         'total':rubric[key]['total']}
        scores[key]=value
    return scores,None


def make_receipt(state, model, optimizer, graph, scorer=None):
    """Measure every approved metric on ONE verified full FP32+AdamW student.

    `scorer` is a future approved current-rubric provider; no provider exists
    for every v15 grade today. Only an exact measured all-capability result
    may be represented as a graduation receipt.
    """
    rubric=inventory.approved_inventory(state.get('config',{}).get('grade_program') or ())
    if (model is None or optimizer is None or graph is None):
        raise ValueError('MISSING_FULL_STUDENT_ADAMW_OR_CURRENT_SCORER')
    if scorer is None:
        if inventory.APPROVED_CURRENT_RUBRIC=='SOURCE_DEFINED_V15_ACQUISITION_V1':
            results=score_source_rubric(model,graph,rubric)
            scorer=lambda model,graph,key,entry:results[key]
        else:
            scorer=score_current_metric
    if not callable(scorer):raise ValueError('MISSING_CURRENT_SCORER')
    if (optimizer_receipt(optimizer)['steps']!=[state['optimizer_step']] or
            any(t.is_floating_point() and t.dtype!=torch.float32
                for t in model.parameters()) or
            digest(graph)!=state['graph_sha256']):
        raise ValueError('INVALID_FULL_FP32_ADAMW_LINEAGE')
    # The native complete student and its own optimizer have already been
    # SHA/readback verified by trainer._load_student at the saved boundary.
    metrics={}
    for key,entry in sorted(rubric.items()):
        result=scorer(model,graph,key,entry)
        if (type(result) is not int or not 0<=result<=entry['total']):
            raise ValueError('INVALID_CURRENT_SCORER_RESULT:'+key)
        metrics[key]={'correct':result,'total':entry['total'],
                      'optimizer_step':state['optimizer_step'],
                      'checkpoint_sha256':state['checkpoint_sha256']}
    return {'schema':completion.SCHEMA,'training_version':state['version'],
            'optimizer_step':state['optimizer_step'],'checkpoint':state['checkpoint'],
            'checkpoint_sha256':state['checkpoint_sha256'],
            'model_sha256':state_hash(model),'graph_sha256':digest(graph),
            'current_rubric_sha256':digest(rubric),'metrics':metrics}


def assess_grade_boundary(state,record,*,run_dir=trainer.RUN,scorer=None):
    """Fail closed until 29 grade-specific current scorers are approved."""
    try:
        inventory.approved_inventory(state.get('config',{}).get('grade_program') or ())
    except ValueError as error:
        return False,str(error)
    if (record.get('grade') not in state['config']['grade_program'] or
            state.get('last_run_status')!='GRADE_BOUNDARY'):
        raise ValueError('GRADUATION_NOT_DURABLE_GRADE_BOUNDARY')
    out=Path(run_dir)
    saved=engine._read(out/'state.json')
    if any(saved.get(key)!=state.get(key) for key in
           ('version','optimizer_step','checkpoint','checkpoint_sha256','last_run_status')):
        raise ValueError('GRADUATION_UNSAVED_GRADE_BOUNDARY')
    rubric=inventory.approved_inventory(saved['config']['grade_program'])
    rubric_sha=digest(rubric)
    # Repeated rejected candidates can revisit the exact same student/AdamW.
    # A prior source-bound counterexample remains conclusive at that same
    # checkpoint; only a different model or rubric needs another inference.
    if scorer is None and inventory.APPROVED_CURRENT_RUBRIC=='SOURCE_DEFINED_V15_ACQUISITION_V1':
        source_screen=saved.get('graduation_screen') or {}
        if (source_screen.get('schema')=='bilqis.v15.nonmastery-screen/v1' and
            source_screen.get('optimizer_step')==saved['optimizer_step'] and
            source_screen.get('checkpoint_sha256')==saved['checkpoint_sha256'] and
            source_screen.get('current_rubric_sha256')==rubric_sha and
            source_screen.get('failed_metric') in rubric and
            type(source_screen.get('correct')) is int and
            source_screen.get('total')==rubric[source_screen['failed_metric']]['total'] and
            0<=source_screen['correct']<source_screen['total']):
            state['graduation_screen']=source_screen
            return False,'UNMASTERED_CURRENT_METRIC:'+source_screen['failed_metric']
        prior=saved.get('mastery_completion') or {}
        if (prior.get('optimizer_step')==saved['optimizer_step'] and
            prior.get('checkpoint_sha256')==saved['checkpoint_sha256'] and
            prior.get('current_rubric_sha256')==rubric_sha and
            set(prior.get('metrics',{}))==set(rubric)):
            complete,reason=completion.completion_status(saved)
            if complete or reason.startswith('UNMASTERED_CURRENT_METRIC:'):
                return complete,reason
    # _load_student verifies checksum, graph, model, AdamW, and optimizer step.
    model,optimizer,graph=trainer._load_student(out,saved,'cpu')
    if scorer is None and inventory.APPROVED_CURRENT_RUBRIC=='SOURCE_DEFINED_V15_ACQUISITION_V1':
        scores,failed=screen_source_rubric(model,graph,rubric,
                                          previous=saved.get('mastery_completion'))
        if failed is not None:
            screen={'schema':'bilqis.v15.nonmastery-screen/v1',
                    'optimizer_step':saved['optimizer_step'],
                    'checkpoint_sha256':saved['checkpoint_sha256'],
                    'current_rubric_sha256':rubric_sha,
                    'failed_metric':failed['key'],
                    'correct':failed['correct'],'total':failed['total']}
            saved['graduation_screen']=screen
            engine._atomic_json(out/'state.json',saved)
            if engine._read(out/'state.json').get('graduation_screen')!=screen:
                raise ValueError('GRADUATION_SCREEN_READBACK_FAILED')
            state['graduation_screen']=screen
            return False,'UNMASTERED_CURRENT_METRIC:'+failed['key']
        scorer=lambda _model,_graph,key,_entry:scores[key]
    receipt=make_receipt(saved,model,optimizer,graph,scorer)
    saved['mastery_completion']=receipt
    saved.pop('graduation_screen',None)
    complete,reason=completion.completion_status(saved)
    if reason.startswith(('INVALID_','STALE_','INCOMPLETE_')):
        raise ValueError(reason)
    engine._atomic_json(out/'state.json',saved)
    readback=engine._read(out/'state.json')
    if readback.get('mastery_completion')!=receipt:
        raise ValueError('GRADUATION_RECEIPT_READBACK_FAILED')
    state['mastery_completion']=receipt
    state.pop('graduation_screen',None)
    return complete,reason


class GraduationWatch:
    def __init__(self,run_dir=trainer.RUN,scorer=None):
        self.run_dir=run_dir
        self.scorer=scorer
        self.completed=False
        self.reason='NOT_ASSESSED'

    def after_grade(self,kind,record,state):
        if kind=='grade' and not self.completed:
            self.completed,self.reason=assess_grade_boundary(
                state,record,run_dir=self.run_dir,scorer=self.scorer)

    def reporter(self,downstream=None):
        def report(kind,record,state):
            self.after_grade(kind,record,state)
            if downstream is not None:
                downstream(kind,record,state)
        return report

    def stop_requested(self,operator_stop=lambda:False):
        return self.completed or operator_stop()


def run_with_graduation(original_run,*,reporter=None,stop_requested=lambda:False,**options):
    out=Path(options.get('run_dir',trainer.RUN))
    existing=out/'state.json'
    if existing.is_file():
        prior=engine._read(existing)
        if prior.get('last_run_status')=='ALL_CURRENT_METRICS_100_PERCENT':
            raise ValueError('GOLDEN_STUDENT_FROZEN_USE_VERSIONED_DESCENDANT')
    if os.environ.get('BILQIS_GRADUATION_FORCE')=='1':
        return original_run(reporter=reporter,stop_requested=stop_requested,**options)
    watcher=GraduationWatch(run_dir=out)
    previous_visit=trainer._grade_visit
    previous_finish=trainer.local_champions.RunChampionPolicy.finish
    prechecked=[None]

    def checked_visit(*args,**kwargs):
        result=previous_visit(*args,**kwargs)
        # The trainer saves the exact FP32+AdamW grade checkpoint BEFORE this
        # hook. Check it before a complete-program champion/soup finalization.
        watcher.after_grade('grade',result[0],args[1])
        prechecked[0]=result[0]
        return result

    def preserve_golden_without_probes(policy,*args,**kwargs):
        if watcher.completed:
            # Existing run-local candidate evidence stays in the frozen run.
            # Do not score remaining contenders, compose soups or touch the
            # exact graduating student just to finish research bookkeeping.
            return {'status':'GOLDEN_PROBES_DEFERRED'}
        return previous_finish(policy,*args,**kwargs)

    def downstream(kind,record,state):
        if kind!='grade' or record is not prechecked[0]:
            watcher.after_grade(kind,record,state)
        if reporter is not None:reporter(kind,record,state)

    with patch.object(trainer,'_grade_visit',checked_visit),\
         patch.object(trainer.local_champions.RunChampionPolicy,'finish',
                      preserve_golden_without_probes):
        result=original_run(reporter=downstream,
                            stop_requested=lambda:watcher.stop_requested(stop_requested),
                            **options)
    if not watcher.completed:
        return result
    # The existing trainer finishes through its graceful grade-boundary
    # path. Commit a durable COMPLETED status *after* its final archival
    # writes, and only after a second readback of the exact student receipt.
    # An interrupted write still retains the prior complete metric receipt,
    # so subsequent launchers can safely replay the dashboard.
    saved=engine._read(out/'state.json')
    complete,reason=completion.completion_status(saved)
    verified,proof=completion.verify_complete_checkpoint(out,saved) if complete else (False,reason)
    if not complete or not verified:
        raise ValueError('GRADUATION_COMPLETION_PROOF_DRIFT:'+proof)
    saved['last_run_status']='ALL_CURRENT_METRICS_100_PERCENT'
    saved['graduation_freeze']={
        'schema':'bilqis.v15.terminal-full-state-freeze/v1',
        'checkpoint':saved['checkpoint'],
        'checkpoint_sha256':saved['checkpoint_sha256'],
        'optimizer_step':saved['optimizer_step'],
        'model_sha256':saved['mastery_completion']['model_sha256'],
        'graph_sha256':saved['mastery_completion']['graph_sha256'],
        'current_rubric_sha256':saved['mastery_completion']['current_rubric_sha256'],
        'run_local_finalization':'DEFERRED_NO_CANDIDATE_PROBES'}
    engine._atomic_json(out/'state.json',saved)
    readback=engine._read(out/'state.json')
    if (readback.get('last_run_status')!='ALL_CURRENT_METRICS_100_PERCENT'
            or readback.get('mastery_completion')!=saved['mastery_completion']
            or readback.get('checkpoint_sha256')!=saved['checkpoint_sha256']
            or readback.get('optimizer_step')!=saved['optimizer_step']):
        raise ValueError('GRADUATION_COMPLETE_STATUS_READBACK_DRIFT')
    return {**result,'status':'ALL_CURRENT_METRICS_100_PERCENT'} if isinstance(result,dict) else result


def main():
    """Retain the original dashboard and CLI through the existing run hooks."""
    original=trainer.run
    try:
        trainer.run=lambda **options:run_with_graduation(original,**options)
        return trainer.main()
    finally:
        trainer.run=original


if __name__=='__main__':
    main()
