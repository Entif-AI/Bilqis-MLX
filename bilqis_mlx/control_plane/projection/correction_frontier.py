"""Project the authenticated accepted correction sidecar without replaying C09."""
from bilqis_mlx.mission_control import CorrectionFrontierSnapshot, CoverageState
from bilqis_mlx.mission_control.contracts.model import is_wire_integer

from ..native_contracts import invalid, is_digest, record_meta, run_ref


def accepted_correction_frontier(generation):
    source = generation.correction_frontier
    if source.get("schema") != "bilqis.mlx.bamf-correction-frontier/v1":
        return ()
    run = run_ref(generation)
    entries = source.get("frontier")
    coordinate = source.get("correction_generation")
    provenance = generation.manifest["provenance"]
    digest = generation.manifest["sidecars"]["correction_frontier"]["sha256"]
    if (not isinstance(entries, (list, dict))
            or not is_wire_integer(coordinate) or coordinate < 0
            or source.get("source_identity") != provenance.get("source_identity")
            or source.get("release_digest") != run.semantic_release_sha256
            or not is_digest(digest)):
        invalid("CONTROL_PLANE_NATIVE_CORRECTION_FRONTIER_DRIFT")
    return (CorrectionFrontierSnapshot(
        record_meta(f"correction-frontier:{run.run_id}:{run.generation}", run,
                    generation, coverage=CoverageState.PARTIAL,
                    evidence_refs=(f"correction-frontier:{digest}",)),
        coordinate, len(entries), digest),)
