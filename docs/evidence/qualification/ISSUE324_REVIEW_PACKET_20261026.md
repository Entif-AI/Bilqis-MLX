# Issue #324 frozen experiment review packet

**Disposition: QUALIFICATION_MANIFEST_FROZEN_AND_READY_FOR_HUMAN_INITIATION.**
**NO OFFICIAL V3 QUALIFICATION ARM HAS BEEN EXECUTED.** The original v2 baseline launch aborted before a completed visit and is preserved as superseded evidence. Bounded repair-validation epochs described below are not qualification evidence.

Canonical manifest digest: `7c84593af015bc38119b0ff75ed64bd322efced17a661dffe3324d5480a5c556`.
Exact executable head: `895a15321020c379d4bf4b12a55d55e45511a4a3`.
Preparation branch: `codex/324-learning-qualification-20261026`, stacked on the verified #333 head.
Executable checkout: `/Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-v3-20261026`. This detached checkout stays at the manifest head while review-only artifacts are committed on the preparation branch.

## Frozen inputs

Engineering dependencies are satisfied by exact-head evidence, independently of open/draft/unmerged lifecycle status:

- #150: `0a0d73a85d8b6214aaa446c04a510d05e904ae5c`.
- #320: `f09e44d35b5f544ef8d3e61ec127e326d0b09eb1`.
- #333: `35cf2b8ccb6c7d0e9f195d7e65e4ef990bfe5994`.

Final FactoryRelease: `05b5e7ad888c2de93153a0207a951fa594d71b1ceb0979d48a0f278338f981d5`.
Curriculum: `a44c9a293683cd2feddbb58b5279ebf9379489a0a6abb46ea4d597e3a0e599a2`.
Semantic graph: `db2297d41d7e50dd44321c323be760f7d66575e8c11b2f6b3d59a304b5a8afd6`.
Semantic catalog/ABI: `477ccbf6c7a9c0e978d94ff88329bccd6b51da46c788782976aefb6fe2021d38`.
Policy/control identity: `733453ffcadebf641a9a789754919c9e82cb11c7c544a8eb6452f4005dc78775`.

The original bounded workload is unchanged. Native source observation generation 44238 had already reached numeric inputs **0..8** before freezing. Its future ceiling 10 is excluded. Earlier notes reporting 0..7 are older observations, not the frozen scope. The same ABI and numeric ceiling apply in every arm; no SKOS or Grade D enters the learner.

V3 intentionally reuses that already-sealed generation-44238 workload, release chain, policy, seeds, fixtures and budgets. The live source run has advanced since the original freeze; refreezing from its current state would change the experiment. V3 therefore changes only the repaired executable identity and fresh run paths.

- A (6): `A.IDENTITY`, `A.PARENT`, `A.LINK`, `A.MEMBER`, `A.EDGE`, `A.MAPS`.
- B (8): `B.NOT`, `B.AND`, `B.OR`, `B.XOR`, `B.IMPLIES`, `B.IFF`, `B.COMPOSITE`, `B.IDBOOLOPS`.
- C (7): `C.COUNT`, `C.NUMBER`, `C.SUCCESSOR`, `C.ADD`, `C.SUB`, `C.MUL`, `C.DIV`.

The prequalified same-ABI release chain activates A, then A+B, then A+B+C through existing admission/promotion/debt gates. Initial assessments cover A only. Staged C introductions retain the existing prerequisite frontier. The current promotion floor is 9/10: acquisition begins strictly above 90%; post-acquisition sweeps require at least 90% mean C capability accuracy. This does not redefine 100% graduation or erase earlier-grade debt.

Both arms start from fresh seeded FP32 weights and zero native AdamW moments. Initialization seed is 324; training seed namespace is 3240. Historical teacher policy/statistics are pinned and inherited identically. The historical student weights and moments, and current live student, are not imported. Initial carried mastery debt is empty because these are fresh learners; observed live debt is retained only as source context in the manifest.

