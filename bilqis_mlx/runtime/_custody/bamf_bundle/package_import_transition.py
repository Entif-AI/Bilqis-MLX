"""B13-issued transition authority for accepted package-import generations."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from bilqis_mlx.data_plane import SHA256_HEX_LENGTH
from bilqis_mlx.errors import ErrorBus, SCHOOL


PACKAGE_IMPORT_TRANSITION_SCHEMA = "bilqis.mlx.bamf-generation-transition/v2"
PACKAGE_IMPORT_KIND = "PACKAGE_IMPORT"
_DIGEST_FIELDS = (
    "package_sha256",
    "screened_candidate_sha256", "reset_policy_sha256", "c05_evidence_sha256",
    "c05_policy_sha256", "source_clearance_sha256",
)
_FIELDS = ("schema", "kind", "invalidate_derived_caches") + _DIGEST_FIELDS
_ISSUER = object()


def _invalid():
    ErrorBus.Raise(
        SCHOOL.STATE.HISTORICAL_ARTIFACT_INVALID,
        reason="BAMF_GENERATION_TRANSITION_INVALID")


def _hex(value):
    return (type(value) is str and len(value) == SHA256_HEX_LENGTH
            and all(char in "0123456789abcdef" for char in value))


@dataclass(frozen=True, init=False)
class PackageImportTransition(Mapping):
    package_sha256: str
    screened_candidate_sha256: str
    reset_policy_sha256: str
    c05_evidence_sha256: str
    c05_policy_sha256: str
    source_clearance_sha256: str
    schema: str = PACKAGE_IMPORT_TRANSITION_SCHEMA
    kind: str = PACKAGE_IMPORT_KIND
    invalidate_derived_caches: bool = True
    _issuance: object = field(init=False, repr=False, compare=False)

    def __init__(self, *args, **kwargs):
        _invalid()

    def __post_init__(self):
        if getattr(self, "_issuance", None) is not _ISSUER:
            _invalid()
        validate_package_import_transition(self)

    def __iter__(self):
        return iter(_FIELDS)

    def __len__(self):
        return len(_FIELDS)

    def __getitem__(self, key):
        if key not in _FIELDS:
            raise KeyError(key)
        return getattr(self, key)


def is_package_import_transition(value) -> bool:
    return (isinstance(value, Mapping)
            and value.get("schema") == PACKAGE_IMPORT_TRANSITION_SCHEMA
            and value.get("kind") == PACKAGE_IMPORT_KIND)


def validate_package_import_transition(value) -> None:
    if (not isinstance(value, Mapping) or set(value) != set(_FIELDS)
            or value.get("schema") != PACKAGE_IMPORT_TRANSITION_SCHEMA
            or value.get("kind") != PACKAGE_IMPORT_KIND
            or value.get("invalidate_derived_caches") is not True
            or any(not _hex(value.get(name)) for name in _DIGEST_FIELDS)):
        _invalid()


def require_issued_package_import_transition(value) -> None:
    if (type(value) is not PackageImportTransition
            or getattr(value, "_issuance", None) is not _ISSUER):
        _invalid()
    value.__post_init__()


def _issue_package_import_transition(
        *, package_sha256, screened_candidate_sha256, reset_policy_sha256,
        c05_evidence_sha256, c05_policy_sha256, source_clearance_sha256,
) -> PackageImportTransition:
    transition = object.__new__(PackageImportTransition)
    for name, value in (
            ("package_sha256", package_sha256),
            ("screened_candidate_sha256", screened_candidate_sha256),
            ("reset_policy_sha256", reset_policy_sha256),
            ("c05_evidence_sha256", c05_evidence_sha256),
            ("c05_policy_sha256", c05_policy_sha256),
            ("source_clearance_sha256", source_clearance_sha256),
            ("schema", PACKAGE_IMPORT_TRANSITION_SCHEMA), ("kind", PACKAGE_IMPORT_KIND),
            ("invalidate_derived_caches", True), ("_issuance", _ISSUER)):
        object.__setattr__(transition, name, value)
    transition.__post_init__()
    return transition
