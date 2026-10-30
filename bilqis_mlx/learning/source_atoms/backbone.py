"""B11 numerical execution from replayed A05/A01 source inputs.

This is an unadmitted execution precursor. It does not issue B05 producer
receipts, authorize motif hits, or establish retained-generation custody.
"""
import mlx.core as mx

from ...runtime.backbone_group_numerical import UnadmittedBackboneSession
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from ...semantics.domains import contract_digest
from .encoding import encode_source_compiled


def start_source_backbone_numerical(compiled, parameters, sources, feature_schema):
    """Compute h0 and input coordinates internally before constructing a session.

    The accepted source encoder replays source, rights, prefix, feature and full
    B01 parameter checks. Each compiled row is one independent source sequence.
    Extent and prefix digests are observations, not B13 generation credentials.
    """
    encoding = encode_source_compiled(compiled, parameters, sources, feature_schema)
    valid = mx.array([[position is not None for position in row]
                      for row in encoding.handles], dtype=mx.bool_)
    return UnadmittedBackboneSession(
        encoding.global_seeds, parameters,
        spec=ModelTopologySpecV2(), extents=compiled.extents,
        scope_ids=mx.zeros(valid.shape, dtype=mx.int32), valid=valid,
        generation=compiled.extents.digest,
        prefix_digest=contract_digest(compiled.compiled))
