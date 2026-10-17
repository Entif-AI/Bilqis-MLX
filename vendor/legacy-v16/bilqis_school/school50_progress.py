"""Read-only School50 progress from existing fixed-panel evaluation receipts.

G is the mean of the 24-question historical grades, B is the mean of the
12-question exposed bridge grades, and N is the four-way score on four taught
arithmetic answers. ALL is the equal-weight mean of these three domains.

Between full-pass reports the grades are not evaluated at the same optimizer
step. Such values must be called latest *observed*, never a contemporaneous
whole-school examination or proof of unseen-expression transfer.
"""
from __future__ import annotations

from copy import deepcopy


GROUPS=('G','B','N')


def _ratio(correct,total):
    if (not isinstance(correct,(int,float)) or isinstance(correct,bool) or
            not isinstance(total,(int,float)) or total<=0 or
            not 0<=correct<=total):
        return None
    return correct/total


def _bridge(folds):
    if not isinstance(folds,dict):return None
    parts=[folds.get(name) for name in ('primary','confirm')]
    if any(not isinstance(part,dict) for part in parts):return None
    if any('correct' not in part or 'questions' not in part for part in parts):
        return None
    return _ratio(sum(part['correct'] for part in parts),
                  sum(part['questions'] for part in parts))


def _numeric(folds):
    if not isinstance(folds,dict):return None
    parts=[(folds.get(name) or {}).get('four_way') for name in ('primary','confirm')]
    if any(not isinstance(part,dict) for part in parts):return None
    if any('correct' not in part or 'questions' not in part for part in parts):
        return None
    return _ratio(sum(part['correct'] for part in parts),
                  sum(part['questions'] for part in parts))


def grade_accuracy(record):
    """Displayed percentage for the just-completed grade's *own* panel."""
    grade=record.get('grade','')
    outcome=record.get('development_after')
    if grade.startswith('B'):
        value=_bridge(outcome)
    elif grade.startswith('G') and isinstance(outcome,(int,float)):
        value=_ratio(outcome,1)
    else:
        value=None
    return round(value*100,1) if value is not None else None


