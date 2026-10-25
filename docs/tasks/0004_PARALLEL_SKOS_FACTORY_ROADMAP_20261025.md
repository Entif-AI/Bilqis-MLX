# Bilqis: parallel semantic-corpus and curriculum-factory roadmap

**Baseline:** 2026-10-25, approximately 00:02 America/New_York. **Posture:** execution planning, not a new semantic or release authority. **Destination:** a source-grounded New Ithkuil candidate can become a verified, prerequisite-safe factory release and a reusable learning opportunity, without changing generic runtime code or the continuing student's neural lineage. **Owner model:** one device/executor per track, one integration owner later.

## Decision and current position

Keep the two current branches separate until each has produced its own complete, reproducible artifact and the integration owner can verify a narrow interface. Do not merge either branch into the other merely to make progress. No current task in the factory's remaining leaf corridor requires the SKOS branch; the SKOS compiler's completion does not require a factory runtime. A planning document must not redirect a working leaf executor away from its own page-local issue gate.

| Lane | Working branch | Verified baseline | What exists | Work still open |
| --- | --- | --- | --- | --- |
| **F: executable school** | `codex/150-factory-microspecs-20261023` | `796ef0a6de01975504af59dc9a9e47f093cbb6c7` (72 commits ahead of `main`) | 55 of 77 SPEC-0006..0082 leaves have `FACTORY_LEAF_DONE` receipts. V2 capacity up to 12, release-bound semantic graph, generic schedule/topology, runtime source context, prepared-successor custody. SPEC-0057, 0058, 0059 completed. | 22 leaves, beginning SPEC-0060 / issue #224. Closure and CI are not yet green. |
| **S: source semantics** | `codex/skos-31-43-pro-20261024` | `8b14e4d727a92c890dcec8228880fc5757e2ae06` (82 commits ahead of `main`) | Standards-first RDF/SKOS identity, canonical graph and provenance, explicit holds, atomic morphology, root/sense, affix-degree, composition/allomorph and conformance slices. | Remaining #19 issue-family source extraction, aggregate/build conformance, graph publication/materialization, operational proof and closeout. |
| **I: integration** | **Not yet started** | None | The distinct responsibilities and governing issue families exist. | One audited translation/admission adapter, executable proof, then staged merge. |

The common `main` baseline in the earlier review was `6a9c7c63c9c21fe513475f3ddd5872f91fb479bc`. The two branches had **zero changed file paths in common** in that review. This reduces text-merge risk, but does not establish behavioral compatibility. Recompute this comparison before merging. Numbers above are a snapshot; issues and commits may continue moving while this document is read.

## Lane F: finish the declarative factory without SKOS dependencies