| Arm | Layers | Heads | Width | FFN | Context | Parameters |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| baseline | 6 | 24 | 384 | 1536 | 96 | 10745856 |
| capacity | 8 | 32 | 512 | 2048 | 96 | 25339904 |

The capacity arm has about 2.36 times the parameters while preserving context length and attention-head width. It is one predeclared contrast, not an architecture search. Both arms use the same initializer distribution, source draws/seed rule, teacher and scheduling policy, retention gates, evaluation and AdamW controls. Optimizer: learning rate 0.00013 before teacher selection, betas (0.9,0.95), epsilon 1e-8, weight decay 0.01. The existing teacher still chooses visit learning rates and candidate strategy. No new selector, reward, retry suppression or early stopping is installed.

## Resource and evaluation bounds

- Per arm: 1,000 completed visits maximum, 16 configured candidate steps maximum per visit, at most 16,000 attempted optimizer updates, batch size 32.
- Per arm: 90-minute session limit at existing safe boundaries. Due exams and final checkpoint finish; this is not a hard process deadline. Other existing resource/stagnation/completion stops remain possible.
- Disk reserve stays 100 GiB. The existing 600,000,000-byte checkpoint estimate exceeds the raw parameter-plus-two-moment arrays (128,950,272 bytes baseline; 304,078,848 bytes capacity). These are tensor-size calculations, not measured peak RAM/disk usage.
- One frozen acquisition seed 32401, followed by independent post-acquisition seeds 32403,32405,32407 on one intact retained checkpoint. The target workload must be fully introduced before it is examined.
- Each full source-oracled fixture has 399 items (A72+B96+C231). Fresh source construction uses at most eight rounds per capability per post seed; total qualification inference is capped by the frozen 2,793-row ceiling.
- Exact delivered training inputs/labels are excluded from fresh probe subsets. Seed-only row ID changes do not establish freshness. Every post sweep needs fresh target witnesses; finite/exhausted per-capability fresh scopes remain NOT_MEASURED. Full mean-C proficiency remains the qualification criterion; fresh scores/overlap/debt/regression are separately visible.
- A resource-exhausted or interrupted arm is not silently extended. There is no automatic experimental resume/budget refund. Preserve its checkpoints and obtain a new explicit epoch decision before any continuation.

## Exact operator commands

First inspect either arm without neural authority:

```sh
cd /Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-v3-20261026
python3 -B -m bilqis_mlx.runtime.qualification --manifest /Users/emilie/Code/.worktrees/bilqis-mlx/324-learning-qualification-20261026/docs/evidence/qualification/issue324-20261026-v3.json --arm baseline --expected-digest 7c84593af015bc38119b0ff75ed64bd322efced17a661dffe3324d5480a5c556 --dry-run
python3 -B -m bilqis_mlx.runtime.qualification --manifest /Users/emilie/Code/.worktrees/bilqis-mlx/324-learning-qualification-20261026/docs/evidence/qualification/issue324-20261026-v3.json --arm capacity --expected-digest 7c84593af015bc38119b0ff75ed64bd322efced17a661dffe3324d5480a5c556 --dry-run
```

After explicit human review/authorization, run the arms sequentially with these proposed commands:

```sh
cd /Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-v3-20261026
python3 -B -m bilqis_mlx.runtime.qualification --manifest /Users/emilie/Code/.worktrees/bilqis-mlx/324-learning-qualification-20261026/docs/evidence/qualification/issue324-20261026-v3.json --arm baseline --expected-digest 7c84593af015bc38119b0ff75ed64bd322efced17a661dffe3324d5480a5c556 --human-run
python3 -B -m bilqis_mlx.runtime.qualification --manifest /Users/emilie/Code/.worktrees/bilqis-mlx/324-learning-qualification-20261026/docs/evidence/qualification/issue324-20261026-v3.json --arm capacity --expected-digest 7c84593af015bc38119b0ff75ed64bd322efced17a661dffe3324d5480a5c556 --human-run
```

