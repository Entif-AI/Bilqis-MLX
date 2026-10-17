"""Preserve a capability-winning candidate's ACTUAL model and AdamW together.

Isolated successor helper: NOT connected to the frozen v15 runner or any
training command. The caller must pass the candidate's own optimizer while
it is still alive, even when that candidate is rejected for student admission.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

import torch

from bilqis_development.continuation import (save as save_full_checkpoint,
                                            load as load_full_checkpoint)
from bilqis_micro.run import optimizer_receipt
from bilqis_ref.model import state_hash
from bilqis_logic.kernel import digest
from . import engine

SCHEMA = 'bilqis.capability-full-candidate/v1'
_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z')


def preserve_candidate(run_dir, *, version, run_id, candidate_id,
                       model, optimizer, graph, candidate_step,
                       parent_checkpoint_sha256, capability_scores):
    """Atomically archive ONE shared full checkpoint for all eligible slots.

    Never manufactures optimizer state, swaps in a different student's AdamW,
    or mutates the cumulative student. The returned file may be pointed to
    by several capability champion records within the same grade.
    """
    for identity in (version, run_id, candidate_id):
        if not _ID.fullmatch(identity):
            raise ValueError('FULL_CANDIDATE_UNSAFE_ID')
    if not parent_checkpoint_sha256 or not capability_scores:
        raise ValueError('FULL_CANDIDATE_MISSING_PROVENANCE')
    receipt = optimizer_receipt(optimizer)
    if receipt['steps'] != [candidate_step] or not receipt['parameter_states']:
        raise ValueError('FULL_CANDIDATE_WRONG_ADAMW_STATE')
    model_sha = state_hash(model)
    graph_sha = digest(graph)
    relative = Path('run-local')/'full-candidates'/version/run_id/(candidate_id+'.pt')
    root = Path(run_dir)
    target = root/relative
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.is_symlink():
        raise ValueError('FULL_CANDIDATE_TARGET_SYMLINK')
    metadata = {
        'schema':SCHEMA, 'version':version, 'run_id':run_id,
        'candidate_id':candidate_id, 'step':candidate_step,
        'parent_checkpoint_sha256':parent_checkpoint_sha256,
        'graph_sha256':graph_sha, 'capability_scores':capability_scores,
    }
    tmp = target.parent/('.'+target.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        save_full_checkpoint(tmp,model,optimizer,graph,metadata)
        # The existing native loader verifies actual restored weights and
        # AdamW, not merely metadata inside an unverified torch file.
        rng = torch.get_rng_state()
        threads = torch.get_num_threads()
        deterministic = torch.are_deterministic_algorithms_enabled()
        try:
            verified_model,verified_opt,archive = load_full_checkpoint(tmp)
        finally:
            torch.set_rng_state(rng)
            torch.set_num_threads(threads)
            torch.use_deterministic_algorithms(deterministic)
        if (archive['metadata'] != metadata or
            digest(archive['graph']) != graph_sha or
            state_hash(verified_model) != model_sha or
            optimizer_receipt(verified_opt) != receipt):
            raise ValueError('FULL_CANDIDATE_ROUNDTRIP_DRIFT')
        if not target.exists():
            try:os.link(tmp,target)  # no-clobber commit, same filesystem
            except FileExistsError:pass
        if target.is_symlink() or not target.is_file():
            raise ValueError('FULL_CANDIDATE_TARGET_UNSAFE')
        if engine._sha(target) != engine._sha(tmp):
            raise ValueError('FULL_CANDIDATE_REPLAY_CONFLICT')
        return {
            'file':relative.as_posix(), 'sha256':engine._sha(target),
            'model_sha256':model_sha, 'optimizer_receipt':receipt,
            'graph_sha256':graph_sha, 'candidate_step':candidate_step,
            'schema':SCHEMA, 'version':version, 'run_id':run_id,
            'candidate_id':candidate_id,
        }
    finally:
        if tmp.exists():tmp.unlink()
