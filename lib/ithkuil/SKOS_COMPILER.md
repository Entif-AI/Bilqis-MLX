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

## 2. Identity resolution (#38)

The resolver consumes only the immutable `CompilerClosure` returned by #37. It does
not reopen CSV files, inspect raw HTML, emit RDF, consult FalkorDB, or read curriculum
state. The normalized layer preserves source records and surface evidence while fixing
semantic identity before later source-reference and RDF stages.

### API

`resolve_identities(closure) -> Resolution` returns immutable records:

- `RecordRef(table, key)` identifies each contributing closure row by its declared
  source-table primary key.
- `Realization(record_ref, lexical_form, realization_type, condition)` preserves a
  surface realization without making it semantic identity.
- `TextAssertion(record_ref, field, text, role, scope, language)` preserves source
  text with an explicit field contract.
- `ResolvedResource(identity, role, source_records, realizations, families, texts,
  schemes)` is one resolved semantic resource.
- `ResolutionIssue(code, semantic_key, record_refs, details)` is a fail-closed held
  result naming every implicated source record.
- `Resolution(resources, issues)` is deterministically ordered and contains both
  successful identities and held ambiguity.

### Five-table normalization contract

`grammatical_categories` supplies the finite category/family contract. It does not
mint extra semantic resources. `morphemes_atomic` is split by explicit known source
shape: `lexical_consonantal_root` and `CS_consonantal_root` become generic #32 root
resources keyed by `(primary_source_id, atomic_id)`; every other explicitly known
atom class becomes a grammar concept keyed by `(category_code, value_code)`.

Rows sharing one grammar identity merge into one resource while retaining every
`RecordRef`, realization, condition, family, and text assertion. Register initial and
final rows therefore remain one REGISTER value when category/value match while both
source families remain visible. Identical forms are not deduplicated across different
source records: the two NRR zero realizations are both retained.

`lexicon_roots` become generic roots keyed by `(source_id, lexicon_root_id)`.
`root_senses` and `lexicon_root_senses` use #31 `sense_from_source()` exactly, including
the declared ROOT-WIDE/UNSPECIFIED sentinels. Sense concepts remain separate from
their notation-bearing roots.

Only successfully resolved roots are eligible sense parents. A root held for conflicting
meaning cannot leave apparently valid child senses behind. The final canonical-identity
pass also rejects duplicate canonical resources from incompatible source tables, and a
post-collision parent check removes any sense whose root was lost at that final pass.

### Text and definition boundary

`value_name` and `root_gloss` are explicit English source preferred-label assertions.
`sense_summary` is the source identity-definition assertion for a sense. No synthetic
sense display label is invented when none exists. `semantic_summary` on atomic rows is
explicitly realization-scoped `source_note`; it is not selected as a canonical concept
definition because #46 owns realization reconciliation. Raw source notation is retained
as a non-language-tagged text assertion, while normalized lexical form lives on the
realization itself. These are deliberately distinct: for example source root `-Č-` is
retained exactly in `root_form_raw` while its realization lexical form is `č`. #40 must
use the raw source assertion for SKOS notation (or an explicitly source-qualified later
alternate), not silently substitute this normalized processing form; #45 owns later
allomorph/realization normalization semantics.

Mutable labels, source hashes, row order, and legacy sense IDs do not participate in
identity. Two source-distinct senses may therefore retain identical English definition
text while remaining distinct identities.

### Fail-closed behavior and current closure

Unknown atom shapes, missing stable keys, unknown family bindings, unresolved parent
roots, conflicting meaning for one semantic coordinate, and IRI collisions produce
`ResolutionIssue` records rather than first-row-wins resources. In particular, two
legacy sense IDs that claim the same structural sense coordinate with different
`sense_summary` values hold the coordinate and name both records.

Against the current validated corpus, 3,090 semantic rows resolve with zero issues to
2,968 resources: 485 grammar concepts, 165 atomic roots, 503 lexicon roots, and 1,815
sense concepts. The 35 grammatical-category rows are family metadata for those atom
rows and are not additional semantic resources.

## 3. Public source-reference projection (#39)

The source projector consumes only a validated #37 `CompilerClosure` plus one #38
semantic identity and its `RecordRef(table, key)` tuple. It does not reopen CSV
files, fetch source URLs, inspect raw HTML/PDF bytes, walk the whole corpus, or infer
authorship, confidence, attestation, ontology semantics, or claim consequence.

