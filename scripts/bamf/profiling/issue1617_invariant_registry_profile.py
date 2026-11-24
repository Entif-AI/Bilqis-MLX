"""Matched native ordinary-visit #1617 spike, using the pinned #1614 profiler.

Run in a detached source snapshot. Supply the existing local donor profiler and
an unused output directory next to the frozen campaign inputs. Each arm gets a
separate disposable database and checkpoint copy. Scoring is strict and fixed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


EXTRA_PROBES = '''default_registry _implementation_digest _source_contract
operator_grant_digest live_source_registry require_task_goal_lowerer
live_task_goal_lowerers a_provider_digest b_provider_digest b_composite_digest
b_idboolops_digest c_provider_digest provider_implementation_digest
_weakness_classifier_digest canonical_graph_for verify_source_row
compile_factory_evaluation_case _factory_evaluation_instrument _factory_gold
execute_dag factory_task_template _factory_task_template_from_validated
factory_evaluation_case_from_source runtime_adapter_for_release'''.split()


def donor(path, output):
    spec = importlib.util.spec_from_file_location('issue1617_donor', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = output
    module.h.ROOT = output
    module.NAMES.update(EXTRA_PROBES)
    module.CLASS_METHODS.update({'OperatorRegistry': ('resolve',),
                                 'SourceAdapterRegistry': ('resolve_owner',)})
    return module


def worker(args, d):
    import mlx.core as mx
    import bilqis_mlx
    from scripts.bamf.profiling.issue1566_teacher_yield_witness import _seed_cadence_projection, _dashboard
    from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
    from bilqis_mlx.presentation.operator_cli.bamf_resume_dispatch import _live_bamf_dashboard_refresh
    from bilqis_mlx.runtime.bamf_operator import session
    from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
    from scripts.bamf.profiling.issue1617_invariant_registry_scope import install_scope

    h = d.h
    folder = args.output / args.worker
    run, plane = folder / 'run', folder / 'plane.sqlite3'
    h.require(Path(bilqis_mlx.__file__).resolve().is_relative_to(Path.cwd().resolve()), 'wrong source snapshot')
    h.require(Path(os.environ['BILQIS_DATA_PLANE']).resolve() == plane.resolve(), 'wrong plane')
    h.require(run.resolve() != (args.output.parent / 'aspirant').resolve(), 'sovereign run prohibited')
    mx.set_memory_limit(24 * 1024**3)
    mx.set_cache_limit(0)
    _seed_cadence_projection(run, plane, h.projection())
    parent = load_accepted_generation(run)
    h.require(parent.generation == 51 and parent.retained_state.optimizer_step == 509, 'initial learner drift')
    del parent
    board, draws = _dashboard(run)
    offset = (run / 'events.jsonl').stat().st_size
    recorder = d.Recorder()
    probes = recorder.install()
    # Both arms use the unchanged production physical/logical batch settings.
    counts = install_scope() if args.worker == 'prepared' else {}
    print('ARM_START', args.worker, len(probes), 'probes', flush=True)
    started = time.monotonic()
    with _live_bamf_dashboard_refresh(board):
        result = session.operate_bamf(run, minutes=5, max_visits=3, steps_per_visit=12,
            batch_size=32, reserve_gib=100.0, source_prefetch_workers=2,
            strict_mode=False, progress=lambda msg: print(args.worker, msg, flush=True))
    mx.synchronize()
    elapsed = time.monotonic() - started
    peak = mx.get_peak_memory()
    attempts = []
    with (run / 'events.jsonl').open('rb') as stream:
        stream.seek(offset)
        for line in stream:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if event.get('event') not in ('BAMF_C16_3_ACCEPTED', 'BAMF_CANDIDATE_REJECTED'):
                continue
            evidence = event.get('evidence', event)
            how = evidence.get('how_outcome', {})
            attempts.append({'capability': evidence.get('capability'),
                             'steps': how.get('attempted_steps', 0),
                             'retained': how.get('retained_steps', 0),
                             'reason': how.get('decision', {}).get('reason')})
    steps = sum(x['steps'] for x in attempts)
    report = {'wall_seconds': elapsed, 'peak_mlx_bytes': peak,
              'attempts': attempts, 'attempted_steps': steps,
              'steps_per_minute': steps * 60 / elapsed,
              'completed_trials_per_hour': len(attempts) * 3600 / elapsed,
              'status': str(result.status), 'visits': result.visits,
              'accepted': result.accepted, 'rejected': result.rejected,
              'generation': result.generation, 'optimizer_step': result.optimizer_step,
              'dashboard_draws': draws, 'probes': probes, 'threads': recorder.threads,
              'scope_counts': dict(counts), 'initial_manifest': h.BASE_MANIFEST}
    h.write(folder / 'profile.json', report)
    h.require(steps == 36 and len(attempts) == 3, 'incomplete matched campaign')
    if args.worker == 'prepared':
        h.require(counts['operator_registry_hit'] > 0, 'no actual operator reuse')
    print('TRAINING_COMPLETE', args.worker, json.dumps({k: v for k, v in report.items() if k not in ('threads', 'probes')}), flush=True)
    mx.clear_cache()
    with evidence_mode(strict=True):
        report['exam'] = h.score(run)
    report['exam_cohort'] = h.COHORT
    report['competence_gain_per_hour'] = (report['exam']['correct'] - 44) * 3600 / elapsed
    h.write(folder / 'result.json', report)
    h.require(h.read(h.BASE / 'bamf-state.json')['manifest_sha256'] == h.BASE_MANIFEST, 'frozen source mutated')
    print('ARM_COMPLETE', args.worker, json.dumps(report['exam']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--donor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--worker', choices=('baseline', 'prepared'))
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--baseline-result', type=Path,
                        help='Reuse a completed matched baseline result without rerunning it')
    args = parser.parse_args()
    args.output = args.output.resolve()
    d = donor(args.donor, args.output)
    if args.worker:
        worker(args, d)
        return
    d.h.preflight()
    arms = ('baseline', 'prepared')
    if args.baseline_result is not None:
        baseline = d.h.read(args.baseline_result)
        d.h.require(baseline['initial_manifest'] == d.h.BASE_MANIFEST
                    and baseline['exam_cohort'] == d.h.COHORT
                    and baseline['attempted_steps'] == 36
                    and baseline['visits'] == 3
                    and len(baseline['attempts']) == 3
                    and baseline['status'] == 'VISIT_LIMIT'
                    and baseline['scope_counts'] == {}, 'invalid completed baseline')
        destination = args.output / 'baseline'
        destination.mkdir()
        d.h.write(destination / 'result.json', baseline)
        print('PRESERVED_COMPLETED_BASELINE', args.baseline_result, flush=True)
        arms = ('prepared',)
    for arm in arms:
        if not (args.output / arm).exists():
            d.h.clone(arm)
        d.h.require(d.h.read(args.output / arm / 'run' / 'bamf-state.json')['manifest_sha256'] == d.h.BASE_MANIFEST, 'arm is not pristine')
    if args.prepare_only:
        print('BOTH_ARMS_PRISTINE', flush=True)
        return
    for arm in arms:
        env = dict(os.environ, PYTHONPATH=str(Path.cwd().resolve()),
                   BILQIS_DATA_PLANE=str(args.output / arm / 'plane.sqlite3'))
        subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()),
                        '--donor', str(args.donor), '--output', str(args.output),
                        '--worker', arm], env=env, check=True)
    left, right = (d.h.read(args.output / arm / 'result.json') for arm in ('baseline', 'prepared'))
    comparison = {'equal_visit_outcomes': left['attempts'] == right['attempts'],
                  'equal_fixed_exam': left['exam'] == right['exam'],
                  'wall_speedup': left['wall_seconds'] / right['wall_seconds'],
                  'baseline': {k: v for k, v in left.items() if k not in ('threads', 'probes')},
                  'prepared': {k: v for k, v in right.items() if k not in ('threads', 'probes')}}
    d.h.write(args.output / 'comparison.json', comparison)
    print('MATCHED_COMPARISON', json.dumps(comparison), flush=True)
    d.h.require(comparison['equal_visit_outcomes'] and comparison['equal_fixed_exam'], 'matched outcome drift')


if __name__ == '__main__':
    main()
