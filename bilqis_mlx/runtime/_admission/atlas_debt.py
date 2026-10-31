"""Read-only C07 view of native debt, with unresolved historical scope explicit."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path

from ..factory.schedule import schedule_program_from_executable_release
from .admission import _require_executable_factory_admission
from .atlas_admission import _invalid, _sha
from .state import _fingerprint, _state_from_json


@dataclass(frozen=True)
class NativeAtlasDebt:
    manifest_sha256: str
    run_id: str
    generation: int
    factory_release_sha256: str
    profile_sha256: str
    checkpoint_sha256: str
    optimizer_step: int
    active_grades: tuple[str, ...]
    capability_grades: tuple[tuple[str, str], ...]
    introduction_frontiers: tuple[tuple[str, int], ...]
    carried_mastery_debt: tuple[str, ...]
    mature_capability_debt: tuple[tuple[str, int], ...]
    mature_grade_debt: tuple[tuple[str, int], ...]
    current_provider_parameters: tuple
    # Native legacy debt lacks per-item historical scope/policy receipts. Current
    # provider parameters describe current scope, never the origin of old debt.
    historical_scope_policy_status: str = field(default='NOT_MEASURED', init=False)
    authorizes_learning: bool = field(default=False, init=False)
    schema_version: str = field(default='bilqis.c07.native-debt-view/v1', init=False)


def read_native_atlas_debt(run_dir: Path, manifest: dict, graph: dict, *,
                           expected_manifest_sha256: str) -> NativeAtlasDebt:
    """Project an owner-supplied current manifest; never discover or mutate a run.

    The caller must obtain the expected digest from its independently loaded run
    owner. Hash equality binds this view to canonical manifest content; it does not confer
    B13 custody authority. Cold Factory admission and native SchoolState validation
    remain responsible for their existing release/catalog/learner invariants.
    """
    if (not isinstance(manifest, dict) or not _sha(expected_manifest_sha256)
            or _fingerprint(manifest) != expected_manifest_sha256
            or not isinstance(manifest.get('run_id'), str) or not manifest['run_id']
            or type(manifest.get('generation')) is not int or manifest['generation'] < 0):
        _invalid('BAMF_ATLAS_CURRENT_MANIFEST_REQUIRED')
    raw_school = manifest.get('school')
    required = ('active_grades', 'introduction_frontiers', 'carried_mastery_debt',
                'mature_capability_debt', 'mature_grade_debt')
    if not isinstance(raw_school, dict) or any(name not in raw_school for name in required):
        _invalid('BAMF_ATLAS_NATIVE_DEBT_EVIDENCE_MISSING')
    release = _require_executable_factory_admission(Path(run_dir), manifest, graph)
    program = schedule_program_from_executable_release(release)
    school = _state_from_json(raw_school, program)
    # Deserialization may migrate legacy debt. Preserve exact persisted evidence
    # instead of silently interpreting migration as a new grade attribution.
    for name in required:
        if _fingerprint(getattr(school, name)) != _fingerprint(raw_school[name]):
            _invalid('BAMF_ATLAS_NATIVE_DEBT_MIGRATION_REQUIRED')
    active = set(school.active_grades)
    capabilities = tuple(c for c in release.execution_plan.capabilities if c.grade_id in active)
    return NativeAtlasDebt(expected_manifest_sha256, manifest['run_id'], manifest['generation'],
        release.release_sha256, _fingerprint(asdict(release.profile)),
        school.current_student.sha256, school.current_student.optimizer_step,
        school.active_grades, tuple((c.capability_id, c.grade_id) for c in capabilities),
        school.introduction_frontiers, school.carried_mastery_debt,
        school.mature_capability_debt, school.mature_grade_debt,
        tuple((c.capability_id, c.provider_parameters) for c in capabilities))
