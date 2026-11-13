"""A12-signed source-export authority for C12 package fixtures."""
from dataclasses import replace
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.runtime.atlas_revalidation import (
    SourceAuthorityKey, SourceAuthorityRegistry, SourceAuthorityScope,
)
from bilqis_mlx.runtime.cognitive_package.staging import authorize_public_export
from bilqis_mlx.semantics.atlas.snapshot_contracts import AtlasArtifactSelection
from bilqis_mlx.semantics.atlas_release_audit import ExportClearanceReceipt
from bilqis_mlx.semantics.cognitive_dependencies import DependencyKind
from bilqis_mlx.semantics.context_eligibility import SourceFrontier
from bilqis_mlx.semantics.domains import contract_digest


PRIVATE = Ed25519PrivateKey.from_private_bytes(bytes.fromhex("29" * 32))
PUBLIC = PRIVATE.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
OWNER = "fixture:a12-source-owner"
REGISTRY = SourceAuthorityRegistry((
    SourceAuthorityKey(
        OWNER, PUBLIC,
        (SourceAuthorityScope(DependencyKind.ARTIFACT, "a12-export:"),),
    ),
))


def selection():
    path = Path(__file__).resolve().parents[3] / "semantics" / "atlas_source_pins_v1.json"
    entry = json.loads(path.read_text())["entries"][0]
    return AtlasArtifactSelection(
        "fixture-atlas", entry["bundle_id"], entry["release_sha256"],
        entry["source_bundle_id"])


def frontier():
    return SourceFrontier(2, 4, ())


def receipt(source, *, exported=None, private=(), revoked=(), lineage=()):
    selected = selection()
    current = frontier()
    exported = (
        tuple(sorted(artifact.digest for artifact in source.artifacts))
        if exported is None else tuple(sorted(exported))
    )
    value = ExportClearanceReceipt(
        OWNER,
        selected.bundle_id,
        selected.release_sha256,
        selected.source_bundle_id,
        contract_digest(current),
        current.rights_epoch,
        current.correction_generation,
        exported,
        tuple(sorted(private)),
        tuple(sorted(revoked)),
        tuple(sorted(lineage)),
        "0" * 128,
    )
    return replace(value, signature_hex=PRIVATE.sign(value.signing_bytes()).hex())


def grant(source, *, exported=None, private=(), revoked=(), lineage=()):
    return authorize_public_export(
        source,
        receipt(
            source, exported=exported, private=private, revoked=revoked,
            lineage=lineage),
        selection(),
        frontier(),
        REGISTRY,
    )
