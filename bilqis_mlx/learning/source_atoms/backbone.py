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
    _invalid as _invalid_producer_receipt, _issue_from_producer,
)
from .encoding import encode_source_compiled, encode_source_compiled_with_handoffs


class _SourceBackboneProducerSession:
    """Own source h0 and the only legal sequential group-receipt construction."""

    def __init__(self, encoded, handoffs, parameters, compiled):
        self._compiled = compiled
        self._parameters = dict(parameters)
        self._sources = None
        self._feature_schema = None
        self._source_digest = contract_digest(tuple(item.digest for item in handoffs))
        self._topology = ModelTopologySpecV2()
        self._generation = execution_generation_digest(
            parameters, spec=self._topology, extents=compiled.extents)
        self._prefix = contract_digest(compiled.compiled)
        valid = mx.array([[position is not None for position in row]
                          for row in encoded.handles], dtype=mx.bool_)
        self._session = UnadmittedBackboneSession(
            encoded.global_seeds, self._parameters,
            spec=self._topology, extents=compiled.extents,
            scope_ids=mx.zeros(valid.shape, dtype=mx.int32), valid=valid,
            generation=self._generation, prefix_digest=self._prefix)
        self._depth_inputs = ()
        self._receipts = ()

    def _bind_authoritative_inputs(self, sources, feature_schema):
        self._sources = sources
        self._feature_schema = feature_schema

    def _receipt_values(self, result=None):
        if self._sources is None or self._feature_schema is None:
            _invalid_producer_receipt()
        encoded, handoffs = encode_source_compiled_with_handoffs(
            self._compiled, self._parameters, self._sources, self._feature_schema)
        source_digest = contract_digest(tuple(item.digest for item in handoffs))
        topology = ModelTopologySpecV2()
        generation = execution_generation_digest(
            self._parameters, spec=topology, extents=self._compiled.extents)
        prefix = contract_digest(self._compiled.compiled)
        if (source_digest != self._source_digest or topology.digest != self._topology.digest
                or generation != self._generation or prefix != self._prefix):
            _invalid_producer_receipt()
        valid = mx.array([[position is not None for position in row]
                          for row in encoded.handles], dtype=mx.bool_)
        replay = UnadmittedBackboneSession(
            encoded.global_seeds, self._parameters,
            spec=topology, extents=self._compiled.extents,
            scope_ids=mx.zeros(valid.shape, dtype=mx.int32), valid=valid,
            generation=generation, prefix_digest=prefix)
        if result is None:
            if self._receipts or self._session.results:
                _invalid_producer_receipt()
            hidden = encoded.global_seeds
            output = _content_digest(hidden)
            return dict(
                source_id="h0", completed_layer=0, hidden=hidden,
                source_handoff_digest=source_digest, topology_digest=topology.digest,
                generation_digest=generation,
                parameter_tree_digest=replay.parameter_tree_digest,
                prefix_digest=prefix,
                scope_digest=contract_digest((source_digest, prefix, generation)),
                input_digest=source_digest, output_digest=output,
                cache_chain_digest=contract_digest(()),
                numerical_execution_digest=contract_digest((
                    "h0", output, replay.parameter_tree_digest)),
                predecessor_receipt_digest=source_digest,
                motif_disposition=NOT_APPLICABLE, motif_read_position="",
                motif_read_digest=contract_digest(()))
        target = result.group_index
        if (target < 1 or target != len(self._session.results)
                or result is not self._session.results[-1]
                or len(self._depth_inputs) != target - 1):
            _invalid_producer_receipt()
        expected = None
        for group_index in range(1, target + 1):
            if group_index == 1:
                expected = replay.advance()
            else:
                features, view = self._depth_inputs[group_index - 2]
                selected = depth_select(
                    self._receipts[:group_index], features, view)
                expected = replay.advance(next_input=selected)
        fields = (
            "group_index", "layer_start", "layer_end", "parameter_content_digest",
            "full_parameter_tree_digest", "scope_content_digest", "input_content_digest",
            "cache_chain_digest", "predecessor_digest", "execution_digest")
        if (any(getattr(result, name) != getattr(expected, name) for name in fields)
                or _content_digest(result.hidden) != _content_digest(expected.hidden)):
            _invalid_producer_receipt()
        source_id = SOURCE_ORDER[target]
        motif_disposition = NO_HIT if source_id == "g1" else NOT_APPLICABLE
        motif_position = MOTIF_POSITION if source_id == "g1" else ""
        motif_read_digest = (
            contract_digest(("B08_QUARANTINED_NO_HIT", source_digest, prefix,
                             generation, expected.execution_digest, MOTIF_POSITION))
            if source_id == "g1" else contract_digest(()))
        return dict(
            source_id=source_id, completed_layer=expected.layer_end,
            hidden=expected.hidden, source_handoff_digest=source_digest,
            topology_digest=topology.digest, generation_digest=generation,
            parameter_tree_digest=expected.full_parameter_tree_digest,
            prefix_digest=prefix, scope_digest=expected.scope_content_digest,
            input_digest=expected.input_content_digest,
            output_digest=_content_digest(expected.hidden),
            cache_chain_digest=expected.cache_chain_digest,
            numerical_execution_digest=expected.execution_digest,
            predecessor_receipt_digest=self._receipts[-1].receipt_digest,
            motif_disposition=motif_disposition, motif_read_position=motif_position,
            motif_read_digest=motif_read_digest)

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
            self._depth_inputs += ((frame_features, depth_parameters),)
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
    producer = _SourceBackboneProducerSession(encoded, handoffs, parameters, compiled)
    producer._bind_authoritative_inputs(sources, feature_schema)
    producer._receipts = ()
    producer._receipts = (_issue_from_producer(producer),)
    return producer
