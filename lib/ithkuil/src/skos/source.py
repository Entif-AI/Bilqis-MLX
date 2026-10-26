"""Public source-reference projection for issue #39."""

from __future__ import annotations

from collections import defaultdict

from rdflib import Graph, Literal, URIRef
from rdflib.namespace import DCTERMS

from .identity import Identity
from .preflight import CompilerClosure
from .resolver import RecordRef, resolve_identities
from .source_public import (
    PublicLocus,
    clean_locator_parts,
    public_source_url,
    safe_public_literal,
)
from .source_types import PRIMARY_KEYS, SourceIssue, SourceProjection


class SourceProjector:
    """Project one resolved resource's RecordRefs into public DCTERMS source RDF."""

    def __init__(self, closure: CompilerClosure):
        if not isinstance(closure, CompilerClosure):
            raise TypeError("SourceProjector requires CompilerClosure")
        self.closure = closure
        self._rows = {}
        for table_name, primary_key in PRIMARY_KEYS.items():
            table = closure.table(table_name)
            self._rows[table_name] = {row[primary_key]: row for row in table.rows}
        self._sources = {
            row["source_id"]: row for row in closure.table("source_manifest").rows
        }
        self._sections = {
            (row["source_id"], row["section_id"]): row
            for row in closure.table("source_sections").rows
        }
        self._tables = {
            (row["source_id"], row["table_id"]): row
            for row in closure.table("source_tables").rows
        }
        assertions = defaultdict(list)
        for row in closure.table("source_assertions").rows:
            assertions[(row["entity_kind"], row["entity_id"])].append(row)
        self._assertions = {
            key: tuple(sorted(rows, key=lambda row: row["assertion_id"]))
            for key, rows in assertions.items()
        }
        resolution = resolve_identities(closure)
        self._resource_refs = {
            resource.identity: frozenset(resource.source_records)
            for resource in resolution.resources
        }
        self._resolved_refs = frozenset(
            ref for refs in self._resource_refs.values() for ref in refs
        )

    def _issue(
        self, code: str, identity: Identity, refs: tuple[RecordRef, ...], *details: str
    ) -> SourceIssue:
        return SourceIssue(code, identity.iri, tuple(sorted(set(refs))), tuple(sorted(details)))

    def _registry_source(
        self,
        identity: Identity,
        ref: RecordRef,
        source_id: str,
        record_url: str,
    ) -> tuple[object | None, SourceIssue | None]:
        source = self._sources.get(source_id)
        if source is None:
            return None, self._issue(
                "SOURCE_REGISTRY_NOT_FOUND", identity, (ref,), f"source_id={source_id}"
            )
        canonical = source["final_url"]
        if record_url != canonical:
            return None, self._issue(
                "SOURCE_URL_REGISTRY_MISMATCH",
                identity,
                (ref,),
                f"source_id={source_id}",
            )
        if not public_source_url(canonical):
            return None, self._issue(
                "SOURCE_URL_NOT_PUBLIC", identity, (ref,), f"source_id={source_id}"
            )
        if safe_public_literal(source["source_id"]) is None or safe_public_literal(source["title"]) is None:
            return None, self._issue(
                "SOURCE_PUBLIC_LITERAL_REJECTED", identity, (ref,), f"source_id={source_id}"
            )
        return source, None

    def _validate_web_locus(
        self,
        identity: Identity,
        ref: RecordRef,
        source_id: str,
        section_id: str,
        table_id: str,
    ) -> SourceIssue | None:
        if section_id:
            section = self._sections.get((source_id, section_id))
            if section is None:
                return self._issue(
                    "SOURCE_SECTION_NOT_FOUND", identity, (ref,), f"section_id={section_id}"
                )
        if table_id:
            table = self._tables.get((source_id, table_id))
            if table is None:
                return self._issue(
                    "SOURCE_TABLE_NOT_FOUND", identity, (ref,), f"table_id={table_id}"
                )
        return None

    def _web_locus(
        self,
        identity: Identity,
        ref: RecordRef,
        row,
        *,
        source_field: str,
        section_field: str,
        table_field: str,
        line_field: str,
        url_field: str,
        anchor_field: str,
    ) -> tuple[PublicLocus | None, SourceIssue | None]:
        source_id = row.get(source_field)
        source, issue = self._registry_source(identity, ref, source_id, row.get(url_field))
        if issue:
            return None, issue
        section_id = row.get(section_field)
        table_id = row.get(table_field)
        issue = self._validate_web_locus(identity, ref, source_id, section_id, table_id)
        if issue:
            return None, issue
        parts = clean_locator_parts(
            [
                ("source", source_id),
                ("section", section_id),
                ("table", table_id),
                ("line", row.get(line_field)),
                ("anchor", row.get(anchor_field)),
            ]
        )
        if parts is None:
            return None, self._issue("SOURCE_PUBLIC_LITERAL_REJECTED", identity, (ref,))
        identifier = ";".join(f"{label}={value}" for label, value in parts)
        citation = "; ".join(
            [source["title"], *(f"{label} {value}" for label, value in parts)]
        ) + "."
        return PublicLocus(
            source["final_url"],
            source_id,
            source["title"],
            parts,
            identifier,
            citation,
        ), None

    def _lexicon_locus(
        self, identity: Identity, ref: RecordRef, row, *, sense: bool
    ) -> tuple[PublicLocus | None, SourceIssue | None]:
        source_id = row["source_id"]
        source, issue = self._registry_source(identity, ref, source_id, row["source_url"])
        if issue:
            return None, issue
        parts = [
            ("source", source_id),
            ("chapter", row["lexicon_chapter"]),
            ("section", row["lexicon_section"]),
            ("root", row["root_form_raw"]),
        ]
        if sense:
            parts.extend(
                [("stem", row["stem"] or "ROOT-WIDE"), ("specification", row["specification"])]
            )
        parts.extend(
            [
                ("printed_page", row["source_printed_page"]),
                ("tracked_chapter_page", row["source_pdf_page"]),
            ]
        )
        cleaned = clean_locator_parts(parts)
        if cleaned is None:
            return None, self._issue("SOURCE_PUBLIC_LITERAL_REJECTED", identity, (ref,))
        identifier = ";".join(
            f"{label}={value}" for label, value in cleaned
        )
        citation_parts = [
            source["title"],
            f"source {source_id}",
            f"chapter {row['lexicon_chapter']}",
            f"section {row['lexicon_section']}",
            f"root {row['root_form_raw']}",
        ]
        if sense:
            citation_parts.extend(
                [
                    f"stem {row['stem'] or 'ROOT-WIDE'}",
                    f"specification {row['specification']}",
                ]
            )
        citation_parts.extend(
            [
                f"printed page {row['source_printed_page']}",
                f"tracked chapter PDF page {row['source_pdf_page']}",
            ]
        )
        citation = "; ".join(citation_parts) + "."
        if safe_public_literal(citation) is None:
            return None, self._issue("SOURCE_PUBLIC_LITERAL_REJECTED", identity, (ref,))
        return PublicLocus(
            source["final_url"],
            source_id,
            source["title"],
            cleaned,
            identifier,
            citation,
        ), None

    def _loci_for_ref(
        self, identity: Identity, ref: RecordRef
    ) -> tuple[tuple[PublicLocus, ...], tuple[SourceIssue, ...]]:
        rows = self._rows.get(ref.table)
        if rows is None:
            return (), (self._issue("UNSUPPORTED_SOURCE_RECORD", identity, (ref,), ref.table),)
        row = rows.get(ref.key)
        if row is None:
            return (), (self._issue("SOURCE_RECORD_NOT_FOUND", identity, (ref,), ref.key),)
        web_args = dict(
            source_field="source_id",
            section_field="section_id",
            table_field="table_id",
            line_field="source_line",
            url_field="source_url",
            anchor_field="source_anchor",
        )
        if ref.table == "morphemes_atomic":
            primary, issue = self._web_locus(
                identity,
                ref,
                row,
                source_field="primary_source_id",
                section_field="primary_section_id",
                table_field="primary_table_id",
                line_field="primary_source_line",
                url_field="primary_source_url",
                anchor_field="primary_source_anchor",
            )
            loci = [primary] if primary else []
            issues = [issue] if issue else []
            for assertion in self._assertions.get(("atomic_morpheme", ref.key), ()):
                assertion_ref = RecordRef("source_assertions", assertion["assertion_id"])
                locus, problem = self._web_locus(identity, assertion_ref, assertion, **web_args)
                if locus:
                    loci.append(locus)
                if problem:
                    issues.append(problem)
            return tuple(sorted(set(loci))), tuple(sorted(set(issues)))
        if ref.table in {"grammatical_categories", "root_senses", "source_assertions"}:
            locus, issue = self._web_locus(identity, ref, row, **web_args)
        elif ref.table == "lexicon_roots":
            locus, issue = self._lexicon_locus(identity, ref, row, sense=False)
        elif ref.table == "lexicon_root_senses":
            locus, issue = self._lexicon_locus(identity, ref, row, sense=True)
        else:
            return (), (self._issue("UNSUPPORTED_SOURCE_RECORD", identity, (ref,), ref.table),)
        return ((locus,) if locus else ()), ((issue,) if issue else ())

    def _project_refs(
        self, identity: Identity, source_records: tuple[RecordRef, ...]
    ) -> SourceProjection:
        graph = Graph()
        loci = set()
        issues = set()
        held = set()
        for ref in sorted(set(source_records)):
            ref_loci, ref_issues = self._loci_for_ref(identity, ref)
            loci.update(ref_loci)
            issues.update(ref_issues)
            for issue in ref_issues:
                held.update(issue.record_refs)
        resource = URIRef(identity.iri)
        for locus in sorted(loci):
            locus_iri = URIRef(locus.iri)
            source_iri = URIRef(locus.source_url)
            graph.add((resource, DCTERMS.source, locus_iri))
            graph.add((locus_iri, DCTERMS.source, source_iri))
            graph.add((locus_iri, DCTERMS.identifier, Literal(locus.identifier)))
            graph.add((locus_iri, DCTERMS.bibliographicCitation, Literal(locus.citation)))
            graph.add((source_iri, DCTERMS.identifier, Literal(locus.source_id)))
            graph.add((source_iri, DCTERMS.bibliographicCitation, Literal(locus.source_title)))
        if not loci:
            issues.add(
                self._issue(
                    "NO_PUBLIC_SOURCE_LOCUS",
                    identity,
                    tuple(source_records),
                    "resource has no permissible public source locus",
                )
            )
            held.update(source_records)
        return SourceProjection(graph, tuple(sorted(issues)), tuple(sorted(held)))

    def project_resource(
        self, identity: Identity, source_records: tuple[RecordRef, ...]
    ) -> SourceProjection:
        allowed = self._resource_refs.get(identity)
        requested = frozenset(source_records)
        if allowed is None:
            issue = self._issue(
                "SOURCE_IDENTITY_NOT_RESOLVED",
                identity,
                tuple(source_records),
                "identity is not a successful #38 resolved resource",
            )
            return SourceProjection(Graph(), (issue,), tuple(sorted(requested)))
        if requested != allowed:
            issue = self._issue(
                "SOURCE_RECORD_BINDING_MISMATCH",
                identity,
                tuple(source_records),
                "expected=" + ",".join(f"{ref.table}:{ref.key}" for ref in sorted(allowed)),
            )
            return SourceProjection(Graph(), (issue,), tuple(sorted(requested)))
        return self._project_refs(identity, source_records)

    def project_group(
        self, identity: Identity, member_source_records: tuple[RecordRef, ...]
    ) -> SourceProjection:
        if identity.kind not in {"scheme", "collection", "ordered_collection"}:
            issue = self._issue(
                "SOURCE_GROUP_KIND_REQUIRED", identity, tuple(member_source_records), identity.kind
            )
            return SourceProjection(Graph(), (issue,), tuple(sorted(set(member_source_records))))
        requested = frozenset(member_source_records)
        unknown = requested - self._resolved_refs
        if unknown:
            issue = self._issue(
                "SOURCE_GROUP_MEMBER_REF_NOT_RESOLVED",
                identity,
                tuple(sorted(unknown)),
            )
            return SourceProjection(Graph(), (issue,), tuple(sorted(unknown)))
        return self._project_refs(identity, tuple(sorted(requested)))
