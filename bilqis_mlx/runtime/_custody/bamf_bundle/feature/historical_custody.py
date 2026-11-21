"""Tensor-thin authenticated custody for accepted BAMF history."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from bilqis_mlx.data_plane import DataPlaneError, data_plane
from bilqis_mlx.learning._retention._atlas_candidate.identity import (
    IDENTITY_SCHEMES,
    LEGACY_IDENTITY_SCHEME,
)
from bilqis_mlx.runtime.checkpoint_outbox import ordinary_outbox_lineage
from bilqis_mlx.runtime.model_topology_v2 import (
    GenerationExtents,
    GenerationProvenance,
    ModelTopologySpecV2,
)

from ..codec import _read_sidecar
from ..records import (
    BAMF_BUNDLE_SCHEMA,
    OBJECTIVE_BOUND_BAMF_BUNDLE_SCHEMA,
    SIDECARS,
    BamfGenerationManifest,
    canonical,
    invalid,
    sha,
    validate_sidecars,
)
from .receipt import is_digest


@dataclass(frozen=True)
class HistoricalBamfBundle:
    """Authenticated historical metadata with no executable tensor payload."""

    manifest: dict
    topology: ModelTopologySpecV2
    extents: GenerationExtents
    provenance: GenerationProvenance
    records: dict
    optimizer_hyperparameters: object
    run_identity: object | None

    @property
    def run_id(self) -> str:
        return self.manifest["run_id"]

    @property
    def generation(self) -> int:
        return self.manifest["generation"]

    @property
    def parent_manifest_sha256(self) -> str | None:
        return self.manifest["parent_manifest_sha256"]

    @property
    def transition(self) -> dict:
        return dict(self.manifest["transition"])

    @property
    def outbox(self) -> tuple:
        return tuple(self.records["outbox"])

    @property
    def correction_frontier(self) -> dict:
        return dict(self.records["correction_frontier"])

    @property
    def teacher_state(self) -> dict:
        return dict(self.records["teacher_state"])

    @property
    def championship_state(self):
        value = self.records.get("championship_state")
        return None if value is None else dict(value)

    @property
    def optimizer_step(self) -> int:
        return self.manifest["optimizer"]["step"]

    @property
    def tensor_identity_sha256(self) -> str:
        return self.manifest["tensors"]["sha256"]


def load_historical_bamf_bundle(
        root: Path, *, expected_manifest_sha256: str) -> HistoricalBamfBundle:
    """Authenticate historical manifest/sidecars/tensor identity without tensor bytes."""
    root = Path(root)
    manifest_path = root / "manifest.json"
    if (root.is_symlink() or not root.is_dir()
            or manifest_path.is_symlink() or not manifest_path.is_file()):
        invalid(DataPlaneError.BUNDLE_ROOT_UNSAFE)
    raw = manifest_path.read_bytes()
    digest = sha(raw)
    if digest != expected_manifest_sha256:
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
    try:
        if data_plane().get_node(digest) != raw:
            invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)
        manifest = BamfGenerationManifest.from_record(json.loads(raw)).to_record()
    except (ValueError, json.JSONDecodeError, KeyError, TypeError):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)

    recorded = set(manifest.get("sidecars", {}))
    optional = {
        "run_identity", "baseline_evidence", "learning_health_state",
        "championship_state",
    }
    if manifest["schema"] in {BAMF_BUNDLE_SCHEMA, OBJECTIVE_BOUND_BAMF_BUNDLE_SCHEMA}:
        optional.add("step_proofs")
    required = set(SIDECARS) - optional
    optimizer = manifest.get("optimizer", {})
    if (not required <= recorded <= set(SIDECARS)
            or set(optimizer) not in (
                {"schema", "step", "hyperparameters"},
                {"schema", "step", "hyperparameters", "identity_scheme"})
            or optimizer.get("identity_scheme", LEGACY_IDENTITY_SCHEME)
               not in IDENTITY_SCHEMES
            or optimizer.get("step") != manifest.get("tensors", {}).get("optimizer_step")):
        invalid()

    records = {name: _read_sidecar(root, manifest["sidecars"][name])
               for name in recorded}
    records.setdefault(
        "step_proofs",
        {"schema": "bilqis.mlx.bamf-step-proofs/v1", "proofs": []},
    )
    tensor = manifest.get("tensors", {})
    legacy_keys = {
        "schema", "filename", "sha256", "optimizer_step",
        "tensor_count", "uncompressed_bytes",
    }
    current_keys = legacy_keys | {"object_sha256"}
    if (not isinstance(tensor, dict)
            or set(tensor) not in (legacy_keys, current_keys)
            or Path(tensor.get("filename", "")).name != tensor.get("filename")
            or not is_digest(tensor.get("sha256"))
            or ("object_sha256" in tensor
                and tensor["object_sha256"] != tensor["sha256"])):
        invalid(DataPlaneError.BUNDLE_PAYLOAD_DRIFT)

    from bilqis_mlx.runtime.atlas_optimizer import AdamWHyperparameters, STATE_SCHEMA
    if optimizer["schema"] != STATE_SCHEMA:
        invalid()
    topology = ModelTopologySpecV2.from_record(manifest["topology"])
    extents = GenerationExtents.from_record(manifest["extents"])
    provenance = GenerationProvenance.from_record(manifest["provenance"])
    validate_sidecars(extents, provenance, records)
    lineage = {"run_id": manifest["run_id"], "generation": manifest["generation"]}
    if not records["outbox"] or not ordinary_outbox_lineage(lineage, list(records["outbox"])):
        invalid("BAMF_OUTBOX_LINEAGE_INVALID")
    hp_record = dict(optimizer["hyperparameters"])
    hp_record["betas"] = tuple(hp_record.get("betas", ()))
    hp = AdamWHyperparameters(**hp_record)
    run_identity = None
    if "run_identity" in records:
        from ..genesis import BamfRunIdentity
        run_identity = BamfRunIdentity.from_record(records["run_identity"])
        if run_identity.run_id != manifest["run_id"]:
            invalid("BAMF_RUN_IDENTITY_DRIFT")
    return HistoricalBamfBundle(
        manifest, topology, extents, provenance, records, hp, run_identity)
