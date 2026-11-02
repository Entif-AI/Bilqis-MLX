"""Deterministic test-only cache artifact signing authority."""
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

_KEY = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
PUBLIC_KEY_HEX = _KEY.public_key().public_bytes(
    serialization.Encoding.Raw,
    serialization.PublicFormat.Raw,
).hex()
OWNER_ID = "bamf-cache-test-authority"


def sign_cache_artifact(payload: bytes) -> bytes:
    return _KEY.sign(payload)
