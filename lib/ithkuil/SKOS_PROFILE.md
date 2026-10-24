# Bilqis New Ithkuil SKOS/RDF profile

Status: normative for the semantic projection, implemented under issues #20 and #31.
This profile preserves the source CSVs as upstream authority. It does not allocate
student tokens, admit curriculum semantics, or change training state. Subsequent
profile sections are owned by #32–36; compiler implementation is owned by #37–43.

## 1. Namespace and stable identity (#31)

The permanent namespace base is `https://github.com/Entif-AI/Bilqis-MLX/`.
The paths below identify resources. They are not claims that GitHub serves an RDF
representation at those paths. A repository rename or deployment move MUST NOT
silently rewrite this base. A future HTTP resolver may provide redirects without
changing the identifier contract.

| Entity kind | Path under the base | Required stable keys |
| --- | --- | --- |
| ConceptScheme | `id/scheme/{scheme_id}` | Profile-owned scheme ID, initially `new-ithkuil` |
| Grammar-value Concept | `id/grammar/{category_code}/{value_code}` | The source category/value pair |
| Family Collection | `id/collection/{family_id}` | Source family key such as `configuration` |
| OrderedCollection | `id/ordered_collection/{collection_id}` | An admitted source-semantic ordered grouping ID |
| Notation datatype | `id/datatype/{notation_system}` | `new-ithkuil` or `grammar-code` |
| Lexical root resource | `id/root/{source_id}/{root_id}` | Public source identity and pinned root entity ID |
| Root-sense Concept | `id/sense/{source_id}/{root_id}/{stem}/{specification}` | Public source identity and source-defined structural sense coordinates |
| Extension term | `vocab/{term}` | Admitted vocabulary term key |

For lexicon records, `root_id` is the existing `lexicon_root_id`; for grammar-site
root records it is the pinned `atomic_id`. A sense's stable composite identifier is
the root plus its source-declared ASCII `stem` and `specification`. Structural code case
is canonicalized to uppercase (`Stem 1` and `STEM 1` are the same coordinate).
Aggregate source coordinates such as `STEMS 1-3` stay aggregate; this contract does
not expand them into invented senses. `sense_from_source` recognizes two explicit
extractor schemas. In both, a present blank `stem` means the source's root-wide
scope and becomes the reserved component `ROOT-WIDE`. In `root_senses` only, a
present blank `specification` means an explicitly unspecified source sense and
becomes `UNSPECIFIED`. A blank specification in `lexicon_root_senses`, an absent
column, unknown source shape, or unknown structural code fails closed. These
sentinels preserve the extractors' declared scopes; they do not infer missing
stems or specifications. In the current corpus this preserves all 1,815 senses,
including 714 lexicon root-wide senses and the grammar-site unspecified senses.

The legacy `sense_id` and `lexicon_sense_id` hashes include mutable summary text in
the existing extractors. They MUST remain source-row locators and MUST NOT be used
as semantic IRI keys. A summary punctuation correction can remint those hashes
without changing the structural sense. If two source records with the same
structural coordinates disagree about meaning, the resolver must hold the conflict
rather than choose one by row order. Source-document identity is evidence and does
not by itself create a `skos:ConceptScheme` or a SKOS mapping relationship. The
source-qualified root/sense IRIs preserve current source-record identity; concrete
corpus projection may reconcile those records only with explicit source proof.
Issue #36 mapping semantics apply to independently governed semantic identities,
not merely to two documents that describe the same New Ithkuil meaning. Equal
glosses or root spellings alone cannot merge source records.

Scheme and datatype keys are profile declarations, not English labels. A new
scheme key requires a genuinely different governed inventory. Merely reserving an
extension term IRI does not admit its predicate or class; #35 and concrete residue
issues own that decision. The `hasRootSense` fixture is a reserved example only.

### Encoding and normalization

Except for the declared uppercase structural sense-code normalization, keys are
nonempty, case-sensitive Unicode strings in NFC. Leading/trailing
whitespace, control/format/surrogate characters, and whole `.` or `..` segments are
rejected. Non-NFC keys are rejected with `IDENTITY_KEY_NOT_NFC`, never silently
collapsed. Key normalization is an upstream, explicitly reviewed identity change.
These restrictions apply to keys, not to literal New Ithkuil notation.

