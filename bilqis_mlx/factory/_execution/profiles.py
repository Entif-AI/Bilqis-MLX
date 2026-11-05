"""Factory execution profiles owner."""
from __future__ import annotations

from dataclasses import dataclass
from .. import execution as _api


@dataclass(frozen=True)
class CapabilityProfile:
    capability_id: str
    provider_parameters: tuple[tuple[str, tuple[str, ...]], ...] = ()
    answer_family_values: tuple[tuple[str, tuple[str, ...]], ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.capability_id, str) or not self.capability_id:
            raise ValueError("FACTORY_PROFILE_CAPABILITY_ID_REQUIRED")
        object.__setattr__(self, "provider_parameters", _api._pairs(self.provider_parameters))
        object.__setattr__(self, "answer_family_values", _api._pairs(self.answer_family_values))


@dataclass(frozen=True)
class GradeProfile:
    grade_id: str
    enabled_capabilities: tuple[str, ...] | None = None
    capabilities: tuple[CapabilityProfile, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.grade_id, str) or not self.grade_id:
            raise ValueError("FACTORY_PROFILE_GRADE_ID_REQUIRED")
        if self.enabled_capabilities is not None and (
                len(set(self.enabled_capabilities)) != len(self.enabled_capabilities) or
                any(not isinstance(item, str) or not item
                    for item in self.enabled_capabilities)):
            raise ValueError("FACTORY_PROFILE_ENABLED_CAPABILITIES_INVALID")
        ids = tuple(item.capability_id for item in self.capabilities)
        if len(set(ids)) != len(ids):
            raise ValueError("FACTORY_PROFILE_DUPLICATE_CAPABILITY_OVERRIDE")


@dataclass(frozen=True)
class CurriculumProfile:
    profile_id: str
    grades: tuple[GradeProfile, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.profile_id, str) or not self.profile_id:
            raise ValueError("FACTORY_PROFILE_ID_REQUIRED")
        ids = tuple(item.grade_id for item in self.grades)
        if len(set(ids)) != len(ids):
            raise ValueError("FACTORY_PROFILE_DUPLICATE_GRADE_OVERRIDE")

    @classmethod
    def full(cls) -> "CurriculumProfile":
        return cls("full")
