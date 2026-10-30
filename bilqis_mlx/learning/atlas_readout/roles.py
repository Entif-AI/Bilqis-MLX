"""Source-derived frame domains and fixed-occurrence shared ROLE logits."""
from typing import Mapping
import mlx.core as mx
from bilqis_mlx.learning.frame_embeddings.composition import _factor_vector
from bilqis_mlx.semantics.atlas_features import AtlasFeatures, _factor_overflow
from bilqis_mlx.semantics.frame_schema import FrameSchema
from bilqis_mlx.semantics.released_frame_schemas import VerifiedReleasedFrameSchemas
from .records import (
    FRAME_DOMAIN_SCHEMA, FRAME_MODALITY, ROLE_MODALITY,
    FrameOutputDomain, RoleCandidate, TypedHeadLogits, invalid, validate_hidden,
)


def _validate_domain(domain, features):
    if (type(domain) is not FrameOutputDomain
            or domain.schema_version != FRAME_DOMAIN_SCHEMA
            or domain.modality_id != FRAME_MODALITY
            or type(features) is not AtlasFeatures
            or features.digest != domain.feature_digest
            or type(domain.schema) is not FrameSchema
            or type(domain.released_schemas) is not VerifiedReleasedFrameSchemas):
        invalid()
    released = domain.released_schemas
    manifest = released.manifest
    released.__post_init__()
    released.require_schema(domain.schema,
                            released.lookup(domain.schema.schema_id, domain.schema.revision))
    if ((features.semantic_release, features.atlas_bundle_id, features.source_bundle_id)
            != (manifest.semantic_release, manifest.atlas_bundle_id, manifest.source_bundle_id)):
        invalid()
    roles = dict(features.role_map)
    if (len(roles) != len(features.role_map)
            or any(role.role_id not in roles for role in domain.schema.roles)
            or any(type(row) is not int or not 0 <= row < 512 for row in roles.values())):
        invalid()


def compile_frame_output(schema, released_schemas, features):
    """Retain source-verified body and factor identity, not a new schema registry."""
    if type(features) is not AtlasFeatures:
        invalid()
    domain = FrameOutputDomain(schema, released_schemas, features.digest)
    _validate_domain(domain, features)
    return domain


def role_logits(hidden, domain, occurrence, parameters, features):
    """DecisionSpec fixes occurrence; only schema-legal role identities compete."""
    validate_hidden(hidden)
    _validate_domain(domain, features)
    if (type(occurrence) is not int or occurrence < 0
            or not isinstance(parameters, Mapping)):
        invalid()
    for name, shape in (('readout.role_query', (128, 768)),
                        ('features.role', (512, 128))):
        value = parameters.get(name)
        if (not isinstance(value, mx.array) or value.shape != shape
                or value.dtype != mx.float32):
            invalid()
    candidates = tuple(RoleCandidate(domain.schema.schema_id, domain.schema.revision,
                                     role.role_id, occurrence)
                       for role in domain.schema.roles if occurrence < role.max_cardinality)
    if not candidates:
        invalid()
    role_map = dict(features.role_map)
    vectors = []
    for candidate in candidates:
        row = role_map[candidate.role_id]
        overflow = (_factor_overflow('role', candidate.role_id)
                    if row == 0 and candidate.role_id != 'UNKNOWN' else None)
        vectors.append(_factor_vector(parameters['features.role'], row, overflow))
    query = hidden @ parameters['readout.role_query'].T
    logits = query @ mx.stack(vectors).T
    return TypedHeadLogits(logits, candidates, ROLE_MODALITY, features.semantic_release)
