"""One stable human-operated School50 CLI across neural training revisions.

Entrypoint is npm run train / npm run dashboard / npm run status. Revision
selection belongs here; the 6-section dashboard never changes with a model.
Only the human's explicit `train` call starts FP32/AdamW updates.
"""
from __future__ import annotations

import argparse
from datetime import datetime,timezone
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

from . import time_first_dashboard_watch as viewer


ROOT=Path(__file__).resolve().parents[1]
V15=ROOT/'runs/primitive-consolidation-v15-run-local'
V16=ROOT/'runs/primitive-consolidation-v16-triplets'


def source_run(explicit=None):
    if explicit is not None:return Path(explicit).expanduser().resolve(strict=False)
    configured=os.environ.get('BILQIS_V15_SOURCE_RUN')
    if configured:return Path(configured).expanduser().resolve(strict=False)
    if (V15/'state.json').is_file():return V15
    return (ROOT.parent/'bilqis-candidate-consolidation-v14'/'runs'/
            'primitive-consolidation-v15-run-local')


def selected_run(explicit=False):
    from . import quantum_triplet_operator_v17 as quantum
    if explicit:return quantum.RUN
    if (quantum.RUN/'state.json').is_file():return quantum.RUN
    return V16 if (V16/'state.json').is_file() else source_run()


def _verified_source_snapshot(run,state):
    """Read a real saved checkpoint without touching its student or AdamW."""
    from . import triplet_operator_v16 as runner
    from . import current_rubric_v16 as rubric
    from . import three_grade_repair_operator_v2_r1 as rescue
    from . import quantum_triplet_operator_v17 as quantum
    if Path(run)==quantum.RUN:
        quantum._verify_state(state)
        student,own_adamw,graph=quantum._load(run,state,'cpu')
        return rubric.score_snapshot(student,graph,
            optimizer_step=state['optimizer_step'],
            checkpoint_sha256=state['checkpoint_sha256'],device='cpu')
    if Path(run)==rescue.RUN:
        rescue._verify_state(state)
        student,own_adamw,graph=rescue._load(run,state,'cpu')
        return rubric.score_snapshot(student,graph,
            optimizer_step=state['optimizer_step'],
            checkpoint_sha256=state['checkpoint_sha256'],device='cpu')
    if state.get('phase')=='GOLDEN_FROZEN':
        # A terminally graduated student is deliberately rejected by the
        # trainable-state validator, but its immutable result must REMAIN
        # inspectable. Verify the same recipe without reopening training.
        runner._opt_in_authority()
        if (state.get('version')!=runner.VERSION or
                state.get('config')!=runner._frozen_configuration()):
            raise ValueError('FROZEN_GOLDEN_DASHBOARD_RECIPE_DRIFT')
    else:
        runner._assert_recipe(state)
    student,own_adamw,graph=runner._load(run,state,'cpu')
    # Loading the optimizer is verification, NOT an optimizer step. No files
    # are saved by this read-only assessment.
    return rubric.score_snapshot(student,graph,
        optimizer_step=state['optimizer_step'],
        checkpoint_sha256=state['checkpoint_sha256'],device='cpu')


def _view_state(state,snapshot):
    # An ephemeral display projection. Never append this to source state.json:
    # an already-training v16 model's frozen recipe must remain unchanged.
    return {**state,'dashboard':{'initial_snapshot':snapshot,
                                  'latest_full_snapshot':snapshot}}


def _status(args):
    from . import quantum_triplet_operator_v17 as quantum
    if args.repair_three:
        from . import three_grade_repair_operator_v2_r1 as rescue
        print(json.dumps(rescue.status(),indent=2,sort_keys=True))
    elif args.triplets or (quantum.RUN/'state.json').is_file():
        print(json.dumps(quantum.status(),indent=2,sort_keys=True))
    elif (V16/'state.json').is_file():
        from . import triplet_operator_v16 as runner
        print(json.dumps(runner.status(),indent=2,sort_keys=True))
    else:
        from . import time_first_runner_v15 as v15
        selected=source_run()
        if not (selected/'state.json').is_file():
            raise ValueError('NO_PREPARED_RUN: '+str(selected))
        print(json.dumps(v15.status(selected),indent=2,sort_keys=True,default=str))
    return 0


def _dashboard(args):
    if args.repair_three:
        from . import three_grade_repair_operator_v2_r1 as rescue
        target=rescue.RUN
    else:
        target=selected_run(args.triplets)
    if not (target/'state.json').is_file():
        raise ValueError('DASHBOARD_RUN_NOT_PREPARED: '+str(target)+
                         '; start with npm run train -- --triplets')
    from . import quantum_triplet_operator_v17 as quantum
    if target in (V16,quantum.RUN) or args.repair_three:
        from . import engine
        state=engine._read(target/'state.json')
        print('Reading the saved FP32 student for a CURRENT-source dashboard '
              'snapshot; optimizer will not be updated.',flush=True)
        snapshot=_verified_source_snapshot(target,state)
        viewer.watch(run_dir=target,follow=args.follow,
                     baseline_snapshot=snapshot)
    else:
        viewer.watch(run_dir=target,follow=args.follow)
    return 0


