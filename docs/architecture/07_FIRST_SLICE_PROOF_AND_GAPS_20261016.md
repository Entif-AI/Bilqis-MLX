# First clean-room compositional slice: proof and remaining requirements

**Status:** Source-only engineering candidate. Source and independent symbolic-oracle verification passed; it is not a released curriculum, teacher policy, or authorized live-model update.
**Governance:** ADR-028, protected [issue #336](https://github.com/socr8s/private-ip/issues/336), behavioral [contract 05](05_BEHAVIORAL_CONTRACT_V1.md), upstream [ledger 06](06_UPSTREAM_SOURCE_METHOD_LEDGER.json).

## Delivered mechanism

The new \`bilqis_mlx.composition\` module contains:

- **core.py:** Immutable typed \`Operation\`, \`Signature\`, \`Literal\` and \`Apply\`; read-only ID \`Catalog\`, curried and arbitrary-slot partial application, binary lifting and unary function composition. Every completed application has an inspectable structure and deterministic semantic-contract hash.
- **catalog_bridge.py:** Transitional, **read-only** binding from the current Registry projection and pinned historical source graph. Checks the **original TokenId, token symbol, original graph digest, row meaning-contract SHA and signature arity** before yielding an operation. This adapter cannot allocate IDs, change historical meaning, or admit a new lesson. The full code-resident catalog and source admission system are still missing.
- **source_micro.py:** Small ingress adapter converting already attested finite-micro query ASTs to generic typed expressions. Unknown source syntax and missing canonical symbols fail explicitly. No Grade B semantic IDs are minted here.
- **methods.py:** Generic exhaustive Boolean truth-case verification and bottom-up independent checking of each already-admitted composite constituent. It generates reusable property receipts rather than training or assessment state.
- **Verification backend contract:** A source backend and an independently identified symbolic backend must agree before yielding a proof receipt. The first implementation provides test-only adapters using the pinned historical source interpreters and installed SymPy. A distinct identity string by itself is **not** proof that two evaluators are truly independent; backend implementations and their source dependencies must be audited.

### Verified commands

\`\`\`sh
python3 -B -m unittest tests.test_composition_core tests.test_composition_source_micro -q
python3 -B -m unittest discover -s tests -q
python3 -B -m json.tool docs/architecture/06_UPSTREAM_SOURCE_METHOD_LEDGER.json
git diff --check
\`\`\`

Most recent source-only checks: **12/12 focused tests** and **246/246 full Python tests** passed. The focused suite exercised **all 22 complete Boolean input vectors** for the original six admitted B operators (two NOT cases and four cases each for AND/OR/XOR/IMPLIES/IFF). It independently checked **72 freshly constructed B micro-world expressions** across their nested A.IDENTITY/A.PARENT/A.LINK operands, matching pinned source gold. It checked generic currying and composition, partial application of arbitrary input positions, original finite-world token ABI, display-name stability, world incompatibility, false independent oracle, unknown source syntax, and changed source meaning-contract SHA. All tests are neural-inert; no actual optimizer or teacher state was loaded for mutation.

The test environment had **SymPy** and **NetworkX** installed; **Z3** and **Hypothesis** were absent at initial preflight. Their inclusion is a future dependency/performance decision, not proof of general model checking already implemented.

## Behavioral acceptance mapping

| Requirement | Disposition | Evidence / outstanding work |
| --- | --- | --- |
| C01 historical identity | **Partial** | Read-only pinned source ID + row contract binding works for the tested nine original tokens. Full 222-ID code-native catalog and lesson-ID allocation require migration. |
| C02 canonical refs | **Partial** | Generic builder uses catalog token indices and source ingress resolves symbolic names. Legacy builders remain string-specific; test source aliases are compatibility fixtures. |
| C03 typed application | **Partial** | Enforces finite Boolean and Entity signature and explicit world-contract equality. Full quantifier/binder grammar and source-translation proofs remain open. |
| C04 functional composition | **Proven on bounded slice** | \`curry\`, \`partial_apply\`, \`lift2\`, \`compose\` create inspectable expressions with canonical digests. |
| C05 scoped binding | **Pending** | General capture-avoiding bound variables, polymorphism and first-order quantification not implemented. |
| C06 external backends | **Partial** | Backend protocol, pinned finite-micro adapter and independent SymPy test backend; production registry/selection/performance not yet implemented. |
| C07 registered laws | **Pending** | Source-backed \`LawRef\`, quantified preconditions, generic metamorphic laws and falsifiers not yet implemented; untracked SemanticLaw prototype remains untouched. |
| C08–C14 lessons, proof and coverage | **Partial** | Complete Boolean input-pattern proof and verified nested source expressions exist. No general exhaustive source-law coverage, independent cross-world bridge, guaranteed input-world diversity, or live lesson-plan compiler. |
| C15–C20 learner and runtime | **Pending** | No code path to live model/AdamW/teacher, five diagnostics, missed-example retention, or spiral scheduler integration has changed. |

## Independent agent findings

Two read-only workers examined upstream source mechanisms and adversarial integration acceptance. Their validated high-priority findings:

1. The living Sheet projection is an **import boundary**, not a full authoritative code-native catalog. Existing snapshot parser expects positional/shape invariants; mutation tests that call \`dataclasses.replace\` can bypass importer constraints. Catalog migration must prove real add/rename/reorder behavior through its actual public ingest boundary.
2. Boolean output type matches do **not** prove a lawful micro/development AST translation. Absent a source-attested common-world interpretation, the 33 cross-world operand candidate slots remain UNKNOWN/UNVERIFIED.
3. Source-generated output label balance is not the same as **complete joint operand truth-pattern coverage**. The new \`exhaustive_boolean_cases\` method checks all 22 finite patterns for the six Boolean source truth operators; actual world-backed composition diversity must be separately verified.
4. A recorded semantic contract SHA must be verified against **source data**, not merely copied between AST and receipt. \`bind_source_catalog\` now rejects source index and row-contract drift. Source-claim review/admission and checkpoint-time release binding remain future work.
5. Bounded constraint search can prove SAT by witness but cannot claim **uniqueness** when truncated to one solution. Solver UNKNOWN/timeout/vacuity need precise receipts in the future Z3/SymStep integration.
6. Proof lineage must connect original source, composition method, independently checked witness, actual delivered teaching, delayed assessment and teacher policy decision. Current source-only receipt addresses only the construction portion.

The source-analysis subagent also found potential **future formal semantic candidates** for PATH, DOMAIN, RANGE and set/function relationships in pinned interpreters. Those are **research candidates**, not a modification of admitted letter Grade B, nor authority to teach unseen set referents or inflected New Ithkuil morphology.

## Next independent implementation unit

The next vertical slice should use the same canonical typed registry and compositional API to register **source-attested laws with machine-checkable preconditions and falsifying examples**, then add a finite-model constraints backend behind the existing checker interface. It must compile relevant law and lesson methods without new named-grade branches and must distinguish incomplete proof scope from tested source facts. Parallel requirements include proper 222-token + original lesson ID code-resident catalog migration and explicit cross-interpreter world translation contracts.

Before any trainer wiring: verify original student/checkpoint semantic release compatibility, teacher-policy noninterference, the five continuous learning signals and actual delivery/retention receipts. Issue #336 remains open until its own empirical acceptance criteria are met under human-owned training.
