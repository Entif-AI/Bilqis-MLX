# New Ithkuil relational grammar CSV experiment

This is a standalone, neural-inert research experiment tracked by protected issue `socr8s/private-ip#347` and governed by `IPR-0220` / protected issue `#336` plus `SPEC-0001`.

The experiment builds a source-traceable relational CSV representation of the current New Ithkuil grammar. Official `ithkuil.net` grammar pages and the linked lexicon are the primary linguistic evidence. The live Bilqis Curriculum Registry is enrichment evidence only. Nothing in this folder admits a semantic identity, grade, lesson, or neural-training action.

## Required outputs

The user-required primary tables are:

- `csv/morphemes_atomic.csv`: singular morphemes, allomorphs, or atomic grammatical exponents;
- `csv/morpheme_compositions.csv`: constructions, templates, or attested forms containing more than one morpheme.

Supporting relational tables may preserve information that would be lossy in those two flat tables, including source hierarchy, grammatical categories, paradigms/examples, typed entity relationships, and Bilqis crosswalk/provenance.

The current schema is documented in [`../SCHEMA.md`](../SCHEMA.md). The present snapshot contains 772 atomic surface records and 1,917 composition/template records, plus 3,855 component edges, 200 grammar-derived root-sense rows, 625 Chapter-1–3 lexicon roots, 1,673 Chapter-1–3 lexicon sense rows, 363 compact lexicon context-evidence rows, 19 explicit C_A allomorph rules, normalized source/category/degree tables, and Bilqis enrichment.

## Ordering boundary

Website hierarchy is source structure and is retained: chapter, section, subsection, anchor, and parent-child relationships belong in the data.

Curriculum teaching order does not belong in the data. Spreadsheet row order, grade order, tranche order, proposed lesson sequence, or any other pedagogical sequence must not be emitted as an ordering field or inferred as authority. Semantic prerequisite or composition relationships may be retained when they describe meaning rather than teaching schedule.

## Source snapshot

From `lib/ithkuil`, run:

```bash
python3 src/fetch_sources.py
```

Raw downloaded source files are written to ignored `_raw/`. `csv/sources/source_manifest.csv` is tracked and records source URLs, content hashes, response metadata, and snapshot time. This keeps the experiment reproducible without vendoring the complete copyrighted source pages into Git.

The grammar HTML is parsed into the tracked relational tables. The canonical lexicon and affix-reference PDFs are fetched and SHA-pinned provenance inputs. The tracked split lexicon Chapters 1–3 are additionally parsed into source-corpus tables with exact split-PDF hashes and page/table loci. Those rows are **not** semantic admission or curriculum order. Chapters 4–7 and the affix-reference PDF remain outside the accepted extraction frontier.

The live Curriculum Registry is exported separately through authenticated Google Drive access. Its workbook bytes are not committed. Derived enrichment rows must retain tab/range provenance and source-state labels.

After the authenticated tab snapshots have been written under ignored `_private/curriculum/`, rebuild the tracked relational data with:

```bash
python3 src/build_structure.py
python3 src/build_curriculum_enrichment.py
python3 src/build_morphology.py
python3 src/build_lexicon_chapters.py
python3 src/validate_dataset.py
```

To regenerate the **revisable curriculum-research projection** (not canonical source truth and not semantic admission), run:

```bash
python3 src/build_curriculum_frontier.py
```

That builder writes the D-O proposal, 96-root reserve, full 503-root source inventory and 1,615-sense candidate surface under ignored `_private/curriculum_frontier/` by default. Set `BILQIS_CURRICULUM_FRONTIER_OUT` to another directory for deterministic test or review builds. Every D-O target names an explicit source root + Stem + Specification and the build fails if that source-sense contract is incomplete.

## Data fidelity

- Preserve exact grammatical forms, category/value abbreviations, source anchors, and identifiers where source fidelity requires them.
- Prefer compact factual normalization or paraphrase for explanatory prose. Do not copy long lesson passages into the CSVs.
- Separate observed source facts, normalized structure, and Bilqis enrichment.
- Keep ambiguous or merely analogous Bilqis mappings explicitly qualified rather than silently equating them with New Ithkuil semantics.
- Every generated record must be traceable to at least one source row, page, section, table, or spreadsheet locus.
- Curriculum research projections must refer back to canonical `lexicon_sense_id` / `lexicon_evidence_id` values; they must not copy grade, rank or teaching-order fields back into canonical source CSVs.


## Accepted later-chapter source extraction (#80)

From the repository root, after restoring the exact pinned raw canonical PDF:

```sh
python3 -B -m lib.ithkuil.src.build_lexicon_chapters \
  --admit-chapter 3 --canonical-pdf lib/ithkuil/_raw/New_Ithkuil_Lexicon.pdf
python3 -B -m lib.ithkuil.src.validate_dataset
```

`lexicon_frontier_pins.json` identifies the split artifact and format before
extraction. Chapter 3 has 17 pages, exactly matching normalized extracted text on
canonical PDF pages 99–115. The receipt makes no byte-derivative claim.
The existing extractor dispatches accepted later chapters through
`lexicon_frontier.py`; an ordinary rebuild retains that accepted frontier.
Admission validates a staged copy of the full CSV corpus before publishing it.
The profile publishes last; Git preserves recoverable source state.

Chapter 3 contributes 122 root observations, 58 explicitly scoped senses and 213
compact evidence rows. The ledger records 183 insufficient-scope debt entries and
five unsupported structures. Two unsupported tables have no supported root link
and remain only in the chapter ledger. Root-linked debt uses the existing evidence
table; unresolved dimensions never become guessed senses. Debt entries count source
units, not distinct roots. 98 Chapter 3 roots have no parsed senses.

New sense locators use source identity, exact root form, Stem and Specification;
English wording never enters the key. Earlier Chapter 1–2 rows retain their exact
accepted bytes and identities. Multi-Stem merged cells, unqualified Stem/Specification
scope and inherited-pattern prose stay debt until separately supported rules exist.
The legacy parser's accepted Chapter 1–2 behavior remains reproducible explicitly.

`sources/lexicon_frontier_manifest.json` binds per-chapter pins, parser version/code
hashes, page maps, output hashes, counts and legacy compatibility hashes.
`sources/lexicon_frontier/chapter-3-accounting.json` retains exact debt loci and
source fingerprints. `tests/fixtures/chapter3_extraction_expected.json` freezes
literal source and output expectations. These artifacts admit source observations
only; they create no curriculum, model update or semantic mapping authority.
