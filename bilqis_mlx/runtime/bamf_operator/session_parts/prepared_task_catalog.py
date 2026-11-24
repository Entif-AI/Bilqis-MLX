"""Session-owned, derived task-route catalog; never learner or assessment authority."""
from collections import OrderedDict
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys
import zlib

from bilqis_mlx.data_plane import REBUILDABLE_OBJECT_REFERENCE_PREFIX, data_plane
from bilqis_mlx.learning.atlas_readout import DecisionKind, DecisionOutput, DecisionSpec
from bilqis_mlx.learning.atlas_readout.plan import MAX_DECISIONS
from bilqis_mlx.runtime.bamf_bundle import is_authenticated_generation_feature_context
from bilqis_mlx.runtime.factory_training_preparation_cache import (
    _learning_first_preparation_binding, _MAX_PREPARED_TASK_ROUTES,
)
from bilqis_mlx.runtime.refinement_request import (
    RefinementRequestDisposition, RefinementRequestKind,
)
from bilqis_mlx.runtime.source_execution import SourceExecutionContext
from bilqis_mlx.runtime.task_goal_readout import PreparedTaskRoute
from bilqis_mlx.semantics.domains import contract_digest

_SCHEMA = "bilqis.bamf.prepared-task-catalog/v1"
_MAX_BYTES = 16 * 1024 * 1024
_CACHE_ERRORS = (OSError, ValueError, TypeError, KeyError, sqlite3.Error, zlib.error)
_INVALID_ROUTE = "PREPARED_TASK_ROUTE_INVALID"


def _compiler_identity():
    # Existing qualification fingerprint, once per session boundary, never per row.
    # Production code changes (including transitive helper changes) invalidate it.
    from bilqis_mlx.runtime.qualification_manifest import implementation_files
    root = Path(__file__).resolve().parents[4]
    files = implementation_files(root)
    if not files:
        raise ValueError("PREPARED_TASK_COMPILER_UNAVAILABLE")
    return contract_digest((sys.version_info[:3], files))


def _restore_route(record):
    decisions = tuple(DecisionSpec(**{
        **item, "kind": DecisionKind(item["kind"]),
        "legal_values": tuple(item["legal_values"]),
        "depends_on": tuple(item["depends_on"]),
    }) for item in record["decisions"])
    targets = tuple(DecisionOutput(**item) for item in record["targets"])
    mask = tuple(tuple(item) for item in record["mask"])
    refinement = record["refinement"]
    disposition = RefinementRequestDisposition(
        RefinementRequestKind(refinement["kind"]), tuple(refinement["requested_roles"]))
    if (not 1 <= len(decisions) <= MAX_DECISIONS or len(decisions) != len(targets)
            or len(mask) != len(decisions)):
        raise ValueError(_INVALID_ROUTE)
    prior = set()
    for decision, target, enabled in zip(decisions, targets, mask, strict=True):
        if (decision.kind not in (DecisionKind.OPERATOR, DecisionKind.OPERAND)
                or decision.decision_id in prior or not set(decision.depends_on) <= prior
                or decision.decision_id != target.decision_id
                or target.value not in decision.legal_values
                or enabled != (target.decision_id, True) or type(enabled[1]) is not bool):
            raise ValueError(_INVALID_ROUTE)
        prior.add(decision.decision_id)
    return PreparedTaskRoute(decisions, targets, mask, disposition)


def _is_digest(value):
    return (type(value) is str and len(value) == 64
            and all(char in "0123456789abcdef" for char in value))


class PreparedTaskCatalog:
    """One bounded working set across accepted generations and normal restarts."""

    def __init__(self, plane, run_dir, binding, compiler_identity):
        self.plane = plane
        self.binding = binding
        self.compiler_identity = compiler_identity
        self.reference = (REBUILDABLE_OBJECT_REFERENCE_PREFIX + _SCHEMA + ":"
                          + contract_digest(str(run_dir.resolve())))
        self.routes = OrderedDict()
        self.initial = {}
        self._restore()

    def _restore(self):
        try:
            stored = self.plane.get_object_reference(self.reference)
        except _CACHE_ERRORS:
            self._discard_unusable_reference()
            return
        try:
            if stored is None or len(stored[1]) > _MAX_BYTES:
                return
            record = json.loads(stored[1])
            if (record["schema"] != _SCHEMA or tuple(record["binding"]) != self.binding
                    or record["compiler"] != self.compiler_identity
                    or not isinstance(record["entries"], list)
                    or len(record["entries"]) > _MAX_PREPARED_TASK_ROUTES):
                return
            restored = OrderedDict()
            for key, route in record["entries"]:
                key = tuple(key)
                if (len(key) != 3 or key[:2] != (self.binding[1], self.binding[5])
                        or not all(_is_digest(value) for value in key) or key in restored):
                    raise ValueError("PREPARED_TASK_KEY_INVALID")
                restored[key] = _restore_route(route)
            self.routes = restored
            self.initial = dict(restored)
        except _CACHE_ERRORS:
            # Cache damage is a miss; fresh provider lowering remains available.
            return

    def _discard_unusable_reference(self):
        try:
            self.plane.discard_rebuildable_object_reference(self.reference)
        except _CACHE_ERRORS:
            return

    def persist(self):
        if not self.routes or self.routes == self.initial:
            return
        try:
            record = {"schema": _SCHEMA, "binding": self.binding,
                      "compiler": self.compiler_identity,
                      "entries": [(key, asdict(route)) for key, route in self.routes.items()]}
            raw = json.dumps(record, ensure_ascii=False, separators=(",", ":"),
                             sort_keys=True, allow_nan=False).encode()
            if (len(raw) <= _MAX_BYTES
                    and _compiler_identity() == self.compiler_identity):
                self.plane.put_object_reference(self.reference, raw)
                # A deduplicated object can already exist with damaged bytes.
                # Never leave a broken optional root for post-stop maintenance.
                try:
                    self.plane.get_object_reference(self.reference)
                except _CACHE_ERRORS:
                    self._discard_unusable_reference()
                    return
                self.initial = dict(self.routes)
        except _CACHE_ERRORS:
            # This optional accelerator must not veto a lawful normal stop.
            return


def attach_catalog(snapshot, previous):
    if (type(snapshot) is not tuple or len(snapshot) != 4
            or type(snapshot[1]) is not SourceExecutionContext):
        return previous
    context = snapshot[1]
    features = context._accepted_feature_context
    if (context.run_dir is None
            or not is_authenticated_generation_feature_context(features)):
        return previous
    binding = (str(context.run_dir), *_learning_first_preparation_binding(context, features))
    if previous is None or previous.binding != binding:
        try:
            previous = PreparedTaskCatalog(data_plane(), context.run_dir, binding,
                                           _compiler_identity())
        except _CACHE_ERRORS:
            return None
    object.__setattr__(context, "_prepared_task_binding", (binding, previous.routes))
    return previous