Encode each component independently as UTF-8 with uppercase percent escapes. Only
RFC 3986 unreserved ASCII characters `A-Z a-z 0-9 - . _ ~` remain unescaped.
In particular `/`, `%`, `?`, `#`, spaces, and non-ASCII bytes are encoded. Slashes
between components are structural. Percent strings are ordinary source text and
are escaped again, so `a/b` and `a%2Fb` stay distinct. No case-folding, transliteration,
label-derived slug, source-line number, file path, row ordinal, or Falkor ID enters
the grammar. The fixed kind prefix and component boundaries prevent cross-kind
and delimiter collisions.

Source snapshot versions, timestamps and file hashes describe evidence, not identity,
and do not enter these IRIs. Root IDs and category/value codes are pinned source
keys; sense keys use the structural composite above. This layer MUST NOT derive
semantic keys from mutable glosses or the legacy gloss-derived sense hashes. An
upstream change to a root or structural coordinate creates a migration review,
not permission to silently rename an existing concept. A changed source text hash
does not itself prove a semantic change or semantic equivalence.

### Identity continuity and failure behavior

Editorial label or note corrections preserve the IRI when semantic identity is
unchanged. Meaning changes require a new stable key/IRI and an explicit successor
record while preserving the old identity and its evidence. The successor record
does not assert `skos:exactMatch`; mapping strength is separately governed by #36.
`check_successor` verifies the caller's explicit semantic-change disposition; it
does not infer semantic equivalence from text similarity or a hash change.

`from_record` reads only the required key fields. Missing keys produce
`MISSING_IDENTITY_KEY`; mutable labels or store IDs never act as a fallback.
`validate_assignments` validates previously stored/imported assignments. Two
different identities assigned one IRI produce `IRI_COLLISION` with both identities.
One identity assigned multiple IRIs produces `IDENTITY_DRIFT`. A wrong single IRI
produces `NONCANONICAL_IRI`. Errors are deterministic under input reordering.
Reusing an IRI for an explicitly changed meaning produces `MEANING_CHANGE_REUSES_IRI`;
a new IRI without the required recorded successor produces `SUCCESSOR_RECORD_REQUIRED`.

### Fixtures and proof

`tests/fixtures/skos_identity.json` is the machine-readable fixture table. It records
entity kind, stable keys, exact expected IRI, rationale, and label-change survival.
It includes the source-backed copular root and two of its distinct senses, both
notation datatypes, a collection, an ordered collection, scheme, extension term,
and an explicitly synthetic Unicode/reserved-character boundary case.

Run from the repository root:

```sh
python3 -B -m unittest lib.ithkuil.tests.test_skos_identity -v
```

The tests assert literal expected IRIs, repeated/reversed builds, label/path/store
metadata changes, changed stable keys, distinct source senses, invalid inputs,
synthetic collisions, identity drift, and explicit successor behavior. No RDF
emission or graph-store materialization is performed by this identity contract.

