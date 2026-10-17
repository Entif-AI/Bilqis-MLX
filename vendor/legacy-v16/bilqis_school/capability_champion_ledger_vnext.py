"""Crash-recoverable, nontraining capability election for a future runner.

Checkpoint publication precedes ledger publication. A crash between them
leaves an orphaned *complete* candidate, never a pointer to a missing file.
Only a single writer may operate on one version/run ledger at a time.
"""
import copy
import json
import os
import uuid
from pathlib import Path

from .capability_champion_policy_vnext import consider_candidate, new_version_registry
from .full_candidate_checkpoint_vnext import preserve_candidate
from . import engine


def _write_atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name('.' + path.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with temp.open('x', encoding='utf-8') as output:
            json.dump(data, output, sort_keys=True, indent=2)
            output.write('\n')
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path)
        fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        temp.unlink(missing_ok=True)


def ledger_path(run_dir, version, run_id, grade_id):
    for value in (version, run_id, grade_id):
        if not isinstance(value, str) or not value or not value.replace('-', '').replace('_', '').isalnum():
            raise ValueError('CAPABILITY_UNSAFE_LEDGER_ID')
    return Path(run_dir) / 'run-local' / 'capability-ledgers' / version / run_id / (grade_id + '.json')


def record_candidate(run_dir, *, version, run_id, grade_id, candidate_id,
                     rubric, scores, admitted_to_student, model, optimizer,
                     graph, candidate_step, parent_checkpoint_sha256):
    """Archive candidate with its actual AdamW, then publish shared pointers.

    Intentional serialized-writer contract: callers must hold the run lock.
    Scores must be measured using one current version/grade rubric.
    """
    path = ledger_path(run_dir, version, run_id, grade_id)
    registry = json.loads(path.read_text()) if path.exists() else new_version_registry(version, rubric)
    if registry['version'] != version or registry['rubric'] != rubric:
        raise ValueError('CAPABILITY_LEDGER_RUBRIC_DRIFT')
    if any(item['candidate_id'] == candidate_id for item in registry.get('attempts', [])):
        raise ValueError('CAPABILITY_CANDIDATE_ALREADY_RECORDED')
    # The archive write must complete while this candidate optimizer exists.
    archive = preserve_candidate(
        run_dir, version=version, run_id=run_id,
        candidate_id=grade_id + '-' + candidate_id, model=model,
        optimizer=optimizer, graph=graph, candidate_step=candidate_step,
        parent_checkpoint_sha256=parent_checkpoint_sha256,
        capability_scores={'grade_id': grade_id, 'scores': scores,
                           'rubric': rubric, 'admitted_to_student': admitted_to_student},
    )
    candidate = {'version': version, 'candidate_id': candidate_id,
                 'checkpoint_sha256': archive['sha256'],
                 'checkpoint_file': archive['file'], 'scores': dict(scores),
                 'admitted_to_student': admitted_to_student,
                 'optimizer_receipt': archive['optimizer_receipt'],
                 'model_sha256': archive['model_sha256']}
    updated = copy.deepcopy(registry)
    slots = consider_candidate(updated, candidate)
    updated.setdefault('attempts', []).append(candidate)
    # An exact below-100 tie has no approved tie-breaker: preserve the
    # challenger without silently changing the incumbent champion.
    updated.setdefault('unresolved_ties', [])
    for cap, total in rubric.items():
        incumbent = registry['champions'][cap]
        if (incumbent and cap not in slots and scores[cap] == incumbent['scores'][cap]
                and scores[cap] < total):
            updated['unresolved_ties'].append({'capability': cap,
                'incumbent_sha256': incumbent['checkpoint_sha256'],
                'challenger_sha256': archive['sha256']})
    _write_atomic(path, updated)
    return {'ledger': str(path), 'archive': archive,
            'updated_capabilities': slots, 'candidate': candidate}


def verify_ledger(run_dir, version, run_id, grade_id):
    """Reject broken references before promotion or teacher qualification."""
    path = ledger_path(run_dir, version, run_id, grade_id)
    registry = json.loads(path.read_text())
    for attempt in registry.get('attempts', []):
        checkpoint = Path(run_dir) / attempt['checkpoint_file']
        if not checkpoint.is_file() or checkpoint.is_symlink() or engine._sha(checkpoint) != attempt['checkpoint_sha256']:
            raise ValueError('CAPABILITY_LEDGER_CHECKPOINT_MISSING_OR_DRIFTED')
    return registry