class Progress:
    """Session-fixed start and evolving last-observed grade measurements."""
    def __init__(self,old,bridges,numeric,*,source_visit=0,source_pass=None):
        self.current={
            'G':{grade:score for grade,score in (old or {}).items()
                 if grade.startswith('G') and _ratio(score,1) is not None},
            'B':{grade:score for grade,folds in (bridges or {}).items()
                 if grade.startswith('B')
                 for score in (_bridge(folds),) if score is not None},
            'N':{'N-direct-4':score for score in (_numeric(numeric),)
                 if score is not None}}
        self.start=deepcopy(self.current)
        self.source_visit=source_visit
        self.latest_visit=source_visit
        self.last_full_pass=source_pass

    def freeze_start(self):
        self.start=deepcopy(self.current)
        self.source_visit=self.latest_visit

    @staticmethod
    def _means(groups):
        result={}
        for group in GROUPS:
            scores=groups.get(group,{})
            result[group]=sum(scores.values())/len(scores)*100 if scores else None
        if all(result[g] is not None for g in GROUPS):
            result['ALL']=sum(result[g] for g in GROUPS)/len(GROUPS)
        else:
            result['ALL']=None
        return result

    def start_means(self):
        return self._means(self.start)

    def current_means(self):
        return self._means(self.current)

    def remaining_to_perfect(self):
        """Misses in the entire known 528 G + 84 B + 4 N question suite.

        No whole-suite gap is reported if even one component is unavailable.
        """
        if (len(self.current['G'])!=22 or len(self.current['B'])!=7 or
                len(self.current['N'])!=1):return None
        wrong={'G':sum(24-round(score*24) for score in self.current['G'].values()),
               'B':sum(12-round(score*12) for score in self.current['B'].values()),
               'N':sum(4-round(score*4) for score in self.current['N'].values())}
        wrong['total']=sum(wrong.values())
        return wrong

    def summary(self,label):
        means=self.start_means() if label=='START' else self.current_means()
        return label+' '+' '.join(
            f'{group} {means[group]:.1f}%' if means[group] is not None
            else f'{group} -' for group in (*GROUPS,'ALL'))

    def observe_grade(self,record):
        """Take only exact measurements recorded after candidate selection."""
        grade=record.get('grade','')
        visit=record.get('visit') or record.get('grade_visit')
        if isinstance(visit,int):self.latest_visit=max(self.latest_visit,visit)
        if grade.startswith('B'):
            score=_bridge(record.get('development_after'))
            if score is not None:self.current['B'][grade]=score
            number=_numeric(record.get('basic_numeric_after'))
            if number is not None:self.current['N']['N-direct-4']=number
        elif grade.startswith('G'):
            score=record.get('development_after')
            if _ratio(score,1) is not None:self.current['G'][grade]=score
        # G candidates evaluate all 22 grades. B visits probe only G09/G10,
        # which is why progress between complete passes has mixed probe ages.
        for key,value in (record.get('old_after') or {}).items():
            if key.startswith('G') and _ratio(value,1) is not None:
                self.current['G'][key]=value

    def observe_pass(self,report):
        """Replace the mixed-age cache with a simultaneous complete panel."""
        old=report.get('old_scores')
        bridges=report.get('bridge')
        numeric=report.get('basic_numeric')
        if not isinstance(old,dict) or not isinstance(bridges,dict):return
        scores={'G':{},'B':{},'N':{}}
        for key,value in old.items():
            if key.startswith('G') and _ratio(value,1) is not None:
                scores['G'][key]=value
        for key,folds in bridges.items():
            ratio=_bridge(folds)
            if key.startswith('B') and ratio is not None:scores['B'][key]=ratio
        ratio=_numeric(numeric)
        if ratio is not None:scores['N']['N-direct-4']=ratio
        if all(scores[group] for group in GROUPS):
            self.current=scores
            self.last_full_pass=report.get('pass')


class CurrentAcquisitionProgress(Progress):
    """V16 source scores, keeping the established G/B/N/ALL instrument panel.

    The twelve B01 numeric items supply N, but count exactly once in TO100.
    Intermediate grade visits are last observed, not a golden examination.
    """
    def __init__(self,snapshot,program):
        self.program=tuple(program)
        self.metrics={}
        self.total_by_metric={}
        self.question_count=0
        self.provenance_note=('current source probes; grades may be at different '
                              'steps; N is the B01 numeric subset')
        self.observed_steps={}
        self.latest_full_step=snapshot['optimizer_step']
        self.latest_visit=0
        self.last_full_pass=None
        self.source_visit=0
        self.current={'G':{},'B':{},'N':{}}
        self._adopt_full(snapshot,initialize=True)
        self.start=deepcopy(self.current)

    def _grade_scores(self):
        grouped={}
        for key,correct in self.metrics.items():
            grade=key.split(':',1)[0]
            pair=grouped.setdefault(grade,[0,0])
            pair[0]+=correct
            pair[1]+=self.total_by_metric[key]
        for grade in self.program:
            if grade in grouped:
                correct,total=grouped[grade]
                self.current[grade[0]][grade]=correct/total
        key='B01:NUMERIC_0_3'
        if key in self.metrics:
            self.current['N']['N-direct-0-3']=self.metrics[key]/self.total_by_metric[key]

    def _adopt_full(self,snapshot,*,initialize=False):
        actual=snapshot.get('metrics') or {}
        if not actual or any(type(item.get('correct')) is not int or
                             type(item.get('total')) is not int or
                             item['total']<=0 or
                             not 0<=item['correct']<=item['total'] or
                             item.get('optimizer_step')!=snapshot['optimizer_step'] or
                             item.get('checkpoint_sha256')!=snapshot['checkpoint_sha256']
                             for item in actual.values()):
            raise ValueError('DASHBOARD_CURRENT_SNAPSHOT_INVALID')
        if not initialize and (set(actual)!=set(self.metrics) or
                               any(actual[key]['total']!=self.total_by_metric[key]
                                   for key in actual)):
            raise ValueError('DASHBOARD_CURRENT_RUBRIC_CHANGED')
        self.metrics={key:item['correct'] for key,item in actual.items()}
        self.total_by_metric={key:item['total'] for key,item in actual.items()}
        self.question_count=sum(self.total_by_metric.values())
        self.latest_full_step=snapshot['optimizer_step']
        self.observed_steps={grade:snapshot['optimizer_step'] for grade in self.program}
        self._grade_scores()

    def observe_snapshot(self,snapshot):
        if snapshot['optimizer_step']<self.latest_full_step:
            raise ValueError('DASHBOARD_CURRENT_SNAPSHOT_TIME_TRAVEL')
        self._adopt_full(snapshot)

    def observe_grade(self,record):
        grade=record.get('grade')
        if grade not in self.program:return
        values=record.get('current_after') or {}
        if (not values or set(values)!=set(k for k in self.metrics
                                           if k.startswith(grade+':'))):
            return
        if any(type(value) is not int or not 0<=value<=self.total_by_metric[key]
               for key,value in values.items()):
            raise ValueError('DASHBOARD_CURRENT_GRADE_BAD_SCORE')
        self.metrics.update(values)
        self.observed_steps[grade]=record.get('optimizer_step')
        self.latest_visit=max(self.latest_visit,record.get('visit',0))
        self._grade_scores()

    def remaining_to_perfect(self):
        if not self.metrics:return None
        wrong={'G':0,'B':0,'N':0}
        for key,correct in self.metrics.items():
            grade=key.split(':',1)[0]
            group='N' if key=='B01:NUMERIC_0_3' else grade[0]
            wrong[group]+=self.total_by_metric[key]-correct
        wrong['total']=sum(wrong.values())
        return wrong


