"""Immutable versioned records for the #42 source-row accounting ledger."""
from __future__ import annotations

from dataclasses import dataclass
import re

from .errors import ProfileError
from .resolver import RecordRef
from .source_public import decoded_classification_view


SCHEMA_VERSION = "bilqis.skos.held-ledger/v1"
STATUSES = ("EMITTED", "HELD", "REJECTED", "UNSUPPORTED", "IR_ONLY")
PRIMARY_SEMANTIC_TABLES = frozenset(
    {"morphemes_atomic", "root_senses", "lexicon_roots", "lexicon_root_senses"}
)
COMPOSITION_TABLE = "morpheme_compositions"
TABLE_KEYS = {
    "source_manifest": ("source_id",),
    "curriculum_manifest": ("workbook_id", "tab"),
    "source_sections": ("section_id",),
    "source_tables": ("table_id",),
    "source_assertions": ("assertion_id",),
    "grammatical_categories": ("category_id",),
    "morphemes_atomic": ("atomic_id",),
    "root_senses": ("sense_id",),
    "lexicon_roots": ("lexicon_root_id",),
    "lexicon_root_senses": ("lexicon_sense_id",),
    "lexicon_root_evidence": ("lexicon_evidence_id",),
    "morpheme_compositions": ("composition_id",),
}
SUPPORT_TABLES = frozenset(TABLE_KEYS) - PRIMARY_SEMANTIC_TABLES - {COMPOSITION_TABLE}
ROOT_ATOM_CLASSES = frozenset({"lexical_consonantal_root", "CS_consonantal_root"})

REASON_EXPLANATIONS = {
    "EMITTED_CORE_SKOS": "The source record contributed to a successfully emitted core semantic resource.",
    "IR_ONLY_SUPPORT": "The record is supporting source/provenance IR and has no standalone semantic resource in this compiler stage.",
    "NON_CORE_COMPOSITION_SEMANTICS": "Composition semantics are outside the current core SKOS compiler scope and remain explicit non-core debt.",
    "MISSING_SEMANTIC_OUTCOME": "The semantic source record reached no emitted, held, rejected, or unsupported outcome.",
    "ACCOUNTING_CONFLICT": "The source record received incompatible or duplicate accounting outcomes.",
    "INVALID_EMITTED_RESOURCE": "The build claimed an emitted resource that failed ledger consistency checks.",
    "UNKNOWN_MANIFEST_TABLE": "The closure contains a table whose accounting policy and stable key are not registered for this ledger version.",
    "UNSUPPORTED_RELATION": "A relation owner classified this source record as unsupported by the current semantic profile.",
    "UNADMITTED_MAPPING": "A mapping owner classified this source record as not admitted for strong SKOS mapping emission.",
    "INVALID_TARGET_REFERENCE": "A semantic owner rejected this source record because its required target is invalid.",
    "NO_PUBLIC_SOURCE_LOCUS": "The semantic resource has no permissible public source locus for strong emission.",
    "NOTATION_COLLISION": "The semantic resource is held because its notation collides within the governing scheme.",
    "CONFLICTING_SEMANTIC_MEANING": "The source records assert conflicting meanings for one claimed semantic identity.",
    "SOURCE_IDENTITY_CONFLICT": "Multiple source record groups claim one canonical semantic identity incompatibly.",
    "IRI_COLLISION": "Distinct semantic identities collide on one canonical IRI.",
    "UNKNOWN_ATOM_SHAPE": "The source record has an atom shape that the current semantic resolver does not admit.",
}

_UNSAFE = re.compile(
    r"(?i)(?:[a-z][a-z0-9+.-]*://\S+|(?:/Users|/home|/private|/tmp)/\S*|~/\S*|"
    r"[A-Za-z]:\\\S*|localhost(?::\d+)?|127\.0\.0\.1(?::\d+)?)"
)
_PROJECT_IRI_PREFIX = "https://github.com/Entif-AI/Bilqis-MLX/"


def sanitize_detail(value: str) -> str:
    return _UNSAFE.sub("[redacted]", str(value))


def public_identity_safe(value: str, *, allow_project_iri: bool = False) -> bool:
    """Stable identity fields are preserved verbatim or rejected, never redacted."""
    text = str(value)
    classified = decoded_classification_view(text)
    if classified is None:
        return False
    if allow_project_iri and text.startswith(_PROJECT_IRI_PREFIX):
        suffix = classified[len(_PROJECT_IRI_PREFIX):] if classified.startswith(_PROJECT_IRI_PREFIX) else classified
        return (not any(char.isspace() or ord(char) < 32 for char in text)
                and not _UNSAFE.search(suffix))
    return not _UNSAFE.search(classified)


