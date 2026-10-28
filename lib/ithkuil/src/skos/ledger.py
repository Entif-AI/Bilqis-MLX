"""Deterministic source-row accounting ledger for issue #42.

Stable identity fields are serialized exactly. Free-text diagnostics are sanitized
before serialization so local paths or non-public URLs cannot leak through errors.
"""
from __future__ import annotations

import json
from typing import Iterable

from rdflib import URIRef
from rdflib.namespace import RDF, RDFS, SKOS

from .builder import BuildResult
from .errors import ProfileError
from .identity import Identity, sense_from_source
from .ledger_model import (
    COMPOSITION_TABLE,
    PRIMARY_SEMANTIC_TABLES,
    REASON_EXPLANATIONS,
    ROOT_ATOM_CLASSES,
    SCHEMA_VERSION,
    STATUSES,
    SUPPORT_TABLES,
    TABLE_KEYS,
    ExplicitDisposition,
    GroupIssue,
    LedgerDiagnostic,
    LedgerEntry,
    LedgerResult,
    OutcomeCandidate,
    public_identity_safe,
    sanitize_detail,
)
from .preflight import CompilerClosure
from .resolver import RecordRef, Resolution, ResolvedResource


def _row_ref(table: str, row) -> RecordRef:
    fields = TABLE_KEYS.get(table)
    if fields is None:
        return RecordRef(table, f"row:{row.fingerprint}")
    return RecordRef(table, "|".join(row.get(field) for field in fields))


def _source_context(row) -> tuple[tuple[RecordRef, ...], tuple[str, ...]]:
    refs = set()
    loci = []
    source_id = row.get("primary_source_id") or row.get("source_id")
    section_id = row.get("primary_section_id") or row.get("section_id")
    table_id = row.get("primary_table_id") or row.get("table_id")
    if source_id:
        refs.add(RecordRef("source_manifest", source_id))
    if section_id:
        refs.add(RecordRef("source_sections", section_id))
    if table_id:
        refs.add(RecordRef("source_tables", table_id))
    fields = (
        ("source", source_id),
        ("section", section_id),
        ("table", table_id),
        ("line", row.get("primary_source_line") or row.get("source_line")),
        ("anchor", row.get("primary_source_anchor") or row.get("source_anchor")),
        ("chapter", row.get("lexicon_chapter")),
        ("lexicon_section", row.get("lexicon_section")),
        ("root", row.get("root_form_raw")),
        ("stem", row.get("stem")),
        ("specification", row.get("specification")),
        ("printed_page", row.get("source_printed_page")),
        ("tracked_chapter_page", row.get("source_pdf_page")),
    )
    for label, value in fields:
        if not value:
            continue
        safe = sanitize_detail(value)
        loci.append(f"{label}:{safe if safe == value else '[redacted]'}")
    return tuple(sorted(refs)), tuple(sorted(set(loci)))


def _attempted_identity(table: str, row) -> tuple[str, tuple[str, ...]]:
    try:
        if table == "morphemes_atomic":
            atom_class = row.get("morpheme_class")
            if atom_class in ROOT_ATOM_CLASSES:
                identity = Identity("root", (row.get("primary_source_id"), row.get("atomic_id")))
            elif row.get("category_code") and row.get("value_code"):
                identity = Identity("grammar", (row.get("category_code"), row.get("value_code")))
            else:
                return "", tuple(filter(None, (row.get("category_code"), row.get("value_code"))))
        elif table == "lexicon_roots":
            identity = Identity("root", (row.get("source_id"), row.get("lexicon_root_id")))
        elif table in {"root_senses", "lexicon_root_senses"}:
            identity = sense_from_source(table, dict(row.values))
        else:
            return "", ()
        return identity.iri, identity.keys
    except ProfileError:
        if table == "root_senses":
            return "", tuple(filter(None, (row.get("source_id"), row.get("atomic_id"), row.get("stem"), row.get("specification"))))
        if table == "lexicon_root_senses":
            return "", tuple(filter(None, (row.get("source_id"), row.get("lexicon_root_id"), row.get("stem"), row.get("specification"))))
        return "", ()


