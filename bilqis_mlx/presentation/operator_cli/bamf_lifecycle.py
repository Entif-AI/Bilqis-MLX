"""C11/C16 BAMF v2 create, dry-run and resume operator boundary."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from bilqis_mlx.runtime.model_topology_v2 import ModelTopologySpecV2
from bilqis_mlx.semantics.atlas.snapshot import AtlasArtifactIdentity
from .bamf_lifecycle_inputs import (
    atlas_manifest_identity, foundation_hyperparameters, fresh_target, invalid,
    source_foundation, validate_foundation_authority,
)


SCHEMA = "bilqis.bamf.operator-lifecycle/v1"


def _foundation_inputs(args, topology: ModelTopologySpecV2, *, materialize_hp: bool):
    if not isinstance(topology, ModelTopologySpecV2):
        invalid("BAMF_OPERATOR_CREATE_V2_TOPOLOGY_REQUIRED")
    if topology != ModelTopologySpecV2():
        invalid("BAMF_OPERATOR_CREATE_TOPOLOGY_CONFLICT")
    if not args.run_id or type(args.run_seed) is not int or args.run_seed < 0:
        invalid("BAMF_OPERATOR_FOUNDATION_IDENTITY_REQUIRED")
    if args.atlas_release_manifest is None:
        invalid("BAMF_OPERATOR_ATLAS_MANIFEST_REQUIRED")
    lease = None
    if args.admission_policy == "staged":
        if args.atlas_admission_scope is not None:
            from bilqis_mlx.runtime.atlas_admission import validate_atlas_command_request
            validate_atlas_command_request(args)
    else:
        from bilqis_mlx.runtime.atlas_admission import validate_atlas_lease_request
        lease = validate_atlas_lease_request(args)
    hp = foundation_hyperparameters(
        args, required=True, materialize=materialize_hp)
    atlas = atlas_manifest_identity(args.atlas_release_manifest)
    if lease is not None:
        if lease.source_approval.atlas_release_sha256 != atlas.release_sha256:
            invalid("BAMF_OPERATOR_ATLAS_LEASE_MANIFEST_CONFLICT")
        if lease.run_identity.lineage_id != args.run_id:
            invalid("BAMF_OPERATOR_ATLAS_LEASE_RUN_ID_CONFLICT")
        if lease.run_identity.topology_digest != topology.digest:
            invalid("BAMF_OPERATOR_ATLAS_LEASE_TOPOLOGY_CONFLICT")
    source, release, graph = source_foundation()
    return source, release, graph, atlas, hp, lease


def _saved_policy(run_dir: Path) -> str:
    reference = run_dir / "autonomy/atlas-admission/current.json"
    if not reference.exists() and not reference.is_symlink():
        return "staged"
    from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
    from bilqis_mlx.runtime.atlas_admission import read_accepted_atlas_lease
    host = AcceptedRuntimeHost(run_dir)
    lease = read_accepted_atlas_lease(run_dir, source_authority=host.source_authority())
    if lease is None:
        invalid("BAMF_OPERATOR_SAVED_ADMISSION_POLICY_INVALID")
    return lease.admission_policy


def _optimizer_record(value) -> dict:
    record = dict(value) if isinstance(value, dict) else asdict(value)
    record["betas"] = list(record["betas"])
    return record


def _report(*, result, run_id, run_seed, topology, atlas, policy, hp,
            source_prefetch_workers, manifest_sha256=None):
    return {
        "schema": SCHEMA,
        "result": result,
        "run_id": run_id,
        "run_seed": run_seed,
        "model_topology": topology.to_record(),
        "atlas_release_manifest": {
            "sha256": atlas.bundle_id,
            "release_sha256": atlas.release_sha256,
            "source_bundle_id": atlas.source_bundle_id,
            "qualification": "A01_SOURCE_PINNED",
        },
        "admission_policy": policy,
        "optimizer_hyperparameters": _optimizer_record(hp),
        "source_prefetch_workers": source_prefetch_workers,
        "generation_manifest_sha256": manifest_sha256,
        "ready_for_training": result in ("CREATED", "READY_TO_RESUME"),
        "neural_updates": 0,
    }


def _resume(args, requested_topology):
    if args.atlas_admission_scope is not None:
        invalid("BAMF_OPERATOR_RESUME_ATLAS_SCOPE_OVERRIDE_FORBIDDEN")
    from bilqis_mlx.runtime.bamf_bundle import (
        load_bamf_generation_authority, read_accepted_generation_feature_receipt,
    )
    run_dir = Path(args.run_dir).expanduser().resolve()
    pointer = run_dir / "bamf-state.json"
    student, manifest_sha256 = load_bamf_generation_authority(pointer)
    features = read_accepted_generation_feature_receipt(pointer)
    topology = student.topology
    identity = student.run_identity
    if identity is None:
        invalid("BAMF_OPERATOR_RESUME_RUN_IDENTITY_REQUIRED")
    if requested_topology is not None and requested_topology != topology:
        invalid("BAMF_OPERATOR_RESUME_TOPOLOGY_CONFLICT")
    if args.run_id is not None and args.run_id != identity.run_id:
        invalid("BAMF_OPERATOR_RESUME_RUN_ID_CONFLICT")
    if args.run_seed is not None and args.run_seed != identity.run_seed:
        invalid("BAMF_OPERATOR_RESUME_RUN_SEED_CONFLICT")
    requested_hp = foundation_hyperparameters(args, required=False)
    if requested_hp is not None and requested_hp != student.optimizer_hyperparameters:
        invalid("BAMF_OPERATOR_RESUME_OPTIMIZER_CONFLICT")
    atlas = AtlasArtifactIdentity(
        features.source_atlas_bundle_id,
        features.source_release_sha256,
        features.source_source_bundle_id,
    )
    if args.atlas_release_manifest is not None:
        requested_atlas = atlas_manifest_identity(args.atlas_release_manifest)
        if requested_atlas != atlas:
            invalid("BAMF_OPERATOR_RESUME_ATLAS_MANIFEST_CONFLICT")
    policy = _saved_policy(run_dir)
    if args.admission_policy_explicit and args.admission_policy != policy:
        invalid("BAMF_OPERATOR_RESUME_ADMISSION_POLICY_CONFLICT")
    return _report(
        result="READY_TO_RESUME", run_id=identity.run_id,
        run_seed=identity.run_seed, topology=topology, atlas=atlas,
        policy=policy, hp=student.optimizer_hyperparameters,
        source_prefetch_workers=args.source_prefetch_workers,
        manifest_sha256=manifest_sha256,
    )


def bamf_lifecycle(args, topology):
    """Resolve one BAMF v2 lifecycle request without entering the neural loop."""
    if args.resume:
        return _resume(args, topology)
    target = fresh_target(args.run_dir)
    if args.dry_run:
        source, release, graph, atlas, hp, lease = _foundation_inputs(
            args, topology, materialize_hp=False)
        validate_foundation_authority(source, release, graph, atlas)
        return _report(
            result="READY_TO_CREATE", run_id=args.run_id, run_seed=args.run_seed,
            topology=topology, atlas=atlas,
            policy="staged" if lease is None else lease.admission_policy, hp=hp,
            source_prefetch_workers=args.source_prefetch_workers,
        )
    if args.human_run is not True:
        invalid("BAMF_OPERATOR_CREATE_EXPLICIT_HUMAN_REQUEST_REQUIRED")
    source, release, graph, atlas, hp, lease = _foundation_inputs(
        args, topology, materialize_hp=True)
    from bilqis_mlx.runtime.bamf_first_student import (
        BamfFoundationConfig, preflight_bamf_foundation,
    )
    config = BamfFoundationConfig(
        str(source), args.run_id, args.run_seed, graph, atlas, hp)
    receipt = preflight_bamf_foundation(config, release, target)
    if receipt.run_identity.initial_topology_digest != topology.digest:
        invalid("BAMF_OPERATOR_CREATED_TOPOLOGY_DRIFT")
    policy = "staged"
    if lease is not None:
        from bilqis_mlx.runtime.accepted_corrections import AcceptedRuntimeHost
        from bilqis_mlx.runtime.atlas_admission import persist_accepted_atlas_lease
        host = AcceptedRuntimeHost(target)
        persist_accepted_atlas_lease(
            target, lease, source_authority=host.source_authority())
        policy = lease.admission_policy
    return _report(
        result="CREATED", run_id=receipt.run_identity.run_id,
        run_seed=receipt.run_identity.run_seed, topology=topology,
        atlas=receipt.atlas_artifact, policy=policy,
        hp=receipt.optimizer_hyperparameters,
        source_prefetch_workers=args.source_prefetch_workers,
        manifest_sha256=receipt.manifest_sha256,
    )


__all__ = ("SCHEMA", "bamf_lifecycle")
