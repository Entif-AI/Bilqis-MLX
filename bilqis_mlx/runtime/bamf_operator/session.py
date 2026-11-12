"""C16.3 persistent BAMF-native human session.

This coordinator composes existing owners.  It is not a curriculum, teacher,
retention, source, optimizer, or publication authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.paths import LEGACY_SOURCE
from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
from bilqis_mlx.runtime.bamf_bundle import (
    authenticate_bamf_execution_feature_context,
    read_accepted_generation_feature_context,
)
from bilqis_mlx.runtime.bamf_bundle.admission import (
    load_accepted_generation,
)
from bilqis_mlx.semantics.atlas.feature_io import persist_feature_manifest
from bilqis_mlx.semantics.atlas.snapshot import (
    AtlasArtifactIdentity, resolve_atlas_artifact_selection,
)
from .locking import bamf_operator_lock


def _invalid(reason: str):
    ErrorBus.raise_(SCHOOL.BAMF_FIRST_STUDENT.INVALID, reason=reason)


@dataclass(frozen=True)
class BamfOperatorResult:
    status: str
    visits: int
    accepted: int
    rejected: int
    generation: int
    optimizer_step: int


def _accepted_lease_digest(run_dir: Path, host: AcceptedRuntimeHost):
    from bilqis_mlx.runtime.atlas_lease_storage import classify_accepted_atlas_epoch
    epoch = classify_accepted_atlas_epoch(run_dir)
    if epoch == "staged":
        return "staged"
    source_authority = host.source_authority()
    if epoch == "v2":
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease_v2
        lease = read_accepted_atlas_lease_v2(
            run_dir, source_authority=source_authority)
    else:
        from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease
        lease = read_accepted_atlas_lease(
            run_dir, source_authority=source_authority)
    if lease is None:
        _invalid("BAMF_OPERATOR_ACCEPTED_ATLAS_LEASE_MISSING")
    return lease.digest()


def _execution_context(run_dir: Path):
    parent = load_accepted_generation(run_dir)
    host = AcceptedRuntimeHost(run_dir)
    context = host.source_context(source_root=LEGACY_SOURCE.resolve())
    _accepted_lease_digest(run_dir, host)
    accepted = read_accepted_generation_feature_context(run_dir / "bamf-state.json")
    identity = accepted.receipt
    selection = resolve_atlas_artifact_selection(AtlasArtifactIdentity(
        identity.source_atlas_bundle_id,
        identity.source_release_sha256,
        identity.source_source_bundle_id,
    ))
    authenticated = authenticate_bamf_execution_feature_context(
        parent, selection.path, run_dir)
    predecessor = accepted.construction_predecessor
    feature = persist_feature_manifest(
        authenticated.features, run_dir / "operator-artifacts" / "features",
        predecessor=predecessor)
    return parent, context, selection.path, feature.path


def _visit(run_dir: Path, reserve_gib: float):
    # C03.4 owns persistent WHAT ordering.  The accepted runtime does not yet
    # expose production issuers/loaders for its signed C06 frontier/history,
    # A09 planning input, or BAMF scheduler projection.  Fail closed rather
    # than reintroducing a release-order or grade-derived scheduler here.
    _execution_context(run_dir)
    _invalid("BAMF_OPERATOR_PRIORITY_AUTHORITY_UNAVAILABLE")


def operate_bamf(
    run_dir: Path, *, minutes: int = 90,
    max_visits: int = 0, reserve_gib: float = 100.0,
) -> BamfOperatorResult:
    """Run the human-authorized BAMF lineage until a bounded stop condition."""
    if (type(minutes) is not int or minutes < 1 or type(max_visits) is not int
            or max_visits < 0 or reserve_gib < 0):
        _invalid("BAMF_OPERATOR_SESSION_BOUNDS_INVALID")
    run_dir = Path(run_dir).resolve()
    deadline = time.monotonic() + minutes * 60
    visits = accepted = rejected = 0
    status = "TIME_LIMIT"
    with bamf_operator_lock(run_dir):
        while time.monotonic() < deadline and (not max_visits or visits < max_visits):
            outcome = _visit(run_dir, reserve_gib)
            if outcome == "COMPLETE":
                status = "FOUNDATION_COMPLETE"
                break
            visits += 1
            if outcome == "REJECTED":
                rejected += 1
                status = "REJECTED_HOLD"
                break
            accepted += 1
        else:
            status = "VISIT_LIMIT" if max_visits and visits >= max_visits else "TIME_LIMIT"
    current = load_accepted_generation(run_dir)
    return BamfOperatorResult(
        status, visits, accepted, rejected, current.generation,
        current.retained_state.optimizer_step)
