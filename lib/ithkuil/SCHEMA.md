# Relational schema

This experiment separates linguistic entities from source assertions. Stable IDs let one entity carry multiple source loci without duplicating the entity itself.

## Primary tables

### `_data/csv/morphemes_atomic.csv`

One row per singular surface exponent, root, or explicitly conditioned allomorph.

Key fields:

- `atomic_id`: stable entity ID derived from the linguistic identity and surface condition.
- `surface_form_raw` / `surface_form_normalized`: source-facing and join-facing forms.
- `morpheme_family` / `morpheme_class`: grammatical role and physical exponent type.
- `category_code`, `value_code`, names: category/value identity.
- `realization_type`, `allomorph_group_id`, `allomorph_condition`: overt, zero, optional, conditioned, underlying, and realized distinctions.
- `derivation`: direct source table, source rule plus table, or another explicit source-backed derivation.
- `primary_source_*`: one canonical source locus; additional attestations live in `source_assertions.csv`.

### `_data/csv/morpheme_compositions.csv`

One row per source-declared multi-morpheme template or source-derived composition.

Key fields:

- `composition_id`: stable entity ID.
- `surface_form_raw`: populated for concrete composed forms.
- `surface_pattern`: populated for templates such as `V_X + C_S` or the ten-slot formative.
- `composition_type`: construction class such as `VXCS_affix`, `case_accessor`, or `construction_template`.
- `component_count`: foreign-key checked against `composition_components.csv`.
- `condition`: source-stated allomorph or construction condition.
- `derivation`: `source_template` or `source_join`. A source join means every component and the joining rule are independently attested.

`position_in_form` in `composition_components.csv` is linguistic component order. It is not curriculum order.

## Structural and provenance tables

- `source_sections.csv`: website chapter/section/subsection hierarchy with parent IDs and real source anchors when present.
- `source_tables.csv`: every HTML table tied to its containing source section and a conservative structural role.
- `source_table_cells.csv`: exact short factual cells plus hashes and lengths for long explanatory cells. Long prose is not mirrored into Git.
- `source_assertions.csv`: many-to-one provenance edges from official source loci to atomic/composed entities.
- `grammatical_categories.csv`: normalized category registry.
- `affix_degrees.csv`: degree semantics attached to attested C_S affix roots.
- `root_senses.csv`: compact stem/specification sense summaries attached to lexical roots.
- `lexicon_roots.csv`: source-corpus inventory of every root heading observed in the tracked New Ithkuil lexicon Chapter 1–2 split PDFs. These are source identities, **not** Bilqis ABI admissions or curriculum capabilities.
- `lexicon_root_senses.csv`: compact source-grounded Stem/Specification senses extracted from explicit Chapter 1–2 lexicon root tables, explicit prose Stem statements, **and compact numbered Stem 1/2/3 inventories for roots that inherit another root's Specification pattern**. Rows retain canonical lexicon source identity plus tracked split-PDF digest and exact page/table-or-prose locus.
- `lexicon_root_evidence.csv`: short source-context evidence for examples, scope restrictions, notes and inherited-Specification caveats. Long source prose is not copied wholesale; each row retains a compact excerpt plus SHA-256 and character count for the full extracted source text and an exact page/root locus.
- `sources/lexicon_split_provenance.csv`: reproducible binding between the tracked Chapter-1/2 page-projection PDFs and the canonical `NI-LEXICON-CURRICULUM` source. It records exact/near-exact extracted-text page comparison counts and deliberately does **not** claim byte-identical derivation.
- `allomorph_rules.csv`: explicit source-listed C_A substitution rules, including multi-step substitutions where the source gives an intermediate form.
- `composition_components.csv`: ordered linguistic component edges for every composed entity/template.

## Bilqis enrichment tables

- `bilqis_ithkuil_crosswalk.csv`: 222 token-level mapping/adjudication records. Newer NI Adjudication vD rows supersede duplicate vD mapping-review semantics while retaining mapping revision provenance. Every row resolves to a pinned current source document or section.
- `bilqis_semantic_bridges.csv`: 330 concept-level bridge rows. Current official sources resolve into the source graph; two 2011 predecessor rows remain explicit historical-only targets. `registry_state_raw` preserves the workbook's exact epistemic/gate state and `bridge_epistemic_state` gives a compact normalized class such as `proposal`, `blocked`, `deferred`, or `historical_only`.

The enrichment tables preserve qualified, partial, adapter, compositional, native-protocol, rejected-equivalence, and historical relation states. They do not promote a similarity into semantic identity.

## Source manifests

- `_data/csv/sources/source_manifest.csv`: 18 official source identities with URL, byte length, hash, HTTP metadata, and snapshot time.
- `_data/csv/sources/curriculum_manifest.csv`: authenticated workbook tab/range/hash receipts for the eight tabs used by the experiment.

The lower-case grammar-site lexicon and the capitalized lexicon URL used in the Curriculum Registry are separate source identities because their bytes and SHA-256 hashes differ.

The grammar extractor parses the official grammar HTML. The canonical lexicon and affix-reference PDFs remain fetched and hash-pinned source identities. The tracked split lexicon Chapters 1 and 2 are additionally parsed into `lexicon_roots.csv` and `lexicon_root_senses.csv`; those tables are a source-corpus layer and do not mint Bilqis token IDs, grades, lessons, or mastery. Later tracked chapters 3–7 can be extracted separately with `python3 src/build_lexicon_chapters.py --next --output <directory>`. Expanded snapshots retain exact input/output hashes, explicit roots-without-senses debt and `tracked_source_projection_observed` status. Canonical full-PDF page equivalence remains `NOT_MEASURED`; these snapshots do not change the canonical Chapter-1/2 tables or current research frontier. The affix-reference PDF remains unparsed.

## Rebuild and validation

With the authenticated curriculum JSON cache already present in ignored `_private/curriculum/`, run from `lib/ithkuil`:

```bash
python3 src/fetch_sources.py
python3 src/build_structure.py
python3 src/build_curriculum_enrichment.py
python3 src/build_morphology.py
python3 src/build_lexicon_chapters.py
python3 src/validate_dataset.py
```

`build_lexicon_chapters.py` requires the pinned extraction dependency in `requirements-extraction.txt` and reads only the tracked split PDFs in `_data/pdf/`. `validate_dataset.py` checks source and entity cardinalities, lexicon root/sense identities and loci, foreign keys, composition component counts, core grammar inventory counts, Slot-IV V_R and register/suppletive coverage, exact C_A substitution rules and triggers, explicit root-paradigm coverage, current-vs-historical crosswalk resolution, exclusion of curriculum-order columns across every derived data table, protected URL leakage, LF line endings, and raw/work-cache Git exclusion.

`build_curriculum_frontier.py` is intentionally **not** part of the canonical source-data rebuild. It is a tracked, deterministic research projection that reads the canonical source-domain tables and writes curriculum-order artifacts to ignored `_private/curriculum_frontier/` (or `BILQIS_CURRICULUM_FRONTIER_OUT`). Its regression test enforces 144 explicit D-O source-sense targets, 96 reserve roots, live A/B/C prerequisite closure, and the prohibition on historical unadmitted Boolean prerequisites. This keeps source truth and pedagogical ordering mechanically separate while making the curriculum proposal reproducible.

