#!/usr/bin/env python3
"""Freeze existing Factory workload metadata; never copy weights or start training."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
from types import MappingProxyType
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from bilqis_mlx.runtime.state import _fingerprint, _durable_json
from bilqis_mlx.runtime.qualification_manifest import (
    SCHEMA, EVALUATION_FIXTURE_SCHEMA, environment_identity, file_digest, implementation_files, workload, require,
)
from bilqis_mlx.runtime.model_topology import CURRENT_DEFAULT_TOPOLOGY, ModelTopologySpec
from bilqis_mlx.runtime.topology_lifecycle import model_implementation
from bilqis_mlx.runtime.admission import _read_executable_factory_release_artifact
from bilqis_mlx.state_dag import read_current

COMPONENTS = MappingProxyType({'150': '0a0d73a85d8b6214aaa446c04a510d05e904ae5c',
              '320': 'f09e44d35b5f544ef8d3e61ec127e326d0b09eb1',
              '333': '35cf2b8ccb6c7d0e9f195d7e65e4ef990bfe5994'})
COMPONENT_REFS = MappingProxyType({'150': 'refs/heads/codex/150-factory-microspecs-20261023',
                  '320': 'refs/heads/codex/320-model-topology-20261026',
                  '333': 'refs/heads/codex/333-factory-teacher-observations-20261026'})
INITIALIZATION_SEED = 324
TRAINING_SEED = 3240
SOURCE_VERIFICATION_SEED = 32420261026
ACQUISITION_SEED = 32401
POST_SEEDS = (32403, 32405, 32407)
FRESH_DRAW_ROUNDS = 8


def store(folder, name, value):
    _durable_json(folder/name, value)
    return {'file': name, 'sha256': _fingerprint(value)}


def source_snapshot(root):
    receipt = read_current(root)
    require(receipt.get('factory_admission_v2') is not None, 'CURRENT_FACTORY_SOURCE_REQUIRED')
    release = _read_executable_factory_release_artifact(root, receipt)
    require(tuple(g.grade_id for g in release.execution_plan.grades) == ('A', 'B', 'C'), 'EXISTING_ABC_WORKLOAD_REQUIRED')
    graph = json.loads((root/receipt['model_bundle']/'semantic-catalog.json').read_text())
    require(_fingerprint(graph) == receipt['semantic_graph_sha256'], 'SOURCE_GRAPH_IDENTITY')
    return receipt, release, graph


def compile_stages(original, graph, source):
    from bilqis_mlx.factory.executable_release import (
        compile_executable_factory_release, compile_successor_profile_release)
    from bilqis_mlx.factory.execution import GradeProfile, CurriculumProfile
    from bilqis_mlx.factory.live_answers import live_answer_registry
    from bilqis_mlx.source_adapters.school import live_source_registry
    stages = []
    known = {g.grade_id: g for g in original.profile.grades}
    grades = original.curriculum.grades
    for count in range(1, len(grades) + 1):
        overrides = tuple(known.get(g.grade_id, GradeProfile(g.grade_id)) if index < count
            else GradeProfile(g.grade_id, enabled_capabilities=())
            for index, g in enumerate(grades))
        profile = CurriculumProfile(original.profile.profile_id, grades=overrides)
        if stages:
            release = compile_successor_profile_release(stages[-1], profile,
                live_source_registry(), live_answer_registry(), source_root=source,
                graph=graph, verification_seed=SOURCE_VERIFICATION_SEED)
        else:
            release = compile_executable_factory_release(original.curriculum, original.source_bindings,
                profile, live_source_registry(), live_answer_registry(), source_root=source,
                graph=graph, verification_seed=SOURCE_VERIFICATION_SEED)
        stages.append(release)
    return tuple(stages)


def source_inputs(source):
    from bilqis_mlx.source import AUDITED_PARENT
    checkpoint = source/'runs/primitive-consolidation-v16-triplets'/AUDITED_PARENT.basename
    teacher = checkpoint.parent/'state.json'
    from bilqis_mlx.cli import GRADE_A_MANIFEST
    manifest = GRADE_A_MANIFEST
    import torch
    payload = torch.load(checkpoint, map_location='cpu', weights_only=True, mmap=True)
    group = payload['optimizer']['param_groups'][0]
    optimizer = {'learning_rate': group['lr'], 'betas': group['betas'],
                 'eps': group['eps'], 'weight_decay': group['weight_decay']}
    paths = (checkpoint, teacher, manifest, source/'bilqis_school/engine.py')
    identities = [{'path': str(path), 'sha256': file_digest(path)} for path in paths]
    require(identities[0]['sha256'] == AUDITED_PARENT.sha256, 'HISTORICAL_SOURCE_CHECKSUM')
    return {'root': str(source), 'checkpoint': str(checkpoint), 'manifest': str(manifest)}, optimizer, identities


def evaluation_fixture(release, graph, source):
    from bilqis_mlx.runtime.assessment import _draw_executable_scope_cohort
    from bilqis_mlx.source_adapters.school import live_source_registry
    capabilities = tuple(cap.capability_id for cap in release.execution_plan.capabilities)
    return {'schema': EVALUATION_FIXTURE_SCHEMA, 'release_sha256': release.release_sha256,
        'cohorts': {str(seed): {'cohort_sha256': cohort.digest, 'rows': list(cohort.rows)}
        for seed in (ACQUISITION_SEED, *POST_SEEDS)
        for cohort, _ in [_draw_executable_scope_cohort(source, graph, release,
            live_source_registry(), capabilities=capabilities, seed=seed)]}}


def freeze(source_run, folder, execution_root):
    from bilqis_mlx.runtime.teacher_observation_capture import policy_epoch
    from bilqis_mlx.learning.learning_experiment import Settings
    from bilqis_mlx.curriculum.promotion import PROMOTION_MEAN_FLOOR
    require(not folder.exists(), 'IMMUTABLE_OUTPUT_ALREADY_EXISTS')
    source = (source_run.parents[1]/'vendor/legacy-v16').resolve()
    receipt, original, graph = source_snapshot(source_run)
    stages = compile_stages(original, graph, source)
    release = stages[-1]
    inputs, optimizer, external = source_inputs(source)
    budget = {'minutes': 90, 'max_visits': 1000, 'steps_per_visit': 16, 'batch_size': 32,
        'attempted_step_ceiling': 16000, 'checkpoint_estimate_bytes': 600_000_000,
        'wall_semantics': 'SOFT_SESSION_LIMIT_AT_SAFE_BOUNDARY; DUE_EXAMS_AND_FINAL_CHECKPOINT_FINISH'}
    policy = {'retention_settings': asdict(Settings()), 'reserve_gib': 100.,
        'source_prefetch_workers': 2, 'full_grade_b': True, 'retention_enabled': True,
        'autonomous_curriculum': False, 'source_teaching_enrichment': False,
        'flash_mode': False, 'numeric_staircase': False, 'optimizer': optimizer,
        'initial_teacher_state_sha256': external[1]['sha256'],
        'stage_epochs': {stage.release_sha256: policy_epoch(
            {**receipt, 'qualification_training_seed': TRAINING_SEED}, stage,
            configured_steps=budget['steps_per_visit'], batch_size=budget['batch_size'],
            settings=Settings(), enrichment=False) for stage in stages}}
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    arms = [{'id': name, 'topology': topology.to_record(), 'initialization_origin': 'fresh-model',
        'initialization_seed': INITIALIZATION_SEED, 'run_dir': str(execution_root/'runs'/('qualification-324-'+name))}
        for name, topology in (('baseline', CURRENT_DEFAULT_TOPOLOGY),
                               ('capacity', ModelTopologySpec(8, 32, 512, 2048, 96)))]
    total_rows = sum(c.exam_item_count for c in release.execution_plan.capabilities)
    budget['qualification_inference_rows_ceiling'] = (1 + 2 * len(POST_SEEDS)) * total_rows
    budget['fresh_source_draw_rounds_per_capability_per_post_seed'] = FRESH_DRAW_ROUNDS
    stage_refs = [{**store(folder, f'release-{i}.json', stage.manifest()),
        'release_sha256': stage.release_sha256} for i, stage in enumerate(stages)]
    manifest = {'schema': SCHEMA, 'implementation': {'head': head, 'components': dict(COMPONENTS),
        'component_refs': dict(COMPONENT_REFS), 'files': implementation_files(ROOT), 'provider': model_implementation(), 'environment': environment_identity()},
        'release': {k:v for k,v in stage_refs[-1].items() if k != 'release_sha256'},
        'stages': stage_refs, 'graph': store(folder, 'semantic-catalog.json', graph),
        'workload': workload(release, graph), 'numeric_maximum': receipt['numeric_maximum'],
        'source': inputs, 'external_files': external, 'optimizer': optimizer,
        'initialization_seed': INITIALIZATION_SEED, 'training_seed': TRAINING_SEED,
        'arms': arms, 'budget': budget, 'budget_sha256': _fingerprint(budget),
        'numeric_scope_sha256': _fingerprint(receipt['numeric_maximum']),
        'policy': {'value': policy, 'sha256': _fingerprint(policy)},
        'observation_capture': True, 'neural_authority': False,
        'initial_state': {'origin': 'fresh-current-factory', 'optimizer_step': 0,
            'carried_mastery_debt': [], 'live_student_not_imported': True},
        'source_observation': {'generation': receipt['generation'], 'run_id': receipt['run_id'],
            'release_sha256': original.release_sha256, 'numeric_maximum': receipt['numeric_maximum'],
            'future_ceiling_not_adopted': receipt.get('numeric_scope_final_maximum'),
            'observed_debt_not_imported': receipt['school'].get('carried_mastery_debt', [])},
        'evaluation': {'target_grade': release.execution_plan.grades[-1].grade_id,
            'acquisition_seed': ACQUISITION_SEED, 'post_acquisition_seeds': list(POST_SEEDS),
            'fresh_draw_rounds': FRESH_DRAW_ROUNDS,
            'fixture': store(folder, 'evaluation-fixture.json', evaluation_fixture(release, graph, source)),
            'criterion': {'numerator': PROMOTION_MEAN_FLOOR.numerator,
                'denominator': PROMOTION_MEAN_FLOOR.denominator,
                'aggregation': 'ARITHMETIC_MEAN_OF_CAPABILITY_ACCURACIES',
                'acquisition': 'STRICTLY_GREATER', 'post_acquisition': 'GREATER_OR_EQUAL'},
            'overlap_key': 'sha256(capability,tokens,gold,answer_kind)',
            'fresh_procedure': 'For each post seed/capability/round, draw using sha256([seed,capability,round])[:16]; exclude exact trained input/label keys; keep first unique rows up to exam_item_count. No teaching embargo.',
            'fresh_requirement': 'Each post sweep includes unseen target-grade probes. Per-capability exhausted fresh scope is NOT_MEASURED. The frozen full target-grade mean remains the qualification criterion.',
            'resume': 'No automatic experimental resume or budget refund; interrupted arm is incomplete pending explicit epoch decision'}}
    manifest['digest'] = _fingerprint(manifest)
    _durable_json(folder/'manifest.json', manifest)
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execution-root', type=Path, required=True)
    args = parser.parse_args()
    manifest = freeze(args.source_run.resolve(), args.output.resolve(), args.execution_root.resolve())
    print(json.dumps({'manifest_sha256': manifest['digest'], 'numeric_maximum': manifest['numeric_maximum'],
                      'implementation_head': manifest['implementation']['head'], 'neural_updates': 0}))


if __name__ == '__main__':
    main()