def require_public_identity_safe(
    field: str, value: str, *, allow_project_iri: bool = False
) -> None:
    if not public_identity_safe(value, allow_project_iri=allow_project_iri):
        raise ProfileError("UNSAFE_LEDGER_IDENTITY_FIELD", field)


@dataclass(frozen=True, order=True)
class ExplicitDisposition:
    record_ref: RecordRef
    status: str
    reason_code: str
    explanation: str
    semantic_iri: str = ""
    semantic_key: tuple[str, ...] = ()


@dataclass(frozen=True, order=True)
class LedgerEntry:
    table: str
    key: str
    status: str
    reason_code: str
    related_reason_codes: tuple[str, ...]
    blocking: bool
    explanation: str
    source_refs: tuple[RecordRef, ...]
    source_loci: tuple[str, ...]
    semantic_iri: str
    semantic_key: tuple[str, ...]

    def as_dict(self) -> dict:
        require_public_identity_safe("entry.table", self.table)
        require_public_identity_safe("entry.key", self.key)
        for ref in self.source_refs:
            require_public_identity_safe("entry.source_ref.table", ref.table)
            require_public_identity_safe("entry.source_ref.key", ref.key)
        for key in self.semantic_key:
            require_public_identity_safe("entry.semantic_key", key)
        if self.semantic_iri:
            require_public_identity_safe(
                "entry.semantic_iri", self.semantic_iri, allow_project_iri=True
            )
        return {
            "table": self.table, "key": self.key, "status": self.status,
            "reason_code": self.reason_code,
            "related_reason_codes": list(self.related_reason_codes),
            "blocking": self.blocking, "explanation": self.explanation,
            "source_refs": [{"table": ref.table, "key": ref.key} for ref in self.source_refs],
            "source_loci": list(self.source_loci),
            "semantic_iri": self.semantic_iri or None,
            "semantic_key": list(self.semantic_key),
        }


@dataclass(frozen=True, order=True)
class LedgerDiagnostic:
    code: str
    blocking: bool
    record_refs: tuple[RecordRef, ...]
    details: tuple[str, ...]

    def as_dict(self) -> dict:
        for ref in self.record_refs:
            require_public_identity_safe("diagnostic.record_ref.table", ref.table)
            require_public_identity_safe("diagnostic.record_ref.key", ref.key)
        return {
            "code": self.code, "blocking": self.blocking,
            "record_refs": [{"table": ref.table, "key": ref.key} for ref in self.record_refs],
            "details": list(self.details),
        }


@dataclass(frozen=True, order=True)
class GroupIssue:
    code: str
    resource_iri: str
    details: tuple[str, ...]

    def as_dict(self) -> dict:
        require_public_identity_safe(
            "group_issue.resource_iri", self.resource_iri, allow_project_iri=True
        )
        return {"code": self.code, "resource_iri": self.resource_iri, "details": list(self.details)}


@dataclass(frozen=True)
class LedgerResult:
    schema_version: str
    manifest_version: str
    profile_version: str
    profile_digest: str
    entries: tuple[LedgerEntry, ...]
    group_issues: tuple[GroupIssue, ...]
    diagnostics: tuple[LedgerDiagnostic, ...]
    core_complete: bool
    whole_release_eligible: bool
    release_ineligible: bool
    blocking: bool

    @property
    def counts(self) -> dict[str, int]:
        return {status: sum(item.status == status for item in self.entries) for status in STATUSES}

    def as_dict(self) -> dict:
        by_table = {}
        for table in sorted({entry.table for entry in self.entries}):
            rows = [entry for entry in self.entries if entry.table == table]
            by_table[table] = {status: sum(row.status == status for row in rows) for status in STATUSES}
        return {
            "schema_version": self.schema_version, "manifest_version": self.manifest_version,
            "profile_version": self.profile_version, "profile_digest": self.profile_digest,
            "counts": {"by_status": self.counts, "by_table": by_table},
            "core_complete": self.core_complete,
            "whole_release_eligible": self.whole_release_eligible,
            "release_ineligible": self.release_ineligible, "blocking": self.blocking,
            "entries": [entry.as_dict() for entry in self.entries],
            "group_issues": [issue.as_dict() for issue in self.group_issues],
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


@dataclass(frozen=True)
class OutcomeCandidate:
    status: str
    reason_code: str
    explanation: str
    origin: str
