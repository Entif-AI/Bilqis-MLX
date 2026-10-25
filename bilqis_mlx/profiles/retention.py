"""Declarative retention policy layered over admitted execution profiles."""
from dataclasses import dataclass


@dataclass(frozen=True)
class FragilePreservationPolicy:
    """Source-selection data for bounded fragile-capability preservation."""
    capabilities: tuple[str, ...]
    per_capability_target: int
    source_selector: str

    def __post_init__(self):
        if (not isinstance(self.capabilities, tuple) or not self.capabilities or
                any(not isinstance(value, str) or not value for value in self.capabilities) or
                len(set(self.capabilities)) != len(self.capabilities) or
                type(self.per_capability_target) is not int or self.per_capability_target < 1 or
                not isinstance(self.source_selector, str) or not self.source_selector):
            raise ValueError("FRAGILE_PRESERVATION_POLICY_INVALID")


_FRAGILE_POLICY = FragilePreservationPolicy(
    ("B.OR", "B.XOR"), 4, "bilqis.mlx.grade-b-u7c-runtime-sampler/v3")
FRAGILE_PRESERVATION_CAPABILITIES = _FRAGILE_POLICY.capabilities


def fragile_preservation_policy() -> FragilePreservationPolicy:
    """Return the current immutable source preservation profile."""
    return _FRAGILE_POLICY


def fragile_preservation_capabilities() -> tuple[str, ...]:
    """Capabilities currently receiving bounded truth-table preservation."""
    return fragile_preservation_policy().capabilities
