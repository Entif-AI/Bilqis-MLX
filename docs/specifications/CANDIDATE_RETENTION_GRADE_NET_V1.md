# Bilqis retained-update grade-net safety specification

**Status:** Normative for the isolated human-training experiment; 2026-10-18, ADR-054 as refined by ADR-055, ADR-056 and ADR-057.
**Scope:** Candidate student + own AdamW admission during individual training visits. Separate from championship succession and whole-school graduation.

## Reproduced failure

The isolated run's immutable event generation **11566** accepted a B.XOR candidate at attempted step **230680** (PROVISIONAL, PAIRED_SCREEN_WITHIN_BUDGET) and retained **16** optimizer steps. Its own paired source-oracled panel measured **B.XOR +1, B.IFF -1, B.IMPLIES -1**, hence **Grade B net -1**. The recorded protected aggregate was diagnostic and did not gate admission. Independent fixed-cohort exams also show declines between successive retained student checkpoints; these separate exams are corroboration, not substitutes for the exact paired candidate evidence.

## Candidate retention requirements

1. **Stage one: the target.** The target capability's parent-versus-candidate fresh source-oracled probe MUST improve strictly. If it does not, reject immediately. Do not spend additional inference on its unscored peers or fixed-grade replay just to re-prove a failure.
2. **Stage two: fill only missing same-grade scores.** For a candidate that passes stage one, reuse exact scores already measured on that candidate checkpoint and paired source question set. Evaluate only the remaining currently admitted capabilities of that grade on paired identical source questions for parent and candidate, with equal question count per grade capability. Missing grade coverage at the final admission decision is a failed screen. Never borrow scores from a different checkpoint, optimizer step, seed or rubric.
3. The sum of fresh correct-answer changes across the entire target grade MUST be **strictly positive**. A net zero or negative result rejects the candidate, regardless of the positive targeted gain and each protected peer's separate tolerance.
4. **Stage three: immutable whole-school frontier.** Only once the target has gained **and the complete fresh same-grade panel has a strictly positive net**, load the latest verified fixed whole-school cohort. Reconstruct the retained parent's exact predictions from the immutable cohort plus its saved misses, then score the candidate on those same rows. Every parent-correct fixed row is monotonic: **zero newly wrong fixed rows are permitted anywhere in the school.** Existing misses may be repaired in any grade. The scheduled lesson's fixed grade may tie while a different grade improves; this is valid progress and MUST NOT be rejected merely because the benefit landed elsewhere. A repaired row never cancels a newly broken row. If no complete whole-school frontier exists, use the comparable fixed-grade fallback when available and require that it not decline.
5. All existing individual protected-capability tolerances, source-gold validation, B.OR/B.XOR fixed per-question composition replay, teacher feedback, student ownership, AdamW custody and graduation rules remain independent additional gates.

## Fragile-semantic preservation during candidate construction

The fixed B.OR/B.XOR replay remains an admission test, not lesson material. When that verified fixed replay exists, candidate construction MUST reserve fresh source-oracled structural siblings rather than truth-cell lookalikes. A structural signature includes connective, operand truth pattern, ordered operand kinds, canonical endpoint co-reference topology and universe size. The visit-scoped source pool MUST cover the fixed replay's structural signatures while excluding every fixed row identity. Each optimizer step rotates a bounded structurally matched slice, preserving Boolean output balance and structural diversity. Exact unresolved examination misses retain their reserved lesson slots. The purpose is to give AdamW a preservation gradient for the specific compositions the admission gate protects, without teaching the held-out answers.

A failure to source a complete, gold-valid fresh truth table is a construction error, not permission to substitute the fixed exam rows. The retention decision still runs the independent 24-row replay afterward and rejects any newly wrong parent-correct item.

If there is no comparable complete fixed cohort, report NOT_MEASURED rather than inventing a score. A target-only rejection is marked TARGET_ONLY_REJECTED, not falsely described as a complete grade screen. Only a candidate that passed its target and fresh same-grade net undergoes the fixed frontier inference. This candidate screen reuses an already materialized cohort as a monotonic retention floor; it is not a new scheduled graduation exam, championship award or source-cohort regeneration.

## Bounded execution, provenance and custody

The current curriculum has six Grade B capabilities (12 fixed exam questions each) and seven Grade C capabilities. The mandatory current-grade completion cost scales with **that grade only**, regardless of total school size. The configurable protection budget controls optional rotating cross-grade sentinels, with two available slots reserved when earlier/other grades exist. It does **not** cap same-grade completeness: a grade larger than eight capabilities must still test its unscored grade members after target improvement. Never extend the screen to every school capability merely because another grade has been admitted.

Reuse the saved fixed-cohort file, including the parent/candidate B.OR/B.XOR predictions when part of the same full-grade replay. No new 8 GB model copy, optimizer reset, retrospective rollback, source-gold rewrite, unapproved teacher-policy change or agent-initiated neural update. A rejected candidate discards only its provisional in-RAM model and own trial AdamW, leaving parent untouched. The teacher receives the measured negative retention evidence.

At a scheduled whole-school exam boundary, the trainer MAY reuse an already verified exam instead of rerunning neural inference only when the retained checkpoint SHA and native AdamW step, cohort digest, rubric, assessment scope and semantic graph are identical and all pending visits retained zero optimizer updates. Stored wrong predictions MUST reconstruct the same scores and teacher misses exactly before reuse. Reuse advances ordinary scheduler/teacher bookkeeping but MUST NOT create a candidate checkpoint, rescore incumbents, mint championships, refresh soups or claim new learning evidence. Any changed identity or accepted in-memory update requires the normal full exam.

## Executable acceptance examples

- Real generation 11566 pattern: B.XOR +1, B.IFF -1, B.IMPLIES -1 => REJECT, SAME_GRADE_NET_REGRESSION, net -1.
- B target +1, peer B -1 => REJECT, NO_POSITIVE_SAME_GRADE_GAIN, net zero.
- Fresh Grade B net +1; fixed Grade B ties; one existing C.DIV miss is repaired and no fixed row regresses => PROVISIONAL is allowed. Cross-grade repair is progress.
- Fresh Grade C net +1; one old C.DIV miss is repaired but a previously-correct C.DIV row becomes wrong, leaving the fixed total tied => REJECT, FIXED_FRONTIER_ITEM_REGRESSION.
- Fresh Grade B net +1 but any previously-correct A/B/C fixed row becomes wrong => REJECT, FIXED_FRONTIER_ITEM_REGRESSION, even when another fixed miss was repaired.
- Target gain with missing same-grade member => fail closed, not PROVISIONAL.
- Target fails first => reject without scoring unrelated peers; retain the true target-only observation and mark the additional grade controls NOT_MEASURED.
- Target passes and two grade capabilities already have valid scores for this exact candidate/cohort => evaluate only the missing capabilities; do not score either previously tested capability again.
- A future grade has more than eight capabilities => completion still includes its entire grade, with bounded optional cross-grade controls; do not fail or silently truncate on the old global panel limit.
- Positive target, strictly positive full fresh-grade net, zero fixed-frontier item regressions and all other guards pass => PROVISIONAL only, not school graduation.
- Real Grade B fixed cohort is 72 items with 12 for each of six capabilities, tied to a verified immutable digest and the current grade-test epoch.

This is a forward-only retention correction. It does not reverse already retained updates, prove generalization beyond the compared cohorts, or claim new cumulative mastery without a human-run neural experiment.
