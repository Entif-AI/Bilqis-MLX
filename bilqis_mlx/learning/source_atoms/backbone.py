"""B11 execution from replayed A05/A01 source inputs.

The numerical precursor remains available for bounded equation tests. The producer
session below is the execution-owned source for B05 boundary receipts; it never
authorizes a B08 motif hit or claims retained-generation custody.
"""
from dataclasses import InitVar, dataclass
import mlx.core as mx

from ...errors import ErrorBus, SCHOOL
from ...runtime.backbone_group_numerical import (
    UnadmittedBackboneSession, _content_digest,
)
from ...runtime.block_attnres import SOURCE_ORDER, COMPLETED_LAYERS
from ...runtime.model_topology_v2 import ModelTopologySpecV2
from ...semantics.domains import contract_digest
from .encoding import encode_source_compiled, encode_source_compiled_with_handoffs


_PRODUCER_SEAL = object()
_NO_HIT = "NO_HIT_QUARANTINED"
_NA = "NOT_APPLICABLE"
_MOTIF_POSITION = "AFTER_LAYER_4_BEFORE_CAPTURE"
_HIDDEN_FRAME_RANK = 3
_SHA256_HEX_LENGTH = 64


def _invalid_producer_receipt():
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _receipt_projection(values):
    return (
        "bilqis.mlx.backbone-boundary-receipt/v1", values["source_id"],
        values["completed_layer"], values["source_handoff_digest"],
        values["topology_digest"], values["generation_digest"],
        values["parameter_tree_digest"], values["prefix_digest"],
        values["scope_digest"], values["input_digest"], values["output_digest"],
        values["cache_chain_digest"], values["numerical_execution_digest"],
        values["predecessor_receipt_digest"], values["motif_disposition"],
        values["motif_read_position"],
    )


@dataclass(frozen=True)
class ProducedBackboneBoundary:
    """Execution-owned B11 boundary receipt consumed by the public B05 selector."""

    source_id: str
    completed_layer: int
    hidden: mx.array
    source_handoff_digest: str
    topology_digest: str
    generation_digest: str
    parameter_tree_digest: str
    prefix_digest: str
    scope_digest: str
    input_digest: str
    output_digest: str
    cache_chain_digest: str
    numerical_execution_digest: str
    predecessor_receipt_digest: str
    motif_disposition: str
    motif_read_position: str
    receipt_digest: str
    _seal: InitVar[object]

    def _validate_contents(self):
        expected_index = SOURCE_ORDER.index(self.source_id) if self.source_id in SOURCE_ORDER else -1
        digests = (
            self.source_handoff_digest, self.topology_digest, self.generation_digest,
            self.parameter_tree_digest, self.prefix_digest, self.scope_digest,
            self.input_digest, self.output_digest, self.cache_chain_digest,
            self.numerical_execution_digest, self.predecessor_receipt_digest,
            self.receipt_digest,
        )
        values = self.__dict__
        expected_motif = _NO_HIT if self.source_id == "g1" else _NA
        expected_position = _MOTIF_POSITION if self.source_id == "g1" else ""
        if (expected_index < 0
                or self.completed_layer != COMPLETED_LAYERS[expected_index]
                or type(self.hidden) is not mx.array or self.hidden.dtype != mx.float32
                or self.hidden.ndim != _HIDDEN_FRAME_RANK
                or any(len(value) != _SHA256_HEX_LENGTH for value in digests)
                or self.output_digest != _content_digest(self.hidden)
                or self.motif_disposition != expected_motif
                or self.motif_read_position != expected_position
                or self.receipt_digest != contract_digest(_receipt_projection(values))):
            _invalid_producer_receipt()

    def __post_init__(self, _seal):
        if _seal is not _PRODUCER_SEAL:
            _invalid_producer_receipt()
        self._validate_contents()


def _make_receipt(**values):
    receipt_digest = contract_digest(_receipt_projection(values))
    return ProducedBackboneBoundary(
        **values, receipt_digest=receipt_digest, _seal=_PRODUCER_SEAL)


class _SourceBackboneProducerSession:
    """Own source h0 and the only legal sequential group-receipt construction."""

    def __init__(self, encoded, handoffs, parameters, compiled):
        self._source_digest = contract_digest(tuple(item.digest for item in handoffs))
        self._topology = ModelTopologySpecV2()
        self._generation = compiled.extents.digest
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
            motif_disposition=_NA, motif_read_position="",
        )
        self._receipts = (_make_receipt(**base),)

    @property
    def receipts(self):
        return self._receipts

    def advance(self):
        result = self._session.advance()
        source_id = SOURCE_ORDER[result.group_index]
        prior = self._receipts[-1]
        values = dict(
            source_id=source_id, completed_layer=result.layer_end, hidden=result.hidden,
            source_handoff_digest=self._source_digest,
            topology_digest=self._topology.digest, generation_digest=self._generation,
            parameter_tree_digest=result.full_parameter_tree_digest,
            prefix_digest=self._prefix, scope_digest=result.scope_content_digest,
            input_digest=result.input_content_digest,
            output_digest=_content_digest(result.hidden),
            cache_chain_digest=result.cache_chain_digest,
            numerical_execution_digest=result.execution_digest,
            predecessor_receipt_digest=prior.receipt_digest,
            motif_disposition=_NO_HIT if source_id == "g1" else _NA,
            motif_read_position=_MOTIF_POSITION if source_id == "g1" else "",
        )
        receipt = _make_receipt(**values)
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


def start_source_backbone_producer(compiled, parameters, sources, feature_schema):
    """Create the B11 producer only by replaying and revalidating actual source rows."""
    encoded, handoffs = encode_source_compiled_with_handoffs(
        compiled, parameters, sources, feature_schema)
    return _SourceBackboneProducerSession(encoded, handoffs, parameters, compiled)