def _train(args):
    if args.minutes is not None and not 0<args.minutes<=1440:
        raise ValueError('SESSION_MINUTES_MUST_BE_BETWEEN_ZERO_AND_1440')
    if not args.triplets:
        if args.repair_three:
            raise ValueError('FOCUS_REPAIR_REQUIRES_TRIPLETS_FLAG')
        if args.source_run is not None or args.device!='mps':
            raise ValueError('V15_SELECTS_DEVICE_AND_SOURCE_THROUGH_ITS_FROZEN_LAUNCHER')
        if not (V15/'state.json').is_file():
            raise ValueError('V15_NOT_IN_THIS_WORKTREE: refusing an accidental '
                'second v15 lineage. Use npm run train -- --triplets for the '
                'successor, or operate the existing frozen v15 worktree directly.')
        if args.dry_run:
            print('DRY RUN: existing v15 --train-dashboard (no neural update)')
            return 0
        env=os.environ.copy()
        if args.minutes is not None:env['MINUTES']=str(args.minutes)
        return subprocess.call(['bash',str(ROOT/'scripts/primitive_consolidation_v15.sh'),
                                '--train-dashboard'],cwd=ROOT,env=env)

    from . import triplet_operator_v16 as original
    if args.repair_three:
        if args.source_run is not None:
            raise ValueError('FOCUS_REPAIR_SOURCE_IS_VERIFIED_STOPPED_V16_ONLY')
        from . import three_grade_repair_operator_v2_r1 as runner
        target=runner.RUN
    else:
        from . import quantum_triplet_operator_v17 as runner
        target=runner.RUN
        if args.source_run is not None:
            raise ValueError('QUANTUM_PARENT_CHOSEN_BY_FULL_PRE_RUN_CHECKPOINT_AUDIT')
    from . import engine
    from . import school50_operator_projection as projection
    # Pure preflight before any clone, GPU work, lock, log or machine mutation.
    original._opt_in_authority()
    source=original.RUN if args.repair_three else runner.SOURCE
    if args.dry_run:
        repair_preflight=None
        if args.repair_three and (source/'state.json').is_file():
            original._assert_recipe(engine._read(source/'state.json'))
        if args.repair_three:
            repair_preflight=runner.preflight()
        else:
            repair_preflight=runner.preflight()
        print(json.dumps({
            'result':'PREFLIGHT_ONLY_NO_TRAINING',
            'blocked_reason':None,
            'command':('npm run train -- --triplets --repair-three' if args.repair_three
                       else 'npm run train -- --triplets'),
            'dashboard':'EXISTING_SCHOOL50_SIX_SECTION_SINGLE_TERMINAL',
            'source':str(source),'source_exists':(source/'state.json').is_file(),
            'successor':str(target),
            'successor_prepared':(target/'state.json').is_file(),
            'teaching':('v2 novel-world, paired answer classes, teacher-selected '
                         'composition and depth, 1150-question rubric unchanged'
                         if args.repair_three else 'v17 easy-medium-hard G12-G14; '
                         'full source weakest-three then next remaining'),
            'repair_preflight':repair_preflight,
            'minutes':args.minutes or 90,'device':args.device},indent=2))
        return 0
    from scripts import checkpoint_custody as custody
    # Keep an emergency reserve before the human starts a new neural session.
    custody.require_headroom(ROOT)
    if not (target/'state.json').is_file():
        if args.repair_three:
            print('Preparing the NEW v2 G12/G13/G14 repair with the original '
                  'adaptive teacher, fresh semantic worlds and native FP32+AdamW. '
                  'The held v1 repair and frozen v16 run will remain unchanged.',flush=True)
            runner.prepare()
        else:
            print('Preparing isolated v17 from the audited strongest '
                  'pre-repair FP32 student and its OWN AdamW. The v16 and '
                  'v2-r1 runs remain untouched.',flush=True)
            runner.prepare()
    state=engine._read(target/'state.json')
    if state.get('phase')=='GOLDEN_FROZEN':
        print('GOLDEN FROZEN: read-only dashboard; no training is permitted.',flush=True)
        return _dashboard(args)
    runner._verify_state(state)
    # Derived custody receipts live outside the self-hashed training recipes.
    # The engine, optimizer, rubric and six-panel dashboard are unchanged.
    custody.sync_run(target)
    custody.require_headroom(target)
    print('Verifying the saved current-source assessment for the existing '
          'student. No training updates during this display preflight.',flush=True)
    snapshot=_verified_source_snapshot(target,state)

    # Stable TUI is an outer presentation boundary. It renders from *saved*
    # training receipts; failures are shown, not allowed to change admission.
    dashboard=projection.create(target,_view_state(state,snapshot),stream=sys.stdout)
    dashboard.mode='READY'
    dashboard.draw()
    if sys.platform=='darwin' and not Path('/usr/bin/caffeinate').is_file():
        raise ValueError('CAFFEINATE_UNAVAILABLE: refusing an unattended Mac training run')
    stopped={'requested':False}
    previous=signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT,lambda *_:stopped.__setitem__('requested',True))
    logs=target.with_name(target.name+'.logs')
    logs.mkdir(parents=True,exist_ok=True)
    name='operator-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+str(os.getpid())+'.jsonl'
    outfile=logs/name
    awake=None
    screen_lock=threading.RLock()
    ui_stopped=threading.Event()
    screen={'panel':dashboard}
    started=dashboard.started
    try:
        if sys.platform=='darwin':
            # Keep the Mac awake without requiring another terminal. Process
            # is tied to this operator PID, never detached for background work.
            awake=subprocess.Popen(['/usr/bin/caffeinate','-i','-w',str(os.getpid())],
                                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        with outfile.open('x',encoding='utf-8',buffering=1) as sink:
            def redraw_current(mode='RUNNING'):
                # Watch only atomic receipts. Pending candidate work is not
                # assigned a fake optimizer step or synthetic accuracy.
                current=engine._read(target/'state.json')
                panel=projection.create(target,_view_state(current,snapshot),
                                        stream=sys.stdout)
                panel.started=started
                panel.log_hint=outfile.name
                panel.mode=mode
                panel.draw()
                screen['panel']=panel

            def ticker():
                while not ui_stopped.wait(3):
                    with screen_lock:
                        try:redraw_current()
                        except Exception as error:
                            # Display degradation must not turn into another
                            # unreceipted neural training failure.
                            sink.write(json.dumps({'kind':'dashboard_warning',
                                'message':str(error)})+'\n')

            def reporter(kind,record,updated):
                nonlocal snapshot
                receipt={'time':datetime.now(timezone.utc).isoformat(),
                         'kind':kind,'step':updated['optimizer_step'],'record':record}
                sink.write(json.dumps(receipt,sort_keys=True,default=str)+'\n')
                # Every grade callback follows the runner's durable state save.
                custody.sync_run(target)
                custody.require_headroom(target)
                with screen_lock:
                    if args.repair_three:
                        # Do not project the source's previous-step 1,150-item
                        # scores onto a new checkpoint. Reread and evaluate
                        # exactly once at each durable rescue-grade boundary.
                        snapshot=_verified_source_snapshot(target,updated)
                    redraw_current('RETEST' if kind=='retest' else 'RUNNING')
            painter=threading.Thread(target=ticker,name='bilqis-dashboard-redraw',
                                     daemon=True)
            painter.start()
            try:
                minutes=args.minutes if args.minutes is not None else 90
                outcome=runner.run(device=args.device,minutes=minutes,
                    stop_requested=lambda:stopped['requested'],reporter=reporter)
                sink.write(json.dumps({'kind':'summary','record':outcome},
                                      sort_keys=True)+'\n')
            except BaseException as error:
                sink.write(json.dumps({'kind':'trainer_error',
                    'error':type(error).__name__,'message':str(error)})+'\n')
                dashboard.push('system',{'kind':'TRAINER ERROR',
                    'detail':str(error)},redraw=False)
                dashboard.mode='ERROR'
                dashboard.draw()
                raise
            finally:
                # Soup reviews and terminal-golden transitions do not always
                # invoke the grade reporter; reconcile them at operator exit.
                try:
                    custody.sync_run(target)
                except Exception as custody_error:
                    sink.write(json.dumps({'kind':'custody_reconciliation_error',
                        'message':str(custody_error)})+'\n')
                    print('Checkpoint custody reconciliation failed: '+
                          str(custody_error),file=sys.stderr,flush=True)
                ui_stopped.set()
                painter.join(timeout=5)
        terminal=engine._read(target/'state.json')
        dashboard=projection.create(target,_view_state(terminal,snapshot),stream=sys.stdout)
        dashboard.started=started
        dashboard.log_hint=outfile.name
        dashboard.mode=('GOLDEN FROZEN' if terminal['phase']=='GOLDEN_FROZEN'
                        else 'OPERATOR STOP')
        dashboard.draw()
        return 0
    finally:
        signal.signal(signal.SIGINT,previous)
        if awake is not None:
            awake.terminate()
            try:awake.wait(timeout=5)
            except subprocess.TimeoutExpired:awake.kill()


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    actions=parser.add_subparsers(dest='action',required=True)
    for name in ('train','dashboard','status'):
        action=actions.add_parser(name)
        action.add_argument('--triplets','--triples',dest='triplets',action='store_true',
                            help='Use global-weakest-three quantum v17 (alias --triples)')
        action.add_argument('--repair-three',action='store_true',
                            help='Use the separately versioned G12/G13/G14 recovery')
        if name=='train':
            action.add_argument('--device',choices=('cpu','mps'),default='mps')
            action.add_argument('--minutes',type=float)
            action.add_argument('--source-run',type=Path)
            action.add_argument('--dry-run',action='store_true')
        elif name=='dashboard':
            action.add_argument('--follow',action='store_true')
    args=parser.parse_args(argv)
    try:
        return {'train':_train,'dashboard':_dashboard,'status':_status}[args.action](args)
    except (ValueError,FileNotFoundError,PermissionError) as error:
        print(f'BILQIS OPERATOR PREFLIGHT: {error}',file=sys.stderr)
        return 2


if __name__=='__main__':
    raise SystemExit(main())