**Executor:** factory device, using its existing worktree and the live `FACTORY_PAGE_GATE_V1` / `FACTORY_EXECUTION_CONTRACT_V2` on each issue. **Authority:** [#150](https://github.com/Entif-AI/Bilqis-MLX/issues/150), SPEC-0001, local leaf specs, later same-page amendments. The issue page, not this roadmap, decides the next legal mutation.

### F1. Finish materialization and admission custody

Start from the current page bookmark [#224 / SPEC-0060](https://github.com/Entif-AI/Bilqis-MLX/issues/224). Recheck its direct prerequisites through the live issue gate, then continue in page order. SPEC-0058 and 0059 were already completed at `5ccc673` and `796ef0a`, respectively. Prove the common prepared-admission tail for same-ABI and append-only successor materialization, then preserve predecessor, release, checkpoint and optimizer identity across cold readback and failed proposals. Never assume that a change in grade schedule implies a token-ABI expansion.

### F2. Close source, instructional and retention custody

Remaining work includes the runtime semantic-footprint callback and provider-specific proof (#225, #227, #228), removal of generic provider verification (#229), source-owned Boolean dependencies (#230), sealed and live instructional-constituent closure (#231–232), fragile retention and replay policy (#233–237), and the compatibility/presentation boundary (#238–239). The invariant is stronger than `the lesson has a source-valid answer`: every student-visible semantic constituent must be the target being introduced or an allowed, demonstrated prerequisite. Checks must cover **actual stochastic draws, enrichment and prefetch**, not only release-sealing samples. Do not use token visibility, source text, or an AST representation as evidence of student mastery.

### F3. Prove generality and retire the second architecture

Run the scheduled [#240 / SPEC-0076](https://github.com/Entif-AI/Bilqis-MLX/issues/240) direct-v2 twelve-capability Grade-Z proof, [#241–#243](https://github.com/Entif-AI/Bilqis-MLX/issues/241) same-ABI, same-grade append and append-grade recovery proofs, and [#244 / SPEC-0080](https://github.com/Entif-AI/Bilqis-MLX/issues/244) synthetic **C→H** chain. That final chain must use arbitrary grade identities and one stable ABI for its specified run, preserve evidence/lineage, and make zero neural updates. Then retire the current legacy transition path (#245) and satisfy [#246 / SPEC-0082](https://github.com/Entif-AI/Bilqis-MLX/issues/246) with `FACTORY_CLOSURE_OK`, no suppressed architectural debt, historical decode preserved, and the declared tests green.

**F exit artifact:** an exact commit/SHA plus reproducible commands proving a new unfamiliar grade can be compiled, verified, admitted synthetically, scheduled, assessed, cold-reloaded and superseded using the common factory without grade-specific production code. This does **not** claim Grade D is pedagogically admissible or that the continuing student has learned anything new.

**Known F gate:** on the last checked factory head, the semantic-ABI CI job passed while portable CI failed on the deliberately exposed factory architecture guard, including remaining `legacy_course` uses, compatibility writer calls and generic grade/provider dispatch. These violations belong to the remaining cutover and closeout work, not to an SKOS dependency. Preserve fail-closed checks; remove the causes rather than introducing a baseline exception.

## Lane S: finish source-to-graph closure independently

**Executor:** SKOS device, retaining its current branch/worktree and issue-by-issue guards. **Authority:** [#19](https://github.com/Entif-AI/Bilqis-MLX/issues/19), child families #20–#30, their own issue contracts and the source evidence. No factory imports or runtime writes belong in this lane.

### S1. Finish the core projection and honest accounting

Complete the already-admitted leaf sequence under #22–#25, then reconcile all domain emitters in **one canonical build**. This includes atomic morphology, composition/component edges, allomorphs, lexicon roots/senses, affix degrees, and source-qualified Bilqis mappings. In particular, do not mistake independent domain test success for whole-build composition. The domain emitters and original `build.py` entrypoint need a unified orchestration and coherent hold/admission accounting owned by the appropriate existing build/conformance issue. Maintain stable source identity, explicit held/debt rows, exact source locations, lexical distinctions and canonical RDF semantics. Never auto-admit a mapped Bilqis capability from SKOS alone.

### S2. Close the source extraction frontier with useful order

Prioritize [#83](https://github.com/Entif-AI/Bilqis-MLX/issues/83) (lexicon Chapter 6) because [#137 / COGAL-07](https://github.com/Entif-AI/Bilqis-MLX/issues/137) explicitly depends on its **zero, one, numerical labeling and ordinal** source senses for Grade D. Continue [#80–#84](https://github.com/Entif-AI/Bilqis-MLX/issues/80) lexicon Chapters 3–7 and [#85](https://github.com/Entif-AI/Bilqis-MLX/issues/85) affix-reference parsing as their own bounded, independent extraction leaves. Chapters are **coverage tasks**, not an invented teaching order. [#86](https://github.com/Entif-AI/Bilqis-MLX/issues/86) produces a generated source-frontier receipt with chapter-by-chapter parsed/debt status. A bounded Chapter 6 slice can unblock source research for D before the entire lexicon is parsed; do not call the whole New Ithkuil frontier complete prematurely.

### S3. Prove deterministic conformance and materialize the graph

Finish #26 conformance: source-derived coverage [#68](https://github.com/Entif-AI/Bilqis-MLX/issues/68), no omissions #69, exact rebuild equivalence #70, lexical/shape conformance and aggregate #72. Keep the versioned #41 canonical graph digest local to RDF build equivalence and materialization receipts. Then complete the #27 Falkor/Akasha graph import and read-only query proof, preserving derived-state status, source-to-node identity and rebuild idempotence. Source/RDF truth stays upstream of the graph database. Follow with #29–#30 operational release work, especially [#93](https://github.com/Entif-AI/Bilqis-MLX/issues/93) clean-room source→IR→RDF rebuild and the final indexed issue gates. Existing [#275](https://github.com/Entif-AI/Bilqis-MLX/issues/275) is a **nonblocking** extra symmetric-blank-node regression fixture, not a reason to reopen #41 or add a new RDF standard.

**S exit artifact:** independently rebuilt pinned sources, IR, canonical RDF digest and generated hold/coverage/frontier receipts, plus a derived Akasha graph whose query results can be traced back to those source artifacts. Its inputs and outputs are documented with exact schema/version/SHA. No runtime token allocations and no human student mutations.

## The integration seam: preserve two distinct semantic authorities

| Upstream source-side fact | Downstream executable-side fact | Required handshake |
| --- | --- | --- |
| SKOS concept/sense IRI, source scope/locus and interpretation status | Code-resident semantic catalog + immutable token/ABI identity | Explicit **reviewed mapping**; never equate IDs merely because labels match. Held or ambiguous source cannot become training gold. |
| Canonical RDF bytes and `#41` graph digest | `ExecutableFactoryRelease.semantic_graph_sha256` over the factory's own token/answer graph | **Two named artifact digests**, different algorithms/domains. Bind provenance in a bridge receipt; do not substitute one digest for the other. |
| Source-defined relations, morphology and composition | Typed operands/results, legal construction, source adapter and independent answer oracle | One deterministic adapter/projection with positive and negative cases; no runtime import of the RDF compiler. |
| Source/IR coverage and outstanding debt | Capability construction prerequisites + actual student mastery/debt evidence | Distinguish **source-qualified** from **pedagogically eligible** from **factory-admitted** from **learned**. |
| Derived Akasha query results | Runtime release verification and instructional execution | Akasha may help **discover** candidates. Deterministic code-resident/release-bound facts control execution; network graph state may never be training authority. |

**Interface contract to freeze before integration:** one small versioned, deterministic and reviewable candidate-projection packet carrying source IRI, source digest/locus, admitted/held disposition, exact target semantic identity proposal, mapping rule/evidence, prerequisite proposal, adapter/oracle contract, and both independent graph identities where applicable. Use existing crosswalk, ABI/AST, source adapter and release interfaces before creating new abstractions. The proposal is non-executable until ordinary factory verification and runtime admission succeed. A new agent-facing API requires a separate AXI evaluation under project governance.

## Cross-track sequence and device allocation

| Wave | Device F: factory | Device S: SKOS/source graph | Integration owner / shared action | Exit condition |
| --- | --- | --- | --- | --- |
| **0, now** | Continue #224 and page-local remaining leaves | Continue active #19 leaf, particularly unified compilation and conformance | **None.** Keep worktrees and branches isolated | Each executor can continue without reading or modifying the other's branch |
| **1** | #225–#239 custody, instructional closure, retention | #80–#86 extraction frontier; #68–#72 domain receipts/build conformance | Read-only review of **interface shapes only** when useful | Source inventory and generic runtime contracts converge independently |
| **2** | #240–#246 synthetic proof, legacy retirement, closure | #27 Falkor/Akasha and #29–#30 clean build/operational proof | Draft bridge contract against **frozen SHA snapshots**, outside both active branches | F has `FACTORY_CLOSURE_OK`; S has reproducible canonical RDF and source/hold receipts |
| **3, first intersection** | Consume immutable artifact; do not reopen generic runtime | Supply immutable source artifact; do not add trainer logic | In **third integration worktree**, implement and test one source→candidate→factory release proof | A bounded D1 or D2 candidate survives the entire source, mapping, oracle, release and synthetic admission path |
| **4, controlled promotion** | Continue factory maintenance without grade-specific forks | Extend source coverage without changing admitted identities silently | Reverse-integrate both branches to a fresh main-based staging branch, run broad non-neural checks, then choose trunk promotion | Clean staged merge with structural guards, historical ABI, conformance and whole-system proof passing |
| **5, first learning** | Factory owns released teaching and measurement | SKOS/Akasha remains source/read-only supplier | Human admits the warranted D stage and starts any actual neural run. Compare fresh assessments and retention without replacing lineage | Evidence of source-grounded acquisition; debt/limits preserved |

Waves describe **dependencies**, not mandatory timeboxes. The two independent devices may work ahead within their own lanes; neither must wait for the other until wave 3. A single small read-only cross-lane planning check is allowed before then, but it must never quietly modify either implementation branch.

### First vertical slice

Use [#137](https://github.com/Entif-AI/Bilqis-MLX/issues/137) as the educational contract. D1 finite set/group is the smallest initial construction from `A.IDENTITY` and `A.MEMBER`. D2 empty set is the next useful source-qualified New Ithkuil demonstration after Chapter 6's ZERO/-VR- sense is verified. Do **not** assume A capabilities are mastered because their tokens have appeared or that B Boolean perfection is required; admitted Grade B debt remains non-gating unless a candidate truly uses that Boolean meaning. Each candidate must show:

1. source-backed **one new semantic distinction** and its IRI/locus;
2. the exact demonstrated prior constituents or earlier same-grade stages;
3. positive specimen and close semantic contrast, neither requiring untaught machinery;
4. deterministic generator, independent oracle and negative/fail-closed case;
5. compiled immutable release, predecessor/custody check, synthetic admission and cold readback;
6. no grade-specific runtime modifications and **zero optimizer updates** in pre-admission testing.

Then, and only with the human-run gate and actual student evidence, measure whether the real learner acquires the distinction. D/E semantic rosters are existing design targets, not automatic factory admissions. F remains a direction to close before its eventual learning boundary.

## Stop, merge and recovery rules

**Do not:** mutate shared `main` from either worker; cherry-pick an unfinished domain into the other's working branch; touch the human's live checkpoint, AdamW or optimizer; change source identity to satisfy a test; invent a separate grade-specific runtime; convert a SKOS source relation directly into a mastery prerequisite; suppress architecture/CI violations; or widen a leaf merely because this roadmap identifies a later integration need.

**Before any integration cherry-pick or merge:** refresh remote heads, inspect both working trees for unrelated edits, compare touched paths again, pin the two parent SHAs, classify source/publication authority, resolve the intended merge ancestry, and preserve a rollback ref. Tests must prove both positive behavior and fail-closed rejection. Use a dedicated third branch to handle interface translation and any real conflict. Keep the existing two executors on their own branches until their completion receipts are independently verified.

**Merge gate F:** SPEC-0082 terminal proof and applicable portable CI green without guard waivers. **Merge gate S:** source-frontier and RDF coverage receipts truthful, canonical build reproducible, and graph materialization/query conformance supported by tests. **Bridge gate:** the new source evidence, mapping, admitted ABI, factory release, independent oracle and instruction closure all agree on the **same specific candidate**, with a negative held/untaught case rejected. **Human learning gate:** operator approval and a live baseline, not a successful synthetic proof.

If a dependency is blocked, leave an issue-local receipt and continue the independent lane. If implementation needs a new decision, return that decision to its existing issue owner; do not let the other lane inherit the problem by accident. Track the active issue number, branch, head SHA, failing gate and next legal action in each executor's own handoff. Documentation may be revised independently on this planning branch; it must not become a competing source of architectural truth.

## References and operating bookmarks

**Factory:** [#150](https://github.com/Entif-AI/Bilqis-MLX/issues/150) · [#224 / SPEC-0060](https://github.com/Entif-AI/Bilqis-MLX/issues/224) · [#246 terminal](https://github.com/Entif-AI/Bilqis-MLX/issues/246) · `docs/specifications/0001_GENERATIVE_CURRICULUM_FACTORY.md` · `docs/tasks/0003_FACTORY_CLOSURE_WORKSTACK.json` · `docs/tasks/0003_FACTORY_CLOSURE_CODEX_RUN_PROTOCOL.md` · `docs/architecture/11_FACTORY_TICKET_NAVIGATION_20261023.md`.

**SKOS:** [#19](https://github.com/Entif-AI/Bilqis-MLX/issues/19) · [#68 receipt](https://github.com/Entif-AI/Bilqis-MLX/issues/68) · [#70 equivalence](https://github.com/Entif-AI/Bilqis-MLX/issues/70) · [#83 Chapter 6](https://github.com/Entif-AI/Bilqis-MLX/issues/83) · [#86 frontier receipt](https://github.com/Entif-AI/Bilqis-MLX/issues/86) · [#93 clean rebuild](https://github.com/Entif-AI/Bilqis-MLX/issues/93) · `lib/ithkuil/SKOS_PROFILE.md` · `lib/ithkuil/SKOS_COMPILER.md`.

**Learning destination:** [#137 COGAL-07](https://github.com/Entif-AI/Bilqis-MLX/issues/137), source-grounded staged D/E and future F. This roadmap does not supersede its curriculum decisions.
