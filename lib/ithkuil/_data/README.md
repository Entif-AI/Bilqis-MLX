# New Ithkuil relational grammar CSV experiment

This is a standalone, neural-inert research experiment tracked by protected issue `socr8s/private-ip#347` and governed by `IPR-0220` / protected issue `#336` plus `SPEC-0001`.

The experiment builds a source-traceable relational CSV representation of the current New Ithkuil grammar. Official `ithkuil.net` grammar pages and the linked lexicon are the primary linguistic evidence. The live Bilqis Curriculum Registry is enrichment evidence only. Nothing in this folder admits a semantic identity, grade, lesson, or neural-training action.

## Required outputs

The user-required primary tables are:

- `csv/morphemes_atomic.csv`: singular morphemes, allomorphs, or atomic grammatical exponents;
- `csv/morpheme_compositions.csv`: constructions, templates, or attested forms containing more than one morpheme.

Supporting relational tables may preserve information that would be lossy in those two flat tables, including source hierarchy, grammatical categories, paradigms/examples, typed entity relationships, and Bilqis crosswalk/provenance.

The current schema is documented in [`../SCHEMA.md`](../SCHEMA.md). The present snapshot contains 772 atomic surface records and 1,917 composition/template records, plus 3,855 component edges, 200 root-sense rows, 19 explicit C_A allomorph rules, normalized source/category/degree tables, and Bilqis enrichment.

## Ordering boundary

Website hierarchy is source structure and is retained: chapter, section, subsection, anchor, and parent-child relationships belong in the data.

Curriculum teaching order does not belong in the data. Spreadsheet row order, grade order, tranche order, proposed lesson sequence, or any other pedagogical sequence must not be emitted as an ordering field or inferred as authority. Semantic prerequisite or composition relationships may be retained when they describe meaning rather than teaching schedule.

## Source snapshot

From `lib/ithkuil`, run:

```bash
python3 src/fetch_sources.py
```

Raw downloaded source files are written to ignored `_raw/`. `csv/sources/source_manifest.csv` is tracked and records source URLs, content hashes, response metadata, and snapshot time. This keeps the experiment reproducible without vendoring the complete copyrighted source pages into Git.

The grammar HTML is parsed into the tracked relational tables. The two lexicon PDFs and affix-reference PDF are currently fetched and SHA-pinned as provenance inputs, but their PDF contents are not yet systematically parsed into canonical lexical records. Lexicon references present in the Bilqis enrichment tables therefore remain source-linked registry/adjudication evidence, not proof that the full lexicon has been ingested.

The live Curriculum Registry is exported separately through authenticated Google Drive access. Its workbook bytes are not committed. Derived enrichment rows must retain tab/range provenance and source-state labels.

After the authenticated tab snapshots have been written under ignored `_private/curriculum/`, rebuild the tracked relational data with:

```bash
python3 src/build_structure.py
python3 src/build_curriculum_enrichment.py
python3 src/build_morphology.py
python3 src/validate_dataset.py
```

## Data fidelity

- Preserve exact grammatical forms, category/value abbreviations, source anchors, and identifiers where source fidelity requires them.
- Prefer compact factual normalization or paraphrase for explanatory prose. Do not copy long lesson passages into the CSVs.
- Separate observed source facts, normalized structure, and Bilqis enrichment.
- Keep ambiguous or merely analogous Bilqis mappings explicitly qualified rather than silently equating them with New Ithkuil semantics.
- Every generated record must be traceable to at least one source row, page, section, table, or spreadsheet locus.

