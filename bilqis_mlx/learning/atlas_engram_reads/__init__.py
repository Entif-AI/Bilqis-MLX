"""Stable motif-read API; the public boundary remains quarantined."""
from .records import (
    READ_SCHEMA, POSITION_SCHEMA, WIDTH, MOTIF_WIDTH, READ_TENSOR_RANK,
    FEATURE_AXIS, BATCH_PREFIX_AXES, DISPOSITIONS, _SHA, _invalid,
    MotifReadPosition, MotifReadResult,
)
from .source import schema_source_handle, schema_evidence_digest, _schema_grant_live
from .numerical import _read_motif_unqualified_candidate
from .guarded import read_motif

for _export in (
    MotifReadPosition, MotifReadResult, schema_source_handle,
    schema_evidence_digest, _schema_grant_live,
    _read_motif_unqualified_candidate, read_motif,
):
    _export.__module__ = __name__
del _export
