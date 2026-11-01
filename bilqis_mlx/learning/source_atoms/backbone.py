"""B11 execution from replayed A05/A01 source inputs.

The numerical precursor remains available for bounded equation tests. The producer
session below is the execution-owned source for B05 boundary receipts; it never
authorizes a B08 motif hit or claims retained-generation custody.
"""
import mlx.core as mx

from ...runtime.backbone_group_numerical import UnadmittedBackboneSession
from ...runtime.backbone_identity import execution_generation_digest
from ...runtime.block_attnres import depth_select
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from ...semantics.domains import contract_digest
from .backbone_receipts import _invalid as _invalid_producer_receipt, _issue_from_producer
from .encoding import encode_source_compiled, encode_source_compiled_with_handoffs


class _SourceBackboneProducerSession:
    """Own source h0 and the only legal sequential group-receipt construction."""

    def __init__(self, encoded, handoffs, parameters, compiled):
        self._source_digest = contract_digest(tuple(item.digest for item in handoffs))
        self._topology = ModelTopologySpecV2()
        self._generation = execution_generation_digest(
            parameters, spec=self._topology, extents=compiled.extents)
        self._prefix = contract_digest(compiled.compiled)
        valid = mx.array([[position is not None for position in row]
                          for row in encoded.handles], dtype=mx.bool_)
        self._session = UnadmittedBackboneSession(
            encoded.global_seeds, parameters,
            spec=self._topology, extents=compiled.extents,
            scope_ids=mx.zeros(valid.shape, dtype=mx.int32), valid=valid,
            generation=self._generation, prefix_digest=self._prefix)
        self._receipts = ()
        self._receipts = (_issue_from_producer(self),)

    @property
    def receipts(self):
        return self._receipts

    def advance(self, frame_features=None, depth_parameters=None):
        completed = len(self._session.results)
        if completed:
            if frame_features is None or depth_parameters is None:
                _invalid_producer_receipt()
            selected = depth_select(self._receipts, frame_features, depth_parameters)
            result = self._session.advance(next_input=selected)
        else:
            if frame_features is not None or depth_parameters is not None:
                _invalid_producer_receipt()
            result = self._session.advance()
        receipt = _issue_from_producer(self, result)
        self._receipts += (receipt,)
        return receipt


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


def start_source_backbone_producer(
    compiled, parameters, sources, feature_schema,
):
    """Create the B11 producer only by replaying and revalidating actual source rows."""
    encoded, handoffs = encode_source_compiled_with_handoffs(
        compiled, parameters, sources, feature_schema)
    return _SourceBackboneProducerSession(encoded, handoffs, parameters, compiled)
