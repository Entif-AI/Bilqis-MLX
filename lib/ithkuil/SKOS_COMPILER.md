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
