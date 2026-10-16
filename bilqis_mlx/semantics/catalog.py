"""Read-only, original-ID semantic operator bindings; admission is separate."""
from __future__ import annotations

from .core import Operation, TypedError

class Catalog:
    """Read-only binding of upstream/canonical-assigned ID to typed operator."""

    def __init__(self, definitions: tuple[Operation, ...]):
        ids = [item.token_index for item in definitions]
        symbols = [item.symbol for item in definitions]
        if len(set(ids)) != len(ids) or len(set(symbols)) != len(symbols):
            raise TypedError("COMPOSITION_DUPLICATE_CATALOG_BINDING")
        self._by_id = {item.token_index: item for item in definitions}
        self._by_symbol = {item.symbol: item.token_index for item in definitions}

    def get(self, original_token_id: int) -> Operation:
        if type(original_token_id) is not int:
            raise TypedError("COMPOSITION_INVALID_CATALOG_ID")
        try:
            return self._by_id[original_token_id]
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_CATALOG_ID") from exc

    def resolve_external_name(self, original_symbol: str) -> Operation:
        """For ingress only. Internals use original catalog-assigned token ID."""
        try:
            return self.get(self._by_symbol[original_symbol])
        except KeyError as exc:
            raise TypedError("COMPOSITION_UNKNOWN_EXTERNAL_ALIAS") from exc
