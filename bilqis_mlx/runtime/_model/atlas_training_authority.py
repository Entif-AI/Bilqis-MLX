"""Bind one source-owned Factory training batch to the exact B11 source row."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.factory.teaching import content_digest
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.runtime.atlas_training_contracts import BamfTrainingBatch

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ISSUER = object()


def _invalid(reason):
    ErrorBus.raise_(SCHOOL.MODEL_TOPOLOGY.INVALID, reason=reason)


@dataclass(frozen=True, init=False)
class BamfTrainingAuthority:
    release_sha256: str
    generation_binding: str
    training_batch_sha256: str
    delivery_capability: str
    source_row_id: str
    source_row_sha256: str
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_TRAINING_AUTHORITY_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not all(isinstance(value, str) and value for value in (
                    self.delivery_capability, self.source_row_id))
                or not all(isinstance(value, str) and _SHA.fullmatch(value)
                           for value in (self.release_sha256,
                               self.generation_binding,
                               self.training_batch_sha256,
                               self.source_row_sha256))):
            _invalid("B11_TRAINING_AUTHORITY_INVALID")

    @property
    def digest(self):
        payload = {
            "release": self.release_sha256,
            "generation": self.generation_binding,
            "batch": self.training_batch_sha256,
            "capability": self.delivery_capability,
            "row": self.source_row_id,
            "row_sha256": self.source_row_sha256,
        }
        wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(wire.encode()).hexdigest()


def _issue(batch, source):
    authority = object.__new__(BamfTrainingAuthority)
    for name, value in (
        ("release_sha256", batch.release_sha256),
        ("generation_binding", batch.generation_binding),
        ("training_batch_sha256", batch.authority_digest),
        ("delivery_capability", batch.delivery_capability),
        ("source_row_id", source.source_row["id"]),
        ("source_row_sha256", content_digest((source.source_row,))),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


def bind_compiled_training_batch(batch, compiled, sources, feature_schema):
    """Issue B11 input only when Factory delivery and source atom are identical."""
    from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch

    if (type(batch) is not BamfTrainingBatch
            or type(compiled) is not CompiledEncoderInput
            or type(sources) is not tuple or len(sources) != 1
            or type(sources[0]) is not SourceAtomRow
            or type(feature_schema) is not FeatureSchema
            or len(batch.rows) != 1):
        _invalid("B11_TRAINING_AUTHORITY_INPUT_INVALID")
    batch.__post_init__()
    provenance = batch.rows[0].provenance
    source = sources[0]
    source_row = source.source_row
    if (content_digest((source_row,)) != batch.delivered_content_sha256
            or source_row.get("id") != provenance.row_id
            or source_row.get("capability") != provenance.capability_id):
        _invalid("B11_TRAINING_SOURCE_ROW_MISMATCH")
    return BamfCompiledBatch(
        compiled, sources, feature_schema, training_authority=_issue(batch, source))
