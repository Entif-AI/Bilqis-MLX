"""Independent post-budget evaluation of a retained qualification checkpoint."""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
from pathlib import Path
import time

from .qualification_manifest import require, QualificationStatus
from ..learning.teacher_observations import MeasurementStatus
from .state import _fingerprint, _durable_json

RESULT_SCHEMA = 'bilqis.factory.learning-qualification-result/v1'


def specimen_key(row):
    """Seed-specific IDs cannot conceal exact repeated model inputs and labels."""
    return _fingerprint({k: row.get(k) for k in ('capability', 'tokens', 'gold', 'answer_kind')})


def scores(rows, guesses):
    totals, correct = Counter(), Counter()
    for row in rows:
        capability = row['capability']
        totals[capability] += 1
        correct[capability] += guesses[row['id']] == row['gold']
    return {cap: {'correct': correct[cap], 'total': total} for cap, total in totals.items()}


def meets_criterion(score, capabilities, criterion, *, acquisition=False):
    if not capabilities or any(cap not in score or score[cap]['total'] <= 0 for cap in capabilities):
        return False
    mean = sum(Fraction(score[cap]['correct'], score[cap]['total']) for cap in capabilities) / len(capabilities)
    floor = Fraction(criterion['numerator'], criterion['denominator'])
    return mean > floor if acquisition else mean >= floor


def _fresh_rows(prepared, source, seed, seen, registry):
    from ..factory.generation import draw_executable_release_rows
    result = []
    for cap in prepared.release.execution_plan.capabilities:
        selected = {}
        for round_index in range(prepared.manifest['evaluation']['fresh_draw_rounds']):
            rows = draw_executable_release_rows(source, prepared.graph, prepared.release, registry,
                seed=int(_fingerprint([seed, cap.capability_id, round_index])[:16], 16),
                capability=cap.capability_id)
            for row in rows:
                key = specimen_key(row)
                if key not in seen:
                    selected.setdefault(key, row)
            if len(selected) >= cap.exam_item_count:
                break
        result.extend(list(selected.values())[:cap.exam_item_count])
    return result


def evaluate_finished_arm(prepared):
    """Inference only; this function never changes a learner or credits a teacher."""
    from ..state_dag import read_current
    from ..source_adapters.school import live_source_registry
    from ..factory.schedule import schedule_program_from_executable_release
    from ..curriculum.scheduler import assessment_capabilities
    from .mlx_checkpoint import load_semantically_bound_bundle
    from .teacher_observation_replay import read_committed_observations
    from ..learning.teacher_observations import summarize_observations
    import mlx.core as mx
    started = time.monotonic()
    root = Path(prepared.arm['run_dir'])
    receipt = read_current(root)
    require(receipt['qualification']['manifest_sha256'] == prepared.manifest['digest'], 'RESULT_MANIFEST')
    release, graph = prepared.release, prepared.graph
    program = schedule_program_from_executable_release(release)
    from .state import _state_from_json
    school = _state_from_json(receipt['school'], program)
    observations = read_committed_observations(root)
    result = {'schema': RESULT_SCHEMA, 'manifest_sha256': prepared.manifest['digest'],
        'arm': prepared.arm['id'], 'checkpoint': receipt['school']['current_student'],
        'observations': summarize_observations(observations), 'status': QualificationStatus.NOT_QUALIFIED,
        'reason': 'ACQUISITION_NOT_DEMONSTRATED', 'sweeps': [], 'evaluation_optimizer_updates': 0}
    full_scope = tuple(c.capability_id for c in release.execution_plan.capabilities)
    if set(assessment_capabilities(program, school)) == set(full_scope):
        parameters, optimizer, _, bound_graph = load_semantically_bound_bundle(root/receipt['model_bundle'])
        require(_fingerprint(bound_graph) == _fingerprint(graph), 'RESULT_GRAPH')
        before_step = int(optimizer.state['step'].item())
        result = _evaluate_sweeps(prepared, receipt, result, parameters, observations, live_source_registry(), mx)
        require(int(optimizer.state['step'].item()) == before_step, 'EVALUATION_OPTIMIZER_MUTATION')
    else:
        result['reason'] = 'FULL_WORKLOAD_NOT_YET_INTRODUCED'
    result['evaluation_wall_seconds'] = time.monotonic() - started
    result['device_memory_peak'] = {'status': MeasurementStatus.NOT_MEASURED}
    _durable_json(root/'qualification-result.json', result)
    return result


