# Deterministic New Ithkuil semantic compiler

The compiler consumes the tracked relational CSV corpus under `_data/csv/`.
`SKOS_PROFILE.md` governs semantic identity and RDF meaning. The compiler does not
fetch sources, call a model, connect to FalkorDB, consult curriculum ordering, or
open student/training state. Each stage preserves source identifiers and explicit
held/error outcomes instead of resolving ambiguity from labels or row order.

Install the source-only dependencies with:

```sh
python3 -m pip install -r lib/ithkuil/requirements-semantic.txt
```

## 1. Tracked CSV input closure (#37)

`src/skos/compiler_input_manifest.json`, version
`bilqis.skos.compiler-input/v1`, defines the exact required files, headers, primary
keys, required fields, finite enum states, ordinary/composite/conditional foreign
keys, source URL bindings and structural invariants. It is checked configuration;
unsupported versions, duplicate names, unsafe relative paths, missing references
and unknown invariant names fail with `INVALID_COMPILER_INPUT_MANIFEST`.

The twelve input tables are `source_manifest`, `curriculum_manifest`,
`source_sections`, `source_tables`, `source_assertions`, `grammatical_categories`,
`morphemes_atomic`, `root_senses`, `lexicon_roots`, `lexicon_root_senses`,
`lexicon_root_evidence` and `morpheme_compositions`. The manifest records their
relative paths and roles. `morpheme_compositions` is included as foreign-key support
because source assertions refer to it; this does not authorize core composition RDF.
`curriculum_manifest` records source provenance only, never semantic or teaching order.
Deferred non-core tables and their owner boundaries are explicit in the manifest.

```python
from lib.ithkuil.src.skos.preflight import preflight

result = preflight("lib/ithkuil/_data/csv")
print(result.as_dict())
closure = result.require_valid()
atomic_rows = closure.table("morphemes_atomic").rows
```

The public preflight has an explicit input root and returns a frozen
`PreflightResult`. A successful result exposes a `CompilerClosure` of immutable
tables and rows. `row[field]` and `row.get(field)` preserve exact source text. Table
rows are sorted by declared keys and content, so iteration is independent of CSV
row order. `load_input_root` owns file I/O; `validate_loaded` validates its immutable
values without further I/O. The downstream build entrypoint is owned by #43.

Blocking input yields sorted findings with `code`, `table`, `key`, `field`, `locus`
and `details`; `.closure` is absent and `require_valid()` raises a stable
`ProfileError`. No RDF, digest or held-ledger artifact is written by preflight.
Malformed CSV records use a content fingerprint rather than an unstable row number.
This diagnostic fingerprint is not semantic identity. Accepted source values are
not silently trimmed, normalized or repaired.

Required failures include missing table/column, unexpected/duplicate headers,
malformed UTF-8/CSV, blank or duplicate primary keys, unknown foreign keys,
source-assertion entity mismatch, missing source assertions, unknown enum states,
source URL drift and lexicon parent/source binding conflicts. A filesystem read
failure is reported as `TABLE_READ_ERROR`; an unknown assertion selector is a
validation finding rather than an uncaught lookup error.

Structural grammar consistency compares `(category_code, value_code)` against
the source's canonical category/value labels. It does not require all realization
summaries, family memberships or surface forms to be identical. Register initial
and final forms legitimately share one grammar identity. Definition disagreements
and source-shape qualification remain the resolver/normalization owners (#38/#46).
Lexicon sense coordinates follow profile section 1; gloss-dependent legacy row IDs
are retained as source locators, not reused as semantic IRI keys.

Source/section and source/table foreign keys are checked together. A source record
may refer to a table from another section of the same document where the source
does so; the compiler does not invent a section-equality rule. Lexicon children must
agree with their referenced root's source, chapter, section and split-PDF binding.
`source_manifest` owns source IDs. Workbook tabs do not become semantic sources.

The existing extraction validator requires cached raw downloads and serves a
different extraction workflow. Semantic preflight deliberately does not call it:
a fresh tracked-CSV checkout is sufficient.

Run the preflight proofs from the repository root:

```sh
python3 -B -m unittest lib.ithkuil.tests.test_skos_preflight \
  lib.ithkuil.tests.test_skos_preflight_hardening -v
```

The tests validate the current corpus, reverse every table, corrupt each required
boundary in a temporary copy, exercise malformed configuration, and prove that a
blocking source error cannot produce an RDF artifact. They assert literal expected
reason codes and source keys; no model or graph database is required.
