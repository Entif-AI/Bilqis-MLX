# Release acceptance audit (#97)

Reviewed branch head: `e714c39d5815f150a680745e77fc16a4c5b8bb4c`. Root contract SHA-256: `6977b73678ae4ad8d9600e68ab1196867072b8649a45fb5b934755c1b6e7a362`.

**Decision: engineering complete; keep GitHub issues open until a separately authorized merge.**

No unmet required criterion was found. Semantic coverage remains partial. Allowed debt is not graduation, source completeness or permission to infer missing assertions. PR #291 remains draft/unmerged.

The machine matrix in [audit.json](audit.json) carries full owning issues, exact artifact/test paths, receipts, source-head ancestry, hashes and row notes. Row evidence uses local JSON Pointer references to shared group arrays, with no second artifact registry. This human table preserves every root checkbox and non-goal. Source parser/compiler/IR/Skill bytes match the #93 source candidate; later source changes are only the census wrapper and #75 reset repair.

## Root acceptance and non-goals

| ID | Requirement | Evidence groups | Status |
| --- | --- | --- | --- |
| AC-01 | The implementation defines a documented, standards-first SKOS/RDF profile for Bilqis New Ithkuil ingestion. | profile | PASS |
| AC-02 | `skos:notation` is used for literal Unicode New Ithkuil notation with a documented notation datatype URI. | profile | PASS |
| AC-03 | Grammar codes may use a distinct notation datatype without replacing the literal Ithkuil notation. | profile | PASS |
| AC-04 | Concepts, ConceptSchemes, Collections/OrderedCollections, lexical labels, documentation properties, semantic relations, and mapping properties are used before project-specific equivalents are invented. | profile | PASS |
| AC-05 | Custom Bilqis vocabulary is limited to relations/data that core SKOS cannot faithfully express. | residue | PASS |
| AC-06 | No SKOS relation is used merely to make the graph prettier if the linguistic semantics do not justify it. | profile, residue | PASS |
| AC-07 | Root forms and root senses remain distinguishable and queryable. | lexicon | PASS |
| AC-08 | Multiple realizations do not create false duplicate concepts. | atomic | PASS |
| AC-09 | Multiple senses do not collapse into one root concept. | lexicon | PASS |
| AC-10 | Same-scheme notation ambiguity is detected. | atomic | PASS |
| AC-11 | A deterministic CSV -> RDF/SKOS compiler exists under the Ithkuil source tooling. | core | PASS |
| AC-12 | Stable IRIs are derived from semantic/source identity, not row order or English labels. | core, profile | PASS |
| AC-13 | Repeated builds over identical inputs are byte-stable or canonically RDF-equivalent. | core, conformance, release | PASS |
| AC-14 | Unsupported/ambiguous mappings fail closed or remain explicitly held. | mapping, core | PASS |
| AC-15 | Source references survive the projection sufficiently to trace semantic nodes back to their public source-graph inputs. | core, lexicon | PASS |
| AC-16 | The compiler reports every skipped/held row and why. | core, conformance | PASS |
| AC-17 | No LLM call is required for a normal rebuild. | core, frontier, release | PASS |
| AC-18 | Configuration compiles reproducibly from current public CSV inputs. | configuration | PASS |
| AC-19 | Exactly 20 semantic Configuration concepts are observed unless the source corpus itself changes and the fixture is deliberately updated. | configuration | PASS |
| AC-20 | Literal UTF-8 forms including `∅` and non-ASCII notation round-trip exactly. | configuration | PASS |
| AC-21 | Family membership is represented by Collection membership, not fake taxonomic hierarchy. | configuration | PASS |
| AC-22 | Grammar-code and New-Ithkuil notation datatypes remain distinguishable. | configuration | PASS |
| AC-23 | The canonical RDF/SKOS artifact can be materialized into an isolated FalkorDB graph/projection. | graph | PASS |
| AC-24 | Materialization is idempotent. | graph | PASS |
| AC-25 | Rebuild from source does not require Falkor state. | release | PASS |
| AC-26 | Foreign graph data prevents unsafe scoped reset. | graph | PASS |
| AC-27 | Read-only smoke queries prove family, code, notation, scheme, mapping, and source lookup paths. | graph | PASS |
| AC-28 | Falkor internal identity never becomes semantic identity. | graph | PASS |
| AC-29 | A materialization receipt binds the graph to the semantic projection digest. | graph | PASS |
| AC-30 | The compiler can consume all currently supported grammar/morphology CSV categories without ad hoc per-category code where a generic rule applies. | atomic | PASS |
| AC-31 | Lexicon roots and senses are covered without root/sense conflation. | lexicon | PASS |
| AC-32 | Affix-degree semantics have a deterministic SKOS projection. | residue | PASS |
| AC-33 | Crosswalk and bridge tables emit only mapping assertions justified by their current state. | mapping | PASS |
| AC-34 | Composition/allomorph data is preserved without being falsely reclassified as SKOS hierarchy. | residue | PASS |
| AC-35 | Source-frontier debt remains explicit until later lexicon chapters and the affix reference are actually parsed. | frontier | PASS |
| AC-36 | Build emits a machine-readable coverage receipt. | conformance | PASS |
| AC-37 | Canonical semantic output is stored in a graph-store-neutral RDF serialization. | core | PASS |
| AC-38 | The semantic corpus is independently usable without FalkorDB. | core, release | PASS |
| AC-39 | The projection is suitable for search, traversal, comparison, later SHACL validation, later OWL formalization, and cross-system mapping. | profile, graph, conformance | PASS |
| AC-40 | Once compiler behavior is stable, the end-to-end New Ithkuil ingestion/rebuild process is captured as a governed reusable Skill. | skill | PASS |
| AC-41 | The Skill calls deterministic scripts for known rules rather than asking a model to reinterpret the same source material every run. | skill | PASS |
| AC-42 | New agent-discovered extraction rules become code + fixtures/tests before being accepted into repeatable corpus generation. | frontier, skill | PASS |
| NG-01 | authorize neural training or curriculum admission; | profile, conformance, release | PASS |
| NG-02 | define curriculum ordering; | profile, conformance, release | PASS |
| NG-03 | make source chapter order pedagogical order; | profile, conformance, release | PASS |
| NG-04 | turn SKOS into a provenance protocol; | profile, conformance, release | PASS |
| NG-05 | turn SKOS into an attestation protocol; | profile, conformance, release | PASS |
| NG-06 | turn SKOS into an attribution protocol; | profile, conformance, release | PASS |
| NG-07 | make claims about evidence strength or consequences; | profile, conformance, release | PASS |
| NG-08 | define Rosetta semantics; | profile, conformance, release | PASS |
| NG-09 | require every CSV column to become an RDF property/class; | profile, conformance, release | PASS |
| NG-10 | require OWL before useful work can ship; | profile, conformance, release | PASS |
| NG-11 | require SHACL before useful work can ship; | profile, conformance, release | PASS |
| NG-12 | require OntoLex before useful work can ship; | profile, conformance, release | PASS |
| NG-13 | require FalkorDB to be the canonical store; | profile, conformance, release | PASS |
| NG-14 | assert that the currently parsed lexicon/affix frontier already equals the full New Ithkuil language; | frontier, mapping | PASS |
| NG-15 | promote proposed or historical Bilqis/Ithkuil mappings into semantic identity. | frontier, mapping | PASS |

