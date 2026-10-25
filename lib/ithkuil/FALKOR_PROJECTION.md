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

## Import and recovery (#74)

Install `requirements-falkor.txt` locally. Import only a verified #72 evidence
bundle; the importer hashes every constituent, independently re-runs all four gates
from its serialized artifacts, and rejects a forged status or missing evidence.
It does not read source CSVs or perform semantic decisions. A public API call
accepts the bundle path, preventing a precomputed projection from bypassing the
conformance boundary.

```sh
python3 -B -m lib.ithkuil.src.skos.falkor_import \
  --bundle PATH/TO/CONFORMANCE-BUNDLE \
  --graph EXPLICIT_OWNED_GRAPH --owner EXPLICIT_OWNER \
  --host 127.0.0.1 --port 16379
```

The client accepts existing credentials through `BILQIS_FALKOR_USERNAME` and
`BILQIS_FALKOR_PASSWORD`; credentials never enter receipts. Host/port select the
local tunnel endpoint. This command runs entirely on the execution machine.

The strategy is upsert by canonical term/edge key within one explicitly owned
projection. A new empty graph receives one `BilqisProjection` marker with owner,
canonical digest, version, expected counts and `state=incomplete`. Existing graphs
without that exact owner marker are refused. A different canonical digest requires
an explicitly safe reset; import does not silently mix artifact versions.

All nodes/edges carry `owner`. Each MERGE sets ownership only on creation and
checks it before updating matched data. A foreign key match cannot be overwritten.
One authorized writer owns the graph; the marker is custody metadata, not a
fabricated distributed lease. A range index on the term key supports deterministic
upserts; retries inspect index state rather than recreating an existing index.

Completion follows full paginated readback, exact reconstruction and digest/shape
verification. The marker is then set complete and read back. A second identical
import verifies the existing closure and returns without semantic writes. Failed
or interrupted batches retain incomplete state and never emit a complete result.
For a timeout or lost acknowledgement, inspect the actual marker and closure first;
never infer that a write failed. Same-artifact retry reconciles through idempotent
upserts. Different-artifact replacement belongs to #75. Automatic transport retries
are disabled; an ambiguous operation is surfaced for reconciliation.

The live test suite requires explicit `BILQIS_FALKOR_LIVE=1`. It creates fresh,
uniquely named test graphs, records their owners, proves an induced partial failure,
resumes that exact graph, and compares full readback after repeat import. It never
resets an existing graph or invokes whole-graph deletion. Ordinary tests cover
artifact tampering, a falsely claimed gate pass, the real aggregate-export/import
boundary, and refusal to bypass conformance with a raw projection dictionary.

References: [query parameters](https://docs.falkordb.com/commands/graph.query),
[read-only queries](https://docs.falkordb.com/commands/graph.ro-query), and
[range indexes](https://docs.falkordb.com/cypher/indexing/range-index).

## Scoped reset and foreign boundaries (#75)

`falkor_reset.plan_reset(importer)` is read-only. It enumerates the exact owned
term/edge keys, counts, graph/owner, represented canonical digest, marker state,
foreign nodes touching owned edges, foreign edges touching owned nodes, and
boundary blockers. Ownership requires the explicit marker plus matching per-term
and per-edge owner. Unknown owned node classes, foreign incoming/outgoing edges,
and an owned edge touching a foreign node refuse deletion.

`reset_owned(importer, plan)` requires that exact graph/owner plan, re-reads it,
and then executes one guarded database query. The query rechecks exact key sets,
marker identity/state/digest and foreign boundaries before deleting only the
selected owned edges and terms. It uses neither `GRAPH.DELETE` nor an unscoped
node deletion. A same-count key swap or foreign edge arriving after the final
client-side read fails the database guard. The marker survives in `empty` state;
readback confirms zero represented counts. A subsequent verified import can rebuild.
Unrelated foreign nodes and edges remain untouched and may coexist with the owned
projection; importer/readback scope and boundary checks preserve that separation.

```sh
# No-mutation plan:
python3 -B -m lib.ithkuil.src.skos.falkor_reset \
  --graph EXPLICIT_OWNED_GRAPH --owner EXPLICIT_OWNER > reset-plan.json
# Execute only this reviewed exact plan:
python3 -B -m lib.ithkuil.src.skos.falkor_reset \
  --graph EXPLICIT_OWNED_GRAPH --owner EXPLICIT_OWNER \
  --execute --plan reset-plan.json
```

An interrupted reset reports reconciliation required. Inspect the surviving marker
and actual owned boundary; do not infer that a timeout means no deletion occurred.
No whole-graph administration is provided. Live tests create only fresh owned test
graphs and synthetic foreign-boundary fixtures. They prove dry-run immutability,
clean reset/rebuild, unrelated foreign-subgraph survival, all three unsafe boundary
cases, wrong graph refusal, same-count stale-plan refusal, and an injected boundary
race inside the final guarded operation. The full corpus graph is not reset by
these tests.
