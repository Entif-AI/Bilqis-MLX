"""Accepted-B13 custody for production BAMF derived-cache authorities."""
from __future__ import annotations

from collections import OrderedDict
import hashlib
import secrets
from threading import RLock

from ..semantics.cognitive_dependencies import DependencyKind

MAX_CAPTURE_RECORDS = 256


def _invalid() -> None:
    from .atlas_cache_codec import _invalid as codec_invalid
    codec_invalid()


def _capture_handle(identity) -> str:
    fields = tuple(str(getattr(identity, name))
                   for name in identity.__dataclass_fields__)
    return hashlib.sha256(
        b"bilqis.mlx.b14-capture-handle/v1\0"
        + "\0".join(fields).encode("utf-8")).hexdigest()


def production_record_for_handle(authority, handle):
    from .atlas_cache_runtime import _production_authority_state
    entry = _production_authority_state(authority)
    if entry is None:
        return None
    capture = entry[3].get(handle)
    if capture is None:
        _invalid()
    _values, identity, packed_owner, row = capture[:4]
    packed_owner.require_row(row)
    if _capture_handle(identity) != handle:
        _invalid()
    return capture


def _cache_registry_key(authority_keys):
    candidates = []
    for key in getattr(authority_keys, "keys", ()):
        exact = tuple(
            scope for scope in key.allowed_scopes
            if scope.kind is DependencyKind.ARTIFACT and scope.key_prefix == "cache:"
        )
        if exact and len(key.allowed_scopes) == 1:
            candidates.append(key)
    if len(candidates) != 1:
        _invalid()
    return candidates[0]


def new_production_authority_owner(issue):
    """Provision one private B14 authority per live accepted B13 cache."""
    lock = RLock()
    issued = {}
    by_cache = {}

    def provision(accepted_cache):
        from bilqis_mlx.runtime.atlas_revalidation import SourceAuthorityRegistry
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )

        cache = require_accepted_execution_cache(accepted_cache)
        authority_keys = cache._correction_registry
        if (type(authority_keys) is not SourceAuthorityRegistry
                or cache.source_authority_registry_sha256 != authority_keys.digest):
            _invalid()
        authority_key = _cache_registry_key(authority_keys)
        with lock:
            existing = by_cache.get(id(cache))
            if existing is not None and existing[0] is cache:
                return existing[1]
            authority = issue(authority_keys, secrets.token_bytes(32), None)
            entry = [authority, cache, authority_key, OrderedDict()]
            issued[id(authority)] = entry
            by_cache[id(cache)] = (cache, authority)
        return authority

    def state(authority):
        with lock:
            entry = issued.get(id(authority))
            if entry is None or entry[0] is not authority:
                return None
            cache = entry[1]
        from bilqis_mlx.runtime.bamf_bundle.execution_cache import (
            require_accepted_execution_cache,
        )
        require_accepted_execution_cache(cache)
        return entry

    def capture(authority, captures):
        if type(captures) is not dict:
            _invalid()
        entry = state(authority)
        if entry is None:
            _invalid()
        records = entry[3]
        with lock:
            for handle, capture_record in captures.items():
                slot = capture_record[4]
                stale = tuple(
                    existing_handle
                    for existing_handle, existing_record in records.items()
                    if existing_record[4] == slot
                )
                for existing_handle in stale:
                    del records[existing_handle]
                records[handle] = capture_record
                records.move_to_end(handle)
            while len(records) > MAX_CAPTURE_RECORDS:
                records.popitem(last=False)

    return provision, state, capture
