"""Ephemeral issuance and numerical-attestation registry for decoder outputs."""
from copy import deepcopy
import hashlib
import numpy as np
from weakref import WeakValueDictionary, finalize

import mlx.core as mx

from bilqis_mlx.runtime.autodiff_trace import (
    defer_host_tensor_validation, host_tensor_validation_enabled,
)
from ..plan import DecisionKind
from ..records import invalid

def _logit_fingerprint(logits):
    """Snapshot evaluated FP32 bytes without replacing the differentiable tensor."""
    mx.eval(logits)
    values = np.array(logits, dtype=np.float32, copy=True, order='C')
    return hashlib.sha256(values.tobytes(order='C')).digest()


def _batched_logit_fingerprints(logits):
    """Fingerprint many materialized 1-D logits with one device-to-host transfer."""
    if not logits:
        return ()
    lengths = tuple(value.size for value in logits)
    flat = mx.concatenate(tuple(value.reshape(-1) for value in logits))
    finite = mx.all(mx.isfinite(flat))
    mx.eval(flat, finite)
    if not bool(finite):
        invalid()
    values = np.array(flat, dtype=np.float32, copy=True, order='C')
    offset = 0
    fingerprints = []
    for length in lengths:
        current = values[offset:offset + length]
        fingerprints.append(hashlib.sha256(current.tobytes(order='C')).digest())
        offset += length
    return tuple(fingerprints)


class _IssuanceRegistry:
    """Own ephemeral numerical receipts; no module-level mutable collection."""

    def __init__(self):
        self.outputs = WeakValueDictionary()
        self.records = {}

    def issue(self, output, meaning, *, fingerprint=True, freeze_meaning=True):
        key = id(output)
        self.outputs[key] = output
        self.records[key] = (
            tuple((record, record.logits,
                   _logit_fingerprint(record.logits) if fingerprint else None)
                  for record in output.decisions),
            deepcopy(meaning) if freeze_meaning else meaning,
        )
        finalize(output, self.records.pop, key, None)
        return output

    def contains(self, output, meaning):
        key = id(output)
        if self.outputs.get(key) is not output:
            return False
        records, frozen_meaning = self.records[key]
        return (meaning == frozen_meaning
                and len(output.decisions) == len(records)
                and all(record is issued and record.logits is logits
                        and (fingerprint is None
                             and not host_tensor_validation_enabled()
                             or fingerprint is not None
                             and _logit_fingerprint(record.logits) == fingerprint)
                        for record, (issued, logits, fingerprint) in zip(output.decisions, records)))

    def contains_live(self, output, meaning):
        """Require only the exact process-issued output and frozen route meaning."""
        key = id(output)
        if self.outputs.get(key) is not output or key not in self.records:
            return False
        records, frozen_meaning = self.records[key]
        return (
            meaning == frozen_meaning
            and len(output.decisions) == len(records)
            and all(
                record is issued and record.logits is logits
                for record, (issued, logits, _fingerprint)
                in zip(output.decisions, records)
            )
        )

    def contains_attested(self, output, meaning):
        """Require the exact live output after numerical attestation, without re-reading logits."""
        key = id(output)
        if self.outputs.get(key) is not output or key not in self.records:
            return False
        records, frozen_meaning = self.records[key]
        return (
            meaning == frozen_meaning
            and len(output.decisions) == len(records)
            and all(
                record is issued
                and record.logits is logits
                and fingerprint is not None
                for record, (issued, logits, fingerprint)
                in zip(output.decisions, records)
            )
        )

    def attest(self, output, meaning):
        if not host_tensor_validation_enabled():
            return False
        key = id(output)
        if self.outputs.get(key) is not output or key not in self.records:
            return False
        records, frozen_meaning = self.records[key]
        if meaning != frozen_meaning or len(output.decisions) != len(records):
            return False
        if any(record is not issued or record.logits is not logits
               for record, (issued, logits, _fingerprint) in zip(output.decisions, records)):
            return False
        output.__post_init__()
        attested = tuple(
            (record, logits, _logit_fingerprint(logits))
            for record, (_issued, logits, _fingerprint) in zip(output.decisions, records)
        )
        self.records[key] = (attested, frozen_meaning)
        return True

    def attest_many(self, outputs, meanings):
        if (not host_tensor_validation_enabled() or not outputs
                or len(outputs) != len(meanings)):
            return False
        pending = []
        all_logits = []
        for output, meaning in zip(outputs, meanings):
            key = id(output)
            if self.outputs.get(key) is not output or key not in self.records:
                return False
            records, frozen_meaning = self.records[key]
            if meaning != frozen_meaning or len(output.decisions) != len(records):
                return False
            if any(record is not issued or record.logits is not logits
                   for record, (issued, logits, _fingerprint)
                   in zip(output.decisions, records)):
                return False
            pending.append((key, records, frozen_meaning))
            all_logits.extend(record.logits for record in output.decisions)
        with defer_host_tensor_validation():
            for output in outputs:
                output.__post_init__()
        fingerprints = _batched_logit_fingerprints(tuple(all_logits))
        cursor = 0
        for key, records, frozen_meaning in pending:
            count = len(records)
            attested = tuple(
                (record, logits, fingerprints[cursor + index])
                for index, (record, logits, _fingerprint) in enumerate(records)
            )
            self.records[key] = (attested, frozen_meaning)
            cursor += count
        return True


_ISSUANCE = _IssuanceRegistry()

def _meaning(output):
    return (output.plan, tuple((r.decision_id, r.kind, r.candidates)
                               for r in output.decisions), output.committed,
            output.status, output.execution_mode, output.frame,
            output.fallback_requested, output.schema_version)


def issued_output(output):
    """Require the exact live decoder result and its frozen source meaning."""
    return _ISSUANCE.contains(output, _meaning(output))


def live_issued_output(output):
    """Require exact process-issued identity without numerical receipt fingerprinting."""
    return _ISSUANCE.contains_live(output, _meaning(output))


def attested_issued_output(output):
    """Require an exact live output whose logits were already numerically attested."""
    return _ISSUANCE.contains_attested(output, _meaning(output))


def _issue_output(output, *, fingerprint=True, freeze_meaning=True):
    if not freeze_meaning and (
            not output.plan.route_only
            or output.frame is not None
            or any(record.kind not in (DecisionKind.OPERATOR, DecisionKind.OPERAND)
                   or any(type(candidate) is not str for candidate in record.candidates)
                   for record in output.decisions)
            or any(type(item.value) is not str for item in output.committed)):
        invalid()
    return _ISSUANCE.issue(
        output, _meaning(output), fingerprint=fingerprint, freeze_meaning=freeze_meaning)


def attest_issued_output(output):
    """Complete deferred decoder evidence after tensors leave autodiff."""
    return _ISSUANCE.attest(output, _meaning(output))


def attest_issued_outputs(outputs):
    """Attest a microbatch of deferred decoder outputs with one logit transfer."""
    if type(outputs) is not tuple:
        return False
    return _ISSUANCE.attest_many(outputs, tuple(_meaning(output) for output in outputs))
