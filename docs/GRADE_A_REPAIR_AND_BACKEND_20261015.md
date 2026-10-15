# Grade A repairs and real-student MLX continuation evidence

**2026-10-15 | Private Bilqis MLX feature branch | Human training remains disabled**

## What was wrong and what changed

The first six-capability Grade A proposal generated 24 instructional and 12 assessment examples per capability. The first audit showed three defects that could invalidate the meaning of a perfect score:

1. `A.MEMBER` was answer-leaky: every TRUE record had a two-element set and every FALSE record had a one-element set. The v2 generator now uses equally sized `[a,c]` and `[b,c]` sets, so set cardinality never reveals membership. Tests inspect the actual generated source records across both partitions.
2. The previous “two independent oracles” assertion overstated independence for entity equality and directed edges. The old EQ and EDGE implementations delegated to identical elementary tests. The v2 `grade_a_oracle.py` re-evaluates all six predicates directly from source-record ASTs with a separately authored implementation. Every proposed row now requires agreement among the historical main evaluator, its historical alternate, and the new evaluator. Literal counterexamples and intentionally reversed edges are regression-tested.
3. The old audit summarized item counts and SHA values but did not freeze the full question/answer inventory. `docs/GRADE_A_CANDIDATE_MANIFEST_V2.json` retains the **actual 216 distinct source records**, encoded token sequences, typed gold labels, capability, train/exam partition, source identities, exact historic 222-token model binding and both train and exam content digests. `grade_a_manifest.verify_manifest()` regenerates the original source rows and refuses altered labels or rows. The fixed held-out exam rubric SHA-256 is `7f351f93b81a1d08a45dd53d5f253ad34c238019015e84284d50ca40378a1370`. The artifact is a **candidate**, not an automatically adopted or authorized curriculum.

`grade_a_evaluator.py` separately scores precisely the 72 pinned exam item IDs for one whole-model checkpoint and optimizer step. A fake `1/1` result cannot substitute for a complete `12/12` result for any of the six capabilities. Missing, extra and out-of-type predictions are rejected.

## Concurrent grade construction without destroying earlier progress

`Course.program_complete` defaults to `False`. A course containing Grade A alone can certify *that released grade* but reaches `AWAITING_NEXT_GRADE` rather than `WHOLE_SCHOOL_MASTERED`. `append_next_grade()` explicitly migrates the course digest and school state, checks that every old grade and its grade-level rubric seal are exactly preserved, and keeps the prior full student and Grade A champion pointer intact.

Visits no longer erase `latest_rubric_digest`. Assessments must retain their selected grade's sealed cumulative rubric and exact per-capability question totals; changing a rubric between visits is rejected. A newly introduced Grade B has its own sealed A+B cumulative examination and may not silently rewrite the Grade A-only examination.

## Actual 222-token whole-student continuation: disposable parity pass

The original **complete** FP32 student/own AdamW at optimizer step `116760` was read with the original pinned native loader, checksum `646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78`. The source was left untouched. `full_student_qualification.py` made two detached in-memory copies, one for PyTorch and one for MLX, then compared one AdamW update across all **39 saved parameter/moment families** with the same categorical loss and global gradient clipping.

The Apple GPU run used **12 real source-bound Grade A candidate examples**, two per capability (TRUE and FALSE), with maximum sequence length 28. Observed maximum absolute discrepancies against PyTorch CPU:

| Check | Absolute difference |
| --- | ---: |
| Cross-entropy loss | 1.1920928955078125e-7 |
| Unclipped gradients | 7.033348083496094e-6 |
| Global gradient norm | 7.05718994140625e-5 |
| Clipped gradients | 1.214444637298584e-6 |
| Post-step weights | 5.960464477539063e-8 |
| Post-step AdamW moments | 1.210719347000122e-7 |

Both copies reached step `116761`; all values were within the fixed `0.002` maximum tolerance. A separate disposable ~129 MB MLX bundle with the full semantic catalog was created in an isolated temporary directory, restored exactly, and then discarded: maximum restored weight/moment error **0.0**, 222 semantic tokens, 39 parameter groups, optimizer step `116761`. The original source SHA matched again after the probe; **zero actual student neural updates** occurred. The same full-model CPU reproduction and temporary-bundle restart also passed.

These results qualify the *single-step cloned optimizer continuity and complete snapshot codec*, not a full training session or adaptive learning outcome. They should not be generalized to hundreds of steps, performance under long GPU sessions, real-world convergence, or ability to produce and retain a trained Grade A champion.

## Repeatable neural-inert commands

```sh
cd ~/Code/bilqis-mlx
npm run test
npm run grade-a:verify
npm run mlx:qualify
npm run train -- --dry-run
```

`npm run grade-a:verify` uses the exact pinned original semantic source and complete student, then checks all 216 proposed items. `npm run mlx:qualify` operates on disposable GPU copies and cleans up the temporary bundle. `npm run train -- --dry-run` still reports launch blockers without updating weights.

## Remaining Grade A release gates

**Actual human training remains blocked.** This repair does not fabricate New Ithkuil-valid carrier/reference morphology for `A..E`, `K0`, and `F0`. Independent curriculum admission must decide whether all six similarly difficult direct predicates and their typed set/function operands belong in Grade A, with justified prerequisite expectations and source-root/case/form coverage. The Grade A course still omits admission SHA fields and remains nonexecutable.

The native letter-grade CLI is also still an intentional training stub, not a long-running optimizer. A supervised human-only operator command must load the exact trained student and its AdamW, dispatch actual source-bound batches through the MLX GPU, integrate adaptive teacher policy without replacing it, evaluate all 72 independently held-out items, archive the complete student/optimizer after verifiable updates, expose School50 telemetry, and prove safe interruption/resume and disk reservations. No agent should use the disposable single-step proof to bypass that integration or permission boundary.

Preserve `legacy-source/v1` historical semantics, all 222 token IDs, original archives and checkpoint. Never reset the old student because the living New Ithkuil catalog changes.
