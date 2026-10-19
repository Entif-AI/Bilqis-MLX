# Bilqis semantic architecture: code-authoritative AST and identity contract

**Status:** SUPERSEDED INITIAL SKETCH. Retained for design provenance, not an implementation blueprint. The user supplied ten existing GitHub implementation candidates and redirected the architecture toward upstream functional composition. See [04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md](04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md). No runtime implementation is authorized by this document.
**Historical context:** User's 2026-10-16 specification-first correction and protected issue #336. ADR-028 now records the replacement, composition-first direction; this draft has no governing authority.
**Scope:** Semantic identity, types, source claims, laws, revisions, generated references, and imported source catalogs.

## 1. The governing rule

The code-resident, versioned semantic AST is the **single machine-semantic authority**. It is the only place in which Bilqis creates or assigns domain identifiers for semantic primitives, capabilities, laws, grades, source-contract bindings, lesson kinds, and other curriculum entities.

Its inputs can include external research, source texts, and spreadsheet proposals. None of those inputs assigns a runtime semantic ID or independently admits a capability. Callers receive typed references or generated accessors from the AST. They do not reconstruct semantic identities from display names, sheet coordinates, grade letters, or manually repeated strings.

The AST must remain an explicitly reviewable artifact **in the repository**, compiled deterministically and pinned to every released student. An AST is authoritative only if its identity allocation, type rules, source proofs, release state, and downstream derivation are enforced. A class named CurriculumAST is insufficient.

### Decision versus remaining design choices

**Confirmed by the user:** The AST lives with code and exclusively owns domain ID allocation. The curriculum is deeply compositional and must remain self-maintaining as semantics are refined or expanded. The current string-specific and sheet-specific code is a design failure. Stop behavioral coding until architectural review.

**Proposed here for review:** A canonical declarative catalog in the repository, compiled into an immutable typed AST. A central identity ledger is part of that catalog. The catalog may have multiple definition files for human navigation, but all identifiers are minted and indexed through that one ledger and validated as one graph.

**Not changed by this proposal:** Current historical 222 token indices, accepted A/B semantic releases, saved student and native AdamW, source manifests, frozen Grade A champion, learned teacher, and Billy Madison graduation rules.

## 2. Observed problem in the present repository

| Existing source | Current behavior | Why it is unsafe as the future authority |
| --- | --- | --- |
| bilqis_mlx/curriculum.py | Capability and Course carry arbitrary string IDs and source references; structural validation insists every capability has a binary answer caste. | Course is a release projection; string names and a binary-only invariant cannot define all future semantic kinds. |
| bilqis_mlx/registry_ast.py | Reconstructs TokenNode, LessonNode, and PrerequisiteNode from a particular spreadsheet snapshot and validates exact headers, rows, legacy IDs, and counts. | Imported Sheet columns are being treated as a parallel definition vocabulary; content counts can be mistaken for semantic law. |
| bilqis_mlx/curriculum_compiler.py | Projects Course into a second CurriculumAST; probe planning branches on six named Grade A capabilities. | A derived projection cannot own the identities whose definitions it imported. |
| bilqis_mlx/live_grade_b.py | Declares three specific A prerequisite names and selects EQ, PARENT, LINK with local literals. | The generator hides a second, narrower curriculum graph from the nominal AST. |
| bilqis_mlx/semantic_coverage.py | Joins Course nodes to Token Atlas symbols; finds type-compatible pairs; checks finite-world witnesses. | Useful diagnostic evidence, but two incoming catalogs and string-based source-dialect inference remain. Type matching alone does not establish lawful composition. |
| Untracked bilqis_mlx/semantic_transformations.py | Local SemanticLaw records hard-code capability, name, effect, and a free-form source_axiom string. | Law identity and supposed authority are neither registered nor resolved. Executable applicability still lives in capability-specific branches. |
| tests/test_registry_ast.py and similar tests | Freeze current numbers of Sheet rows/bridges/grades and exact human-readable slugs. | Routine vocabulary or editorial growth can break tests without violating any semantic invariant. Conversely, synchronized code/test omissions can remain green. |

The untracked transformation prototype also excludes examination IDs from its candidate-input set. That is a historical research behavior and must not migrate into live teaching: the accepted live curriculum permits examined constructions in later instruction.

## 3. Separate five things currently conflated