Standards basis: [W3C SKOS Reference](https://www.w3.org/TR/skos-reference/),
[RFC 3986](https://www.rfc-editor.org/rfc/rfc3986), and
[RFC 3987](https://www.rfc-editor.org/rfc/rfc3987). The namespace, key grammar and
error codes above are this project's profile choices, not additional W3C rules.

## 2. Resource shapes and semantic organization (#32)

This section fixes which source entities become SKOS concepts, schemes, collections,
ordered collections, or generic RDF resources. It does not define labels, notation
datatypes, semantic relations, mappings, provenance, or curriculum structure.

| Source entity | RDF/SKOS shape | Scheme rule | Grouping/order rule |
| --- | --- | --- | --- |
| Grammar value such as Configuration `MFF`, Case `ACT`, or Register `NRR` | `skos:Concept` | One or more explicitly declared semantic inventories via `skos:inScheme` | Family membership may use `skos:Collection`; it does not imply hierarchy |
| Grammar family such as Configuration, Case, or Register | `skos:Collection` | A collection is grouping structure, not a second concept identity | Emit `skos:member`; CSV/table/chapter order is ignored |
| Source-defined semantic paradigm with meaningful order | `skos:OrderedCollection` | Members keep their existing concept identities | Emit one `skos:memberList` only when the order is explicitly semantic in the source |
| Lexicon root resource | generic RDF resource | Source-document identity is not a concept scheme | The resource may receive notation under #33 without becoming a `skos:Concept` merely for that purpose |
| Root-sense identity | `skos:Concept` | Participate in the admitted semantic scheme(s) | Remains distinct from the notation-bearing root and from sibling Stem/Specification senses |
| Independently governed semantic inventory | `skos:ConceptScheme` | Scheme identity is profile-governed, never inferred from a source file/URL | Source documents can support one scheme without becoming schemes themselves |

### Concept and scheme rules

Every emitted semantic concept has one stable #31 IRI and at least one explicit
`skos:inScheme` assertion. When the same underlying concept legitimately
participates in more than one scheme, emit multiple `skos:inScheme` triples from
that one concept IRI. Do not clone the concept merely to create scheme-local IDs.
When two independently governed inventories have distinct identities, preserve
both identities; #36 decides whether a SKOS mapping relation is justified.

Source documents, source IDs, source URLs, chapter boundaries, tracked PDF splits,
and extractor files are evidence/provenance boundaries. They do not automatically
become concept schemes. In particular, the grammar HTML and lexicon PDF can describe
the same New Ithkuil inventory without requiring a cross-scheme mapping merely
because the evidence arrived through different documents.

### Collection rules

Use `skos:Collection` for real grammatical or semantic grouping where membership
does not mean subsumption. Configuration, Case, and Register are representative
unordered family collections. `skos:member` carries membership. The compiler MUST
NOT derive `skos:broader` or `skos:narrower` from family membership, table nesting,
file layout, chapter placement, or collection containment. #35 owns any later
semantic-relation admission independently of these shapes.

Member order supplied by a CSV reader has no semantic effect on a normal
collection. Reversing or shuffling source rows must therefore leave the resulting
collection graph unchanged.

### OrderedCollection admission

`skos:OrderedCollection` is admitted only when the source itself defines a
meaningful semantic/paradigmatic order. The current Level scale is a positive
fixture: source table `NI-WEB-CH05:T034` names the ordered comparison scale from
MINIMAL through EQUATIVE to MAXIMAL as
`MIN, SBE, IFR, DFT, EQU, SUR, SPL, SPQ, MAX`. The shape contract emits that
source-defined scale with `skos:memberList` and an RDF list.

CSV row order, source table order without independent semantic meaning, source
chapter order, filesystem order, and curriculum/pedagogical order are prohibited
order bases. Case remains an unordered collection merely because the source prints
its values in rows. Curriculum prerequisites and teaching sequence remain a
separate projection over stable semantic IDs.

### Root and sense separation

A notation-bearing lexicon root can remain an independently addressable generic RDF
resource. It MUST NOT be typed as `skos:Concept` merely because #33 later attaches a
notation. Source-defined Stem/Specification meanings are separate `skos:Concept`
resources using the #31 sense IRI grammar. This preserves one root with many senses
without collapsing those meanings into the written root form. A custom root→sense
predicate is not admitted here; #35 owns that extension decision if graph consumers
demonstrate the need.

### Executable contract and fixtures

`src/skos/shapes.py` exposes frozen resource specs and a pure RDFLib graph builder.
It accepts only declared scheme references, concept members, and explicit
`SOURCE_SEMANTIC` ordered collections. Unsupported order bases fail with
`ORDER_BASIS_NOT_SOURCE_SEMANTIC`; undeclared schemes/members and wrong identity
kinds fail closed rather than generating guessed RDF.

`tests/fixtures/skos_shapes_positive.ttl` is the literal positive RDF fixture. It
contains representative Configuration, Case, Register, Level, root, and root-sense
shapes plus one synthetic second scheme proving that multi-scheme participation
keeps one concept IRI. `tests/fixtures/skos_shapes_forbidden.ttl` records triples
that the shape layer must never manufacture: false hierarchy, Case/table order,
curriculum order, root-as-concept coercion, and scheme-specific concept clones.

Run from the repository root with the semantic dependency set installed:

```sh
python3 -m pip install -r lib/ithkuil/requirements-semantic.txt
python3 -B -m unittest lib.ithkuil.tests.test_skos_shapes -v
```

The tests compare the emitted graph with the positive RDF fixture, prove the
forbidden triples are absent, read the Level `skos:memberList` through RDFLib's RDF
Collection interface, reject non-semantic order bases, prove ordinary collection
row shuffling is graph-invariant, and keep the root resource distinct from its
sense concepts.
