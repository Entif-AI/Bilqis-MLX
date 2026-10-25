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

## 5. Canonical graph bytes and digest (#41)

`canonicalize(graph)` returns immutable UTF-8 N-Triples bytes, the SHA-256 of all
those bytes, the triple count and deterministic algorithm metadata. It accepts one
complete RDF graph. Named-graph datasets are rejected instead of silently hashing
only a default graph. No subset selection, entailment or lexical normalization is
performed. The compiler's complete graph, including source-reference triples and
ordered collection lists, is the input.

Algorithm `bilqis-rdflib-canonical-ntriples/v1` pins RDFLib 7.6.0:

1. Validate RDF triple positions and reject IRI terms with no absolute scheme,
   non-scalar Unicode, C0/C1 controls, N-Triples-forbidden IRI characters, or
   malformed percent escapes. This is a deterministic RDF-term syntax preflight;
   it does not dereference IRIs or apply scheme-specific URL policy.
2. Use RDFLib's `to_canonical_graph` to replace arbitrary blank-node labels with
   graph-content-derived canonical labels.
3. Serialize using the pinned RDFLib N-Triples serializer, preserve exact literal
   lexical forms, sort the complete serialized triple lines by UTF-8 bytes and
   terminate every nonempty output line with LF. An empty graph yields zero bytes.
4. Compute SHA-256 over exactly that byte string. Bind the algorithm ID, RDFLib
   version, serialization, encoding, byte count and triple count in metadata.

This is the project's versioned canonical **graph** representation. It is not a
claim to implement W3C RDF Dataset Canonicalization. N-Triples supplies the standard
RDF syntax; RDFLib supplies deterministic blank-node labeling. A change in the
canonicalizer version requires an explicit algorithm compatibility review rather
than silently changing existing digest meaning.

Only ASCII LF bytes separate serialized statements. Unicode line-separator code
points inside a literal are preserved as literal text. NFC/NFD, datatype lexical
forms, language, punctuation and source whitespace are not normalized away.
Serialization prefixes, graph identifiers, working directories, timestamps,
process hash seeds and store IDs do not participate in the semantic graph bytes.

`canonical_diff(left, right, limit=20)` reports bounded added/removed canonical
statements and both full graph digests. A developer-friendly Turtle rendering is
not the canonical artifact and must never substitute its bytes for this digest.
The full rebuild gate is exercised by #43; unit fixtures cover independent fresh
processes, shuffled triples, renamed blank nodes, RDF lists and exact Unicode.

