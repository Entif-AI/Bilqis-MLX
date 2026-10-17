"""Certified golden whole-program student as the next version's common root.

This is a nontraining successor bootstrap helper. A golden checkpoint is a
*single complete student and its own AdamW*, never a model soup. It can be
the initial champion of every grade capability, with one frozen teacher
vote per grade it actually mastered. Newly introduced capabilities need
fresh baseline assessments; an old 100% score cannot be inherited for them.

Nothing in this module activates the pedagogically blocked v16 syllabus.
"""
from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import torch

from . import engine
from .capability_champion_policy_vnext import consider_candidate, new_version_registry
from .training_completion import completion_status
from bilqis_micro.run import optimizer_receipt


def golden_bootstrap(*, old_state, old_grade_metrics, golden_path,
                     next_version, new_grade_rubrics, baseline_assessments):
    """Build fresh-version champion registries seeded by ONE golden student.

    old_grade_metrics maps every *previously mastered* grade to the exact
    metric IDs used by the old version's complete, same-checkpoint receipt.
    baseline_assessments must be read-only same-checkpoint scores under the
    **new** version's rubric, including newly introduced capabilities.
    These registries are plans, not persisted live runner state.
    """
    complete, reason = completion_status(old_state)
    if not complete:
        raise ValueError('GOLDEN_SOURCE_NOT_100_PERCENT:' + reason)
    if not old_grade_metrics or not new_grade_rubrics or not next_version:
        raise ValueError('GOLDEN_MISSING_GRADE_CONTRACT')
    old_metrics = old_state['config']['current_assessment_metrics']
    covered = [metric for names in old_grade_metrics.values() for metric in names]
    if (not all(isinstance(names, list) and names for names in old_grade_metrics.values())
            or len(set(covered)) != len(covered) or set(covered) != set(old_metrics)):
        raise ValueError('GOLDEN_INCOMPLETE_OLD_GRADE_COVERAGE')
    if not set(old_grade_metrics).issubset(new_grade_rubrics):
        raise ValueError('GOLDEN_PREVIOUS_GRADE_MISSING')
    sha = old_state['checkpoint_sha256']
    path = Path(golden_path)
    if (not path.is_file() or path.is_symlink() or path.name != old_state['checkpoint']
            or engine._sha(path) != sha):
        raise ValueError('GOLDEN_SOURCE_FILE_MISMATCH')
    # File hash alone cannot distinguish a true whole-state student from a
    # legacy weights-only soup. Require the actual native AdamW continuation.
    with torch.no_grad():
        model, optimizer, _payload = engine.load_checkpoint(path)
    adamw = optimizer_receipt(optimizer)
    if (adamw['steps'] != [old_state['optimizer_step']]
            or not adamw['parameter_states']
            or any(param.dtype != torch.float32 for param in model.parameters())):
        raise ValueError('GOLDEN_SOURCE_NOT_FULL_FP32_ADAMW')
    if set(baseline_assessments) != set(new_grade_rubrics):
        raise ValueError('GOLDEN_NEW_GRADE_ASSESSMENTS_MISSING')

    registries = {}
    for grade, rubric in new_grade_rubrics.items():
        measured = baseline_assessments[grade]
        if set(measured) != set(rubric):
            raise ValueError('GOLDEN_BASELINE_CAPABILITY_COVERAGE:' + grade)
        scores = {}
        for cap, total in rubric.items():
            row = measured[cap]
            if (not isinstance(row, dict) or row.get('checkpoint_sha256') != sha
                    or row.get('optimizer_step') != old_state['optimizer_step']
                    or row.get('version') != next_version
                    or row.get('total') != total
                    or type(row.get('correct')) is not int
                    or not 0 <= row['correct'] <= total):
                raise ValueError('GOLDEN_BASELINE_INVALID_SCORE:' + grade + ':' + cap)
            scores[cap] = row['correct']
        registry = new_version_registry(next_version, rubric)
        candidate = {'version': next_version,
                     'candidate_id': 'golden-inherited-baseline',
                     'checkpoint_sha256': sha,
                     'scores': scores,
                     'admitted_to_student': True,
                     'origin': 'certified-prior-version-golden-student'}
        consider_candidate(registry, candidate)
        registries[grade] = registry

    # Exactly one grade-scoped vote for each PREVIOUSLY mastered grade;
    # no extra votes merely because one file leads several capabilities.
    # A newly introduced grade must qualify before it can earn a vote.
    teacher_votes = {grade: {'checkpoint_sha256': sha, 'checkpoint': str(path),
                             'source_optimizer_step': old_state['optimizer_step']}
                     for grade in old_grade_metrics}
    return {'old_version': old_state['version'], 'next_version': next_version,
            'golden_checkpoint_sha256': sha, 'golden_checkpoint': str(path),
            'golden_optimizer_step': old_state['optimizer_step'],
            'golden_optimizer_receipt': adamw,
            'capability_registries': registries,
            'qualified_grade_teacher_votes': teacher_votes,
            'trainable_student_parent_sha256': sha,
            'inactive_historical_candidates': True}


def clone_trainable_golden(golden_path, student_path, *, expected_sha256):
    """Byte-clone complete model+AdamW into an isolated *nontraining* file.

    The caller must verify golden completion and authorize new-run setup
    first. This never edits the original or manufactures optimizer moments.
    Refuse an existing target; do not hardlink the student's mutable file.
    """
    source, target = Path(golden_path), Path(student_path)
    if (not source.is_file() or source.is_symlink()
            or engine._sha(source) != expected_sha256):
        raise ValueError('GOLDEN_CLONE_SOURCE_MISMATCH')
    if source.resolve() == target.resolve() or target.exists() or target.is_symlink():
        raise ValueError('GOLDEN_CLONE_TARGET_EXISTS_OR_SOURCE')
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.parent / ('.' + target.name + '.' + uuid.uuid4().hex + '.tmp')
    try:
        with source.open('rb') as data, temp.open('xb') as output:
            shutil.copyfileobj(data, output)
            output.flush()
            os.fsync(output.fileno())
        if engine._sha(temp) != expected_sha256:
            raise ValueError('GOLDEN_CLONE_BYTES_DRIFTED')
        try:
            os.link(temp, target)
        except FileExistsError:
            raise ValueError('GOLDEN_CLONE_TARGET_EXISTS_OR_SOURCE') from None
        fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return {'student_checkpoint': str(target), 'sha256': expected_sha256,
                'same_inode_as_frozen_golden': False}
    finally:
        temp.unlink(missing_ok=True)