def _diag(code: str, refs: Iterable[RecordRef] = (), *details: str) -> LedgerDiagnostic:
    return LedgerDiagnostic(code, True, tuple(sorted(set(refs))), tuple(sorted(sanitize_detail(item) for item in details)))


def _strong_type_present(build: BuildResult, resource: ResolvedResource) -> bool:
    expected = SKOS.Concept if resource.role == "concept" else RDFS.Resource
    return (URIRef(resource.identity.iri), RDF.type, expected) in build.graph


def _explanation(code: str, fallback: str = "") -> str:
    if fallback:
        return sanitize_detail(fallback)
    return REASON_EXPLANATIONS.get(code, f"Upstream compiler stage held this record with reason {code}.")


def build_ledger(
    closure: CompilerClosure,
    resolution: Resolution,
    build: BuildResult,
    *,
    profile_version: str,
    profile_digest: str,
    explicit_dispositions: Iterable[ExplicitDisposition] = (),
) -> LedgerResult:
    """Account every closure row exactly once without manufacturing semantic truth."""
    if not isinstance(closure, CompilerClosure):
        raise ProfileError("COMPILER_CLOSURE_REQUIRED", type(closure).__name__)
    if not isinstance(resolution, Resolution):
        raise ProfileError("RESOLUTION_REQUIRED", type(resolution).__name__)
    if not isinstance(build, BuildResult):
        raise ProfileError("BUILD_RESULT_REQUIRED", type(build).__name__)
    if not profile_version:
        raise ProfileError("PROFILE_VERSION_REQUIRED")
    if not profile_digest:
        raise ProfileError("PROFILE_DIGEST_REQUIRED")

    rows = {}
    diagnostics = []
    for table in closure.tables:
        for row in table.rows:
            ref = _row_ref(table.name, row)
            if ref in rows:
                diagnostics.append(_diag("DUPLICATE_ACCOUNTING_REF", (ref,), table.name))
            rows[ref] = row
        if table.name not in TABLE_KEYS:
            diagnostics.append(_diag("UNKNOWN_MANIFEST_TABLE", (), table.name))

    resolved_groups: dict[str, list[ResolvedResource]] = {}
    for resource in resolution.resources:
        resolved_groups.setdefault(resource.identity.iri, []).append(resource)
    for iri, resources in sorted(resolved_groups.items()):
        if len(resources) > 1:
            diagnostics.append(
                _diag(
                    "DUPLICATE_RESOLUTION_IRI",
                    (ref for resource in resources for ref in resource.source_records),
                    f"variants={len(resources)}",
                )
            )
    resolved_by_iri = {
        iri: resources[0] for iri, resources in resolved_groups.items() if len(resources) == 1
    }
    resolved_by_ref: dict[RecordRef, list[ResolvedResource]] = {}
    for resource in resolution.resources:
        for ref in resource.source_records:
            resolved_by_ref.setdefault(ref, []).append(resource)
    for ref, resources in resolved_by_ref.items():
        if len({resource.identity.iri for resource in resources}) > 1:
            diagnostics.append(_diag("RESOLUTION_REF_MULTIPLE_IDENTITIES", (ref,), *(r.identity.iri for r in resources)))

    candidates: dict[RecordRef, list[OutcomeCandidate]] = {}
    def add(ref: RecordRef, status: str, reason: str, explanation: str, origin: str) -> None:
        if ref not in rows:
            diagnostics.append(_diag("OUT_OF_SCOPE_RECORD_REF", (ref,), origin, reason))
            return
        candidates.setdefault(ref, []).append(OutcomeCandidate(status, reason, explanation, origin))

    for resource in build.emitted:
        canonical = resolved_by_iri.get(resource.identity.iri)
        valid = canonical is not None and resource == canonical and _strong_type_present(build, resource)
        reason = "EMITTED_CORE_SKOS" if valid else "INVALID_EMITTED_RESOURCE"
        status = "EMITTED" if valid else "REJECTED"
        if not valid:
            diagnostics.append(_diag("INVALID_EMITTED_RESOURCE", resource.source_records, resource.identity.iri))
        for ref in resource.source_records:
            add(ref, status, reason, _explanation(reason), "build.emitted")

    for issue in resolution.issues:
        for ref in issue.record_refs:
            add(ref, "HELD", issue.code, _explanation(issue.code), "resolution.issue")

    group_issues = []
    for issue in build.issues:
        if not issue.record_refs:
            group_issues.append(GroupIssue(issue.code, issue.resource_iri, tuple(sorted(sanitize_detail(item) for item in issue.details))))
            continue
        for ref in issue.record_refs:
            add(ref, "HELD", issue.code, _explanation(issue.code), "build.issue")

    explicit_seen = set()
    explicit_semantics: dict[RecordRef, tuple[str, tuple[str, ...]]] = {}
    for item in explicit_dispositions:
        if item.status not in STATUSES:
            diagnostics.append(_diag("INVALID_EXPLICIT_STATUS", (item.record_ref,), item.status))
            continue
        if item.record_ref not in rows:
            diagnostics.append(_diag("EXPLICIT_REF_NOT_IN_CLOSURE", (item.record_ref,), item.reason_code))
            continue
        if (
            item.record_ref.table in PRIMARY_SEMANTIC_TABLES
            and item.status not in {"HELD", "REJECTED", "UNSUPPORTED"}
        ):
            diagnostics.append(
                _diag(
                    "INVALID_PRIMARY_EXPLICIT_STATUS",
                    (item.record_ref,),
                    item.status,
                )
            )
            continue
        if item.record_ref in explicit_seen:
            diagnostics.append(_diag("DUPLICATE_EXPLICIT_DISPOSITION", (item.record_ref,), item.reason_code))
        explicit_seen.add(item.record_ref)
        if item.semantic_iri or item.semantic_key:
            explicit_semantics[item.record_ref] = (item.semantic_iri, item.semantic_key)
        add(item.record_ref, item.status, item.reason_code, _explanation(item.reason_code, item.explanation), "explicit")

    entries = []
    for ref, row in sorted(rows.items()):
        table = ref.table
        items = candidates.get(ref, [])
        if not items:
            if table in PRIMARY_SEMANTIC_TABLES:
                items = [OutcomeCandidate("REJECTED", "MISSING_SEMANTIC_OUTCOME", _explanation("MISSING_SEMANTIC_OUTCOME"), "ledger")]
                diagnostics.append(_diag("MISSING_SEMANTIC_OUTCOME", (ref,)))
            elif table == COMPOSITION_TABLE:
                items = [OutcomeCandidate("UNSUPPORTED", "NON_CORE_COMPOSITION_SEMANTICS", _explanation("NON_CORE_COMPOSITION_SEMANTICS"), "ledger")]
            elif table in SUPPORT_TABLES:
                items = [OutcomeCandidate("IR_ONLY", "IR_ONLY_SUPPORT", _explanation("IR_ONLY_SUPPORT"), "ledger")]
            else:
                items = [OutcomeCandidate("UNSUPPORTED", "UNKNOWN_MANIFEST_TABLE", _explanation("UNKNOWN_MANIFEST_TABLE"), "ledger")]

        statuses = {item.status for item in items}
        explicit_count = sum(item.origin == "explicit" for item in items)
        emitted_count = sum(item.origin == "build.emitted" for item in items)
        conflict = len(statuses) > 1 or explicit_count > 1 or emitted_count > 1 or (explicit_count and len(items) > 1)
        reasons = tuple(sorted({item.reason_code for item in items}))
        if conflict:
            status, reason, blocking = "REJECTED", "ACCOUNTING_CONFLICT", True
            explanation = _explanation(reason)
            diagnostics.append(_diag("ACCOUNTING_CONFLICT", (ref,), *reasons))
        else:
            status = next(iter(statuses))
            reason = reasons[0]
            blocking = reason in {"MISSING_SEMANTIC_OUTCOME", "UNKNOWN_MANIFEST_TABLE", "INVALID_EMITTED_RESOURCE"}
            explanation = sorted({item.explanation for item in items})[0]

        resource_options = resolved_by_ref.get(ref, [])
        if ref in explicit_semantics:
            semantic_iri, semantic_key = explicit_semantics[ref]
        elif len(resource_options) == 1:
            semantic_iri = resource_options[0].identity.iri
            semantic_key = resource_options[0].identity.keys
        else:
            semantic_iri, semantic_key = _attempted_identity(table, row)
        source_refs, source_loci = _source_context(row)
        entries.append(LedgerEntry(
            table, ref.key, status, reason, reasons, blocking, explanation,
            source_refs, source_loci, semantic_iri, semantic_key,
        ))

    emitted_iris = {resource.identity.iri for resource in build.emitted}
    for rdf_type in (SKOS.Concept, RDFS.Resource):
        for subject in sorted(
            {value for value in build.graph.subjects(RDF.type, rdf_type) if isinstance(value, URIRef)},
            key=str,
        ):
            if str(subject) not in emitted_iris:
                diagnostics.append(
                    _diag(
                        "UNACCOUNTED_STRONG_SEMANTIC_SUBJECT",
                        (),
                        f"subject_sha256={__import__('hashlib').sha256(str(subject).encode('utf-8')).hexdigest()}",
                        f"rdf_type={rdf_type}",
                    )
                )

    for entry in entries:
        unsafe = (
            not public_identity_safe(entry.table)
            or not public_identity_safe(entry.key)
            or any(
                not public_identity_safe(ref.table) or not public_identity_safe(ref.key)
                for ref in entry.source_refs
            )
            or any(not public_identity_safe(key) for key in entry.semantic_key)
            or (
                bool(entry.semantic_iri)
                and not public_identity_safe(entry.semantic_iri, allow_project_iri=True)
            )
        )
        if unsafe:
            diagnostics.append(
                _diag(
                    "UNSAFE_LEDGER_IDENTITY_FIELD",
                    (RecordRef(entry.table, entry.key),),
                    "stable identity value rejected from public serialization",
                )
            )

    for entry in entries:
        if entry.status not in {"HELD", "REJECTED", "UNSUPPORTED"} or not entry.semantic_iri:
            continue
        iri = URIRef(entry.semantic_iri)
        if any(build.graph.triples((iri, None, None))) or any(build.graph.triples((None, SKOS.member, iri))) or any(build.graph.triples((None, RDF.first, iri))):
            diagnostics.append(_diag("HELD_RESOURCE_IN_STRONG_GRAPH", (RecordRef(entry.table, entry.key),), entry.semantic_iri))

    ordered_entries = tuple(sorted(entries))
    ordered_groups = tuple(sorted(set(group_issues)))
    ordered_diagnostics = tuple(sorted(set(diagnostics)))
    blocking = any(entry.blocking for entry in ordered_entries) or any(item.blocking for item in ordered_diagnostics)
    core_complete = not blocking and not ordered_groups and not any(
        entry.table in PRIMARY_SEMANTIC_TABLES and entry.status != "EMITTED"
        for entry in ordered_entries
    )
    unsupported_semantic_inventory = any(
        entry.status == "UNSUPPORTED"
        and (entry.table in PRIMARY_SEMANTIC_TABLES or entry.table == COMPOSITION_TABLE)
        for entry in ordered_entries
    )
    whole_release_eligible = core_complete and not unsupported_semantic_inventory
    release_ineligible = not whole_release_eligible
    return LedgerResult(
        SCHEMA_VERSION, closure.manifest_version, profile_version, profile_digest,
        ordered_entries, ordered_groups, ordered_diagnostics,
        core_complete, whole_release_eligible, release_ineligible, blocking,
    )


def ledger_json_bytes(result: LedgerResult) -> bytes:
    """Serialize stable UTF-8 JSON with no current-time/workdir/store identity."""
    if not isinstance(result, LedgerResult):
        raise ProfileError("LEDGER_RESULT_REQUIRED", type(result).__name__)
    payload = json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (payload + "\n").encode("utf-8")