1. **Identity:** Stable opaque references, numeric historical token indices, aliases, and namespace ownership.
2. **Meaning:** Typed semantic definitions, signatures, value domains, binding/scope rules, and versioned relationships.
3. **Authority/evidence:** Exact external source claims, their provenance and interpretation scope, plus separately implemented validating oracles.
4. **Instruction:** Constructible expression families, valid transformations, objectives, progression, evidence obligations, and assessment designs.
5. **Learning:** Actual student/teacher/checkpoint state, observed predictions, scheduled exposure, mastery, and retention.

The AST owns the first four as *typed declarations and dependency references*. External sources establish whether declared meanings are justified. The runtime owns observed learning state. Neither a Sheet nor a neural outcome silently rewrites the AST.

## 4. Canonical identity model

The identity ledger stores one entry per durable domain entity. Every identifier is **allocated once**, checked for collision, and never reissued. Distinct concepts get distinct identity namespaces:

| Domain identity | Stability | Owner | Notes |
| --- | --- | --- | --- |
| SemanticId | Immutable | Canonical AST identity ledger | Names a semantic concept/function independent of a displayed slug or assigned grade. |
| TokenId | Immutable numeric ABI | Canonical AST token map | Historical 0..221 indices are adopted without renumbering. Future append-only indices require separate vocabulary admission. |
| CapabilityId | Immutable | Canonical AST | Names a teachable mastery objective; grade membership is a relationship, not part of its identity. |
| LawId | Immutable | Canonical AST | Names an admitted semantic relation/axiom, not a free-form comment. |
| TransformId | Immutable | Canonical AST | Names a typed construction operator, independently implemented behind an adapter. |
| GradeId / LessonKindId | Immutable | Canonical AST | Display letters, lesson titles, and current stage order are attributes/relationships. |
| SourceClaimId | Immutable | Canonical AST | Refers to a source record whose content and external locus have independent digests. |
| ContractRevision | Content-addressed | AST compiler | Captures a semantic meaning/signature and admitted supporting claims at one revision. |
| ReleaseId | Content-addressed | Release compiler | Locks the complete admitted semantic AST, generated rules, grading rubric and executable adapter manifests. |

Source providers still assign **their own** IDs (GitHub issue numbers, Sheet file IDs, row IDs, New Ithkuil chapter/section IDs). We store these as ExternalReference provenance, never as Bilqis semantic identities. The user instruction that the AST assigns IDs applies to Bilqis's domain IDs, not to impersonating external providers' identifiers.

### 4.1 Names, aliases, and IDs are different

- A display label is editable. It may be translated or clarified without migrating model state.
- An alias is versioned and resolves through the AST. Historical names remain readable. Ambiguous aliases fail resolution.
- A semantic ID is opaque, and code does not parse its spelling for grade, type, interpreter or behavior.
- A numeric token ID is a model ABI index, kept separate from SemanticId. An identity may have an admitted token mapping, but capability, law and token counts are different.
- Changing an alias does not change a semantic contract digest. Changing typed meaning or lawful compositions creates a new contract revision and invalidates affected generated artifacts.
- Incompatible meaning changes require a distinct semantic identity or an explicitly reviewed migration. Historical checkpoints remain pinned to their original meaning.

Legacy names such as A.IDENTITY and historical proposed lesson labels are **versioned aliases**, retained for loading existing receipts. New systems never derive grade from a prefix such as A. and never derive an operator from string suffixes such as XOR.

### 4.2 The one ID allocator

The only allocation API is a catalog transaction with an explicit authority receipt:

~~~text
CatalogChange(kind, proposed_definition, source_claim_refs, decision_ref)
  -> VALIDATE proposal and collision/lineage
  -> ALLOCATE stable domain ID in canonical identity ledger
  -> WRITE declarative typed definition with that ID
  -> COMPILE entire graph and changed dependency closure
  -> EMIT reviewed diff and source/ABI/release receipts
  -> ADMIT only after separately governed source and validation gates
~~~

An importer may stage descriptions but cannot allocate IDs. A generator, test, teacher, CLI, or spreadsheet-exporter may reference existing IDs but cannot invent them. A release build rejects unknown IDs and undeclared relations.

## 5. Declarative AST model

The following is **interface pseudocode** showing the target model, not shipped Python and not new identity assignments:

~~~python
SemanticDefinition(
    identity: SemanticId,
    revision: ContractRevision,
    signature: FunctionType(inputs=[TypeRef, ...], output=TypeRef),
    meaning: MeaningAST,
    domain_constraints: PredicateAST,
    source_claims: tuple[SourceClaimId, ...],
    admissibility: AdmissionState,
)

