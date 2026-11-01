"""B11 execution from replayed A05/A01 source inputs.

The numerical precursor remains available for bounded equation tests. The producer
session below is the execution-owned source for B05 boundary receipts; it never
authorizes a B08 motif hit or claims retained-generation custody.
"""
import mlx.core as mx

from ...runtime.backbone_group_numerical import (
    UnadmittedBackboneSession, _content_digest,
)
from ...runtime.backbone_identity import execution_generation_digest
from ...runtime.block_attnres import SOURCE_ORDER, depth_select
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from ...semantics.domains import contract_digest
from .backbone_receipts import (
    MOTIF_POSITION, NO_HIT, NOT_APPLICABLE,
    ProducedBackboneBoundary, _invalid as _invalid_producer_receipt,
    _issue_receipt, require_produced_backbone_boundary,
)
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
        output = _content_digest(encoded.global_seeds)
        base = dict(
            source_id="h0", completed_layer=0, hidden=encoded.global_seeds,
            source_handoff_digest=self._source_digest,
            topology_digest=self._topology.digest, generation_digest=self._generation,
            parameter_tree_digest=self._session.parameter_tree_digest,
            prefix_digest=self._prefix,
            scope_digest=contract_digest((self._source_digest, self._prefix, self._generation)),
            input_digest=self._source_digest, output_digest=output,
            cache_chain_digest=contract_digest(()),
            numerical_execution_digest=contract_digest(("h0", output, self._session.parameter_tree_digest)),
            predecessor_receipt_digest=self._source_digest,
            motif_disposition=NOT_APPLICABLE, motif_read_position="",
            motif_read_digest=contract_digest(()),
        )
        self._receipts = (_issue_receipt(**base),)

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
        source_id = SOURCE_ORDER[result.group_index]
        prior = self._receipts[-1]
        hidden = result.hidden
        motif_disposition, motif_position = NOT_APPLICABLE, ""
        motif_read_digest = contract_digest(())
        if source_id == "g1":
            motif_disposition, motif_position = NO_HIT, MOTIF_POSITION
            motif_read_digest = contract_digest((
                "B08_QUARANTINED_NO_HIT", self._source_digest, self._prefix,
                self._generation, result.execution_digest, MOTIF_POSITION,
            ))
        values = dict(
            source_id=source_id, completed_layer=result.layer_end, hidden=hidden,
            source_handoff_digest=self._source_digest,
            topology_digest=self._topology.digest, generation_digest=self._generation,
            parameter_tree_digest=result.full_parameter_tree_digest,
            prefix_digest=self._prefix, scope_digest=result.scope_content_digest,
            input_digest=result.input_content_digest,
            output_digest=_content_digest(hidden),
            cache_chain_digest=result.cache_chain_digest,
            numerical_execution_digest=result.execution_digest,
            predecessor_receipt_digest=prior.receipt_digest,
            motif_disposition=motif_disposition,
            motif_read_position=motif_position,
            motif_read_digest=motif_read_digest,
        )
        receipt = _issue_receipt(**values)
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
