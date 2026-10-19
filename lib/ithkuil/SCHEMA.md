# Relational schema

This experiment separates linguistic entities from source assertions. Stable IDs let one entity carry multiple source loci without duplicating the entity itself.

## Primary tables

### `data/morphemes_atomic.csv`

One row per singular surface exponent, root, or explicitly conditioned allomorph.

Key fields:

- `atomic_id`: stable entity ID derived from the linguistic identity and surface condition.
- `surface_form_raw` / `surface_form_normalized`: source-facing and join-facing forms.
- `morpheme_family` / `morpheme_class`: grammatical role and physical exponent type.
- `category_code`, `value_code`, names: category/value identity.
- `realization_type`, `allomorph_group_id`, `allomorph_condition`: overt, zero, optional, conditioned, underlying, and realized distinctions.
- `derivation`: direct source table, source rule plus table, or another explicit source-backed derivation.
- `primary_source_*`: one canonical source locus; additional attestations live in `source_assertions.csv`.

### `data/morpheme_compositions.csv`

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
- `allomorph_rules.csv`: explicit source-listed C_A substitution rules, including multi-step substitutions where the source gives an intermediate form.
- `composition_components.csv`: ordered linguistic component edges for every composed entity/template.

## Bilqis enrichment tables

- `bilqis_ithkuil_crosswalk.csv`: 222 token-level mapping/adjudication records. Newer NI Adjudication vD rows supersede duplicate vD mapping-review semantics while retaining mapping revision provenance. Every row resolves to a pinned current source document or section.
- `bilqis_semantic_bridges.csv`: 330 concept-level bridge rows. Current official sources resolve into the source graph; two 2011 predecessor rows remain explicit historical-only targets. `registry_state_raw` preserves the workbook's exact epistemic/gate state and `bridge_epistemic_state` gives a compact normalized class such as `proposal`, `blocked`, `deferred`, or `historical_only`.

The enrichment tables preserve qualified, partial, adapter, compositional, native-protocol, rejected-equivalence, and historical relation states. They do not promote a similarity into semantic identity.

## Source manifests

- `sources/source_manifest.csv`: 18 official source identities with URL, byte length, hash, HTTP metadata, and snapshot time.
- `sources/curriculum_manifest.csv`: authenticated workbook tab/range/hash receipts for the eight tabs used by the experiment.

The lower-case grammar-site lexicon and the capitalized lexicon URL used in the Curriculum Registry are separate source identities because their bytes and SHA-256 hashes differ.

## Rebuild and validation

With the authenticated curriculum JSON cache already present in ignored `_work/curriculum/`:

```bash
python3 scripts/fetch_sources.py
python3 scripts/build_structure.py
python3 scripts/build_curriculum_enrichment.py
python3 scripts/build_morphology.py
python3 scripts/validate_dataset.py
```

`validate_dataset.py` checks source and entity cardinalities, foreign keys, composition component counts, core grammar inventory counts, Slot-IV V_R and register/suppletive coverage, exact C_A substitution rules and triggers, explicit root-paradigm coverage, current-vs-historical crosswalk resolution, exclusion of curriculum-order columns across every derived data table, protected URL leakage, LF line endings, and raw/work-cache Git exclusion.

