"""B12 custody for an accepted package-import state transition."""
from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256
import json
import re

import mlx.core as mx
import numpy as np

from bilqis_mlx.errors import ErrorBus, SCHOOL
from bilqis_mlx.runtime.atlas_optimizer import AdamWStateTree
from .atlas_candidate import CandidateState
from .atlas_plasticity import IdentityRowAge, PlasticityPolicy


IMPORT_TRANSACTION_SCHEMA = "bilqis.mlx.package-import-transaction/v1"
IMPORT_RESET_SCHEMA = "bilqis.mlx.package-import-reset/v1"
IMPORT_ORIGIN = "PACKAGE_IMPORT"
_ISSUER = object()
_IDENTITY = re.compile(r"identity\.bank\.(\d+)\Z")


def _invalid() -> None:
    ErrorBus.Raise(SCHOOL.MODEL_TOPOLOGY.INVALID)


def _sha(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


@dataclass(frozen=True, order=True)
class ImportResetSlice:
    parameter_name: str
    start: int
    stop: int

    def __post_init__(self):
        if (not isinstance(self.parameter_name, str) or not self.parameter_name
                or type(self.start) is not int or type(self.stop) is not int
                or not 0 <= self.start < self.stop):
            _invalid()


def reset_policy_sha256(slices: tuple[ImportResetSlice, ...]) -> str:
    _validate_slices(slices)
    payload = {
        "schema": IMPORT_RESET_SCHEMA,
        "origin": IMPORT_ORIGIN,
        "changed_slices": [
            {"parameter_name": item.parameter_name, "start": item.start, "stop": item.stop}
            for item in slices
        ],
        "reset": {
            "optimizer_m": "changed-slice-zero",
            "optimizer_v": "changed-slice-zero",
            "optimizer_count": "changed-count-owner-zero",
            "identity_row_age": "changed-row-zero",
            "accepted_fast_since_full": 0,
        },
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(raw).hexdigest()


@dataclass(frozen=True, init=False)
class PackageImportTransaction:
    parent: CandidateState
    retained: CandidateState
    parent_manifest_sha256: str
    package_sha256: str
    reset_slices: tuple[ImportResetSlice, ...]
    reset_policy_sha256: str
    origin: str = IMPORT_ORIGIN
    schema_version: str = IMPORT_TRANSACTION_SCHEMA
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid()

    def __post_init__(self):
        if (getattr(self, "_issuance", None) is not _ISSUER
                or type(self.parent) is not CandidateState
                or type(self.retained) is not CandidateState
                or not _sha(self.parent_manifest_sha256) or not _sha(self.package_sha256)
                or self.origin != IMPORT_ORIGIN
                or self.schema_version != IMPORT_TRANSACTION_SCHEMA):
            _invalid()
        self.parent.__post_init__()
        self.retained.__post_init__()
        _validate_slices(self.reset_slices)
        if (self.reset_policy_sha256 != reset_policy_sha256(self.reset_slices)
                or self.retained.optimizer_step != self.parent.optimizer_step
                or self.retained.allocations != self.parent.allocations
                or self.retained.policy.mode != self.parent.policy.mode
                or self.retained.policy.accepted_fast_since_full != 0):
            _invalid()


def _validate_slices(slices):
    if (not isinstance(slices, tuple) or not slices
            or any(type(item) is not ImportResetSlice for item in slices)
            or slices != tuple(sorted(set(slices)))):
        _invalid()
    spans = {}
    for item in slices:
        item.__post_init__()
        prior = spans.setdefault(item.parameter_name, [])
        if any(not (item.stop <= start or stop <= item.start) for start, stop in prior):
            _invalid()
        prior.append((item.start, item.stop))


def _reset_array(value, spans):
    raw = np.asarray(value).reshape(-1).copy()
    for start, stop in spans:
        raw[start:stop] = 0
    return mx.array(raw.reshape(value.shape), dtype=value.dtype)


def _rows(parameter, spans):
    if parameter.ndim < 1:
        return ()
    width = parameter.size // parameter.shape[0]
    return tuple(sorted({row for start, stop in spans
                         for row in range(start // width, (stop - 1) // width + 1)}))


def _reset_count(count, parameter, spans):
    if count.shape == ():
        return mx.array(0, dtype=mx.uint64)
    raw = np.asarray(count).copy()
    for row in _rows(parameter, spans):
        raw[row] = 0
    return mx.array(raw, dtype=mx.uint64)


def _validate_parameter_delta(parent, imported, spans):
    previous = np.asarray(parent).reshape(-1)
    current = np.asarray(imported).reshape(-1)
    changed = np.zeros(previous.shape, dtype=bool)
    for start, stop in spans:
        changed[start:stop] = True
    if not np.array_equal(previous[~changed], current[~changed]):
        _invalid()


def _reset_policy(parent: PlasticityPolicy, parameters, spans_by_name):
    touched = set()
    for name, spans in spans_by_name.items():
        match = _IDENTITY.fullmatch(name)
        if match:
            touched.update((int(match.group(1)), row) for row in _rows(parameters[name], spans))
    ages = tuple(
        IdentityRowAge(item.bank_index, item.row_index,
                       0 if item.identity in touched else item.accepted_age)
        for item in parent.row_ages)
    return PlasticityPolicy(parent.mode, 0, ages)


def begin_package_import(
    parent: CandidateState, imported_parameters, reset_slices: tuple[ImportResetSlice, ...],
    *, parent_manifest_sha256: str, package_sha256: str,
) -> PackageImportTransaction:
    """Create one reset import state; this neither decides acceptance nor publishes."""
    if type(parent) is not CandidateState or not isinstance(imported_parameters, dict):
        _invalid()
    parent.__post_init__()
    _validate_slices(reset_slices)
    if set(imported_parameters) != set(parent.optimizer.parameters):
        _invalid()
    spans_by_name = {}
    for item in reset_slices:
        if item.parameter_name not in parent.optimizer.parameters:
            _invalid()
        spans_by_name.setdefault(item.parameter_name, []).append((item.start, item.stop))
    parameters = {}
    moments_m, moments_v, counts = {}, {}, {}
    for name, previous in parent.optimizer.parameters.items():
        value = imported_parameters[name]
        if (not isinstance(value, mx.array) or value.shape != previous.shape
                or value.dtype != mx.float32 or not bool(mx.all(mx.isfinite(value)))):
            _invalid()
        parameters[name] = mx.array(value)
        spans = spans_by_name.get(name, ())
        if spans and max(stop for _, stop in spans) > previous.size:
            _invalid()
        _validate_parameter_delta(previous, value, spans)
        moments_m[name] = _reset_array(parent.optimizer.m[name], spans) if spans else parent.optimizer.m[name]
        moments_v[name] = _reset_array(parent.optimizer.v[name], spans) if spans else parent.optimizer.v[name]
        counts[name] = _reset_count(parent.optimizer.update_counts[name], previous, spans) if spans else parent.optimizer.update_counts[name]
    optimizer = AdamWStateTree(parameters, moments_m, moments_v, counts)
    retained = CandidateState(
        optimizer, _reset_policy(parent.policy, parent.optimizer.parameters, spans_by_name),
        parent.allocations, parent.optimizer_step)
    transaction = object.__new__(PackageImportTransaction)
    for key, value in (
        ("parent", parent), ("retained", retained),
        ("parent_manifest_sha256", parent_manifest_sha256), ("package_sha256", package_sha256),
        ("reset_slices", reset_slices), ("reset_policy_sha256", reset_policy_sha256(reset_slices)),
        ("origin", IMPORT_ORIGIN), ("schema_version", IMPORT_TRANSACTION_SCHEMA), ("_issuance", _ISSUER),
    ):
        object.__setattr__(transaction, key, value)
    transaction.__post_init__()
    return transaction

