# A08.1b.3 source-owned morphology law: bounded partial

Issue #555, parent A08.1b #418. This is **not a
constructive lesson adapter or ADAPTER_READY**.

## Source authority and exact pinned example

The A01 `source-rows.json` census certifies source-row
identities only. It does **not** contain the row's actual
grammar law. `lib/ithkuil/_data/README.md` explicitly
classifies the tracked morphology CSVs as a source-traceable
research projection, not semantic or neural admission.

The new `bilqis_mlx/factory/morphology_source.py`
therefore produces only a
`bilqis.morphology-source-law-proposal/v1` record with
`SOURCE_ROW_EVIDENCE_NOT_ADMITTED` status. It combines
two independently checked sources:

1. The registered, immutable A01 Atlas selection and
   exact source-bundle manifest, including the census
   of `morpheme_compositions` and `morphemes_atomic`
   source keys.
2. The Ithkuil source owner's versioned
   `sources/extraction_frontier.json` receipt and its
   SHA-pinned `morpheme_compositions.csv`,
   `composition_components.csv`, `morphemes_atomic.csv`,
   `source_tables.csv` and `sources/source_manifest.csv`
   bytes. The source reference must reconcile the
   table ID, source ID, line and official source URL.

One literal, unconditional source composition is
`COMP-00a9e6c3998d74`: atomic
`ATOM-b062726ad5143d` (`a`) followed by
`ATOM-7671e7f56ccfb8` (`sw`) yields the
attested surface `asw`, with source locus
`NI-WEB-CH07:T011` at line `5709`.
The resolver preserves exact row, component and
atomic-row digests plus a derived law digest.
The consumer assertion rederives the law from the
registered source and compares canonical bytes.

This is **source evidence**, not a new grammar rule
inferred from the output spelling. The resolver
explicitly holds conditional/allomorphic examples
such as `COMP-0060583f4d9807` rather than
pretending a context-free concatenation is always
legal. Unknown or unpinned IDs, modified CSV bytes,
forged frontier receipts, mutated law metadata and
source-reference drift fail closed.

## Prime proof and remaining scope

Consumed reviewed unified `7ad8f8a`, already an
ancestor of Lane A `9fa752b`; no no-op merge.
The real pinned A01 corpus test:

`BILQIS_ATLAS_REAL_CORPUS=<pinned conformance bundle> python -B scripts/run_tests.py bilqis_mlx/factory/tests/test_morphology_source.py`

**3 passed, 0 failed, 0 skipped.**
The static error-control and module-size checks
reported no new findings in this module.

**A08.1b.3 remains OPEN.** This partial does not
issue A13 source grants, generate positive/negative
teaching examples, register a Factory
`ConstructionProgram`, provide a full independent
checker, cover the complete morphology source
family or award learning/retention credit.
Those gates require source-owned law qualification,
task-scoped A13 rights and executable independent
assessment. Independent EGM of this new partial
is pending. No source promotion, live training,
optimizer mutation or self-merge occurred.