References: [W3C RDF 1.1 N-Triples](https://www.w3.org/TR/n-triples/),
[RDFLib canonical graph API](https://rdflib.readthedocs.io/en/stable/apidocs/rdflib.compare/).

## 6. Deterministic held/error accounting (#42)

`src/skos/ledger.py` consumes the immutable #37 `CompilerClosure`, the complete #38
`Resolution`, and #40 `BuildResult`. It does not reopen source files, infer a missing
semantic decision, inspect process state, or use time, working-directory, graph-store,
or model identity. `profile_version` and `profile_digest` are explicit required inputs.

### Row accounting contract

Every row in the compiler closure receives exactly one row disposition:

- `EMITTED` for source rows attached to a #38 resource present in
  `BuildResult.emitted` with its required strong RDF type;
- `HELD` for semantic rows retained by resolver or builder issues;
- `REJECTED` for invalid explicit targets or accounting-integrity failures;
- `UNSUPPORTED` for known semantic input outside the current core projection;
- `IR_ONLY` for source/provenance/support rows that may support RDF without owning a
  standalone semantic resource.

The current semantic row scope is exactly `morphemes_atomic`, `root_senses`,
`lexicon_roots`, and `lexicon_root_senses`. `morpheme_compositions` remains explicit
non-core `UNSUPPORTED` debt. Every other table registered in the #37 manifest is
`IR_ONLY` at this stage. A future manifest table without an explicit ledger key and
policy produces `UNKNOWN_MANIFEST_TABLE` and blocks accounting rather than silently
succeeding.

Many source rows may contribute to one resolved resource. If that resource emits, all
of its contributing semantic rows are `EMITTED`; if it is held, all of its contributing
rows are `HELD`. Multiple errors for one source row remain in `related_reason_codes`
while the row still receives one disposition. Empty-`record_refs` group issues from
#40 are retained separately in `group_issues` so a scheme or collection problem cannot
double-count member rows.

### Integrity and partial-build semantics

Ordinary semantic holds are valid partial-build evidence. They set
`release_ineligible=true` while leaving `blocking=false`. Accounting defects block the
artifact: a missing semantic outcome, duplicate or out-of-scope row reference,
incompatible dispositions, invalid `BuildResult.emitted` resource, unknown future
table, or a held/rejected/unsupported semantic identity that still appears as a strong
RDF subject or collection member. Required profile identity is fail-closed before a
ledger is produced.

`core_complete` means the four primary semantic tables are fully emitted with no
blocking or group-level graph defect. `whole_release_eligible` additionally requires
that no semantic inventory remains `UNSUPPORTED`; current composition debt therefore
cannot masquerade as a whole-release pass even when the core semantic projection is
complete. `release_ineligible` is the exact inverse of `whole_release_eligible`.

This distinction lets #43 return a deterministic partial graph plus its complete
ledger without calling that result fully conformant. Later full-coverage and release
gates remain responsible for requiring zero unresolved semantic debt where their
contracts demand it.

### Stable record and disclosure boundary

Each row entry preserves the exact table/key identifier, source-reference keys,
source-locus coordinates, semantic IRI/key when available, primary and related reason
codes, explanation, and blocking classification. `held_ledger.schema.json` versions
the serialized shape and `held_ledger_reason_codes.json` versions ledger-owned reason
codes plus the upstream pass-through policy.

Dedicated identity fields are never rewritten by a diagnostic sanitizer. Free-text
explanations, diagnostic details, and group-issue details are sanitized before JSON
serialization so local host paths, loopback locations, file URLs, and arbitrary URL
text from an error cannot leak through the diagnostic channel. Source loci store
stable public coordinates rather than raw URLs.

Stable row keys, source-reference keys, and semantic keys are never silently redacted.
If one contains a raw URL, localhost value, or host filesystem path, accounting records
`UNSAFE_LEDGER_IDENTITY_FIELD` and the public JSON serializer raises rather than
publishing a transformed identity. Canonical Bilqis project semantic IRIs are permitted
as explicit IRI fields. This keeps identity fidelity and disclosure safety separate.

### Deterministic serialization and current-corpus evidence

`ledger_json_bytes(result)` emits sorted-key UTF-8 JSON with one trailing newline.
Entry, diagnostic, group-issue, reason-code, and source-reference order are canonical;
row order and issue order do not affect the bytes.

Against the current #37 closure and #40 builder:

- #38 resolves 2,968 resources;
- #40 emits 2,579 resources, reports 568 build issues, and produces 19,489 triples;
- the ledger accounts all 10,588 manifest rows exactly once: 2,590 `EMITTED`, 500
  `HELD`, 1,917 `UNSUPPORTED`, 5,581 `IR_ONLY`, and zero `REJECTED`;
- the 500 held source rows carry 499 `NOTATION_COLLISION` primary reasons and one
  `SOURCE_TEXT_TOO_LONG` reason;
- there are zero accounting diagnostics, so `blocking=false`,
  `core_complete=false`, `whole_release_eligible=false`, and
  `release_ineligible=true`.

`tests/fixtures/skos_ledger_expected.json` is a literal byte-level expected ledger.
`test_skos_ledger.py` also covers unknown shapes, identity/definition conflicts,
notation collision, unsupported relation, unadmitted mapping, missing public source
locus, invalid targets, held-to-emitted repair, multiple rows per resource, group-only
issues, duplicate/out-of-scope accounting, diagnostic sanitization, shuffled input and
reason order, and the literal full-corpus counts above.

## 7. One reproducible build entrypoint (#43)

Run from the repository root after installing `requirements-semantic.txt`:

```sh
python3 -B -m lib.ithkuil.src.skos.build \
  --input-root lib/ithkuil/_data/csv \
  --output-root /path/to/skos-artifacts \
  --profile bilqis-skos-profile/1
```

The input root defaults to this package's tracked `_data/csv` directory. The output
root is required and must not be a symlink, inside the source CSV root, or inside
the compiler's own source package. This prevents output metadata from becoming
compiler input on the next rebuild. The supported profile is
explicit; unknown versions fail. The Python API is `compile_corpus(input_root)` for
immutable artifact bytes and `build(input_root, output_root)` for verified publication.
Both traverse the same preflight, identity, source, core RDF, canonicalization and
held-accounting stages. Normal builds have no network, model, graph-store, registry,
training, student or optimizer dependency. No source or input file is modified.

Each successful publication has:

```text
output-root/
  CURRENT.json
  generations/<bundle-sha256>/
    manifest.json
    canonical.nt
    held.json
    digest.json
    input.json
```

`CURRENT.json` is the only mutable selection. A complete generation is written and
read back before the pointer changes atomically. Each payload's exact byte count
and SHA-256 are recorded in `manifest.json`; the generation ID hashes the manifest.
Repeated identical builds reuse the same verified generation. A failed input or
accounting check writes nothing, and a failure before the pointer swap leaves any
prior valid pointer intact. Existing malformed/tampered generations or pointers are refused
rather than overwritten. A process crash cannot leave a pointer selecting half a
new artifact set; an unselected complete generation may be safely reused on retry.
Payload files, generation directories and pointer updates are flushed in order.
After the atomic pointer swap, the selection is committed: a subsequent directory
sync error is reported as `DIRSYNC_UNCONFIRMED` only after full new-generation
readback succeeds. This warning does not claim power-loss durability. A failure to
read back after the swap returns `COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED`
with the generation identity; the caller must reconcile the actual pointer before
retrying. It must not assume the write did not happen. Publication uses a narrow
process-released output lock; competing writers receive `COMPILER_OUTPUT_BUSY`.
This is a local readback/durability mechanism, not a remote attestation claim.

`input.json` binds exact loaded table values, schema version, column names and row
counts using a row/column-order-independent closure digest. It contains table
digests rather than copying source text. `digest.json` binds the complete canonical
graph bytes to the profile contract hash and compiler-package file hashes. The
metadata contains no build timestamp or input/output filesystem location. A shared
Git commit is useful execution evidence but is not substituted for content identity.

Exit status 0 means a coherent artifact set was produced and verified. The JSON
summary explicitly says `complete` or `partial` and includes `release_ineligible`.
Held or unsupported semantic rows remain visible in `held.json`; a successful
partial build does not satisfy later complete-corpus release gates. Structurally
invalid input, invalid accounting, unsupported profile and publication errors exit
2 with a stable JSON reason on stderr. A post-commit readback failure uses status
`reconcile_required`; ordinary pre-commit failures use `blocked`. Neither erases
prior immutable generations. `verify_publication(output_root)` independently checks the
selected manifest and every payload digest.

Agent interface disposition: `RAW_INTERFACE_JUSTIFIED`. This extends the repository's
existing Python module/argparse interface with one deterministic command, bounded
JSON status, stable nonzero failures, explicit paths, content-addressed idempotency
and receipt readback. An additional service, scaffold or runtime is unnecessary for
this local compiler. `--help` is the discoverability surface. Contract tests invoke
the actual module in fresh processes, including CSV-only fresh workspaces, reordered
inputs, failure paths and repeated publication.

### Publication commit and recovery semantics

The v1 publication bundle contains exactly four payload files: `canonical.nt`,
`held.json`, `digest.json`, and `input.json`. `manifest.json` records their exact
byte counts and SHA-256 values, and its bytes determine the generation ID.

Publication writes and verifies a complete generation before changing
`CURRENT.json`. The atomic replacement of `CURRENT.json` is the commit point.
Routine failures before that replacement leave the previously selected generation
unchanged. Temporary staging files created by the failed attempt are removed.

After the commit point, the publisher reads the selected generation back through
the normal verification path and requires that readback to select the expected
committed bundle ID. A different valid generation is a reconciliation-required
state, not success. If the final output-directory `fsync` fails but the expected
generation readback succeeds, publication returns the verified receipt with
`durability_warning.code = DIRSYNC_UNCONFIRMED`. This means the selected generation
is coherent in the running system, but power-loss durability of the final directory
entry was not confirmed.

If readback fails after `CURRENT.json` was replaced, publication raises
`COMPILER_PUBLICATION_COMMITTED_READBACK_REQUIRED` with the committed bundle ID.
The caller must reconcile the actual pointer and generation state. It must not
report the attempt as an ordinary precommit failure or assume the old pointer still
applies.

`verify_publication(output_root)` accepts only the exact generated v1
`CURRENT.json` bytes and the exact four-file manifest contract. Symlinked output
roots, `CURRENT.json`, `generations/`, generation directories, manifests, or payload
files are rejected at their publication boundary. The local lock prevents
cooperating publishers from changing the same output root concurrently. This is a
local consistency and durability protocol, not a remote authentication or
attestation mechanism.

## Configuration golden projection (#44)

Configuration is the first bounded conformance slice over the existing deterministic
compiler corridor. `src/skos/configuration.py` adds one owner function only:

`select_configuration_resources(closure, resolution) -> ConfigurationSelection`

The selector consumes the validated #37 closure and #38 resolution. It does not parse
CSV independently, construct identities, project source metadata, emit RDF, or
canonicalize bytes. The existing `SourceProjector`, `build_core_graph`, and
`canonicalize` APIs retain those responsibilities.

### Source-backed slice

The current tracked `morphemes_atomic.csv` contains exactly 20 rows whose explicit
`category_code` is `CONFIGURATION`. The selector starts from that full source class;
it does not filter by value code, family, surface form, or resolver success. Every one
of those source rows must appear in exactly one selected resolved resource, while many
source rows may normalize to one semantic resource. A Configuration row with a missing
or unsupported semantic key therefore fails closed instead of vanishing from the
projection.

The source fixture pins the current public evidence independently of builder output:

- source document `NI-WEB-CH03`, “Chapter 3: Morphology”, canonical public URL
  `https://www.ithkuil.net/newithkuil_03_morphology.htm`, source-content SHA-256
  `93d9d61682fa2d051fc667cf2952a0e521b07ec42629e2788f57b0b2f4c34c0f`;
- section `NI-WEB-CH03:3.1`, source line `3063`;
- table `NI-WEB-CH03:T003`, source line `3239`;
- 20 literal value-code / value-name / Unicode-form / realization-type / atomic-ID /
  source-assertion-ID tuples in `configuration_source.json`;
- exact tracked-file digests for the atomic, source assertion, section, table, and
  source-registry CSVs.

The source table's own metadata fields are preserved in the machine-readable fixture,
but its `row_count` field is not used to infer the semantic concept count. The 20-count
oracle comes from the explicit Configuration rows in the tracked atomic IR.

### Expected RDF closure

`configuration_expected.ttl` is a literal RDF oracle authored from the pinned source
facts and the already-governing #31–#36 profile rules. It expects:

- 20 `skos:Concept` resources with literal stable IRIs
  `.../id/grammar/CONFIGURATION/<code>`;
- one New Ithkuil `skos:ConceptScheme`;
- one `configuration` `skos:Collection` containing all 20 concepts;
- exact source `value_name` as English `skos:prefLabel` and exact
  `semantic_summary` as English `skos:note`;
- exact source form as typed New Ithkuil `skos:notation`, including `∅`, plus the
  grammar value code as the separate grammar-code typed notation;
- the same public source locus on every concept, the scheme, and the collection;
- no `skos:broader` or `skos:narrower` assertions.

The literal oracle has 169 triples. Its #41 canonical N-Triples bytes are checked in as
`configuration_expected.nt` with SHA-256
`a415febbec9e0b53a6cd251d99853b8c23ac53a0e17af986a1e19a1178ae5b42`.
`configuration_expected.json` pins that digest, triple count, concept count, canonical
algorithm, RDFLib version, and zero expected positive-slice build issues.

### Fail-closed proofs

`configuration_malformed.json` is a machine-readable negative fixture. It adds a
second physical row for the MSS semantic key with a conflicting source label/meaning.
The existing resolver reports `CONFLICTING_SEMANTIC_MEANING`, and the bounded selector
reports `CONFIGURATION_RESOLUTION_HELD`; no plausible replacement concept is emitted.

The tests also prove that:

- duplicate physical source records are not silently deduplicated;
- row/source-assertion/resource order does not change the canonical digest;
- a Configuration row with a blank semantic value remains in scope and fails closed;
- the same surface form on two distinct Configuration values produces
  `NOTATION_COLLISION` and holds both claimants rather than merging them;
- a conflicting preferred source label holds that resource;
- substituting another source URL holds the resource with source-registry mismatch;
- two physical forms for one semantic identity normalize to one resolved resource,
  exercising the existing #38 representation without implementing #45 policy here.

### Proof recipe

With the run-root Python environment and the repository root on `PYTHONPATH`:

```text
PYTHONPATH=. /Users/emilie/Code/.entif-proof-runtime/bilqis-mlx-pro-20261024/venv/bin/python -m unittest -v \
  lib.ithkuil.tests.test_skos_configuration \
  lib.ithkuil.tests.test_skos_configuration_hardening
```

For the checked-in source snapshot the positive projection is: 20 selected source
rows, 20 resolved/emitted concepts, zero build issues, 169 triples, one scheme, one
20-member family collection, and zero broader/narrower triples. Updating the count,
literal identities/forms, or digest requires a corresponding deliberate source
snapshot change; changing only the golden files is not sufficient evidence.

## 8. Source-faithful composition resources (#57)

`project_compositions(closure, profile)` projects the canonical
`morpheme_compositions` rows as linguistic construction resources. A composition is
not a SKOS concept. The projector emits no `skos:broader`, `skos:narrower`,
`skos:related`, or `skos:notation`, and it emits no component edges. #58 owns
component relationships and linguistic order.

### Identity and source-controlled typing

The stable resource IRI is derived only from `composition_id`:

```text
https://github.com/Entif-AI/Bilqis-MLX/id/composition/<composition_id>
```

Surface form, construction name, source order, row position, labels, and normalized
text do not participate in identity. The implementation reuses the existing identity
key validation before encoding the source ID.

The source's exact `composition_type` and `derivation` codes select RDF classes under
the source-identity namespace, not the Bilqis extension-vocabulary namespace:

```text
.../id/composition-type/<composition_type>
.../id/composition-derivation/<derivation>
```

Each class is emitted as `rdfs:Class` with the exact source code as
`dcterms:identifier`. The issue-local machine profile admits only the nine current
composition types and the two current derivations. A future unreviewed source code is
held as `UNKNOWN_COMPOSITION_TYPE` or `UNKNOWN_COMPOSITION_DERIVATION`; it is never
classified from the spelling or shape of the surface form.

### Generic RDF/DC Terms first

The source fields map to existing terms where those terms keep their meaning:

| Source field | RDF representation |
| --- | --- |
| `composition_id` | `dcterms:identifier` |
| `construction_name` | `dcterms:title` |
| `semantic_summary` | `dcterms:description` |
| `surface_form_raw` | `rdf:value` with the existing New Ithkuil datatype |
| `composition_type` | source-controlled `rdf:type` class |
| `derivation` | source-controlled `rdf:type` class |
| public source loci | the same `dcterms:source` locus structure used by #39 |

The raw surface is passed through the existing New Ithkuil typed-literal validator.
`surface_form_normalized` is not emitted. This keeps punctuation and Unicode code
points exactly as extracted; for example, source `hmo’e` remains distinct from the
normalized `hmo'e` form.

The source table has no `notes` column. Its note-like `semantic_summary` is therefore
preserved as `dcterms:description`; the projector does not manufacture a separate
notes field.

### Three necessary extension predicates

`composition_profile.json` is an issue-local reviewed profile, not the final #60
vocabulary freeze. It admits only three Bilqis properties:

| Term | Why generic RDF/DC Terms is insufficient |
| --- | --- |
| `surfacePattern` | Concrete rows carry both a realized form and a structural pattern. Reusing `rdf:value` for both would erase their source roles. |
| `condition` | A realization condition is machine-relevant and distinct from the semantic description. Flattening both into `dcterms:description` loses that role. |
| `componentCount` | #57 must preserve the source-declared component cardinality while #58 still owns the component edges. `dcterms:extent` means size or duration and does not state this cardinality faithfully. |

Each registry entry binds the canonical term IRI, definition, domain/range, real
source fixture, source field, source justification, rejected SKOS/generic-RDF
alternative, recurrence, and machine need. `load_composition_profile` rechecks the
real source fixture and exact term IRI. It also parses the negative RDF fixture in
which a real composition is deliberately mis-modeled as a `skos:Concept` with SKOS
notation/hierarchy. This instantiates #35's standards-first boundary without adding a
second general vocabulary-governance engine.

### Source traceability

The projector reuses `source_public` validation and `PublicLocus` identity. For each
composition it projects the row's primary source locus plus every
`source_assertions.csv` record whose `entity_kind` is `morpheme_composition`. Any
invalid source registry binding, section/table reference, public URL, or public
literal holds the whole composition resource rather than leaking a partial graph.

Current source evidence is especially crisp: 1,906 `source_join` rows have two
source assertions each, while the 11 `source_template` rows have one each. The
derivation class itself comes from the explicit `derivation` field; assertion count
is corroborating provenance and is not used to guess the class.

### Component boundary and accounting

`component_count` is emitted as the source-declared `xsd:nonNegativeInteger` through
`bilqis:componentCount`. #57 does not load or emit `composition_components.csv` in
the runtime projection because #21's canonical closure does not yet own that table
and #58 owns component edges/order. Conformance tests independently compare all
current source declarations with `composition_components.csv`: 1,917 compositions
correspond to 3,855 component rows with zero count mismatches.

The result is:

```text
CompositionProjection(graph, emitted_ids, held_ids, issues)
```

Rows with an unadmitted type/derivation, invalid declared count, invalid exact raw
surface, or invalid source trace are held as whole resources. The current reviewed
corpus emits all 1,917 composition IDs with zero holds. Pattern/form strings are
never identity: a synthetic same-form/different-ID regression proves that two stable
composition IDs remain two RDF resources.

Current full-corpus proof: 1,917 emitted, 0 held, 0 issues, 20,506 RDF triples,
3,901,535 canonical UTF-8 N-Triples bytes, SHA-256
`25f9778d87c08aa37655b7d8517e4df3516ccfc39610bb1ad9ecdbfc010fadb0`. Two fresh
processes with different hash seeds produced the same receipt.

Proof is in `test_skos_composition.py`, the literal positive N-Triples fixture
`skos_composition_expected.nt`, and the negative SKOS fixture
`skos_composition_negative.ttl`. The tests cover a concrete source join, an exact
Unicode form whose normalized spelling differs, a source template, public source
loci, profile admission, unknown-type holding, full-resource failure, input-row
reordering, and canonical graph equality.

## Multiple-realization normalization (#45)

#45 adds one bounded intermediate view over the existing #38 identity resolver:

`normalize_atomic_realizations(closure, resolution) -> RealizationNormalization`

It does not parse source independently, create a second identity system, add concept
definitions, call Falkor/model state, or alter #47 notation-collision policy. The
semantic identity remains whatever #38 resolved. Grammar rows use the declared
`category_code + value_code` key; atomic roots remain source-qualified root identities;
sense records are not atomic realization groups.

### Current source census

The pinned source snapshot contains 772 `morphemes_atomic` rows. Of these, 607 are
grammar realization rows resolving to 485 grammar semantic keys, while 165 are atomic
root rows resolving to 165 source-qualified roots. The normalized atomic view therefore
contains 650 semantic groups while preserving all 772 source realizations.

The 122 grammar rows collapsed beyond one-row-per-concept are not guessed duplicates.
They come from 122 two-row semantic keys with these literal source type combinations:

- 77 `conditioned_allomorph + overt`;
- 32 `realized_allomorph + underlying_glottal`;
- 6 `overt + standalone_allomorph`;
- 5 `overt + overt_optional`;
- 1 `standalone_allomorph + zero`;
- 1 two-row `zero` group (Register NRR initial/final).

The current source has no same-key `zero + overt` pair. The source-backed fixture does
not manufacture one. A separate synthetic conformance test appends an overt UPX row to
prove that the generic category/value rule would still produce one identity if such a
source pair were admitted later.

### Preserved realization facts

Each normalized realization retains, separately:

- source record ID;
- raw source notation and separately normalized form;
- the New Ithkuil notation datatype IRI;
- realization type;
- allomorph-group ID and source condition;
- family, morpheme class, and slot;
- source ID, section ID, table ID, source line, public source URL, and source anchor.

`∅` is the literal U+2205 source notation. It is not treated as blank. A missing raw or
normalized form is a stable `MISSING_REALIZATION_FORM` held reason.

### Source-backed proving cases

`realization_source_expected.json` pins actual tracked rows and source-assertion IDs;
`realization_normalized_expected.json` pins the expected normalized groups without
serializing the implementation under test. Representative current-source cases are:

| Case | Source rows / raw forms | Source distinction preserved |
| --- | --- | --- |
| Configuration UPX | `ATOM-e09a479fdaca6d` / `∅` | `zero`, default/unmarked |
| Configuration DDS | `ATOM-02a4496bfbac3a` / `ţs` | ordinary single overt form |
| Perspective+Essence M.NRM | `ATOM-2096dbdae9a4c2` / `l`; `ATOM-52561afd815916` / `∅` | standalone vs zero |
| Affiliation ASO | `ATOM-9b4208b045f444` / `nļ`; `ATOM-f08340cc673ded` / `l` | sole exponent vs inside C_A complex |
| Effect 1:BEN | `ATOM-bab207e06f0db1` / `ia`; `ATOM-c2249e51c173ff` / `uä` | overt default vs immediately-preceded-by-y allomorph |
| Case ACT | `ATOM-1dd3cebdcc2f9f` / `ai’`; `ATOM-b0078ab5063976` / `a’i` | underlying glottal vs realized glottal form; curly raw apostrophes preserved while normalized ASCII forms remain separate |
| Register DSV | `ATOM-0c655eea22faae` / `hai`; `ATOM-257e51f4a984fb` / `ha` | final optional vs initial form; family/slot/condition retained |
| Register NRR | `ATOM-0a27199f07517d`, `ATOM-68f38fe846454a` / `∅`, `∅` | final and initial source rows remain separate while one semantic identity is retained |
| Extension ATV vs DPL | both source-backed with raw `b` among their realizations | two distinct semantic identities despite the homograph |

The fixture uses only source vocabulary actually present in the tracked IR. In
particular, no extra “prefix” relationship is inferred when the source row provides
only its own family, slot, and condition fields.

### Fail-closed boundaries

The normalizer emits stable issues instead of repairing source ambiguity:

- `UNKNOWN_REALIZATION_TYPE` for an unrecognized realization class;
- `MISSING_REALIZATION_FORM` for blank raw/normalized notation;
- `MISSING_ALLOMORPH_GROUP` when the required grouping reference is absent;
- `DUPLICATE_REALIZATION_SOURCE_REF` when one atomic source key occurs twice;
- `ALLOMORPH_GROUP_SEMANTIC_CONFLICT` when one grammar allomorph-group ID claims
  multiple category/value identities;
- `UPSTREAM_RESOLUTION_HELD` when #38 already held the source row;
- `REALIZATION_RESOURCE_CARDINALITY` when one source row maps to zero or multiple
  resolved resource variants;
- `INCOMPATIBLE_REALIZATION_SEMANTIC_KEY` when a resolved resource disagrees with the
  source-declared semantic key.

Same-form distinct concepts are deliberately not merged, and this issue does not mark
homographs as safe. #47 remains the owner of same-scheme notation-collision policy.

### Proof recipe

Focused proof from the repository root with semantic dependencies installed:

```text
python3 -B -m unittest -v \
  lib.ithkuil.tests.test_skos_realization \
  lib.ithkuil.tests.test_skos_realization_hardening
```

The source fixture also pins the exact current realization-type census and tracked
input SHA-256 digests. A future source update may change these numbers, but a test or
fixture-only count edit is not source evidence.

## Lexicon roots (#50)

`project_lexicon_roots(closure)` is a domain view over the merged compiler corridor.
It does not reimplement root identity, notation, text, or public-source projection.
It selects the `lexicon_roots` resources produced by #38 and sends them unchanged
through #39 and #40.

Root identity is `Identity("root", (source_id, lexicon_root_id))`. The English
`root_gloss`, normalized spelling, source row order, and later senses do not
participate. The exact `root_form_raw` becomes `skos:notation` with the existing New
Ithkuil datatype. A root is emitted as an addressable `rdfs:Resource`, not a
`skos:Concept`, so #51 can create independent sense concepts without collapsing the
root into one meaning.

`lexicon_root_evidence` remains supporting source IR. #50 checks every evidence row's
stable root ID and exact raw root form against its canonical `lexicon_roots` row. A
conflict holds the whole root. Valid repeated evidence IDs are exposed on
`LexiconRootRecord.evidence_ids` and do not mint duplicate root resources or promote
evidence prose into semantic labels. The RDF source locus itself remains the
canonical #39 lexicon-root locus.

Current proof: 503 source root rows project to 503 root resources, with zero held
roots. `LEXROOT-0bd881a56fac9e` preserves exact `-Č-` notation and has eight repeated
supporting evidence rows while remaining one resource. Reordering root and evidence
rows produces the same canonical graph. A synthetic conflicting evidence spelling is
held with `LEXICON_ROOT_FORM_CONFLICT` and emits no partial root RDF.

## Lexicon sense concepts (#51)

`project_lexicon_senses(closure)` selects the lexicon sense resources resolved by
#38 and delegates RDF text/source/shape emission to #34, #39 and #40. It does not use
the legacy `LEXSENSE-*` value as semantic identity. The canonical concept coordinate
is the existing #31 identity:

```text
(source_id, lexicon_root_id, stem-or-ROOT-WIDE, specification)
```

This is deliberate because current legacy sense IDs are extraction records whose
hash can change when gloss text changes. `LexiconSenseRecord.source_sense_ids`
retains every source-row ID that supports the stable coordinate, so source-row
traceability survives without allowing a gloss-derived identifier to rename the
concept.

Each admitted sense is a `skos:Concept` in the New Ithkuil scheme. Exact
`sense_summary` source text is emitted as `skos:definition`; no preferred label is
synthesized because the current source IR has no separate sense-label field. Public
source loci remain #39 `dcterms:source` loci. `evidence_status` and
`source_locus_kind` remain exact source metadata on `LexiconSenseRecord`; they are not
promoted into semantic confidence or provenance claims in RDF.

Equal duplicate source rows for the same coordinate converge on one concept and
retain both source IDs. Conflicting semantic content at one coordinate is held by
the existing resolver and produces no concept RDF. Distinct roots with identical
English summaries remain distinct because gloss text never enters the identity.

Current proof: all 1,615 parsed lexicon sense rows produce 1,615 independently
addressable concepts with zero held rows. The copular root has 12 distinct concepts.
Changing the legacy ID of a real source row leaves its concept IRI unchanged, and
reordering all sense rows leaves the canonical graph unchanged.

## Stem and Specification dimensions (#52)

`project_lexicon_dimensions(closure)` adds the source's lexical dimensions to the
stable #51 sense concepts without changing their identity. Three issue-local Bilqis
predicates are necessary because SKOS and DC Terms do not define New Ithkuil Stem,
Specification, or extractor-locus roles:

- `bilqis:lexiconStem`
- `bilqis:lexiconSpecification`
- `bilqis:sourceLocusKind`

The first two are semantic dimensions. `sourceLocusKind` is source-mode metadata and
remains separate from the sense meaning. Its values are exactly the current IR enum:
`table`, `prose`, or `compact_numbered_stem`.

Blank source Stem coordinates are represented by the already-governing #31 canonical
value `ROOT-WIDE`; `STEM 1`, `STEM 2`, `STEM 3`, and `STEMS 1-3` remain distinct.
Specification remains one of `BSC`, `CTE`, `CSV`, `OBJ`. The projector emits no
`skos:broader`, `skos:narrower`, collection ordering, or curriculum relation from
these dimensions.

The source extractor states that some prose and compact-numbered rows arise where a
root inherits another root's Specification pattern. The relational IR does not carry
a separate boolean `inherited` field. #52 therefore preserves the exact recorded
`source_locus_kind` and does not reverse-engineer an inheritance flag from spelling,
blank fields, row adjacency, or model judgment. Direct table rows remain queryably
different from prose/compact source modes.

`query_senses(records, parent_root=..., stem=..., specification=...)` performs an
exact deterministic dimension query. It returns stable sense identities and assigns
no ordering semantics to Stem numbers.

Current proof covers all 1,615 senses with exactly one Stem, Specification, and
source-locus-kind assertion each. Fixtures include a direct table sense (`-SČ-`), a
prose inherited-pattern shape (`-RMC-`), compact numbered inherited stems (`-KŢG-`),
and the source's combined `STEMS 1-3` coordinate (`-ŘḐŘ-`). Unknown source modes are
held instead of guessed; an impossible `STEM 4` remains held by the upstream identity
contract. Reordering source rows leaves canonical dimension RDF unchanged.

## Root-to-sense relation decision (#53)

The current profile needs one directional structural relation from an addressable
root resource to each independently identified sense concept. The reviewed decision
is `bilqis:hasSense`:

```text
root rdfs:Resource  -- bilqis:hasSense -->  sense skos:Concept
```

It is not symmetric, transitive, hierarchical, or a SKOS semantic relation. No
inverse predicate is minted.

### Standards-first decision

| Candidate | Decision | Reason |
| --- | --- | --- |
| `skos:broader` / `skos:narrower` | Reject | SKOS semantic relations have concept domain/range and assert semantic hierarchy. The root is deliberately not a concept, and a sense is not a taxonomic specialization of its notation-bearing root. |
| `skos:related` | Reject | It is a symmetric concept-to-concept associative semantic relation and cannot state the directional lexical role. |
| `skos:member` | Reject | It is collection membership; roots are not `skos:Collection` resources. |
| `dcterms:hasPart` | Reject | DCMI defines physical/logical inclusion. A separately identified sense is not asserted as a physical/logical part of the root resource. |
| `rdfs:seeAlso` | Reject | It supplies a generic navigation hint, not the root-to-sense semantic role needed for deterministic queries. |
| `ontolex:sense` | Reject for this profile | OntoLex defines this property from `ontolex:LexicalEntry` to `ontolex:LexicalSense`. Adopting it would require a broader OntoLex type/model commitment that #53 explicitly does not make. |
| `bilqis:hasSense` | Admit | It states exactly the recurring source relation while preserving the established root resource and SKOS sense concept types. |

The machine registry `root_sense_extension.json` records the term definition,
domain/range expectations, real source fixture, source justification, standards gap,
recurrence, and machine need. The #35 admission gate is extended only with a
`root_sense` source binding to `lexicon_root_senses.csv`; its default decision matrix
still returns `RELATIONAL_IR_ONLY` until the raw term is re-qualified against the
source and negative fixture. The term is not a SKOS subproperty.

The negative fixture binds the real source row `LEXSENSE-e3f64d03c6f6ec` to the
tempting false `skos:broader` relation. Admission therefore cannot be self-attested by
the registry prose alone.

`project_root_sense_links()` consumes #50 roots, #51 senses, and #52 dimension
admission. It emits a link only when the parent root and dimension-complete sense are
both present. Missing endpoints are held with no partial relation edge.

Current proof emits exactly 1,615 `bilqis:hasSense` triples for the 1,615 parsed
senses, with zero holds. The Unicode/multi-sense root `-Č-` has exactly 12 links in a
literal N-Triples fixture. Removing that parent root holds all 12 sense links. No
`skos:broader`, `skos:narrower`, `skos:related`, or `skos:member` edge appears in the
positive graph.

## Representative lexicon golden fixtures (#54)

`skos_lexicon_golden_cases.json` freezes a compact, source-derived conformance set
over the #50–#53 APIs. It is expected output, not a new semantic layer. The fixture
records exact stable IRIs, source-row IDs, Stem/Specification values, source-locus
modes and locus IRIs for deliberately different source shapes.

The positive set contains:

- Unicode/multi-sense root `-Č-`: exact typed root notation, eight supporting
  evidence records, one root resource, and 12 root→sense links.
- Direct table sense `-SČ-` / `STEM 1` / `BSC`.
- Prose inherited-pattern shape `-RMC-` / `STEM 1` / `BSC`.
- Compact numbered inherited-pattern shape `-KŢG-` / `STEM 1` / `BSC`.
- Combined `STEMS 1-3` prose coordinate for `-ŘḐŘ-`.
- The real `-NY-` and `-RNY-` root-wide CSV senses whose English definitions are
  byte-identical while their source roots, source-row IDs and semantic IRIs remain
  distinct.

The negative fixture behavior is executable rather than blessed prose. A synthetic
raw-form conflict in `lexicon_root_evidence` holds the root and emits no partial root
RDF. A duplicate stable sense coordinate with conflicting source meaning holds both
source rows and emits no concept RDF for that coordinate.

The golden suite also recomputes the full four-layer lexicon graph after reversing
the primary root, sense and supporting-evidence rows. Canonical output must remain
identical. Current frozen aggregate expectations are 503 root resources, 1,615 sense
concepts, 4,845 dimension triples and 1,615 `bilqis:hasSense` links.

These fixtures describe only the currently parsed tracked Chapter 1–2 frontier. They
do not create source claims for Chapters 3–7 or the affix-reference corpus, and they
do not import curriculum state.

## Chapter 1–2 lexicon reconciliation (#55)

`reconcile_lexicon_frontier(input_root, relation_profile_path=...,
negative_fixture_path=...)` composes the #50 root, #51 sense, #52 dimension, and #53
root→sense layers into one graph-store-neutral lexicon-domain graph. It canonicalizes
that graph with #41 and returns `LexiconReconciliation(graph, canonical, receipt)`.

The receipt is `bilqis.skos.lexicon-reconciliation/v1`. It derives every count from
the loaded relational closure at runtime. It records exact emitted/held partitions
for roots and source sense rows, roots with zero parsed senses, roots with multiple
senses, root notation count, Stem/Specification/source-mode coverage, Chapter counts,
held reasons, exact #43-style source-table digests, canonical RDF metadata and a
digest of the receipt body.

Every root and sense source ID must have exactly one disposition. Overlap, missing
accounting or out-of-scope accounting raises a stable `ProfileError`. Zero-sense roots
are source-frontier debt, not held semantic failures: they remain emitted root
resources and are listed separately under `roots_with_zero_parsed_sense_ids`.

If a later semantic layer holds a sense that #40 could otherwise emit, #55 excludes
that incomplete sense subject and its private source locus from the reconciled graph.
The source row remains explicitly held in the receipt. This prevents a partially
modeled sense from masquerading as a complete lexicon-domain result.

The source digest covers exact sorted values from `lexicon_roots`,
`lexicon_root_senses`, and `lexicon_root_evidence`, using the same input-receipt
normalization as #43. The RDF digest is the complete canonical #41 graph digest.

Current source expectations, verified rather than hard-coded by production logic:

- 503 root rows, all 503 emitted;
- 1,615 sense rows, all 1,615 emitted;
- 219 emitted roots with no parsed sense yet;
- 282 roots with more than one parsed sense;
- 503 exact root notations;
- Stem coverage: ROOT-WIDE 714, STEM 1/2/3 300 each, STEMS 1-3 1;
- Specification coverage: BSC 847, CSV/CTE/OBJ 256 each;
- source modes: table 1,522, prose 54, compact numbered 39.

The frontier block explicitly says this closes only the currently tracked New Ithkuil
Lexicon Chapters 1–2 projection. Chapters 3–7 and the pinned affix-reference source
remain outside closure. No receipt text or count claims full official-lexicon
coverage.

Package-local tests verify exact current counts, debt separation, frontier statement,
source/canonical digest binding, exact accounting failures, explicit held behavior for
an unreviewed source mode, and canonical/receipt equality after reversing root,
sense, and evidence rows. Fresh-process proof is run with different hash seeds and
working directories over the same explicit source and staged-module paths.

## Concept-level definition normalization (#46)

#46 adds a deterministic post-#45 text-normalization step without changing semantic
identity or inventing prose:

`normalize_atomic_definitions(closure, resolution, realizations=None) -> DefinitionNormalization`

The result contains a derived `Resolution` suitable for the existing builder/ledger,
an exact-source definition inventory, per-source-row classifications, and any newly
held `ResolutionIssue`s. `definition_graph(result)` projects only selected exact source
text as concept-scoped `skos:definition` triples through the existing #34 text profile.

### Classification domain

Every atomic `semantic_summary` candidate processed by this leaf receives one of the
contract classes:

`CONCEPT_DEFINITION | REALIZATION_NOTE | SOURCE_EDITORIAL | HELD_CONFLICT | IGNORE_WITH_REASON`

The current source uses the first two only. The latter three remain explicit legal
states so future source/editorial shapes cannot fall through into an implicit choice.

The deterministic current rules are deliberately narrow:

1. One summary, or multiple realization rows with the exact same summary, is an exact
   source-backed concept definition. All contributing rows remain provenance sources.
2. A two-row `underlying_glottal` / `realized_allomorph` pair with one allomorph group
   is normalized only when the realized summary is literally `<base> realized glottal
   form`. The underlying summary is the definition; the qualified source text remains
   a realization note. No suffix is removed to create new prose.
3. A fixed Register adjunct summary whose literal ending names its source slot
   (`register initial adjunct` or `register final adjunct`) remains a realization note.
   When both variants exist, no common-prefix “definition” is synthesized.
4. Any other divergent semantic summaries for one identity become
   `CONFLICTING_SEMANTIC_MEANING` with exact source rows and `field=semantic_summary`.

### Current source proof

The tracked atomic grammar inventory contains 607 realization rows for 485 grammar
semantic keys. The summary shapes are:

- 363 single-row/single-summary identities;
- 84 multi-realization identities whose summaries are byte-for-byte identical;
- 32 Case identities with the exact underlying/realized-glottal source pattern;
- 6 Register identities whose initial/final summaries are explicitly realization-slot
  wording.

The resulting current normalization has:

- 479 concepts with exact source `skos:definition` text;
- 563 source candidates classified `CONCEPT_DEFINITION`;
- 44 source candidates classified `REALIZATION_NOTE`;
- 6 Register concepts with notes only and no fabricated concept definition;
- zero held definition conflicts.

Representative literal fixtures pin Configuration DDS, Effect 1:BEN, Case ACT, and
Register DSV source row IDs, source-assertion IDs, source loci, summary text, realization
types, grouping metadata, and the exact expected definition/note disposition.

### Builder and ledger integration

For admitted grammar resources, #46 removes source-note assertions that have been
promoted to exact concept definitions while preserving realization-specific notes.
The semantic identity, source rows, notation realizations, labels, families and schemes
remain unchanged. `definition_graph()` supplies the exact concept-definition triples.

For an unresolved summary conflict the resource is removed from the derived
`Resolution` and an ordinary `ResolutionIssue` with the already-governed #42 reason
`CONFLICTING_SEMANTIC_MEANING` is added. The existing builder therefore emits no strong
resource, and the existing ledger marks every implicated atomic row `HELD` without a
new ledger architecture or explicit-disposition bypass.

### Negative proof

The hardening fixture changes the conditioned Effect 1:BEN summary to a genuinely
different claim. Both physical source rows are reported, both candidates classify as
`HELD_CONFLICT`, the grammar resource disappears from the derived resolution, the
builder emits no `skos:Concept`, and #42 records both rows as
`HELD / CONFLICTING_SEMANTIC_MEANING`. Reversing every table and row yields the same
normalization and conflict receipt.

### Proof recipe

The focused proof uses the run-root environment and a bounded package overlay made of
repo symlinks plus staged #45/#46 modules only:

```text
python3 -B \
  -m unittest -v \
  lib.ithkuil.tests.test_skos_definition \
  lib.ithkuil.tests.test_skos_definition_hardening
```

No model, English-label match, row-order tie-break, Falkor state, curriculum order, or
filesystem coordinate participates in definition selection.

## Atomic notation collision policy (#47)

`analyze_atomic_collisions(closure, resolution, admissions=()) -> AtomicCollisionReport`
reuses the #33 typed-notation key and #38 identities. The exact key remains
`(governing scheme, notation datatype, exact Unicode lexical form)`; no NFC folding,
ASCII folding, label matching, category inference, or family hierarchy participates.

The report binds every collision to complete claimant IRIs and exact atomic source rows
with source/section/table/line/public URL. Default policy is strict. A
`HomographAdmission` is legal only when it names one exact collision key, the complete
claimant set, and a non-empty rule ID. Partial, unknown, or duplicate admissions fail
closed. This is an explicit exception mechanism, not a global uniqueness relaxation.

Current atomic source produces 1,256 notation claims over 650 atomic resources. There
are 151 exact collision keys involving 388 resources and 499 source rows; no homograph
is admitted by default, so atomic release eligibility is false. Real fixtures include
grammar-code `ACT` shared by CASE/ACT and CASE_ACCESSOR_VX/ACT, and New Ithkuil `b`
shared by EXTENSION/ATV, EXTENSION/DPL, and REFERENTIAL/ma.DETRIMENTAL. Register NRR's
two physical `∅` rows remain one claimant because they resolve to one semantic concept.

`collision_resolution(resolution, report)` converts unresolved collisions into ordinary
`NOTATION_COLLISION` ResolutionIssues and removes all held claimant resources before
the builder, so #42 can account them without concept deletion or identity merging.
Explicit admissions remain visible as `ADMITTED / EXPLICIT_HOMOGRAPH_ADMISSION` records.
The staged extension to the existing `build_core_graph` API adds only the optional
`notation_admissions=` keyword. It validates the same exact key and complete claimant
set before skipping that one collision; default calls remain strict and byte-compatible.
Thus an explicit admission reaches the actual emitter instead of existing only in a
side report, while invalid or partial policy input fails before graph assembly.

Focused proof uses run-root `venv/bin/python -m unittest` on `test_skos_collision` and
`test_skos_collision_hardening`. Same lexical strings under distinct datatypes/schemes
continue to use the already-green #33 primitive tests.

## Full generic atomic compilation (#48)

`compile_atomic(closure, resolution=None, admissions=()) -> AtomicCompileResult` composes
the existing semantic owners instead of adding category-specific emitters: #38 identity,
#45 realization normalization, #46 definition normalization, #47 exact collision policy,
then the existing SourceProjector/core builder. `atomic_report_json_bytes(result)` emits
a deterministic category-accounting summary.

Category support is structural. The runtime reads `category_code`, `value_code`,
`morpheme_class`, family registry membership and source metadata from the validated IR;
it never matches English category/value labels. Atomic roots retain source-qualified root
identity, grammar rows retain category/value identity, and family membership remains
SKOS Collection membership rather than taxonomy or curriculum order.

Current source contains 772 atomic rows across 34 category codes. The strict current
collision policy yields 272 emitted rows and 500 held rows, with zero rejected or silent
rows. These correspond to 261 emitted atomic resources; 499 held rows are involved in
unresolved #47 notation collisions and one is held by the existing `SOURCE_TEXT_TOO_LONG`
profile boundary. The resulting bounded atomic graph has 2,052 triples. The literal
category fixture names all 34 categories and their exact source/emitted/held counts.

Unknown/new category rows cannot disappear: a source category absent from the structural
family registry becomes explicit upstream-held state and still appears in the category
report. Conversely, a synthetic structurally equivalent category supplied through the
same category/family metadata and stable keys compiles through the same runtime path,
demonstrating that adding a category does not require new architecture or an English-name
branch.

Every row has exactly one `EMITTED`, `HELD`, or fail-closed `REJECTED` outcome. Existing
definition and collision reason codes are preserved; the orchestrator does not reinterpret
their meaning. No lexicon sense, mapping, composition, Falkor or curriculum projection is
introduced here.

## Atomic corpus reconciliation (#49)

The API reconcile_atomic(closure, compiled) -> AtomicReconciliation closes the
atomic-domain accounting equation over the #48 artifact. It does not compile or
reinterpret source. atomic_reconciliation_json_bytes(result) serializes the complete
stable receipt, including all row outcomes. atomic_source_digest(closure) hashes exact
atomic IR row values as canonical sorted JSON, independent of table row/column order.

Current source reconciliation is complete: 772 atomic rows, 650 semantic identities,
34 category codes and 122 multi-realization identities. The identity equation is
650 = 261 emitted + 389 held. The emitted set is 104 concepts + 157 roots. The
2,052-triple atomic graph contains 104 grammar-code notation triples and 272 New Ithkuil
notation triples. Held identities are 388 NOTATION_COLLISION + 1 SOURCE_TEXT_TOO_LONG;
held rows are 499 + 1 respectively.

The receipt pins atomic source SHA-256
02a833abc5a116bd651bf50da3c94ef995610612c94c09d31f26cd7d8a6eb540 and canonical
atomic RDF SHA-256 885e502b20bac8805a3a30e49f1c0d43d5b674a5ec8f823bf475d7234a360167.
It validates that source and outcome row IDs are a one-to-one set, no row is rejected,
every row has a semantic identity, every semantic identity is uniformly emitted or held,
the emitted identity set equals the builder result, every held identity is absent from
strong RDF and collection membership, and the source category set equals #48 accounting.

Failures name stable rows or semantic IRIs. The negative proof removes
ATOM-02a4496bfbac3a from row outcomes and receives
ATOMIC_RECONCILIATION_ROW_MISMATCH with missing=ATOM-02a4496bfbac3a. A second
regression adds one structurally admitted source row/category and proves the receipt
changes to 773 rows / 651 identities with a different source digest. Reordered source
tables/rows produce byte-identical receipts.

This is atomic morphology closeout only. It does not claim whole-#19 release eligibility
and does not aggregate lexicon, mapping, composition, curriculum, or store coverage.

## Affix-degree semantic concepts (#56)

`project_affix_degrees(closure, degree_rows)` projects the currently deferred
`affix_degrees.csv` rows without making the compiler manifest change that belongs to
the later full-compilation integration. The function consumes the validated core
closure plus immutable degree rows, so #72 can pass a future manifest-owned table
without changing the semantic API.

The extractor's legacy `degree_id` is not semantic identity: it is generated from
`(atomic_id, degree, meaning_summary)`, so a source wording change would rename it.
The stable degree concept IRI therefore uses `(affix_root_atomic_id, degree)` and
retains every legacy `degree_id` as `dcterms:identifier` source-row identity.

Each degree is a `skos:Concept` in the New Ithkuil scheme, with exact source
`meaning_summary` as `skos:definition`. The numeric source degree is represented by
generic `rdf:value` as `xsd:nonNegativeInteger`. One project relation,
`bilqis:degreeOf`, links the degree concept to the already-resolved semantic identity
of its `morphemes_atomic` affix root. No `skos:broader`, `skos:narrower`, or ordered
collection relation is inferred from the degree number.

Source trace uses the existing public-source policy through the small
`residue_source` bridge: source registry URL, section/table coordinates, line/anchor,
and public-literal checks must all pass before the concept is emitted.

Current source proof covers 271 degree rows over 30 affix roots. Twenty-nine roots
have degrees 1–9 and one source root has explicit degree 0–9. All 271 current rows
emit with zero holds. A resolved resource outside the source's `affix_root` family
is held with `AFFIX_DEGREE_ROOT_KIND_INVALID`, so an unrelated grammar resource
cannot acquire affix degrees merely because its ID resolves. A deterministic query returns one root's degrees numerically
for display/query purposes only; that ordering is not asserted in RDF and carries no
curriculum meaning. Duplicate source coordinates with conflicting meanings, unknown
affix roots, or blank meaning text are held as whole concepts rather than inferred
from neighboring degrees.

## Ordered composition components (#58)

`project_composition_components(closure, component_rows, compositions)` consumes the
#57 parent projection plus deferred `composition_components.csv` rows. A parent group
is emitted only when its parent composition exists and was emitted, every position is
a positive unique integer, positions are contiguous from 1 through the parent
`component_count`, and every component has exactly one atomic reference or literal
symbol value.

Component occurrence identity is the source `component_id` under
`id/composition-component/`. The occurrence uses generic RDF/DC Terms wherever they
state the source fact faithfully:

- `dcterms:isPartOf` links occurrence to its parent construction;
- `rdf:_1`, `rdf:_2`, … encode the exact linguistic position on the parent;
- `rdf:value` preserves either the exact source atomic ID or literal/symbol;
- `dcterms:references` points atomic occurrences at the #38-resolved semantic
  resource for that atomic ID;
- `dcterms:identifier` preserves the component occurrence ID.

Only two new #58 terms are required: `bilqis:componentRole` and
`bilqis:slotLabel`. The already-proven #57 `bilqis:condition` is reused for component
conditions. Component role and slot are not taxonomy, source provenance, or
pedagogical sequencing.

The source table itself has no independent source-locus columns. #58 therefore does
not fabricate a component locus. Each occurrence is linked to the parent composition,
whose #57 resource already carries the source loci proved by the composition row and
source assertions.

Current source proof: 3,855 rows, 3,812 atomic references, 43 literal/symbol
occurrences, zero both/neither value rows, zero unknown atomic IDs, zero duplicate
positions and zero parent count mismatches. Fixtures reconstruct the nine-component
Standard formative and both atomic and source-template compositions exactly. Any
count drift, duplicate position, impossible value-kind combination or unknown atomic
ID holds the entire parent component group so a shortened sequence cannot masquerade
as complete. If every component of a nonempty admitted parent is missing, validation
fails with `COMPONENT_GROUP_MISSING` and the exact parent identity before RDF emission;
an absent group cannot evade the per-group checks. The numeric order is linguistic structure only; no curriculum field or
relation is emitted.

## Explicit allomorph substitution rules (#59)

`project_allomorph_rules(closure, rule_rows)` projects the current
`allomorph_rules.csv` as rule resources, not semantic concepts. Rule identity is the
source `allomorph_rule_id` under `id/allomorph-rule/`. The rule graph has no
`skos:Concept`, `skos:broader`, `skos:narrower` or `skos:related` assertions and does
not modify #38/#45 semantic identities.

The rule preserves four source roles using issue-local extension predicates:

- `bilqis:inputPattern`
- `bilqis:intermediatePattern` when the source provides one
- `bilqis:outputPattern`
- `bilqis:allomorphDomain`

The already-proven `bilqis:condition` term is reused for the source condition. Pattern
strings are literal source text. #59 does not parse them into a rule language or
interpret bracket syntax. A future unfamiliar pattern therefore remains literal if
the source row is otherwise valid.

The current source does not carry an `allomorph_group_id` or a semantic concept key
for these rules. It carries only the affected-domain text `C_A affix-complex`.
Consequently #59 emits that exact literal domain and does not fabricate a group or
concept edge. This keeps rule structure separate from the #45 realization groups,
whose semantic identities remain whatever #38 resolved.

Public source loci reuse the #56 `residue_source` bridge and the common
`source_public` policy. Current source proof: 19 unique rules, all in one explicit
domain/source locus; 17 are direct substitutions and two carry intermediate patterns.
Fixtures include `fbm → fv → vw`, Unicode `ţbn → tḑ → ḑy`, and direct `řř → ňš`.
Missing required domain/input/output/condition fields are held without partial RDF;
row order does not affect canonical output.

## Minimal Bilqis extension vocabulary freeze (#60)

`extension_vocabulary.json` is the normative current-corpus freeze for linguistic
residue that generic RDF, RDFS, DC Terms and SKOS cannot state without distortion.
It is a term registry, not a parallel ontology. Each admitted property has one
canonical `Identity("term", ...)` IRI, definition, domain/range expectation,
cardinality, real source fixture and required fields, source justification, owning
issues, rejected standards/custom alternatives, non-goals and no unproven SKOS
subproperty claim.

The current admitted set is exactly 13 properties:

- lexicon dimensions: `lexiconStem`, `lexiconSpecification`;
- root/sense structure: `hasSense`;
- affix degree: `degreeOf`;
- composition: `surfacePattern`, `condition`, `componentCount`;
- component occurrence: `componentRole`, `slotLabel`;
- explicit allomorph rules: `inputPattern`, `intermediatePattern`, `outputPattern`,
  `allomorphDomain`.

The #59 research result is evidence, not authority by itself. #60 independently
admits its four pattern/domain roles because the actual 19-row source table recurs,
machine consumers must distinguish the roles, generic `rdf:value`/DC relations lose
that distinction, and the terms do not mint semantic concepts or SKOS relations.

Four reviewed candidates are explicitly not admitted:

- `sourceLocusKind`: extractor/provenance mode, excluded from this semantic freeze;
- `componentPosition`: `rdf:_n` already preserves order;
- `degreeNumber`: typed `rdf:value` already carries the scalar;
- `surfaceReplacement`: #35 fixture-only example superseded by the three actual #59
  source roles.

The `sourceLocusKind` decision propagates upstream rather than being filtered later.
The `upstream-correction/` packet removes that issue-local predicate from the owning
#52 public graph while retaining the exact mode on `LexiconDimensionRecord` and #55
receipt coverage. It also regenerates the #52/#54 exact fixtures and #55 canonical
snapshot from the corrected graph. `lexiconStem` and `lexiconSpecification` remain
admitted semantic dimensions. The original staged #52/#54/#55 files remain unchanged
as review evidence for the pre-freeze state.

`load_extension_vocabulary()` validates every admitted fixture directly against the
tracked CSV row; registry prose cannot self-attest a term. `validate_graph_vocabulary`
fails any `.../vocab/*` predicate not in the admitted set. Current #56/#57/#58/#59
graphs exercise ten of the terms; the corrected #52 public dimension graph exercises
two and keeps source mode record-only; #53 exercises `hasSense`. Tests prove a
fabricated vocabulary predicate still fails closed.

## Linguistic residue reconciliation (#61)

`reconcile_residue()` composes the current #56 affix-degree, merged #57 composition,
#58 component-occurrence and #59 allomorph-rule projections and validates the merged
graph against the normative #60 vocabulary. It consumes the already-validated core
closure plus immutable deferred-table rows; it does not introduce a second compiler
manifest or held-ledger implementation. The later full-compilation owner can pass
manifest-owned rows through the same API.

Every source row from the four current tables must have exactly one disposition:
`emitted`, `held`, or explicitly reasoned `IR_ONLY`. Overlap, missing disposition,
out-of-scope IDs, duplicate primary IDs, or an IR-only table outside the governed set
fails closed. Held rows carry the domain projector's machine reason codes. Current
source uses no IR-only exceptions.

The receipt contains each table's exact source count, complete emitted-ID list,
held IDs/reasons, IR-only IDs/reasons, deterministic source-row digest, aggregate
held-reason census, the exact #60 extension predicates used, combined residue-source
digest, complete canonical RDF metadata and receipt-body digest.

Current expected census is 6,062 source rows: 271 affix degrees, 1,917 compositions,
3,855 component occurrences and 19 allomorph rules. All 6,062 current rows emit with
zero held and zero IR-only rows. The merged graph uses only ten of #60's 13 admitted
terms; the three lexicon-only terms are outside #61's residue slice.

Negative proofs deliberately remove a component occurrence (the remaining parent
group is held rather than shortened), duplicate an affix-degree source ID (rejected
before projection), and blank a required allomorph output (the rule is explicitly
held, never dropped). The generic partition validator separately proves overlap,
missing and out-of-scope dispositions fail closed.

Source digests sort rows by their authoritative source key and graph canonicalization
uses #41, so reversing all three deferred row sequences cannot change source, graph,
or receipt digests. Fresh-process proof repeats the complete reconciliation from
separate temporary working directories and hash seeds.

## Source-qualified mapping emission (#63)

`mapping_emit.emit_admitted_mappings(rows, endpoint_graph, policy)` consumes explicit
`ReviewedMappingRow(RecordRef, MappingClaim)` records. Raw crosswalk/bridge prose is
never interpreted as review authority. The emitter recomputes the exact #62 normalized
admission and #36 proof requirements, then verifies both endpoints are admitted SKOS
concepts with membership in their declared, known concept schemes. An absent endpoint,
ambiguous concept/collection type or mismatched scheme produces a row-bound issue.

Predicate strength comes only from the finite table. Broad/narrow direction and
inverse edges follow #36; symmetric predicates emit their reciprocal edge. The emitter
preserves both identities and never creates `owl:sameAs`. Equivalent assertions share
RDF triples while `MappingAssertion.record_refs` preserves every contributing input
row. Duplicate source-row identities are rejected. Cross-claim semantic conflicts
prevent a complete graph rather than selecting a preferred assertion.

The current raw corpus has no concept-target admissions. The five positive fixtures
are explicitly synthetic reviewed inputs, not newly approved Bilqis mappings.
Source review and independent-scheme governance remain upstream premises; strings
and graph membership do not prove that a human/source review actually occurred.
Later #65 validates batch conflicts and #66 reconciles the complete source domain.

Proof: `python -B -m unittest lib.ithkuil.tests.test_skos_mapping_emit -v` compares
ten literal expected triples, exact/close separation, both directional inverses,
duplicate accounting, unknown/raw states, missing endpoints/schemes, ambiguous types,
missing exactness evidence and reordered-input equivalence.

## Non-admitted mapping source preservation (#64)

`mapping_rows.load_mapping_rows(input_root)` reads the two explicit mapping CSV
tables, rejects malformed records and duplicate/missing stable IDs, and returns
immutable rows. `preserve_nonadmitted(rows, policy)` evaluates the #62 exact table
and returns `MappingHeldRecord` values whose `entry` uses the existing #42
`LedgerEntry` shape. No separate epistemic or RDF vocabulary is introduced.

Each record preserves qualified source row identity, original relation/equivalence/
review states, raw endpoint identifiers, current/historical source era, permissible
source loci and semantic differential/caution text. Nonpublic commentary is listed
in `withheld_fields` rather than copied to public artifacts; identity/state fields
are preserved verbatim or rejected. Raw target IDs are evidence, not a claim that a
source document resolves as an admitted concept. An emitting decision is refused
by this held-only function and must go through the independently checked #63 path.

All 552 current rows are accounted for: 551 held and one rejected, including two
historical-only predecessors. No strong mapping graph is created. Unknown future
states remain explicitly unsupported and block a complete mapping-domain status.
Rebuilding changed source state creates a new disposition without mutating prior
input values or recorded outputs. Tests compare exact stable IDs, original states,
commentary, historical distinction, order invariance, schema errors and a controlled
state transition.

## Mapping endpoint and conflict validation (#65)

`mapping_validate.validate_mapping_batch` validates a complete normalized mapping
batch before strong output is accepted. Missing/ambiguous/nonconcept endpoints,
unknown future states, contradictory exact-versus-rejected claims, and conflicting
material policy assertions produce stable `MappingIssue` records with every involved
source row and the conflicting endpoint/predicate details. Any such issue prevents
complete batch output; the result contains no strong triples.

An opposite broad/narrow direction under one source/review basis is a contradiction.
Separately qualified hierarchy cycles remain legal under the #36 SKOS contract.
Exact and close claims may coexist when they have independently specified source
review bases; conflicting versions of one source assertion are never reconciled by
choosing the stronger or weaker label. Equivalent duplicate rows preserve both row
identities while canonicalizing their RDF triples once. Known non-admitted proposal
states remain held; the guard does not promote them or invent a source review.

Tests exercise every required negative independently, all involved row IDs, order
invariance, legal duplicates and a separately qualified reciprocal hierarchy.

## Complete mapping-domain reconciliation (#66)

`mapping_corpus.compile_mapping_corpus(input_root)` composes the #62 raw admission
matrix, #63 endpoint-bound emitter, #64 held preservation and #65 batch validator.
The result contains the strong mapping graph and one deterministic reconciliation
receipt. A raw held/proposal state cannot be overridden by supplying a reviewed
claim. An emitting raw policy row additionally requires the matching stable source
row, source/target identity, exact predicate and reviewed evidence before emission.

The receipt derives current source counts, all dispositions, predicate triple counts,
state/reason breakdowns, historical rows, unsupported/conflict counts, declared
source-target pairs and equivalent-assertion duplicates. Each source row occurs once;
every emitted triple has its contributing row references; held rows contribute none.
Removing an accounting record fails with the exact missing stable source ID.

Current source evidence is 222 crosswalk plus 330 bridge rows, 551 held, one rejected,
two historical-only predecessors, zero admitted mapping triples and zero unsupported
rows/conflicts. Complete accounting does not mean all mappings are admitted. The
receipt explicitly reports `requires_semantic_review` and does not manufacture
concept-target matches from source-document references. Unknown future raw states
prevent complete mapping status and suppress the batch's strong output.

The pure `compile_mapping_rows` API accepts immutable input rows and optional
explicitly reviewed records for future admitted source states. Positive source-to-RDF
integration tests are labeled synthetic, bind their review to the exact row/endpoints,
and do not approve any current raw mapping. #68 consumes this receipt without taking
over mapping policy or semantic adjudication.

## Semantic coverage receipt schema (#67)

The v1 receipt contract is bilqis.skos.semantic-coverage/v1. The durable JSON Schema
is coverage_receipt.schema.json; coverage_schema.validate_coverage_receipt() applies
the same structural rules plus the cross-field additive accounting checks that JSON
Schema cannot express by itself. The implementation uses only the Python standard
library and the existing ProfileError; no dependency was added to the shared venv.

The receipt has explicit top-level sections for compiler/profile identity, consumed
source/IR artifact digests, canonical RDF digest/triple count, extensible per-domain
accounting, global disposition totals, declared source-frontier debt, blocking conflict
summary, and build status.

Every domain contains exactly the five row dispositions
EMITTED | HELD | REJECTED | UNSUPPORTED | IR_ONLY, source-row total, semantic counts
for concepts/roots/senses/mappings/compositions/allomorphs, notation totals keyed by
datatype/system IRI, and explicit frontier-debt entries. New domains may be added through
the common domain schema without changing existing field meaning. Unknown disposition
names fail closed.

The validator enforces both accounting equations: each domain source-row total equals
the sum of its five dispositions, and global totals equal the sum of all domain totals.
Inputs require unique (domain, artifact) identities and lowercase SHA-256 digests.
Canonical RDF/profile digests are also exact lowercase SHA-256. The schema contains no
curriculum or admission-authority field.

Fixtures include one complete four-domain synthetic receipt and five literal invalid
receipts: missing source digest, malformed RDF digest, inconsistent accounting totals,
unknown disposition enum, and missing frontier-debt declaration. The command
python -m lib.ithkuil.src.skos.coverage_schema RECEIPT.json exits zero with a small
machine-readable validation result or exits 2 with a stable error code.

#67 defines structure only. #68 owns computation from domain artifacts.

## Whole-source semantic coverage generation (#68)

CoverageBuild is a composed semantic artifact containing the merged domain graph, its
#41 canonical bytes/digest, and one #67 semantic-coverage receipt. The public entry point
build_coverage() consumes the actual atomic #49, lexicon #55, residue #61, and mapping
#66 results plus the validated source closure. Domain adapters translate those owner
receipts into one common row/disposition schema without reinterpreting source meaning.

compose_coverage() is the lower-level composition boundary used by tests and the later
#72 explicit registry command. It merges the supplied domain graphs, canonicalizes the
union exactly once, optionally verifies a caller-provided #41 CanonicalRdf byte-for-byte,
derives global totals/conflict summaries/build status, and runs the #67 validator before
returning. coverage_json_bytes() emits stable receipt bytes.

Current source coverage, using the #60-corrected lexicon dimension projector, contains
9,654 in-scope source/IR rows: 8,452 EMITTED, 1,051 HELD, 1 REJECTED, 0 UNSUPPORTED,
and 150 IR_ONLY. The combined graph has 77,614 triples and canonical SHA-256
a81a1ec6d5f48e297eaa6901a2f1d609711777f5d2bc35f57f01103d6983ed7e.
It is explicitly partial, not release-clean.

Atomic contributes 772 rows, 104 emitted concepts, 157 emitted roots, and unresolved
notation/text debt. Lexicon contributes 2,268 rows: 503 roots, 1,615 senses, and 150
source-evidence IR-only rows. Its corrected graph is exactly 21,387 triples with SHA-256
5446888f0987c8d4465608028028dd2dfd602301f7426f86abee0a2dba32eb33; no
sourceLocusKind predicate is filtered downstream because the corrected owner projector
never emits it. Residue contributes 6,062 fully emitted rows including 1,917 compositions
and 19 allomorph rules. Mapping contributes 552 rows, currently 551 held and one rejected.

Known source-frontier debt remains explicit: 219 tracked lexicon roots have zero parsed
senses, two lexicon source frontiers remain outside the tracked closure, and all 552
current mapping rows still require semantic review/admission. The current partial status
therefore survives even though the receipt itself reconciles.

A separate four-domain bounded clean fixture has four emitted rows, no debt/conflicts,
four triples, and canonical SHA-256
64a084ddf108eba38205905d8015e6f3c50e191f42ff8fa5ccd9f441c6e07008. It proves the
same generator can produce build_status=complete when the source fixture is genuinely
clean rather than by weakening held/debt semantics.

## Global no-omission accounting gate (#69)

The gate takes two independent inputs: the stable source-row set inspected from source
or domain reconciliation inputs, and the #67 coverage receipt generated from build
outputs. This avoids the circular claim that a receipt is complete merely because it
lists every row it chose to include.

SourceRowIdentity is the stable tuple (domain, table, key). validate_no_omission()
first compares that independent set to every row entry in the receipt. Missing, extra,
or multiply-accounted rows fail with NO_OMISSION_MISMATCH and literal locators such as
atomic:morphemes_atomic:ATOM-A3. Duplicate source IDs fail separately.

Only after the set equation is proven does the gate run the full #67 schema/arithmetic
validator. `semantic_iri` is optional because an emitted source row may own an RDF
assertion or structural occurrence rather than a standalone semantic resource. IR_ONLY
rows require a non-empty reason code and owner. HELD, REJECTED, UNSUPPORTED, and IR_ONLY rows remain accounted
but fail if their semantic IRI appears in the supplied strong-subject set.

The synthetic source fixture covers atomic, lexicon, residue composition, residue
affix, and mapping rows. Five omission fixtures each remove one independently named
row while keeping the shortened receipt internally additive, proving the independent
source set catches silent loss. Additional fixtures cover duplicate accounting and an
IR_ONLY row without rationale.

#68 supplies the real source-row sets and computed receipt. This leaf owns only the
independent accounting gate and does not decide whether an emitted semantic assertion
is correct.

Current composed proof against the #68 receipt independently enumerates 9,654 source
rows across atomic, lexicon, residue, and mapping inputs and accounts exactly 9,654
receipt rows: 8,452 EMITTED, 1,051 HELD, 1 REJECTED, 0 UNSUPPORTED, and 150 IR_ONLY.
No duplicate/missing source-row locator is present. Strong-subject checking uses actual
RDF subjects, matching the established held-resource boundary; arbitrary URIRefs that
appear only as objects are not reclassified as emitted subjects by this gate.

## Canonical RDF determinism gate (#70)

The checker delegates canonical meaning entirely to #41. compare_graphs() canonicalizes
two RDF graphs and returns a deterministic case receipt containing both digests, triple
counts, and the first removed/added canonical N-Triples assertion when they differ.
require_equivalent() turns a mismatch into CANONICAL_DETERMINISM_MISMATCH with that
meaningful delta.

compare_bundles() applies the same check to #43 ArtifactBundle canonical.nt artifacts
and independently verifies that each bundle metadata digest matches the canonical bytes.
The shared `rdf_read.read_canonical_graph` boundary preserves typed literal lexical
forms exactly with per-literal normalization disabled, and rejects noncanonical bytes.
For example, `"01"^^xsd:integer` stays distinct from `"1"^^xsd:integer`; reading
a valid artifact must not silently change its digest. Downstream conformance and
graph projection reuse this same parser.
repeat_build_check(input_root) runs the deterministic compiler twice. The CLI command
python -m lib.ithkuil.src.skos.determinism --input-root CSV_ROOT runs that repeat gate
and prints a compact machine-readable report.

The current merged #43 core canonical digest is pinned by the fixture as
062ff653652b0b4b8876a92f3c99b1d0451f26a75950f3241b8f2d2ba0915577 for 19,489 triples.
This is a determinism oracle for the merged core build, not a claim that later staged
domain graphs are release-complete.

Tests cover all five contract scenarios: repeated same-process build; CSV rows and
columns reversed in a fresh temporary source tree; fresh subprocesses in different
temporary working directories and Python hash seeds; an exact Unicode-heavy notation
graph containing decomposed C-caron and the literal empty-set sign; and an intentional
semantic literal mutation. The first four preserve canonical digest/equivalence. The
mutation changes digest and reports exact first removed/added assertions.

No timestamp, temp path, process hash seed, Falkor ID, model state, or curriculum data
enters the canonical comparison.

## Independent graph conformance (#71)

`src/skos/conformance_shapes.ttl` encodes proven public profile invariants.
Each named shape carries `dcterms:identifier` and `dcterms:source` authority links:

| Shape | Owning invariant |
| --- | --- |
| ConceptIdentity | Concept IRI shape, #31/#32; affix-degree coordinates, #56 |
| SchemeIdentity | Scheme IRI shape, #31/#32 |
| ConceptScheme | Required declared concept schemes, #32 |
| Notation | Admitted notation datatypes and nonempty unpadded literals, #33 |
| PreferredLabels | Preferred-label language uniqueness and label disjointness, #34 |
| SourceLinks | Required source-link presence on source-bound resources, #39 |
| NoCurriculum | Exclusion of curriculum/training predicates, #19/#32 |
| MappingEndpoints | Concept endpoints in distinct schemes, #36/#63 |

The shapes validate resource structure; they do not reconstruct semantic keys,
prove source authenticity, infer linguistic theory, or encode private policy.
`NoCurriculum` checks predicate IRIs, including otherwise untyped subjects; it does
not interpret source text containing words such as curriculum or training.

Mapping admission cannot be inferred from RDF endpoints. The independent
`MappingAdmission` detector (#63/#66) requires exact triple support from the
upstream admitted mapping output. An absent support artifact admits zero mappings.
A support artifact is an explicit upstream premise, never approval inferred from a
matching graph, source label, or endpoint shape. The current corpus emits zero
admitted mappings while preserving mapping debt.

Run independently over canonical N-Triples:

```sh
python3 -B -m lib.ithkuil.src.skos.shacl --rdf PATH/canonical.nt
# When upstream emits admitted mappings, also supply its canonical output:
# --admitted-mappings PATH/admitted-mappings.nt
python3 -B -m unittest lib.ithkuil.tests.test_skos_shacl -v
```

The validator uses pySHACL with inference disabled, validates a copy, and binds its
machine-readable report to the unchanged canonical RDF digest. Exit 0 means graph
conformance; exit 2 means violation or invalid input. Every violation identifies
focus node, named shape, invariant, and owning issues. Fixtures intentionally break
each shape independently, reject unsupported mapping assertions, and preserve
exact Unicode notation. The positive fixture is the existing canonical #40 core
graph. A separate whole-current-corpus run validates all 77,614 triples at canonical
digest `a81a1ec6d5f48e297eaa6901a2f1d609711777f5d2bc35f57f01103d6983ed7e`.
Graph conformance does not erase the coverage receipt's partial/held/debt state.