Only the last two commands can update fresh official experiment students and their own AdamW, teacher/run receipts, candidate/champion records and checkpoints. They write under `/Users/emilie/Code/.worktrees/bilqis-mlx/324-frozen-execution-v3-20261026/runs/qualification-324-baseline` and `.../qualification-324-capacity`. They do not target the continuing canonical student. Neither official v3 command has been run.

## Verified preparation evidence

- Both v3 arm dry-runs pass at exact head `895a1532…`, with `neural_authority=false`, `actual_optimizer_updates=0`, and neither official v3 run directory created.
- Seven CLI mutation cases (head, topology, curriculum, numeric scope, policy, budget, manifest seal) fail closed with zero updates. Unit tests also reseal mutations to exercise internal identity checks.
- Qualification unit suite: 15 tests pass, including the staged-release terminal-evaluation regression. The focused v2 semantic-authority diagnostics regression also passes.
- A final one-visit, five-minute disposable qualification-path validation at the v3 production bytes completed end to end with exit 0. Its expected result is `NOT_QUALIFIED / FULL_WORKLOAD_NOT_YET_INTRODUCED`; it proves launch, visit, observation publication, checkpoint stop and terminal evaluation survive the repaired seams. It is not an official arm and cannot satisfy #324 learning criteria.
- Factory architecture/closure, source/ABI, release/docs/errors and hygiene/size guards pass. Independent external ABI enforcement remains advisory/unconfigured locally.
- PM-2026-10-26-007 / RC-135 / PAT-096 records the repaired portable mock-import issue and was read back in the native ledger.
- Manual launch exposed two post-preparation defects. First, lesson diagnostics received scheduler-only `ScheduleCapability` authority after Factory-v2 cutover; `1edba645…` routes diagnostics through the admitted semantic curriculum and adds a v2-authority regression. Second, early terminal evaluation restored staged Grade-A state against the final A+B+C schedule; `b4e535c5…` restores against the currently admitted release, and `6c815d4f…` locks that behavior with a focused regression. Final executable `895a1532…` removes the one new opaque diagnostic error identity caught by `quality:check`; the full quality gate then passes with zero new baseline-relative findings.
- The aborted v2 baseline directory is preserved in the superseded v2 execution checkout and MUST NOT be resumed or counted. V3 uses fresh run identities. V1/v2 are historical evidence; v3 is the single active manifest.

## Remaining #324 acceptance

- [x] Exact-head engineering prerequisites, implementation/component provenance, immutable manifest and checksums.
- [x] Frozen A/B/C workload, integer scope, same policy, two typed topology arms, controlled initialization/training seeds.
- [x] Frozen fixtures, fresh-probe protocol, post-acquisition sweep seeds and finite budgets.
- [x] Fresh-run/preflight guard, observation wiring, source/identity mismatch failures and zero-update proof.
- [ ] Human-authorized baseline acquisition/retention run.
- [ ] Human-authorized capacity-arm run on the same frozen workload.
- [ ] Actual post-acquisition proficiency/retention and three seeded sweeps with per-capability/fresh-probe results.
- [ ] Actual checkpoint/recovery, candidate/debt/scheduling/resource evidence and causal comparison.
- [ ] Final QUALIFIED or NOT_QUALIFIED receipt. Learning and cross-topology benefit remain NOT_MEASURED.

One seed pair and one capacity contrast can expose sensitivity but cannot establish a population-level causal law. If both arms fail similarly, preserve competing policy/runtime/capacity/interference hypotheses. Missingness and source-gold remain explicit. IPR-0220 is OPEN. PR #291/SKOS has since merged independently to main, but no SKOS semantics enter this frozen experiment. No official v3 arm, Factory merge, Grade D, semantic cutover or historical resume/migration has been performed.