## Parent gates

| Parent | Gate evidence | Status |
| --- | --- | --- |
| #20 | profile | PASS |
| #21 | core | PASS |
| #22 | configuration, atomic | PASS |
| #23 | lexicon | PASS |
| #24 | residue | PASS |
| #25 | mapping | PASS |
| #26 | conformance | PASS |
| #27 | graph | PASS |
| #28 | frontier | PASS |
| #29 | skill | PASS |
| #30 | release | PASS |

## Declared debt and scope

- 500 atomic rows remain HELD for identity/definition/notation decisions (#46/#47/#49).
- 551 mapping rows remain HELD and one REJECTED (#62/#64–#66); no production mapping is fabricated.
- 9,488 lexicon evidence rows remain IR_ONLY (#55/#80–#84/#86); 5,097 roots have no parsed senses.
- Grammar index, lowercase lexicon PDF and Chapter 0 TOC remain pinned/unparsed. Prose exhaustiveness and legacy debt are not measured as zero. Affix unsupported tables and ambiguous occurrences remain visible (#28/#85/#86).
- Frontier categories overlap and must not be added to semantic row totals. Exact per-reason counts and owners are in the machine matrix.

## Important distinctions

The Configuration golden fixture has 20 concepts from its source-backed bounded selection. The full release holds CONFIGURATION/MFF for NOTATION_COLLISION. Both outcomes satisfy their separate contracts; a bounded lookup must not be reused as release gold.

#80/#81 have verified PR turn-in receipts and ancestor commits despite empty issue-comment threads. OPEN issue state is not an engineering blocker. Historical parent inventories are superseded by the full #93/#94 census and #95 graph proof. #75 full-scale paging and atomic-memory correction supersedes its old insufficient bounded proof.

Rosetta VocabPack integration is a separate consumer seam under the root authority amendment, not permission to widen this lane into Rosetta Core work. The corpus remains domain semantic authority; Falkor/Akasha, ABI/AST/curriculum and evidence protocols remain separate consumers/owners.

## Verification and lifecycle

486 portable SKOS tests pass (13 live-only skips); five explicit live reset tests pass separately. 12 focused Configuration tests pass. #93 proves two independent pinned-source/IR/RDF builds; #94 accounts 25,692 rows; #95 proves two full graph rebuilds/read-only journeys; #96 mechanically verifies commands/paths and executes literal SPARQL examples. Existing evidence was inspected rather than blindly replaying source or destructive store operations.

No implementation defect was repaired inside #97. No semantic/source/RDF/neural mutation, merge or manual issue closure occurred. Incidents PM-2026-10-26-004/005/006 preserve the contained recovery history. IPR-0220 remains binding. #30/#19 may be turned in through PR auto-close references only; this audit authorizes no merge.
