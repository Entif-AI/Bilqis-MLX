# New Ithkuil relational grammar CSV experiment

This is a standalone, neural-inert research experiment tracked by protected issue `socr8s/private-ip#347` and governed by `IPR-0220` / protected issue `#336` plus `SPEC-0001`.

The experiment builds a source-traceable relational CSV representation of the current New Ithkuil grammar. Official `ithkuil.net` grammar pages and the linked lexicon are the primary linguistic evidence. The live Bilqis Curriculum Registry is enrichment evidence only. Nothing in this folder admits a semantic identity, grade, lesson, or neural-training action.

## Required outputs

The user-required primary tables are:

- `data/morphemes_atomic.csv`: singular morphemes, allomorphs, or atomic grammatical exponents;
- `data/morpheme_compositions.csv`: constructions, templates, or attested forms containing more than one morpheme.

Supporting relational tables may preserve information that would be lossy in those two flat tables, including source hierarchy, grammatical categories, paradigms/examples, typed entity relationships, and Bilqis crosswalk/provenance.

The current schema is documented in [`SCHEMA.md`](SCHEMA.md). The present snapshot contains 710 atomic surface records and 1,645 composition/template records, plus normalized source, component, category, degree, sense, and Bilqis-enrichment tables.

## Ordering boundary

Website hierarchy is source structure and is retained: chapter, section, subsection, anchor, and parent-child relationships belong in the data.

Curriculum teaching order does not belong in the data. Spreadsheet row order, grade order, tranche order, proposed lesson sequence, or any other pedagogical sequence must not be emitted as an ordering field or inferred as authority. Semantic prerequisite or composition relationships may be retained when they describe meaning rather than teaching schedule.

## Source snapshot

Run:

```bash
python3 scripts/fetch_sources.py
```

Raw downloaded source files are written to ignored `_raw/`. `sources/source_manifest.csv` is tracked and records source URLs, content hashes, response metadata, and snapshot time. This keeps the experiment reproducible without vendoring the complete copyrighted source pages into Git.

The live Curriculum Registry is exported separately through authenticated Google Drive access. Its workbook bytes are not committed. Derived enrichment rows must retain tab/range provenance and source-state labels.

After the authenticated tab snapshots have been written under ignored `_work/curriculum/`, rebuild the tracked relational data with:

```bash
python3 scripts/build_structure.py
python3 scripts/build_curriculum_enrichment.py
python3 scripts/build_morphology.py
python3 scripts/validate_dataset.py
```

## Data fidelity

- Preserve exact grammatical forms, category/value abbreviations, source anchors, and identifiers where source fidelity requires them.
- Prefer compact factual normalization or paraphrase for explanatory prose. Do not copy long lesson passages into the CSVs.
- Separate observed source facts, normalized structure, and Bilqis enrichment.
- Keep ambiguous or merely analogous Bilqis mappings explicitly qualified rather than silently equating them with New Ithkuil semantics.
- Every generated record must be traceable to at least one source row, page, section, table, or spreadsheet locus.

