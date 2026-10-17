"""Read-only wide School50 v14 dashboard, reusing the v11 renderer.

The running trainer owns its neural state and its terminal. This companion
never opens a writer lock, imports the neural runner, or changes a checkpoint.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from .spiral_dashboard import Dashboard
from . import school50_progress as progress


ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/primitive-consolidation-v14-acquisition-first'


def _candidate(trial,grade):
    earlier=trial.get('bridge_before') or {}
    later=trial.get('bridge_after') or {}
    confirmation=trial.get('confirmation') or {}
    return {
        'grade':trial.get('grade',grade['grade']),
        'attempt':trial['attempt'],
        'policy_id':trial.get('policy_id','-'),
        'instruction_method':trial.get('instruction_method'),
        'bridge_before':earlier.get('primary'),
        'bridge_after':later.get('primary'),
        'bridge_confirm_before':earlier.get('confirm'),
        'bridge_confirm_after':later.get('confirm'),
        'old_before':trial.get('old_before') or
                     confirmation.get('before_scores') or grade.get('old_before'),
        'old_after':trial.get('old_after') or
                    confirmation.get('after_scores') or grade.get('old_after'),
        'teacher_credit':trial.get('teacher_credit'),
        'reward':trial.get('raw_reward'),
        'loss_last':trial.get('last_loss'),
        'allocation':trial.get('row_exposures'),
        'decision':'SELECT' if trial.get('selected') else trial.get('decision','-'),
        'reason':trial.get('reason','-'),
    }


def _numeric_score(numbers,arm):
    return sum(numbers.get(fold,{}).get(arm,{}).get('correct',0)
               for fold in ('primary','confirm'))


class LogView:
    """Reconstruct only observable rows from an append-only v11 JSONL log."""
    def __init__(self,dashboard,program):
        self.dashboard=dashboard
        self.program=tuple(program)
        self.pending=None
        self.trials=[]

    def _complete_grade(self):
        record=self.pending
        if record is None:return
        if len(self.trials)!=record['attempts']:
            # Do not invent missing attempts during an incomplete log append.
            return
        current=self.program.index(record['grade'])
        next_index=(current+1)%len(self.program)
        prefix=record['pass']+(next_index==0)
        state=self.dashboard.state
        state.update(phase='ACQUISITION',next=self.program[next_index],
                     prefix=prefix,failures='-',max_failures='-',
                     step=record['optimizer_step'],visits=record['visit'],
                     teacher=record['teacher_events'],stop='RUNNING')
        for trial in self.trials:
            self.dashboard.push('candidate',_candidate(trial,record),redraw=False)
        if self.dashboard.progress is not None:
            self.dashboard.progress.observe_grade(record)
        score=progress.grade_accuracy(record)
        self.dashboard.push('grade',{
            'grade_visit':record['visit'],'grade':record['grade'],
            'step':record['optimizer_step'],
            'eligible':sum(trial['decision'] in ('PROMOTE','ELIGIBLE')
                           for trial in self.trials),
            'selected':record['updates']>0,'prefix':prefix,
            'outcome':record['disposition'],'accuracy':score,
            'next':self.program[next_index]},
            redraw=False)
        if record['grade'].startswith('B'):
            earlier=record.get('basic_numeric_before') or {}
            later=record.get('basic_numeric_after') or {}
            self.dashboard.push('system',{
                'kind':'B BASIC REPLAY','grade':record['grade'],
                'detail':(f"4-way {_numeric_score(earlier,'four_way')}/4 > "
                          f"{_numeric_score(later,'four_way')}/4; 101-way "
                          f"{_numeric_score(earlier,'full_101')}/4 > "
                          f"{_numeric_score(later,'full_101')}/4; EXPOSED")},
                redraw=False)
        self.pending=None
        self.trials=[]

    def feed(self,event):
        kind=event.get('kind')
        record=event.get('record') or {}
        if kind=='grade':
            self._complete_grade()
            if self.pending is not None:
                raise ValueError('WATCH_INCOMPLETE_GRADE_LOG')
            self.pending=record
            self.trials=[]
            if record.get('attempts')==0:self._complete_grade()
        elif kind=='candidate_attempt':
            if self.pending is None or record.get('grade')!=self.pending.get('grade'):
                raise ValueError('WATCH_CANDIDATE_NOT_FOR_CURRENT_GRADE')
            self.trials.append(record)
            self._complete_grade()
        elif kind=='pass':
            self._complete_grade()
            if self.dashboard.progress is not None:
                self.dashboard.progress.observe_pass(record)
            self.dashboard.push('system',{
                'kind':'FULL PASS',
                'detail':(f"{record['pass']}: old {100*record['old_mean']:.2f}% "
                          f"bridge {record['bridge_correct']}/84 "
                          f"{record['disposition']}")},redraw=False)
            self.dashboard.push('system',{'kind':'B REPLAY SCORE',
                'detail':(f"arithmetic {record['basic_numeric_four_way_correct']}/4 "
                          f"four-way, {record['basic_numeric_full_101_correct']}/4 "
                          f"full-101; bridge {record['bridge_correct']}/84 EXPOSED")},
                redraw=False)
            for group in (('G03','G11','G12'),('G19','G20','G22')):
                self.dashboard.push('system',{'kind':'G PREREQUISITES',
                    'detail':' '.join(f"{g} {100*record['prerequisite_grades'][g]:.0f}%"
                                       for g in group)},redraw=False)
            joint=record.get('joint_tracking') or {}
            best=joint.get('best_joint')
            if best:
                self.dashboard.push('system',{'kind':'B/G JOINT FRONTIER',
                    'detail':(f"peak {best['bridge_correct']}/84, "
                              f"{best['bridge_contrasts']} contrasts, "
                              f"old {100*best['old_mean']:.2f}%, "
                              f"pass {best['pass']}; "
                              f"nondominated {len(joint.get('nondominated',[]))}")},
                    redraw=False)
            debt=', '.join(
                (f"{item['grade']} -{item['lost_questions']}/24" if
                 item['kind']=='HISTORICAL_GRADE_REGRESSION' else
                 f"MEAN < {100*item['minimum']:.2f}%")
                for item in record.get('rollback_triggers',[])) or 'none'
            self.dashboard.push('system',{'kind':'V8 RETENTION',
                'detail':f"would-rollback: {debt}; student+AdamW carried"},
                redraw=False)
        elif kind=='summary':
            self.dashboard.mode='FINISHED'
            self.dashboard.state['stop']=(record.get('last_session') or {}).get(
                'stop_reason',record.get('status','FINISHED'))
        elif kind=='trainer_error':
            self.dashboard.mode='ERROR'
            self.dashboard.push('system',{'kind':'TRAINER ERROR',
                'detail':record.get('message','unknown')},redraw=False)


def _start_time(path):
    try:
        stamp=path.name.split('acquisition-',1)[1].split('.jsonl',1)[0]
        timestamp=stamp.split('-',1)[0]
        return datetime.strptime(timestamp,'%Y%m%dT%H%M%SZ').replace(
            tzinfo=timezone.utc).timestamp()
    except (ValueError,IndexError):
        return time.time()


def watch(*,run_dir=RUN,log_file=None,follow=False,stream=None,poll_seconds=.5,
          title=None,baseline_snapshot=None):
    """Read source JSONL and show a separate TTY; never open the run for writes."""
    run_dir=Path(run_dir).expanduser()
    state=json.loads((run_dir/'state.json').read_text(encoding='utf-8'))
    if state.get('mode')=='--triplets':
        return _watch_current_triplets(run_dir,state,follow=follow,
                                      stream=stream or sys.stdout,
                                      poll_seconds=poll_seconds,
                                      baseline_snapshot=baseline_snapshot)
    if log_file is None:
        logs=sorted(run_dir.with_name(run_dir.name+'.logs').glob('acquisition-*.jsonl'))
        log_file=logs[-1] if logs else None
    log_file=Path(log_file).expanduser() if log_file is not None else None
    program=state['config']['grade_program']
    # Display identity follows the run receipt, never a copy of its trainer.
    # A new grade curriculum must not require a new watcher implementation.
    if title is None:
        version=str(state.get('version','')).rsplit('/',1)[-1].upper()
        label=version if version.startswith('V') and version[1:].isdigit() else ''
        title=f'BILQIS / SCHOOL50 {label} WATCH'.replace('  ',' ')
    legacy=False
    if log_file is None:
        legacy=True
    else:
        with log_file.open('r',encoding='utf-8') as probe:
            first=probe.readline().strip()
        legacy=bool(first and not first.startswith('{'))
    dashboard=Dashboard(stream=stream or sys.stdout,clock=time.time,redraw=False,
                        title=title)
    dashboard.started=_start_time(log_file) if log_file else time.time()
    dashboard.log_hint=(log_file.name+' (read-only)' if log_file
                        else 'STATE ONLY: no session JSONL yet')
    dashboard.state={
        'phase':state['phase'],'next':program[state['grade_index']],
        'prefix':state['passes_completed']+1,'failures':'-','max_failures':'-',
        'step':state['optimizer_step'],'visits':state['visits'],
        'teacher':state['teacher']['events'],'stop':state['last_run_status']}
    # A watcher can attach halfway through a session. Read its first durable
    # grade visit and reconstruct exactly which probes were known at startup.
    start_visit=state.get('visits',0)
    if not legacy:
        with log_file.open('r',encoding='utf-8') as probe:
            for line in probe:
                if not line.endswith('\n'):break
                event=json.loads(line)
                if event.get('kind')=='grade':
                    start_visit=event['record']['visit']-1
                    break
    dashboard.attach_school50(run_dir,cutoff_visit=start_visit,state=state)
    dashboard.push('system',{'kind':'READ-ONLY VIEW',
        'detail':'Independent monitor; training continues in its original TTY'},
        redraw=False)
    if legacy:
        # The inherited v14 --train launcher wrote plain text into *.jsonl.
        # That file cannot be promoted to a fabricated structured run log.
        # Show the actual persisted grade/candidate receipts instead.
        dashboard.mode=('READY' if str(state.get('last_run_status','')).startswith('READY')
                        else 'SNAPSHOT')
        dashboard.push('system',{'kind':'LEGACY LOG FORMAT',
            'detail':'State-derived history only; new --train-dashboard writes structured JSONL'},
            redraw=False)
        for trial in state.get('candidate_ledger',[])[-40:]:
            dashboard.push('candidate',_candidate(trial,{'grade':trial['grade']}),
                           redraw=False)
        for record in state.get('grade_ledger',[])[-29:]:
            dashboard.push('grade',{
                'grade_visit':record['visit'],'grade':record['grade'],
                'step':record['optimizer_step'],'eligible':0,
                'selected':record['updates']>0,'prefix':record['pass'],
                'outcome':record['disposition'],
                'accuracy':progress.grade_accuracy(record),
                'next':program[record['visit']%len(program)]},redraw=False)
        dashboard.draw()
        return dashboard
    view=LogView(dashboard,program)
    with log_file.open('r',encoding='utf-8') as source:
        def consume():
            offset=source.tell()
            line=source.readline()
            if not line:return False
            if not line.endswith('\n'):
                source.seek(offset)
                return False
            view.feed(json.loads(line))
            return True
        while consume():pass
        dashboard.draw()
        if follow:
            last_redraw=time.monotonic()
            try:
                while True:
                    if consume():
                        dashboard.draw()
                        last_redraw=time.monotonic()
                    else:
                        if time.monotonic()-last_redraw>=2:
                            dashboard.draw()
                            last_redraw=time.monotonic()
                        time.sleep(poll_seconds)
            except KeyboardInterrupt:
                # Ctrl-C here affects only this viewer, never the trainer.
                pass
    return dashboard


def _watch_current_triplets(run_dir,state,*,follow,stream,poll_seconds,
                           baseline_snapshot=None):
    """The SAME watcher and renderer; v16 contributes only a data adapter."""
    from . import school50_operator_projection as projection
    path=run_dir/'state.json'
    signature=None
    dashboard=None
    try:
        while True:
            stamp=path.stat()
            current=(stamp.st_mtime_ns,stamp.st_size)
            if current!=signature:
                signature=current
                state=json.loads(path.read_text(encoding='utf-8'))
                if baseline_snapshot is not None:
                    state={**state,'dashboard':{
                        'initial_snapshot':baseline_snapshot,
                        'latest_full_snapshot':baseline_snapshot}}
                dashboard=projection.create(run_dir,state,stream=stream,
                    title='BILQIS / SCHOOL50 V16 WATCH')
                dashboard.draw()
            if not follow or state.get('phase')=='GOLDEN_FROZEN':
                break
            time.sleep(poll_seconds)
    except KeyboardInterrupt:
        # The watcher never shares the neural writer lock, nor controls the
        # parent training process's signal handler.
        pass
    return dashboard


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-dir',type=Path,default=RUN)
    parser.add_argument('--log-file',type=Path)
    parser.add_argument('--follow',action='store_true',
                        help='Poll the active log until Ctrl-C (viewer only)')
    args=parser.parse_args()
    watch(run_dir=args.run_dir,log_file=args.log_file,follow=args.follow)


if __name__=='__main__':
    main()