### RDF shape

Only standard Dublin Core Terms predicates are emitted:

- semantic resource `dcterms:source` deterministic source-locus IRI;
- locus `dcterms:source` canonical public source-document URL;
- locus `dcterms:identifier` compact public locator;
- locus `dcterms:bibliographicCitation` human-readable public citation;
- source document `dcterms:identifier` source-registry ID;
- source document `dcterms:bibliographicCitation` public registry title.

The locus IRI is a deterministic SHA-256-derived project IRI over canonical JSON
containing the admitted public document URL plus an ordered list of named source
coordinates. Human-readable `identifier` and citation strings are display only and
do not enter the fingerprint as delimiter-joined text; punctuation such as `;`,
`=`, or `|` inside a source coordinate cannot alias another coordinate structure.
The locus is a traceability node, not semantic identity. Duplicate identical loci
therefore collapse while multiple distinct loci remain attached to the same semantic
IRI.

### Binding and public-disclosure rules

Every `RecordRef` is resolved against the exact row in the immutable compiler
closure. `SourceProjector` resolves #38 once at construction and pre-indexes the
exact semantic-identity → `RecordRef` binding. `project_resource` requires the
caller's identity and record set to match that resolved binding exactly. A valid
source row therefore cannot be transferred as apparent support for an unrelated or
arbitrary semantic IRI. This index is built once; per-resource projection does not
rerun whole-corpus resolution.

Grammar rows bind through the tracked `source_manifest`, source-qualified
section/table registries keyed as `(source_id, section_id)` and
`(source_id, table_id)`, and their exact source fields. Reusing a locus ID in a
different source therefore cannot overwrite the intended row by CSV order. Atomic rows additionally
include all exact `source_assertions` for that atomic entity, so secondary public
loci survive. A primary atomic locus and an identical assertion locus collapse to one
source assertion.

Lexicon roots and senses use their exact row loci. A lexicon-sense citation includes
source chapter, section, root form, stem, specification, printed page, and
`source_pdf_page` explicitly described as the **tracked chapter PDF page**.
`source_pdf_page` is not asserted as a page number in the canonical whole-lexicon
PDF and the projector never appends `#page=` to the canonical lexicon URL.

Public document URLs must exactly match the source registry and use HTTPS on the
strict `ithkuil.net` / `www.ithkuil.net` allowlist. Userinfo/credentials, query
strings, fragments, local/file URLs, localhost/loopback hosts, protected-repository
URLs, unsafe path traversal, and out-of-registry URL substitutions are held rather
than serialized. Literal fields are also checked for control/surrogate text and
private/local-path markers before they can enter public RDF.

Source IDs, section/table IDs, line/page coordinates, and citations are locators only.
They do not state authority, confidence, authorship, evidentiary weight, or semantic
equivalence.

### Held behavior

`SourceProjector.project_resource(identity, source_records)` returns
`SourceProjection(source_graph, issues, held)`. Missing rows, missing registry
bindings, invalid public URLs, invalid section/table bindings, unsupported record
shapes, and unsafe public literals produce deterministic `SourceIssue` records.
No `dcterms:source` assertion is emitted for an invalid locus. If no permissible
public locus remains for the resource, the result also contains
`NO_PUBLIC_SOURCE_LOCUS` and the source graph is empty. #42 owns later durable
held-ledger serialization.

The graph may contain safe loci while a different contributing locus is held. Callers
MUST inspect `issues`; #40 must hold the semantic resource on any #39 issue rather
than treating a safe partial source graph as complete source closure.

Constructed profile/group resources have no exact semantic source row of their own.
For #40 schemes, collections, or ordered collections, the separate
`project_group(identity, member_source_records)` method accepts only those identity
kinds and only `RecordRef` values already bound to successful #38 member resources.
It projects the union of those real member loci using the same standard DCTERMS shape;
it does not invent source metadata for the group itself.

The implementation pre-indexes closure rows and source assertions once in
`SourceProjector(closure)`; projecting each resolved resource therefore avoids a
whole-table scan per resource.

## 4. Core SKOS graph assembly (#40)

`src/skos/builder.py` composes the already-normalized #38 resources with the #32
resource-shape contract, #33 notation contract, #34 source-text projection, and #39
public-source projector. It does not reopen CSV files or reinterpret raw source rows.

### API and accounting

