"""Bind one source-owned Factory training batch to the exact B11 source row."""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.source_execution import source_content_digest
from bilqis_mlx.learning.frame_encoder import CompiledEncoderInput
from bilqis_mlx.learning.source_atoms import SourceAtomRow
from bilqis_mlx.semantics.atlas_features import FeatureSchema
from bilqis_mlx.semantics.cognitive_dependencies import DependencyRef
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
    source_family_id: str
    episode_id: str
    immediate_dependencies: tuple[DependencyRef, ...]
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid("B11_TRAINING_AUTHORITY_CALLER_CONSTRUCTION_FORBIDDEN")

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or not all(isinstance(value, str) and value for value in (
                    self.delivery_capability, self.source_row_id,
                    self.source_family_id, self.episode_id))
                or not all(isinstance(value, str) and _SHA.fullmatch(value)
                           for value in (self.release_sha256,
                               self.generation_binding,
                               self.training_batch_sha256,
                               self.source_row_sha256))
                or type(self.immediate_dependencies) is not tuple
                or not self.immediate_dependencies
                or any(not isinstance(item, DependencyRef)
                       for item in self.immediate_dependencies)
                or self.immediate_dependencies != tuple(sorted(
                    set(self.immediate_dependencies)))):
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
            "source_family": self.source_family_id,
            "episode": self.episode_id,
            "immediate_dependencies": tuple(
                (ref.kind.value, ref.key)
                for ref in self.immediate_dependencies),
        }
        wire = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(wire.encode()).hexdigest()


def _issue(batch, source, provenance):
    if (not provenance.source_family_id or not provenance.episode_id
            or not provenance.immediate_dependencies):
        _invalid("B11_TRAINING_SOURCE_INDEPENDENCE_REQUIRED")
    authority = object.__new__(BamfTrainingAuthority)
    for name, value in (
        ("release_sha256", batch.release_sha256),
        ("generation_binding", batch.generation_binding),
        ("training_batch_sha256", batch.authority_digest),
        ("delivery_capability", batch.delivery_capability),
        ("source_row_id", source.source_row["id"]),
        ("source_row_sha256", provenance.source_row_content_sha256),
        ("source_family_id", provenance.source_family_id),
        ("episode_id", provenance.episode_id),
        ("immediate_dependencies", provenance.immediate_dependencies),
        ("_issuance", _ISSUER),
    ):
        object.__setattr__(authority, name, value)
    authority.__post_init__()
    return authority


def extend_training_dependencies(
    authority: BamfTrainingAuthority,
    dependencies: tuple[DependencyRef, ...],
) -> BamfTrainingAuthority:
    """Return the same source authority with execution-observed C09 inputs added.

    C02 can freeze source-owned premises before B11 runs, but retained motifs and
    correction-owned artifacts are only knowable after the real forward path has
    executed.  The B11 owner therefore extends, never replaces, that frontier.
    """
    if (type(authority) is not BamfTrainingAuthority
            or type(dependencies) is not tuple
            or any(not isinstance(item, DependencyRef) for item in dependencies)):
        _invalid("B11_TRAINING_EXECUTION_DEPENDENCIES_INVALID")
    authority.__post_init__()
    merged = tuple(sorted(set((*authority.immediate_dependencies, *dependencies))))
    if merged == authority.immediate_dependencies:
        return authority
    extended = object.__new__(BamfTrainingAuthority)
    for name in (
        "release_sha256", "generation_binding", "training_batch_sha256",
        "delivery_capability", "source_row_id", "source_row_sha256",
        "source_family_id", "episode_id",
    ):
        object.__setattr__(extended, name, getattr(authority, name))
    object.__setattr__(extended, "immediate_dependencies", merged)
    object.__setattr__(extended, "_issuance", _ISSUER)
    extended.__post_init__()
    return extended


def bind_compiled_training_batch(batch, compiled, sources, feature_schema, *, row_index=0):
    """Issue one B11 row from an exact source-owned C02 delivery batch."""
    from bilqis_mlx.runtime.atlas_model_contracts import BamfCompiledBatch

    if (type(batch) is not BamfTrainingBatch
            or type(compiled) is not CompiledEncoderInput
            or type(sources) is not tuple or len(sources) != 1
            or type(sources[0]) is not SourceAtomRow
            or type(feature_schema) is not FeatureSchema
            or type(row_index) is not int
            or not 0 <= row_index < len(batch.rows)):
        _invalid("B11_TRAINING_AUTHORITY_INPUT_INVALID")
    batch.__post_init__()
    provenance = batch.rows[row_index].provenance
    source = sources[0]
    source_row = source.source_row
    if (source_content_digest((source_row,)) != provenance.source_row_content_sha256
            or source_row.get("id") != provenance.row_id
            or source_row.get("capability") != provenance.capability_id):
        _invalid("B11_TRAINING_SOURCE_ROW_MISMATCH")
    return BamfCompiledBatch(
        compiled, sources, feature_schema,
        training_authority=_issue(batch, source, provenance),
        visit_provenance=provenance.visit)