CapabilityDefinition(
    identity: CapabilityId,
    meaning_refs: tuple[SemanticId, ...],
    prerequisites: DependencyExpr,
    answer_types: tuple[AnswerTypeRef, ...],
    evidence_obligations: tuple[CoverageRuleRef, ...],
)

GradeDefinition(
    identity: GradeId,
    member_capabilities: tuple[CapabilityId, ...],
    order: GradeOrder,
    graduation_policy: GraduationPolicyRef,
)

SemanticRelease(
    identities: IdentityCatalog,
    definitions: SemanticGraph,
    rules: RuleGraph,
    source_manifest: SourceManifest,
    admissions: AdmissionLedger,
    version_lock: ReleaseDigest,
)
~~~

**Types must be algebraic objects**, not unvalidated signature strings such as Boolean*Boolean->Boolean. At the boundary, an imported signature is parsed once into a typed function tree. The compiler supports functions, relations, sets, maps, quantifiers, polymorphism, native answer tokens, and restricted linguistic morphology where sources justify them. Unknown type constructors are explicit unresolved nodes; no best-effort type coercion.

### 5.1 Dependency graph

Dependencies have explicit kinds, not a single undifferentiated string list:

- REQUIRES_MASTERY: pedagogical sequencing between capabilities.
- USES_SEMANTIC: a construction uses an admitted semantic primitive.
- COMPOSES_AT: a type-checked operand or grammar slot.
- VALIDATED_BY: a source claim, oracle, proof, or transformation rule.
- CONSTRAINED_BY: type, world, lexical, grammar and boundary restrictions.
- TEACHES / ASSESSES: generated plans and probes derived from the same meaning rules.
- SUPERSEDES / ALIAS_OF: version and migration lineage.

Each edge has a stable identity assigned by the AST's graph compiler from canonical endpoints, relation kind, and versioned role. It cannot be minted ad hoc by a consumer. A type-compatible connection is a **candidate**, not automatically an admitted dependency or mandatory lesson. Composition/grammar rules determine REQUIRED, PERMITTED, INAPPLICABLE, or UNRESOLVED status. Only REQUIRED and admitted PERMITTED edges produce executable construction obligations.

For example, all six admitted A finite-world predicates yield Boolean results. That makes them *candidates* for Boolean operators in B. Three use the historical micro-world interpreter and three use the development-world interpreter. A verified cross-interpreter representation is needed before either group can be combined indiscriminately in one executable world. This preserves the useful discovery from the last audit without equating type compatibility to source authority.

## 6. Semantic laws are registered, typed and executable through adapters

### 6.1 What the current SemanticLaw really does

The untracked prototype's dataclass stores capability, name, expected truth effect and source_axiom. apply_law checks those strings, executes a handwritten transformation, and compile_transformations generates candidate records with parent ID, transformation name, expected gold, orbit hash and admitted=False. The source_axiom field is returned as metadata, not resolved as a source authority reference. The actual meaning of reverse_query differs across the named capabilities because conditional branches implement the distinction.

Its term entity-renaming-bijection describes a mathematical operation: a bijection is an invertible one-to-one renaming of finite-world entities, applied consistently to the world and query. Consistent renaming preserves truth under identity-independent finite-world semantics. A free-form label for that fact is not a source proof or an AST law.

### 6.2 Target law contract

~~~python
LawDefinition(
    identity: LawId,
    quantified_type_variables: tuple[TypeVariable, ...],
    applicability: PredicateAST,        # e.g., finite closed Entity world
    preconditions: PredicateAST,        # bijection on entity names
    transformation: TransformRef,      # registered typed operator
    relation: OutcomeRelation,         # EQUIVALENT / NEGATED / IMPLIES / ...
    source_claims: tuple[SourceClaimId, ...],
    witness_requirements: WitnessSpec,
    revision: ContractRevision,
)

TransformationAdapter(
    transformation: TransformRef,
    accepts: TypedExpressionSchema,
    produces: TypedExpressionSchema,
    source_interpreter: InterpreterRef,
    independent_oracle: OracleRef,
)
~~~

An **AST law declaration says what must be true** and cites the formal/source basis. An **adapter says how to transform a concrete representation**. An independent oracle tests the predicted relation on constructed examples. Neither declaration nor adapter alone establishes admission.

Law applicability comes from typed predicates and registered semantic traits, not a table of A.IDENTITY/A.PARENT/A.MAPS string comparisons. For instance, entity-renaming invariance applies to any admitted finite-world semantic function that is invariant under bijective relabeling, subject to its types and binding scopes. A directed-edge reversal only flips truth under the law's stated witness preconditions; it is not an unconditional theorem about all graphs.

