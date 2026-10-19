# Evergreen contracts: mechanical qualification and remaining gates

**Priority update (ADR-041):** This is a record of optional qualification machinery. Its remaining research gates and generic-cutover work are deferred for exploratory trials. Start with the small learning experiment in `HANDOFF.md`; use only checks needed for correct answers and recoverable state. ADR-042 subsequently integrates C’s native catalog and replaces the external-review prerequisite with existing source/custody checks; see the current README and HANDOFF for the human pilot.

Protected [issue #336](https://github.com/socr8s/private-ip/issues/336) remains **OPEN** under IPR-0220. The receiving agent qualified and repaired the drafts at source **`f14b90dc82153555b4d9d365f21580667368db0e`**, following untested scaffold `b88b2fe` and handoff `b941f2e`. The earlier no-tests instruction applied to that authoring turn; the receiving handoff explicitly authorized this test/analysis pass. Full M3 result: **466 passed, 2 skipped (468 total)**; hosted source CI **39044710480** passed at the same source. The [machine receipt](../../evidence/development/EVERGREEN_CONTRACT_QUALIFICATION_20261017.json) binds exact files, preflight and unchanged custody. No new source, grade, policy or real neural execution is approved.

Qualification repaired nested immutable-mapping serialization, malformed input boundaries, complete input/intermediate/output scope checks, native identity/catalog matching, template fingerprints and observed transformation nondeterminism. `verification.curriculum.inspect_construction_contracts` is the opt-in mechanical consumer; it preserves the existing Boolean gate and always retains independent source/family/mastery qualification gaps. Additional checker modules are bound by `VERIFIER_FILES`. Temporary native model tests exercise existing custody/outbox owners; the generic runtime cutover executor remains missing.

## What is present

| Owner | Draft behavior | Deliberately unfinished |
| --- | --- | --- |
| `semantics/domains.py` | Source locator plus exact content hash; immutable finite literal domains; explicit literal/decimal-text codecs; binary, finite and native-token answer declarations; declaration digest | Authentic source completeness; independent adapter qualification; actual native Registry/catalog reconciliation |
| `curriculum_contracts.py` | Explicit leaf-path domain bindings over existing templates; all eight construction-family dispositions; counts, budget and family/source-review debt | Opt-in consumer inspection exists; independent family debt discharge and wider admitted outputs remain missing |
| `verification/construction_contracts.py` | Output-domain witness checks using existing Catalog and constituent proofs; pinned obligation/cohort transformation receipts using existing finite-law checker | Independent source approval, executable-law attestation, non-equivalence and invalid-case oracles |
| `grade_release_plan.py` | Pure disposable cutover intent/observation/action plan; parent generation and bundle drift checks; crash/retry and event-replay obligations | Generic executor and authenticated intent/readback integration; existing native bundle/outbox crash primitives tested only on toys |
| `selection_outcomes.py` | Comparable post-replay trials; per-capability Pareto frontier with optimizer-step/attention costs; explicit missing metrics and negative observations | Authentic independent outcome attestations, causal transfer evidence and integration into the existing selection dossier |

These are internal source-only library contracts (`NOT_AGENT_FACING`), with no new CLI, Registry, solver, trainer or journal. The existing candidate verifier imports the opt-in contract consumer; ordinary admission still uses its original Boolean checks. Synthetic fixture sources are not production evidence. All five modules were imported and tested in this receiving pass; the original b88b2fe authoring checkpoint remained explicitly untested.

## Domain and answer contract

The canonical `Literal` remains `str | bool`. A Number's existing wire representation is decimal **text**, as in `semantics.numeric.number`; Python integer computation is a separate adapter concern. `FiniteDomain.encode` explicitly converts a native integer to canonical decimal text, excludes Boolean-as-integer aliasing, and enforces membership in the declared finite domain. `decode` reverses that conversion only for declared members. No core ABI or historical identity changed.

A source hash and a `closed=True` declaration are not semantic approval. An independently pinned source package must justify that the declared values exhaust the relevant scope. Boolean closed domains must contain both values. Other finite domains still require independent completeness review; narrowing them cannot silently erase source-required coverage.

Native-token mappings declare bijections among domain literals, indices and explicit stable catalog identities. Witness inspection requires the actual supplied SemanticCatalog fingerprint and checks each token index, identity, literal signature and arity. These mechanical checks allocate nothing and do not establish authenticity or approve the literal-to-identity meaning. Before admission, reconcile the release with the authentic native Registry and its append-only receipt; derive current vocabulary size from that graph. Historical prefix compatibility stays with the existing ABI owner. Multi-token answers remain unsupported.

The current candidate compiler/readiness path remains Boolean-only. New `finite_typed`/`native_token` dispositions are proposals; they must not be added to real grade dossiers or used to bypass the current rejection of unsupported answers before independent qualification.

## Construction-family obligations

Every proposed capability considers DIRECT, COMPOSITION, DECOMPOSITION, RECONSTRUCTION, CONTRAST, INVERSE, NEGATIVE and INVALID. REQUIRED and NOT_APPLICABLE carry source bindings and a rationale; UNREVIEWED and missing dispositions remain debt. REQUIRED also remains debt until independently checked witnesses are supplied. A family list or an empty debt list is not approval; the plan always remains unqualified.

Leaf paths are tuples of argument positions in the existing `TypedExpressionTemplate`. The planner requires exact path, type, world and ordered literal-domain equality and records finite-product size before any sampling. Budget overflow is debt, not silent truncation. This does not prove source-complete semantic coverage, lawful transformations or previously demonstrated student prerequisite mastery.

`verify_domain_witness` checks the supplied expected full construction-contract digest, Catalog bindings, all declared input/intermediate/final domains and independent constituent/whole proofs. A matching expected digest establishes integrity; independent source approval remains separate. Existing backends must return canonical wire values. In particular, the existing research numeric evaluator's raw integer result must pass through a separately reviewed adapter before it becomes a `Proof.result`; do not broaden the shared Proof schema silently. Input and intermediate paths must match exactly and their declared domains must be closed. Authentic native meaning/completeness qualification still precedes any live integration.

`verify_transformation_family` currently supports only declared reconstruction/inverse **equivalence** candidates. It reuses `LawCandidate`, `Catalog` and `check_finite_equivalence`; it records the complete input cohort, checks each applicable precondition/transform twice for observed determinism, and supplies the captured rewrites to the existing checker. This finite repeat check does not prove callback purity or source legitimacy. COUNTEREXAMPLE and UNKNOWN remain outcomes. The existing checker requires Apply-to-Apply rewrites; inverse laws ending in a Literal are not implemented. A valid rewrite callback is not a source-attested law. The receipt must eventually bind the executing transformation implementation and independently reviewed source bytes, not merely matching locators.

Contrast and negative examples are not equivalence. INVALID needs independently source-defined rejection categories. Do not infer invalidity merely because both implementations throw an exception. Decomposition/reconstruction needs constituent teaching and assessment receipts in the appropriate earlier grade/stage; subexpression proof does not establish student mastery.

## Disposable cutover contract

`CutoverIntent` binds the current generation, parent complete bundle, parent/successor releases, package/review/source receipts, successor course and catalog. Complete bundle identity keeps model **and own AdamW together**, with optimizer step and current vocabulary size. Same-size vocabulary is permitted when a new grade uses existing tokens; growth must be append-only when actually required.

The proposed order is:

1. Recheck independent source/admission, cumulative prior mastery, exact parent and source receipts through existing owners.
2. Verify append-only catalog and preserve all historical identities; check the actual 100 GiB reserve plus next complete checkpoint estimate through existing disk policy.
3. Allocate a **disposable** copied model and own AdamW through `vocabulary_growth` only when needed. Preserve all prior parameter rows, moments, teacher history and protected champion/soup pointers. No optimizer update.
4. Stage a new complete bundle with existing `mlx_checkpoint`; read it back independently and verify exact bytes, semantic binding, FP32 tensors, moments, optimizer step and old-row invariance.
5. Commit one generation using the existing school state's immutable outbox protocol and an actual writer/generation fence. An exception before pointer publication leaves the parent authoritative and a recoverable staged candidate.
6. Replay committed events by ID/payload after crash; never repeat allocation/optimization merely because event publication was interrupted.

The planner performs none of these effects. Its readback fingerprint is only a declared reference, not proof that bytes were read. The executor must authenticate and bind that receipt to the intent and staged bundle. Even the observed-commit branch describes event-readback work; it cannot authorize admission, real resumption or writes to the human run. Do not add a second transaction journal or model format.

## Outcome-guided selection contract

`SelectionTrial` retains matched before/after per-capability correctness, common parent complete bundle, protocol/source scope, exact assessment, final checkpoint, optimizer cost and measured human attention. Trials are comparable only after cumulative replay and on identical prior capability/cohort baselines. A missing attention observation is NOT_MEASURED, not zero. Temporary acquisition-stage forgetting is not a rejection criterion.

The frontier requires no arbitrary scalar weights: one option dominates another only when it is no worse on every measured capability and both costs, and strictly better on at least one dimension. Ties and tradeoffs remain on the frontier. Neither a frontier nor declared outcome hashes select Grade D. Candidate-specific novel learning objectives and transfer cohorts need independent qualification; the first slice deliberately compares only a common assessment substrate. Authentic independent outcome attestations and causal controls remain required.

## Qualification matrix and remaining work

The receiving pass added 26 tests across four contract test modules and exercised this matrix. Exact mechanical proof and source admission remain distinct:

- Reject duplicate literals, mismatched type/world, noncanonical decimal text, integer/Boolean aliasing, partial closed Boolean domains, absent source hashes and native mapping collisions; round-trip existing Number wire values without changing `core.py`.
- Hash equivalent nested dataclass/mapping contracts deterministically; mutate a source byte/revision/domain/answer mapping and require a changed digest. Do not trust a dossier's own expected hash.
- Add a synthetic unknown capability with earlier-stage constituents, bind exact leaf paths, and expose every missing family or source witness. Reject duplicate/missing/extra leaf paths and reordered or narrowed domains. Confirm the old Boolean generator/checker behavior remains unchanged.
- Reject wrong output-domain gold, raw numeric backend values, unbound catalog operators, forged expected pins, source/independent disagreement and cross-world transformations. Preserve COUNTEREXAMPLE/UNKNOWN and the full applied cohort; test stateful/nondeterministic rewrite callbacks and source-implementation drift before reliance.
- Exercise every cutover crash window, parent/generation drift, other pending intent, same-size/new vocabulary, forged readback, staged orphan, duplicate replay and own-AdamW byte preservation on temporary complete bundles only. Missing executor/readback authority must never become READY.
- Compare tied, dominated and trading-off trials, negative transfer, changed parent/cohort/protocol/source scope, absent attention and incomplete replay. Verify no selected grade or teacher reward is produced.

The opt-in contract consumer and extended checker-byte inventory are now implemented, and focused/full M3 qualification passed. The two skipped tests require human JSON relative to this isolated worktree; an explicit actual-run preflight separately verified 216 historical records and retained both C blockers. Generic executor crash/retry qualification remains incomplete: the new tests compose existing native bundle/generation/outbox primitives, rather than implementing admission. Source-complete domains, authenticated transformations/readbacks, family-debt discharge and causal outcome/transfer attestation remain required. Neither source mechanics nor toy-model success authorizes actual neural training. C's authentic Registry/review and all empirical learning gates remain open.
