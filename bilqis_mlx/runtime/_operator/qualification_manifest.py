"""Frozen qualification inputs; validation never allocates or mutates a student."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import StrEnum
import hashlib
import json
from pathlib import Path
import subprocess

from ..errors import ErrorBus, SCHOOL
from ..factory.executable_release import ExecutableFactoryRelease
from ..factory.schedule import schedule_program_from_executable_release
from .model_topology import ModelTopologySpec
from .state import _fingerprint

SCHEMA = "bilqis.factory.learning-qualification/v1"
ARM_COUNT = 2
POST_SWEEPS = 3
EVALUATION_FIXTURE_SCHEMA = "bilqis.factory.qualification-evaluation-fixture/v1"


class QualificationStatus(StrEnum):
    READY = "QUALIFICATION_MANIFEST_FROZEN_AND_READY_FOR_HUMAN_INITIATION"
    QUALIFIED = "QUALIFIED"
    NOT_QUALIFIED = "NOT_QUALIFIED"
    NOT_READY = "NOT_READY"


def require(condition, reason):
    if not condition:
        ErrorBus.Raise(SCHOOL.QUALIFICATION.INVALID, detail=reason)


def environment_identity():
    from importlib.metadata import version
    import platform
    return {'python': platform.python_version(), 'machine': platform.machine(),
            'system': platform.system(), 'macos': platform.mac_ver()[0],
            'libraries': {name: version(name) for name in ('mlx', 'numpy', 'torch')}}


def file_digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def implementation_files(root):
    """Seal production Python independently of documentation-only commits."""
    root = Path(root)
    return {str(p.relative_to(root)): file_digest(p)
            for p in sorted((root / 'bilqis_mlx').rglob('*.py'))
            if 'tests' not in p.parts and '__pycache__' not in p.parts}


def read_object(folder, reference):
    relative = Path(reference['file'])
    require(not relative.is_absolute() and '..' not in relative.parts, 'ARTIFACT_PATH')
    path = Path(folder) / relative
    require(path.is_file() and not path.is_symlink(), 'ARTIFACT_MISSING')
    value = json.loads(path.read_text())
    require(_fingerprint(value) == reference['sha256'], 'ARTIFACT_DIGEST')
    return value


def workload(release, graph):
    release.verify_semantic_catalog(graph)
    return {'release_sha256': release.release_sha256,
            'semantic_graph_sha256': _fingerprint(graph),
            'semantic_catalog_sha256': release.semantic_catalog_sha256,
            'curriculum_sha256': release.curriculum.digest(),
            'execution_plan_sha256': release.execution_plan.digest(),
            'grades': {g.grade_id: list(g.capabilities) for g in release.execution_plan.grades},
            'provider_parameters': {c.capability_id: dict(c.provider_parameters)
                                    for c in release.execution_plan.capabilities},
            'source_bindings': asdict(release.source_bindings)}


@dataclass(frozen=True)
class QualificationPreparation:
    manifest: dict
    arm: dict
    release: ExecutableFactoryRelease
    graph: dict
    stages: tuple = ()
    evaluation_fixture: dict | None = None

    @property
    def initial_release(self):
        return self.stages[0] if self.stages else self.release

    def persist_releases(self, root):
        from .admission import _persist_executable_factory_release
        for release in self.stages:
            _persist_executable_factory_release(root, release)

    def initial_model(self):
        from .model_topology import create_student
        topology = ModelTopologySpec.from_record(self.arm['topology'])
        parameters, optimizer = create_student(topology, len(self.graph['tokens']),
            seed=self.arm['initialization_seed'], optimizer_config=self.manifest['optimizer'])
        config = {**{k: getattr(topology, k) for k in (
            'layers', 'heads', 'width', 'ffn_dimension', 'context')},
            'precision': 'fp32', 'vocab_size': len(self.graph['tokens'])}
        config['answer_heads'] = {head.kind: {'values': list(head.values),
            'token_ids': list(head.token_ids)} for head in self.initial_release.answer_heads}
        binary = next(head for head in self.initial_release.answer_heads if head.kind == 'binary')
        return parameters, optimizer, config, self.graph, list(binary.token_ids), topology, {
            'origin': 'fresh-model', 'seed': self.arm['initialization_seed']}

    def receipt_fields(self):
        return {'qualification': {'manifest_sha256': self.manifest['digest'],
                    'arm': self.arm['id'], 'release_sha256': self.release.release_sha256,
                    'allowed_releases': [r.release_sha256 for r in (self.stages or (self.release,))]},
                'qualification_training_seed': self.manifest['training_seed'],
                'numeric_maximum': self.manifest['numeric_maximum'],
                'numeric_scope_final_maximum': self.manifest['numeric_maximum']}


def validate(path, arm_id, *, implementation_root, expected_digest):
    path, root = Path(path), Path(implementation_root)
    manifest = json.loads(path.read_text())
    digest = manifest.get('digest')
    require(digest == expected_digest, 'EXPECTED_MANIFEST_DIGEST')
    require(manifest.get('schema') == SCHEMA and digest == _fingerprint(
        {k: v for k, v in manifest.items() if k != 'digest'}), 'MANIFEST_DIGEST')
    implementation = manifest['implementation']
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == implementation['head'], 'FACTORY_HEAD')
    require(implementation_files(root) == implementation['files'], 'IMPLEMENTATION_FILES')
    if 'environment' in implementation:
        require(environment_identity() == implementation['environment'], 'RUNTIME_ENVIRONMENT')
    for component in implementation['components'].values():
        require(subprocess.run(['git', '-C', str(root), 'merge-base', '--is-ancestor',
            component, head], capture_output=True).returncode == 0, 'COMPONENT_ANCESTRY')
    release = ExecutableFactoryRelease.from_manifest(
        read_object(path.parent, manifest['release']), manifest['workload']['release_sha256'])
    graph = read_object(path.parent, manifest['graph'])
    stages = tuple(ExecutableFactoryRelease.from_manifest(read_object(path.parent, ref), ref['release_sha256'])
                   for ref in manifest.get('stages', ()))
    for previous, successor in zip(stages, stages[1:]):
        successor.verify_successor_of(previous)
    if stages:
        require(stages[-1] == release, 'FINAL_STAGE_RELEASE')
        require(all(stage.semantic_catalog == release.semantic_catalog for stage in stages), 'STAGE_ABI')
    require(json.loads(json.dumps(workload(release, graph))) == manifest['workload'], 'SEMANTIC_WORKLOAD')
    require(len(manifest['arms']) == ARM_COUNT, 'TWO_ARMS_REQUIRED')
    require(len({a['id'] for a in manifest['arms']}) == ARM_COUNT, 'ARM_IDENTITIES')
    for arm in manifest['arms']:
        ModelTopologySpec.from_record(arm['topology'])
        require(arm['initialization_origin'] == 'fresh-model', 'INITIALIZATION_ORIGIN')
        require(arm['initialization_seed'] == manifest['initialization_seed'], 'INITIALIZATION_SEED')
    require(len({a['topology']['digest'] for a in manifest['arms']}) == ARM_COUNT, 'TOPOLOGY_CONTROL')
    selected = [a for a in manifest['arms'] if a['id'] == arm_id]
    require(len(selected) == 1, 'UNKNOWN_ARM')
    require(type(manifest['training_seed']) is int, 'TRAINING_SEED')
    budget = manifest['budget']
    require(all(type(budget[k]) is int and budget[k] > 0
        for k in ('minutes', 'max_visits', 'steps_per_visit', 'batch_size')), 'FINITE_BUDGET')
    require(budget['attempted_step_ceiling'] == budget['max_visits'] * budget['steps_per_visit'], 'STEP_BUDGET')
    require(manifest['observation_capture'] is True, 'CAPTURE_REQUIRED')
    require(manifest['neural_authority'] is False, 'AUTHORITY_MUST_BE_ABSENT')
    require(len(manifest['evaluation']['post_acquisition_seeds']) == POST_SWEEPS and
        len(set(manifest['evaluation']['post_acquisition_seeds'])) == POST_SWEEPS, 'POST_SWEEP_SEEDS')
    require(manifest['policy']['sha256'] == _fingerprint(manifest['policy']['value']), 'POLICY_DIGEST')
    require(manifest['budget_sha256'] == _fingerprint(budget), 'BUDGET_DIGEST')
    require(manifest['numeric_scope_sha256'] == _fingerprint(manifest['numeric_maximum']), 'NUMERIC_SCOPE_DIGEST')
    for identity in manifest['external_files']:
        require(file_digest(identity['path']) == identity['sha256'], 'SOURCE_FILE_DRIFT')
    fixture = None
    if 'fixture' in manifest['evaluation']:
        fixture = read_object(path.parent, manifest['evaluation']['fixture'])
        require(fixture.get('schema') == EVALUATION_FIXTURE_SCHEMA, 'EVALUATION_FIXTURE_SCHEMA')
    run_dir = Path(selected[0]['run_dir'])
    require(not run_dir.exists() and not run_dir.is_symlink(), 'FRESH_RUN_REQUIRED')
    from ..factory.live_answers import live_answer_registry
    from ..source_adapters.school import live_source_registry
    from .jit_adoption import verify_current_implementations
    verify_current_implementations(release, live_source_registry(), live_answer_registry())
    schedule_program_from_executable_release(release)
    return QualificationPreparation(manifest, selected[0], release, graph, stages, fixture)
