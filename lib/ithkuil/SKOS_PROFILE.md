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
| Root-sense Concept | `id/sense/{source_id}/{sense_id}` | Public source identity and pinned source sense ID |
| Extension term | `vocab/{term}` | Admitted vocabulary term key |

For lexicon records, `root_id` is the existing `lexicon_root_id` and `sense_id` is
`lexicon_sense_id`. For grammar-site root records, the root key is the pinned
`atomic_id` and the sense key is `sense_id`. Different source domains remain
distinct until an explicit mapping contract justifies a relation. A label match
or identical root spelling cannot merge their identities.

Scheme and datatype keys are profile declarations, not English labels. A new
scheme key requires a genuinely different governed inventory. Merely reserving an
extension term IRI does not admit its predicate or class; #35 and concrete residue
issues own that decision. The `hasRootSense` fixture is a reserved example only.

### Encoding and normalization

All keys are nonempty, case-sensitive Unicode strings in NFC. Leading/trailing
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
and do not enter these IRIs. The upstream source entity IDs are treated as pinned
keys: this layer MUST NOT recompute them from mutable glosses. An upstream extractor
that remints a key creates a migration review, not permission to silently rename an
existing concept. Its source fingerprint is not a semantic-equivalence assertion.

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
