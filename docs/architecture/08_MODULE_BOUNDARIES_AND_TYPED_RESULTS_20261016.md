# Bilqis MLX: compositional module boundaries and typed result vocabulary

**Status:** User-confirmed ADR-029 implementation contract under protected IPR-0220 / issue #336. Applies to the pure source-only semantics slice; does not admit new curriculum or authorize neural optimization.

## Why this split exists

The existing `bilqis_mlx/composition/` package mixed four independent responsibilities: typed meaning and higher-order construction, old-source ingress, finite verification, and law falsification. The last addition duplicated literal result states between code and tests and used a free-form `LawContract` record that implied registration without enforcing it. This is the precise recurring module/identity problem from `PM-2026-10-16-004`, `RC-087`, `PAT-069`.

The user-supplied donor study in [04](../history/architecture/04_COMPOSITION_AND_UPSTREAM_REUSE_DECISION.md) supports splitting along **domain** boundaries rather than grade letters or pipeline stages: [LENs](https://github.com/pietrobarbiero/logic_explained_networks/tree/5d36cebeead6958490cc27f797c331468eb9238b) distinguishes model packages from `lens.logic`; [SymStep](https://github.com/Zangir/SymStep/tree/8b7091c67b07d578878063bc3b0109365dc7341b) separates constraint engine and ledger; and [mathematical logic](https://github.com/hjbolus/Mathematical-Logic-Through-Python/blob/cc7fe8275545bec0236c007670f154b1ecf388c3/propositions/semantics.py) separates semantic interpretation from expression syntax. These are patterns, not wholesale copied implementations.

## Actual packages and ownership

| Package | Owns | Must not own |
| --- | --- | --- |
| `bilqis_mlx/semantics/` | Typed immutable expression nodes, functional composition, read-only catalog references and candidate law *declarations*. Future authoritative code-native identity ledger is added **here**, reconciling the existing `registry_ast` and original token/lesson IDs. | Oracle scoring, external-source parsing, optimizer policy, arbitrary ID minting outside catalog. |
| `bilqis_mlx/source_adapters/` | Read-only historical Token Atlas/registry bridge and finite-micro source AST translation into semantic expressions. | Semantic identity allocation, proof truth, lesson scheduling. |
| `bilqis_mlx/verification/` | Source and independent backend contracts, finite Boolean coverage, countermodels, typed statuses, verification receipts. | Semantic meaning allocation, grade-specific teaching policy, student weights. |

Future curriculum generation and learning diagnostics may get separate packages **only when actual implementations need those boundaries**. Do not create empty scaffolding, duplicate a canonical `registry_ast`, or retain permanent `composition` compatibility wrappers when every internal caller can migrate.

## Dependency direction

~~~text
semantics (pure, no source/trainer imports)
   ^               ^
   |               |
source_adapters   verification (symbolic/finite backends)
                    ^
                    |
           future curriculum planner / teacher-facing options
~~~

`verification` may import the immutable semantic AST and declared law *candidates*. `source_adapters` may import semantic types. `semantics` must import neither. Both independent verification and source translation are injectable into a future admission gate; neither may silently assign identity or admit source claims.

## Typed vocabulary and compatibility

- `LawCheckStatus` and any other new result-state enums live with the verification result they characterize. Producers, consumers and tests **import** these symbols; values such as `VERIFIED_FINITE_SCOPE` remain their existing serialized strings where historical compatibility requires it.
- A proposed law is a `LawCandidate`, **not** a `RegisteredLaw`. It is impossible to infer law admission from free-form strings or passing a finite test. Registration will require one canonical law identity/revision, checked source-claim references, preconditions, and a catalog release receipt.
- A finite law test returning `VERIFIED_FINITE_SCOPE` attests **only** its explicitly checked witness cohort. Empty applicable cohort is `UNKNOWN_NO_APPLICABLE_CASES`; an explicit contradictory example is `COUNTEREXAMPLE`. Neither source agreement nor finite coverage establishes universal validity.
- Shared wire/status constants are imported for identity; behavioral tests also assert literal expected Boolean truth values and concrete counterexample contents. Tests must fail for wrong behavior even when code and test import the same enum.
- New error-code families should use a typed definition where shared across modules; a single local exception explanation need not be promoted to a global enum.

## Migration and proof

1. Preserve the current source-only verification baseline and original ID/meaning checks.
2. Move the established algebra, adapter and proof code to domain owners without changing evaluation semantics. Migrate all in-repository imports and remove the obsolete package in the same wave.
3. Centralize result-state definitions and separate candidate law contracts from independently observed proof receipts.
4. Test existing Grade A/B source construction, Boolean truth vectors, type/world rejection, false-law counterexamples, vacuity and oracle disagreement. Check import boundaries mechanically to prevent regression.
5. Complete a second bounded unit before claiming **registered** law admission: source-attested law refs from the code-native catalog with independent falsifiers and release-bound proof receipts. Original lesson/222-token migration and new-grade generation remain distinct pending proofs.

**Preservation:** Seven preexisting dirty tracked Grade B files, untracked NI research, native student+AdamW, teacher, original release manifests and protected private issues are out of this refactor's mutation scope.