def from_run_state(state,*,cutoff_visit):
    """Reconstruct exact as-of-session-start scores without checkpoint access.

    The base is the verified pass-11 whole-panel record. After that, apply
    saved grade visits and synchronized pass reports only through cutoff_visit.
    This works for a fresh v11 launch and a later manually resumed session.
    """
    if state.get('mode')=='--triplets':
        dashboard=state.get('dashboard') or {}
        initial=dashboard.get('initial_snapshot')
        if not initial:return Progress(None,None,None)
        # A separately versioned acquisition continuation may use a
        # smaller scheduling queue while retaining the unchanged complete
        # 29-grade syllabus. The display still owns the full program.
        program=(state.get('triplets',{}).get('eligible_program') or
                 state.get('config',{}).get('grade_program') or [])
        result=CurrentAcquisitionProgress(initial,program)
        newest=dashboard.get('latest_full_snapshot')
        if newest and newest['optimizer_step']>initial['optimizer_step']:
            result.observe_snapshot(newest)
        for record in state.get('grade_ledger',[]):
            if (record.get('visit',0)<=cutoff_visit and
                    record.get('optimizer_step',0)>result.latest_full_step):
                result.observe_grade(record)
        result.latest_visit=min(cutoff_visit,state.get('visits',0))
        return result
    carry=state.get('carry_forward') or {}
    source=state.get('carry_origin') or {}
    initial_visit=source.get('visits',0)
    result=Progress(carry.get('window_start_old_scores'),
                    carry.get('window_start_bridge'),state.get('numeric_start'),
                    source_visit=initial_visit,
                    source_pass=carry.get('start_passes_completed'))
    reports={report['pass']:report for report in state.get('pass_ledger',[])
             if isinstance(report.get('pass'),int) and
             report['pass']>carry.get('start_passes_completed',0)}
    for record in state.get('grade_ledger',[]):
        visit=record.get('visit',0)
        if not initial_visit<visit<=cutoff_visit:continue
        result.observe_grade(record)
        if record.get('grade')=='G22' and record.get('pass') in reports:
            result.observe_pass(reports[record['pass']])
    result.freeze_start()
    return result
