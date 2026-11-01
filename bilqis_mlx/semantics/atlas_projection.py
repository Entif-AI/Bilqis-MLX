"""Historical Atlas projection API; implementation lives in cohesive source owners."""
from __future__ import annotations
from bilqis_mlx.errors import ErrorBus
from bilqis_mlx.errors import SCHOOL
from bilqis_mlx.errors import SEMANTIC_COVERAGE
from bilqis_mlx.vocabulary_growth import digest as semantic_digest
from bisect import bisect_left
from collections.abc import Mapping
from dataclasses import asdict
from dataclasses import dataclass
from lib.ithkuil.src.skos.canonical import canonicalize
from lib.ithkuil.src.skos.coverage_schema import validate_coverage_receipt
from lib.ithkuil.src.skos.errors import ProfileError
from lib.ithkuil.src.skos.publication import json_bytes
from lib.ithkuil.src.skos.rdf_read import read_canonical_graph
from pathlib import Path
from rdflib import BNode
from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import DCTERMS
from rdflib.namespace import RDF
from rdflib.namespace import SKOS
from typing import NoReturn
import hashlib
import json
import os
import re
import shutil
import tempfile
from .atlas_projection_parts.common import (
    ATLAS_ARTIFACT_SCHEMA,
    ATLAS_CONCEPT_RECORD_SCHEMA,
    ATLAS_MANIFEST_SCHEMA,
    ATLAS_RELATION_RECORD_SCHEMA,
    ATLAS_RELEASE_SCHEMA,
    ATLAS_SNAPSHOT_SCHEMA,
    ATLAS_VALIDATION_SCHEMA,
    ATLAS_WITHHELD_RECORD_SCHEMA,
    BANK_SIZE,
    CONFORMANCE_SCHEMA,
    COVERAGE_SCHEMA,
    GATE_VERSIONS,
    HEX64,
    NATIVE_REGISTRY_HEADER_COLUMNS,
    NATIVE_REGISTRY_IDENTITY_COLUMN,
    NATIVE_REGISTRY_MIN_ROWS,
    NATIVE_REGISTRY_SYMBOL_COLUMN,
    REQUIRED_BUNDLE_FILES,
    REQUIRED_GATES,
    SHAPE_POLICY,
    _canonical_bytes,
    _canonical_line,
    _digest,
    _fail,
)
from .atlas_projection_parts.concepts import (
    AbiEntry,
    AtlasConcept,
    AtlasLabel,
    AtlasRealization,
    AtlasRelation,
    CorpusCoverageRow,
    FormalDomainBinding,
    HeldMapping,
    SourceLocus,
    SourceRecordRef,
)
from .atlas_projection_parts.releases import (
    AtlasArtifactReceipt,
    AtlasCounts,
    AtlasRelease,
    ReleaseValidation,
)
from .atlas_projection_parts.snapshots import (
    FrozenAtlasConcept,
    FrozenAtlasRelation,
    FrozenAtlasSnapshot,
)
from .atlas_projection_parts.abi import (
    _build_abi_entries,
    _json_input,
    _prior_abi,
    _validate_abi_entries,
)
from .atlas_projection_parts.coverage import (
    _coverage_record,
    _validate_source_census,
)
from .atlas_projection_parts.bundle import (
    _validated_gates,
    _verify_bundle,
)
from .atlas_projection_parts.rdf import (
    _concept,
    _concept_kind,
    _locus,
    _stable_term,
)
from .atlas_projection_parts.compiler import (
    _normalize_bindings,
    compile_atlas_release,
)
from .atlas_projection_parts.validation import (
    validate_atlas_release,
)
from .atlas_projection_parts.artifacts import (
    _artifact_payloads,
)
from .atlas_projection_parts.persistence import (
    _sync_directory,
    _verify_persisted,
    persist_atlas_release,
)

def load_atlas_snapshot(
    bundle_dir: str | Path,
    *,
    expected_bundle_id: str | None = None,
    expected_release_sha256: str | None = None,
    expected_source_bundle_id: str | None = None,
) -> FrozenAtlasSnapshot:
    """Compatibility facade for the frozen snapshot reader."""
    from .atlas_snapshot import load_atlas_snapshot as _load_atlas_snapshot
    return _load_atlas_snapshot(
        bundle_dir,
        expected_bundle_id=expected_bundle_id,
        expected_release_sha256=expected_release_sha256,
        expected_source_bundle_id=expected_source_bundle_id,
    )

# Preserve historical pickle and public type identity.
for _record in (
    SourceRecordRef,
    AtlasLabel,
    AtlasRealization,
    AtlasRelation,
    SourceLocus,
    AtlasConcept,
    HeldMapping,
    FormalDomainBinding,
    AbiEntry,
    CorpusCoverageRow,
    AtlasCounts,
    AtlasRelease,
    ReleaseValidation,
    AtlasArtifactReceipt,
    FrozenAtlasConcept,
    FrozenAtlasRelation,
    FrozenAtlasSnapshot,
):
    _record.__module__ = __name__
