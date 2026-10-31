"""Canonical logical paths for physically compartmentalized source owners."""
from pathlib import Path
from types import MappingProxyType


LOGICAL_SOURCE_COMPARTMENTS = (
    (("bilqis_mlx", "factory", "curriculum"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "factory", "lifecycle"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "factory", "sources"), ("bilqis_mlx", "factory")),
    (("bilqis_mlx", "learning", "_championship"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_engram"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_retention"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_salience"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "learning", "_teaching"), ("bilqis_mlx", "learning")),
    (("bilqis_mlx", "runtime", "_admission"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_batch"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_capability"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_correction"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_custody"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_depth"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_model"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_operator"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_projection"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_source"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "runtime", "_teacher"), ("bilqis_mlx", "runtime")),
    (("bilqis_mlx", "semantics", "foundation"), ("bilqis_mlx", "semantics")),
)

LOGICAL_SOURCE_ALIASES = MappingProxyType({
    "bilqis_mlx/runtime/_admission/atlas_lease_contracts.py":
        "bilqis_mlx/runtime/atlas_admission.py",
    "bilqis_mlx/runtime/_admission/atlas_lease_storage.py":
        "bilqis_mlx/runtime/atlas_admission.py",
    "bilqis_mlx/runtime/_batch/atlas_training_contracts.py":
        "bilqis_mlx/runtime/atlas_training_adapter.py",
    "bilqis_mlx/runtime/_batch/atlas_training_delivery.py":
        "bilqis_mlx/runtime/atlas_training_adapter.py",
    "bilqis_mlx/runtime/_batch/fixed_frontier_evidence.py":
        "bilqis_mlx/runtime/candidate_evidence.py",
    "bilqis_mlx/runtime/_batch/retention_support.py":
        "bilqis_mlx/runtime/candidate_evidence.py",
    "bilqis_mlx/runtime/_capability/capability_evaluation.py":
        "bilqis_mlx/runtime/capability_retention.py",
    "bilqis_mlx/runtime/_correction/atlas_correction_branches.py":
        "bilqis_mlx/runtime/atlas_requalification.py",
    "bilqis_mlx/runtime/_correction/atlas_requalification_contracts.py":
        "bilqis_mlx/runtime/atlas_requalification.py",
    "bilqis_mlx/runtime/_correction/atlas_stale_replay.py":
        "bilqis_mlx/runtime/atlas_temporal_revalidation.py",
    "bilqis_mlx/runtime/_correction/atlas_temporal_contracts.py":
        "bilqis_mlx/runtime/atlas_temporal_revalidation.py",
    "bilqis_mlx/runtime/_custody/championship_source_repair.py":
        "bilqis_mlx/runtime/reconciliation.py",
    "bilqis_mlx/runtime/_custody/resume_metadata.py":
        "bilqis_mlx/runtime/reconciliation.py",
    "bilqis_mlx/runtime/_depth/depth_contracts.py":
        "bilqis_mlx/runtime/block_attnres.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_contracts.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_events.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_store.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_outbox_corrections.py":
        "bilqis_mlx/runtime/akasha_outbox.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_contracts.py":
        "bilqis_mlx/runtime/akasha_staging.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_queries.py":
        "bilqis_mlx/runtime/akasha_staging.py",
    "bilqis_mlx/runtime/_projection/akasha_staging_store.py":
        "bilqis_mlx/runtime/akasha_staging.py",
})


def logical_source_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root)
    alias = LOGICAL_SOURCE_ALIASES.get(relative.as_posix())
    if alias is not None:
        return alias
    parts = relative.parts
    for physical, canonical in LOGICAL_SOURCE_COMPARTMENTS:
        if parts[:3] == physical:
            return Path(*canonical, *parts[3:]).as_posix()
    return relative.as_posix()
