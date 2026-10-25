# Canonical RDF to FalkorDB projection

Normative contract #73, version `1.0.0`. FalkorDB is derived state. The canonical
RDF default graph and its stable IRIs remain authoritative. This contract does
not change the semantic profile, held-state admission, source truth or curriculum.

## Exact storage model

Every subject/object RDF term becomes one `RdfTerm` node. Every asserted triple
becomes exactly one directed `RDF` relationship. Its `predicate_iri` property is
the exact RDF predicate. No predicate is replaced by an approximate semantic
relation, no inferred inverse/transitive triple is added, and no triple is omitted.
A relationship's constant type is storage structure; `predicate_iri` carries the
RDF semantics. Predicate resources also become nodes when they occur as subjects
or objects. Their use solely as predicates is represented by the edge property.

| RDF construct | Node/relationship representation | Reconstructable assertion |
| --- | --- | --- |
| IRI resource | `RdfTerm:Resource`, `kind=iri`, exact `iri` | Same IRI |
| Literal | `RdfTerm:Literal`, exact `lexical`, `datatype`, `language` | Same lexical RDF literal; no normalization |
| Blank node | `RdfTerm:BlankNode`, canonical `blank_id` | Same canonical blank-node structure |
| `rdf:type skos:ConceptScheme` | RDF edge plus derived `ConceptScheme` subject label | Original type triple |
| `rdf:type skos:Concept` | RDF edge plus derived `Concept` subject label | Original type triple |
| `rdf:type skos:Collection` / `OrderedCollection` | RDF edge plus matching derived subject label | Original type triple |
| `skos:inScheme`, `skos:member`, `skos:memberList` | RDF edge with exact predicate IRI | Same membership/list head |
| `rdf:first`, `rdf:rest` | RDF edges through scoped blank nodes | Same ordered RDF list |
| `skos:prefLabel`, `altLabel`, `hiddenLabel` | RDF edges to literal nodes | All labels and language tags |
| `skos:notation` | RDF edge to exact typed literal | Unicode lexical form plus datatype |
| `dcterms:source` and source-locus metadata | RDF edges to resource/literal nodes | Complete source-reference chain |
| SKOS documentation and semantic relations | RDF edges with exact predicates | Original asserted semantics only |
| SKOS mapping predicates | RDF edges with exact predicates | Original admitted mapping, no inferred identity |
| Approved Bilqis extensions | RDF edges with exact vocabulary IRIs | Original source-grounded relation |
| Other RDF 1.1 predicates/classes | Explicit opaque, lossless RDF pass-through | Original triple; no store interpretation |

Type labels are derived indexes, never additional RDF assertions. The generic
pass-through preserves unfamiliar predicates without asserting they are admitted
semantic extensions. Upstream profile/conformance still owns admission. The
adapter must not interpret unknown predicates or use pass-through to manufacture
strong mappings. Literal values live on literal nodes, avoiding scalar-property
loss of multiplicity, language, datatype, blank-node structure or source links.

## Identity and idempotency

`key` is lowercase SHA-256 of compact UTF-8 JSON arrays (`ensure_ascii=False`,
separators comma/colon). Exact identity arrays:

- IRI node: `["iri", iri]`.
- Literal node: `["literal", lexical, datatype_or_empty, language_or_empty]`.
- Blank node: `["bnode", canonical_rdf_sha256, canonical_blank_id]`.
- RDF edge: `["triple", source_key, predicate_iri, target_key]`.

The canonicalizer is the pinned #41 implementation. It rejects unsupported terms,
invalid/relative IRIs and dataset/named-graph input before projection. Blank-node
source labels are canonicalized before keying. Scope by content digest prevents
unrelated graphs from merging unrelated blank nodes. Graph names, hostnames,
paths, timestamps and Falkor internal IDs never enter these identities.

Every semantic IRI node retains its exact `iri`; term/edge keys are storage keys,
not replacement semantic IDs. Resource keys persist across label corrections.
Blank-node keys may change when the canonical graph changes; they are deliberately
not semantic resource identities. All nodes/edges are explicitly ownership-tagged
by the importer; operational ownership and run receipts remain outside RDF.

## Supported boundary and round-trip proof

All valid RDF 1.1 default-graph triples supported by #41 are reconstructable with
canonical-equivalent bytes. Unknown predicates are lossless opaque pass-through.
Named graphs/datasets, quoted triples/RDF-star, generalized RDF, invalid term
positions, malformed Unicode and invalid IRIs are unsupported and must fail before
any database write. There is no accepted lossy mode.

`falkor_projection.project_graph` is the pure executable reference.
`reconstruct_graph` independently rebuilds RDF, recomputes canonical digest,
node/edge keys, labels and counts, and rejects missing/duplicate/drifted content.
The tiny Unicode-notation golden JSON is derived directly from the identity arrays
above; tests also round-trip the existing full core fixture, source chains,
ordered lists, exact non-normalized typed literals and opaque predicates. Dataset
and invalid-term negative fixtures fail. No live database mutation occurs in #73.

```sh
python3 -B -m unittest lib.ithkuil.tests.test_skos_falkor_projection -v
```
