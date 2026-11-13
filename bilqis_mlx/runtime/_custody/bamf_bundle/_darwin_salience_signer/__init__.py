"""Fixed Darwin host boundary for the private C06 source-authority signer."""
from __future__ import annotations

import json
import os
import re

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from bilqis_mlx.semantics.cognitive_dependencies import DependencyRef
from .._darwin_source_authority import (
    HOST_SALIENCE_SIGNER_LOGICAL_PATH,
    open_host_source_authority_signer_fd,
)
from ..records import invalid


_MAX_BYTES = 16 * 1024
_HEX_32 = re.compile(r"[0-9a-f]{64}")


class HostSourceAuthoritySigner:
    """Ephemeral signer whose public identity must already be trusted by C09."""

    def __init__(self, owner_id: str, private_key_hex: str, registry):
        if (not isinstance(owner_id, str) or not owner_id
                or not isinstance(private_key_hex, str)
                or _HEX_32.fullmatch(private_key_hex) is None):
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
        try:
            key = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(private_key_hex))
        except ValueError:
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
        public = key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        self.owner_id = owner_id
        self.public_key_hex = public
        self._key = key
        self._registry = registry

    def sign(self, dependency: DependencyRef, payload: bytes) -> str:
        if not isinstance(dependency, DependencyRef) or not isinstance(payload, bytes):
            invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
        self._registry.require_claimed_authority(
            self.owner_id, dependency, self.public_key_hex)
        return self._key.sign(payload).hex()


def read_host_system_source_authority_signer(registry) -> HostSourceAuthoritySigner:
    """Read the fixed private signer and bind it to the already-accepted C09 registry."""
    fd = open_host_source_authority_signer_fd(max_bytes=_MAX_BYTES)
    try:
        size = os.fstat(fd).st_size
        raw = os.read(fd, size + 1)
    except OSError:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    finally:
        os.close(fd)
    if len(raw) != size:
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    if (not isinstance(record, dict)
            or set(record) != {"schema", "owner_id", "private_key_hex"}
            or record.get("schema") != "bilqis.mlx.source-authority-signer/v1"):
        invalid("BAMF_C09_SOURCE_AUTHORITY_TRUST_ROOT_INVALID")
    return HostSourceAuthoritySigner(record["owner_id"], record["private_key_hex"], registry)


__all__ = ("HostSourceAuthoritySigner", "read_host_system_source_authority_signer")