def _verify_cohort(prepared, cohort):
    if prepared.evaluation_fixture is not None:
        expected = prepared.evaluation_fixture['cohorts'].get(str(cohort.seed))
        require(expected is not None and expected['cohort_sha256'] == cohort.digest, 'EVALUATION_FIXTURE_DRIFT')


def _evaluate_sweeps(prepared, receipt, result, parameters, observations, registry, mx):
    from .assessment import _draw_executable_scope_cohort
    from ..learning.student_ops import _predictions
    evaluation = prepared.manifest['evaluation']
    source = Path(prepared.manifest['source']['root'])
    full_scope = tuple(c.capability_id for c in prepared.release.execution_plan.capabilities)
    target = prepared.manifest['workload']['grades'][evaluation['target_grade']]
    cohort, _ = _draw_executable_scope_cohort(source, prepared.graph, prepared.release, registry,
        capabilities=full_scope, seed=evaluation['acquisition_seed'])
    _verify_cohort(prepared, cohort)
    acquisition = scores(cohort.rows, _predictions(mx, parameters, list(cohort.rows), receipt['config'], receipt['answer_ids']))
    result['acquisition'] = {'scores': acquisition, 'seed': evaluation['acquisition_seed'], 'cohort_sha256': cohort.digest}
    if not meets_criterion(acquisition, target, evaluation['criterion'], acquisition=True):
        return result
    seen = {specimen_key(p['row']) for item in observations for step in item['steps'] for p in step['positions']}
    for seed in evaluation['post_acquisition_seeds']:
        cohort, _ = _draw_executable_scope_cohort(source, prepared.graph, prepared.release, registry,
            capabilities=full_scope, seed=seed)
        _verify_cohort(prepared, cohort)
        measured = scores(cohort.rows, _predictions(mx, parameters, list(cohort.rows), receipt['config'], receipt['answer_ids']))
        fresh = _fresh_rows(prepared, source, seed, seen, registry)
        fresh_scores = scores(fresh, _predictions(mx, parameters, fresh, receipt['config'], receipt['answer_ids'])) if fresh else {}
        sweep = {'seed': seed, 'scores': measured, 'cohort_sha256': cohort.digest,
            'fresh_scores': fresh_scores, 'fresh_rows': fresh,
            'exact_training_overlap': sum(specimen_key(row) in seen for row in cohort.rows),
            'criterion_met': meets_criterion(measured, target, evaluation['criterion']),
            'fresh_coverage': any(cap in fresh_scores for cap in target),
            'fresh_scope': {cap: (MeasurementStatus.MEASURED if cap in fresh_scores else MeasurementStatus.NOT_MEASURED) for cap in target},
            'fresh_criterion_met': (meets_criterion(fresh_scores, target, evaluation['criterion'])
                if all(cap in fresh_scores for cap in target) else
                {'status': MeasurementStatus.NOT_MEASURED, 'reason': 'PARTIAL_FRESH_SCOPE'})}
        result['sweeps'].append(sweep)
    passed = all(s['criterion_met'] and s['fresh_coverage'] for s in result['sweeps'])
    result.update(status=QualificationStatus.QUALIFIED if passed else QualificationStatus.NOT_QUALIFIED,
        reason='THREE_POST_ACQUISITION_SWEEPS' if passed else 'POST_ACQUISITION_OR_FRESH_COVERAGE_FAILED')
    return result