The compiler handles an unproven law by emitting SOURCE_PROOF_MISSING or INVALID_PRECONDITION coverage debt. It must never silently manufacture a source_axiom name.

### 6.3 Law output and provenance

Successful construction returns a typed witness, not only another question row:

~~~text
TransformationWitness {
  source_expression, transformed_expression,
  semantic_id, law_id, law_revision, adapter_revision,
  source_claim_refs, checked_preconditions,
  expected_relation, independent_oracle_results,
  input/output token ABI, canonical_structural_class,
  source_generation_seed, verification_receipt, admission_state
}
~~~

This can feed teaching and testing after admission; the teacher sees source-valid choices rather than a forced mix. A stored examination cohort remains an immutable measurement receipt, while previously examined constructions remain eligible for instruction.

## 7. External Sheet and primary-source boundary

The current Bilqis Curriculum Registry Sheet is valuable human-facing material and a historical record. The redesigned flow is:

~~~text
Official grammar/lexicon + pinned legacy source + Sheet research/proposals
           |                    |                       |
           +--------------------+-----------------------+
                                |
              source/proposal import and validation
                                |
                     PROPOSED AST changes
                                |
        reviewed canonical code-resident identity ledger
                  + typed semantic declarations
                                |
                   compiled signed/versioned AST
                                |
               generated human-readable Sheet views
                 + curriculum/tests/source receipts
~~~

Source authority about New Ithkuil grammar remains in the verified official grammar and lexicon, not in self-written AST labels. The code AST is authoritative for **Bilqis's versioned interpretation and identifiers**. An external source claim must be preserved with exact location/version/content hash, scope, and review disposition.

Sheet importer and exporter are **boundary adapters**. Imported rows are mapped to existing AST IDs by stable references or staged as unresolved proposals. Row position, count, title and free-text phrase cannot mint a semantic ID. Changes to external data generate a reviewable delta; they never rewrite a pinned release automatically. The export carries AST ID, revision and provenance and clearly labels research versus admitted state.

## 8. Release states and compatibility

**State progression:** RESEARCH_PROPOSAL -> SOURCE_ATTESTED -> SEMANTICALLY_VALIDATED -> ADMITTED -> RELEASED -> MEASURED. A source-attested item may remain unadmitted. A measured item may still be unmastered. Deprecation or supersession never destroys the historical release.

Each student binds the complete semantic release digest, the ordered token ABI mapping, admitted grade roster, answer-caste ABI, source/oracle digests, and generator/rubric versions. Loaded checkpoints resolve identities through **their pinned release**, not the latest catalog.

The original 222 token positions and historic source identifiers are imported into the canonical catalog with immutable compatibility assertions. Additional token positions must be allocated append-only. No semantic alias revision may renumber those 222 entries, reset the FP32 student, invalidate its own AdamW, or rewrite teacher history.

## 9. Non-negotiable compile-time invariants

1. One definition per stable domain ID, one owner for ID allocation, and no duplicate/ambiguous alias within a release.
2. No runtime module or test invents domain IDs or dispatches semantics by parsing display slugs.
3. Every used semantic type and law has a declared source/proof contract; unresolved claims stay unresolved.
4. Every generated item is traceable to release, typed expression, rules, source, oracle, seed and witness.
5. Every semantic revision invalidates *exactly the dependent generated families* and preserves previous pinned releases.
6. Every assessment's required constituents were separately admitted and taught, with the original source-verifiable full-rubric graduation threshold unchanged.
7. Every imported Sheet statement is either matched to an existing AST referent, staged as a proposal, or rejected with a specific reason.
8. Grade, law, answer type and curriculum dimensions remain extensible without editing a named-grade switch.
9. No unverified research module becomes an executable instruction source or changes actual student/teacher state.

## 10. Architecture review decisions

The selected **logical** shape is one code-authoritative typed AST backed by an append-only identity ledger and source-bound proofs. The choice of on-disk declaration syntax (strict JSON, TOML, or a limited typed DSL) remains an implementation-detail checkpoint. It must support deterministic canonicalization, diff clarity, schema checks, and generated code references.

The critical review question is whether semantic declarations should be exclusively declarative data compiled by Python, or a restricted executable Python DSL compiled into the same canonical AST. The first option is recommended for auditability and independence from arbitrary module execution.
