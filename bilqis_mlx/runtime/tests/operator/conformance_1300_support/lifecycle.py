"""Production bootstrap/enrollment boundaries for the #1300 disposable run."""
from __future__ import annotations

from pathlib import Path

from bilqis_mlx.factory.schedule import schedule_program_from_executable_release
from bilqis_mlx.runtime.accepted_priority_visit import accepted_priority_school
from bilqis_mlx.runtime.atlas_admission import (
    AtlasAdmissionEnrollmentRequestV2,
    enroll_accepted_atlas_lease_v2,
)
from bilqis_mlx.runtime.active_generated_grade import read_active_generated_grade
from bilqis_mlx.runtime.bamf_bundle.admission import load_accepted_generation
from bilqis_mlx.runtime.bamf_operator.session import _execution_context
from bilqis_mlx.runtime.foundation_teacher_owner import select_foundation_priority_visit


def bootstrap_staged_generation_zero(run_dir: Path):
    """Exercise the #1383 neural-inert production bootstrap exactly once."""
    before = load_accepted_generation(run_dir)
    parent, context, atlas_path, _feature_path = _execution_context(run_dir)
    program = schedule_program_from_executable_release(context.release)
    school = accepted_priority_school(parent, program)
    selected = select_foundation_priority_visit(
        run_dir, context, atlas_path, program=program, school=school)
    active = read_active_generated_grade(run_dir)
    after = load_accepted_generation(run_dir)
    return before, selected, active, after


def enroll_prepared_lease(run_dir: Path, lease, *, source_authority):
    """Submit fixture request data through the public accepted C07 enrollment owner."""
    accepted = load_accepted_generation(run_dir)
    identity = accepted.run_identity
    request = AtlasAdmissionEnrollmentRequestV2(
        lease.lease_id,
        identity.run_id,
        identity.run_seed,
        identity.initial_topology_digest,
        lease.source_approval,
        lease.resource_ceiling,
        lease.requested_at,
        lease.human_command_sha256,
    )
    return enroll_accepted_atlas_lease_v2(
        run_dir, request, human_started=True, source_authority=source_authority)
