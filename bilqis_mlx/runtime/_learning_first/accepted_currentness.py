"""Process-live accepted-state identity checks for ordinary BAMF execution."""
from bilqis_mlx.runtime.bamf_bundle.currentness_transaction import (
    AcceptedCurrentnessTransaction,
    _ISSUER,
    _retained_root_guard,
    invalid,
)


def require_accepted_currentness_identity(transaction, cache=None, parent=None):
    """Fence accepted roots without walking every retained tensor leaf."""
    if (type(transaction) is not AcceptedCurrentnessTransaction
            or getattr(transaction, "_issuance", None) is not _ISSUER
            or (cache is not None and transaction._cache is not cache)
            or (parent is not None and transaction._parent is not parent)
            or getattr(transaction._cache, "_currentness_transaction", None)
               is not transaction
            or transaction._cache.accepted_manifest_sha256
               != transaction.accepted_manifest_sha256
            or transaction._cache.generation_binding != transaction.generation_binding
            or getattr(transaction._cache, "_candidate_identity_sha256", None)
               != transaction.candidate_identity_sha256
            or transaction._parent.topology.digest != transaction.topology_digest
            or transaction._parent.extents.digest != transaction.extents_digest
            or _retained_root_guard(transaction._parent) != transaction._retained_root):
        invalid("B13_CURRENTNESS_TRANSACTION_DRIFT")
    return transaction


__all__ = ("require_accepted_currentness_identity",)
