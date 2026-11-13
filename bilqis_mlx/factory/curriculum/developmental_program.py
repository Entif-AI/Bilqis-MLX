"""Immutable BAMF developmental-program declarations consumed by C14 planning."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
from pathlib import Path

from bilqis_mlx.errors import ErrorBus, FACTORY


SCHEMA = "bilqis.bamf.developmental-program/v1"
DEFAULT_PROGRAM_PATH = (
    Path(__file__).resolve().parents[3] / "configs" / "curricula" /
    "bamf-developmental-v1.json"
)


def _fail(reason: str) -> None:
    ErrorBus.raise_(FACTORY.DEVELOPMENTAL_PROGRAM.INVALID, reason=reason)


def _digest(value) -> str:
    return hashlib.sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode("utf-8")).hexdigest()


class DevelopmentalLevel(str, Enum):
    L0 = "L0"
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


@dataclass(frozen=True)
class DevelopmentalDomainProgram:
    level: DevelopmentalLevel
    purpose: str
    domains: tuple[str, ...]
    constructive_steps: tuple[str, ...]
    source_requirements: tuple[str, ...]
    optional: bool = False
    packages_bounded_capabilities: bool = False

    def __post_init__(self) -> None:
        if (not isinstance(self.level, DevelopmentalLevel)
                or not isinstance(self.purpose, str) or not self.purpose.strip()
                or type(self.optional) is not bool
                or type(self.packages_bounded_capabilities) is not bool):
            _fail("DEVELOPMENTAL_DOMAIN_PROGRAM_IDENTITY_INVALID")
        for values, reason in (
                (self.domains, "DEVELOPMENTAL_DOMAIN_PROGRAM_DOMAINS_INVALID"),
                (self.constructive_steps,
                 "DEVELOPMENTAL_DOMAIN_PROGRAM_STEPS_INVALID"),
                (self.source_requirements,
                 "DEVELOPMENTAL_DOMAIN_PROGRAM_SOURCES_INVALID")):
            if (not values or len(values) != len(set(values))
                    or any(not isinstance(item, str) or not item.strip()
                           for item in values)):
                _fail(reason)


@dataclass(frozen=True)
class BamfDevelopmentalProgram:
    schema: str
    program_id: str
    policy_version: str
    levels: tuple[DevelopmentalDomainProgram, ...]

    def __post_init__(self) -> None:
        expected = tuple(DevelopmentalLevel)
        if (self.schema != SCHEMA
                or not isinstance(self.program_id, str) or not self.program_id
                or not isinstance(self.policy_version, str) or not self.policy_version
                or tuple(item.level for item in self.levels) != expected):
            _fail("DEVELOPMENTAL_PROGRAM_MANIFEST_INVALID")

    @property
    def level_map(self) -> dict[DevelopmentalLevel, DevelopmentalDomainProgram]:
        return {item.level: item for item in self.levels}

    def require_level(self, level: DevelopmentalLevel | str) -> DevelopmentalDomainProgram:
        try:
            identity = level if isinstance(level, DevelopmentalLevel) else DevelopmentalLevel(level)
        except (TypeError, ValueError):
            _fail("DEVELOPMENTAL_PROGRAM_LEVEL_UNKNOWN")
        return self.level_map[identity]

    def manifest(self) -> dict:
        return {
            "schema": self.schema,
            "program_id": self.program_id,
            "policy_version": self.policy_version,
            "levels": [
                {**asdict(item), "level": item.level.value}
                for item in self.levels
            ],
        }

    def digest(self) -> str:
        return _digest(self.manifest())


def _domain_program(payload: dict) -> DevelopmentalDomainProgram:
    if not isinstance(payload, dict):
        _fail("DEVELOPMENTAL_DOMAIN_PROGRAM_PAYLOAD_INVALID")
    try:
        expected = {
            "level", "purpose", "domains", "constructive_steps",
            "source_requirements", "optional", "packages_bounded_capabilities",
        }
        if set(payload) != expected:
            _fail("DEVELOPMENTAL_DOMAIN_PROGRAM_FIELDS_INVALID")
        return DevelopmentalDomainProgram(
            DevelopmentalLevel(payload["level"]),
            payload["purpose"],
            tuple(payload["domains"]),
            tuple(payload["constructive_steps"]),
            tuple(payload["source_requirements"]),
            payload["optional"],
            payload["packages_bounded_capabilities"],
        )
    except (KeyError, TypeError, ValueError):
        _fail("DEVELOPMENTAL_DOMAIN_PROGRAM_PAYLOAD_INVALID")


def load_bamf_developmental_program(
        path: str | Path = DEFAULT_PROGRAM_PATH) -> BamfDevelopmentalProgram:
    """Load the C14 program as data; this function performs no admission or training."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, TypeError, json.JSONDecodeError):
        _fail("DEVELOPMENTAL_PROGRAM_READ_INVALID")
    if not isinstance(payload, dict) or set(payload) != {
            "schema", "program_id", "policy_version", "levels"}:
        _fail("DEVELOPMENTAL_PROGRAM_FIELDS_INVALID")
    try:
        levels = tuple(_domain_program(item) for item in payload["levels"])
        return BamfDevelopmentalProgram(
            payload["schema"], payload["program_id"],
            payload["policy_version"], levels)
    except (KeyError, TypeError):
        _fail("DEVELOPMENTAL_PROGRAM_PAYLOAD_INVALID")
