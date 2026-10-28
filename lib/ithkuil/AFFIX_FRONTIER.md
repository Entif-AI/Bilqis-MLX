# Affix-reference source extraction (#85)

## Source and mapping review

The observation authority is `NI-AFFIX-PDF`, the manifest-pinned 140-page PDF 1.3
`newithkuil_affixes.pdf`, SHA-256
`5b758ff4c79ba6ccb6e241e59507f7849a7c470c4b34b431bf546cd028aea3aa`.
This is Stage A source extraction, not semantic or curriculum admission.

The structural inventory finds 440 tables. A strict ordinary-form probe finds
406 complete affix tables, 18 recognized headers with irregular degree bodies,
and 16 other structures. PIC appears twice on page 136 and requires explicit
duplicate handling before publication. These are observation counts, not final
admission counts.

Observed forms include ordinary two-column tables; blank layout columns;
multi-affix numeric, motion and spatial overviews; headerless continuation
tables; missing or split root boundaries; cross-page RTI and DPC tables;
three/four-field degree rows (LVL, MCS, SNC); nested IVL headings; a wide
case-accessor chart; explanatory prose, cross-references and footnotes.
Each unadmitted form remains source-locus debt. Proximity does not authorize
joining a continuation or assigning a footnote to an affix.

Two mappings were considered. Adding `affix_degrees` would require an existing
atomic root foreign key that the PDF does not supply. That would fabricate a
linguistic identity. The existing `source_tables` and `source_table_cells`
instead represent observed structure directly. They retain physical row/column
coordinates, source identity, compact literal cells and complete-text hashes.
PDF page anchors plus the extraction ledger retain exact table/cell bounding
boxes. No relational column or enum change is needed. Section/chapter references
remain empty when the PDF does not declare that hierarchy.

Table identity is the explicit affix code within `NI-AFFIX-PDF`. Cell identity
uses that code plus header field or explicit degree and field role. Page,
extraction order and English wording are locators/content, never identity.
Literal notation, including asterisks, is not interpreted as a root relation.
Repeated/conflicting identities are held rather than silently overwritten.
All pre-existing HTML structure and atomic/degree identities remain unchanged.

## Execution checkpoint

- Blocking first steps: pinned source and observed shapes checked; mapping above
  reviewed against existing schemas and the morphology builder's HTML-only path.
- Independent workstreams: one extractor/test owner; one integration/docs owner.
- Shared mutable state: only the integration owner publishes canonical CSVs.
- Smallest safe decomposition: one source parser, existing rebuild entrypoint,
  staged dataset validation, and one generated admission receipt. No per-page work.

Only issue-specific extraction, compatibility, negative-case and admission proofs
are required before the relevant subsystem gate. Completed lexicon slices are
not re-audited as a prerequisite.

## Result

The admitted strict rule accepts 403 complete tables and 8,060 cells. Thirty-five
tables remain unsupported; both PIC occurrences are held. The initial probe's
406 candidates included SPT's explicit alternate-form notation `-rw/-ry`, not
admitted by the single-root rule, plus those two repeated identities.

The complete ledger accounts for all 440 detected tables and every nonempty
extracted text span. It records 19,954 observations, including emitted cell
observations. Dispositions are 8,463 parsed, 1,994 table-covered spans, 9,495
unsupported table/text observations and two conflicts. Partial table overlap
is not full coverage and remains explicit debt. Long text is represented by
full-text digest and length rather than copied into Git.

Canonical totals are 727 tables and 13,457 cells, including the unchanged
324-table/5,397-cell HTML slice. The existing 271 affix-degree rows, 772 atomic
rows, and all lexicon rows are byte-identical. Core RDF retains SHA-256
`49aaf11d3d2a7d4dd758be022e8a82ce66804ef6b03a2d210b8289ca7d263d60`
and 67,869 triples. The only core ledger growth is 403 `IR_ONLY` source rows.

The independent pre-commit review found a validator-only source-pin gap.
Validation now rehashes the actual PDF, not only its manifest and receipt; a
negative fixture proves local source drift is rejected without rebuilding.
Agent-interface disposition is `RAW_INTERFACE_JUSTIFIED`: this extends the
existing source-rebuild CLI and adds no parallel agent protocol.
