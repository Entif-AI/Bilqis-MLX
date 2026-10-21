"""Declarative retention policy layered over admitted execution profiles."""


FRAGILE_PRESERVATION_CAPABILITIES = ("B.OR", "B.XOR")


def fragile_preservation_capabilities() -> tuple[str, ...]:
    """Capabilities currently receiving bounded truth-table preservation."""
    return FRAGILE_PRESERVATION_CAPABILITIES