`build_core_graph(resources, source_projector, *, ordered_collections=())` returns:

- `BuildResult.graph`: the strong RDF graph for resources that passed every gate;
- `BuildResult.emitted`: the exact sorted `ResolvedResource` records represented by
  that strong graph, including every contributing `RecordRef` from merged identities;
- `BuildResult.issues`: deterministic `BuildIssue(code, resource_iri, record_refs,
  details)` records for #42 accounting.

A semantic-resource issue carries that resource's complete `source_records` tuple.
Group-only scheme/collection/ordered-collection issues use the group's IRI and an empty
`record_refs` tuple; member IRIs and navigational source refs remain in `details`. This
keeps a group problem from falsely classifying otherwise emitted semantic rows as held.

### All-or-nothing resource admission

For each resolved semantic resource, the builder validates its #32 shape, adapts only
the explicit #38 text roles into #34, constructs #33 notation, and requests #39 source
projection with the resource's exact source-record tuple. A failure in any of those
surfaces holds the entire semantic resource. Partial source graphs returned alongside a
#39 issue are discarded. No held semantic IRI remains as a subject or object of the
strong RDF graph.

The exact raw New Ithkuil notation comes only from #38 `TextAssertion` records with
role `source_notation_raw`. `Realization.lexical_form` is never used as exact source
notation. Grammar concepts additionally receive the source grammar value code as a
separate `grammar-code` typed notation. No display label is synthesized for a sense
that has only a source definition.

After per-resource validation, the builder analyzes all notation claims using #33's
default uniqueness rule. Every resource implicated in a blocking same-scheme,
same-datatype, exact-lexical collision is held. The builder does not choose a winner or
declare current homographs non-unique; corpus policy for those cases remains downstream.

### Schemes and groups

Every emitted concept has explicit `skos:inScheme`. A scheme is emitted only after
`SourceProjector.project_group` admits public source loci derived from the surviving
member resources. If a required scheme cannot be publicly sourced, all concepts that
claim that scheme are held and scheme membership is recomputed, so no surviving
`skos:inScheme` points to an absent scheme.

Ordinary family collections are derived only from the `families` keys already retained
by #38 on admitted concept resources. They emit `skos:member` and never imply
`skos:broader` or `skos:narrower`. Root resources are not coerced into SKOS concepts to
make them collection members, so root-only family metadata is not projected as a SKOS
collection at this stage.

Ordered collections are accepted only as explicit #32 `OrderedCollectionShape` values
whose basis is `SOURCE_SEMANTIC`. CSV order, source-file order and curriculum order are
never inspected by the builder. An ordered collection is a closed structure: if one of
its declared members is held or missing, the whole ordered collection is held and no
shortened `skos:memberList` is emitted. The validated Level order from #32 can therefore
be supplied explicitly; in the current corpus it remains held because its member
concepts are among the unresolved default-unique notation homographs.

### Current-corpus evidence

With the current validated relational closure and the staged #38/#39 implementations:

- #38 resolves 2,968 resources with zero resolver issues;
- #40 emits 2,579 semantic resources and holds 389;
- 567 deterministic `NOTATION_COLLISION` issue records cover the colliding resources
  and exact collision keys, and one `SOURCE_TEXT_TOO_LONG` issue holds one resource;
- the strong graph contains 19,489 triples, one public-source-backed concept scheme,
  nine admitted family collections, and no implicit ordered collection;
- none of the 389 held semantic IRIs occurs anywhere in the emitted graph;
- supplying the nine-member Level `SOURCE_SEMANTIC` manifest emits no shortened list
  and records `ORDERED_COLLECTION_MEMBER_NOT_EMITTED` for all nine held members.

These counts describe the current input under #33's strict default uniqueness rule.
They are held-accounting evidence for #42, not a claim that later corpus-policy issues
have been completed.

### Proof

`tests/fixtures/skos_builder_core.ttl` is the literal golden graph covering a scheme,
multi-scheme concept, generic root, root-sense concept, ordinary collection, ordered
collection, preferred label, definition, realization note, exact Unicode notation,
grammar-code notation, and public source references. `test_skos_builder.py` compares it
by RDF graph isomorphism, compares shuffled input by exact triple set, checks the RDF
list, and exercises fail-closed text, source, shape, collision, scheme and ordered-list
behavior. The adjacent #32-#34/#38/#39 test suites remain the contract proofs for their
individual layers.
