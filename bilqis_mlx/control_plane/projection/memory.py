"""Project authenticated motif allocation without hydrating learner tensors."""
from pathlib import Path

from bilqis_mlx.mission_control import CoverageState, MemorySnapshotV2
from bilqis_mlx.learning.atlas_engram import INITIAL_MOTIF_CAPACITY
from bilqis_mlx.runtime.bamf_bundle.motif.codec import snapshot_from_record

from ..native_contracts import invalid, missing_value, record_meta, run_ref
from ..native_custody import _read_bound_json


def accepted_memory_records(root: Path, generation):
    manifest = generation.manifest
    binding = manifest["sidecars"].get("motif_allocation")
    if binding is None:
        return ()
    raw = _read_bound_json(
        root / "bamf-bundles" / generation.manifest_sha256, binding,
        reason="CONTROL_PLANE_NATIVE_MEMORY_BINDING_DRIFT")
    snapshot = snapshot_from_record(raw)
    extents = manifest["extents"]
    run = run_ref(generation)
    if (snapshot.manifest.digest != extents["motif_key_map_digest"]
            or snapshot.manifest.capacity // INITIAL_MOTIF_CAPACITY != extents["motif_page_count"]
            or snapshot.manifest.semantic_release != run.semantic_release_sha256):
        invalid("CONTROL_PLANE_NATIVE_MEMORY_ALLOCATION_DRIFT")
    return (MemorySnapshotV2(
        record_meta(f"memory:{run.run_id}:{run.generation}", run, generation,
                    coverage=CoverageState.PARTIAL,
                    evidence_refs=(f"motif-allocation:{binding['sha256']}",)),
        *(missing_value() for _ in range(5)),
        len(snapshot.manifest.slots), snapshot.manifest.capacity,
        len(snapshot.pending_keys), len(snapshot.aliases),
        snapshot.digest, snapshot.manifest.digest),)
