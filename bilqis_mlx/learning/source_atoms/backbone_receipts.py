"""Execution-owned B11 backbone boundary receipt authority."""
from __future__ import annotations

from dataclasses import InitVar, dataclass
import re
import weakref

import mlx.core as mx

from ...errors import ErrorBus, SCHOOL
from ...runtime.backbone_group_numerical import _content_digest
from ...runtime.block_attnres import SOURCE_ORDER, COMPLETED_LAYERS
from ...semantics.domains import contract_digest


_PRODUCER_SEAL = object()
NO_HIT = "NO_HIT_QUARANTINED"
NOT_APPLICABLE = "NOT_APPLICABLE"
MOTIF_POSITION = "AFTER_LAYER_4_BEFORE_CAPTURE"
_HIDDEN_FRAME_RANK = 3
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_ISSUED_RECEIPTS = weakref.WeakValueDictionary()


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def receipt_projection(values):
    return (
        "bilqis.mlx.backbone-boundary-receipt/v1", values["source_id"],
        values["completed_layer"], values["source_handoff_digest"],
        values["topology_digest"], values["generation_digest"],
        values["parameter_tree_digest"], values["prefix_digest"],
        values["scope_digest"], values["input_digest"], values["output_digest"],
        values["cache_chain_digest"], values["numerical_execution_digest"],
        values["predecessor_receipt_digest"], values["motif_disposition"],
        values["motif_read_position"], values["motif_read_digest"],
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
    motif_read_digest: str
    receipt_digest: str
    _seal: InitVar[object]

    def _validate_contents(self):
        expected_index = SOURCE_ORDER.index(self.source_id) if self.source_id in SOURCE_ORDER else -1
        digests = (
            self.source_handoff_digest, self.topology_digest, self.generation_digest,
            self.parameter_tree_digest, self.prefix_digest, self.scope_digest,
            self.input_digest, self.output_digest, self.cache_chain_digest,
            self.numerical_execution_digest, self.predecessor_receipt_digest,
            self.motif_read_digest, self.receipt_digest,
        )
        expected_motif = NO_HIT if self.source_id == "g1" else NOT_APPLICABLE
        expected_position = MOTIF_POSITION if self.source_id == "g1" else ""
        if (expected_index < 0
                or self.completed_layer != COMPLETED_LAYERS[expected_index]
                or type(self.hidden) is not mx.array or self.hidden.dtype != mx.float32
                or self.hidden.ndim != _HIDDEN_FRAME_RANK
                or any(not isinstance(value, str) or not _SHA256.fullmatch(value)
                       for value in digests)
                or self.output_digest != _content_digest(self.hidden)
                or self.motif_disposition != expected_motif
                or self.motif_read_position != expected_position
                or self.receipt_digest != contract_digest(receipt_projection(self.__dict__))):
            _invalid()

    def __post_init__(self, _seal):
        if _seal is not _PRODUCER_SEAL:
            _invalid()
        self._validate_contents()


def _issue_from_producer(producer, result=None):
    """Mint only from the live B11 producer's actual executed state.

    This callable intentionally accepts no receipt metadata or hidden tensor.
    Even an explicit private import can only ask an existing producer to seal
    the boundary it has actually reached.
    """
    from .backbone import _SourceBackboneProducerSession
    if type(producer) is not _SourceBackboneProducerSession:
        _invalid()
    values = _SourceBackboneProducerSession._receipt_values(producer, result)
    digest = contract_digest(receipt_projection(values))
    receipt = ProducedBackboneBoundary(
        **values, receipt_digest=digest, _seal=_PRODUCER_SEAL)
    _ISSUED_RECEIPTS[digest] = receipt
    return receipt


def require_produced_backbone_boundary(receipt: ProducedBackboneBoundary) -> None:
    if type(receipt) is not ProducedBackboneBoundary:
        _invalid()
    receipt._validate_contents()
    if _ISSUED_RECEIPTS.get(receipt.receipt_digest) is not receipt:
        _invalid()
