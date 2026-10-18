# Bilqis retained-update grade-net safety specification

**Status:** Normative for the isolated human-training experiment; 2026-10-17, ADR-054 as refined by ADR-055.
**Scope:** Candidate student + own AdamW admission during individual training visits. Separate from championship succession and whole-school graduation.

## Reproduced failure

The isolated run's immutable event generation **11566** accepted a B.XOR candidate at attempted step **230680** (PROVISIONAL, PAIRED_SCREEN_WITHIN_BUDGET) and retained **16** optimizer steps. Its own paired source-oracled panel measured **B.XOR +1, B.IFF -1, B.IMPLIES -1**, hence **Grade B net -1**. The recorded protected aggregate was diagnostic and did not gate admission. Independent fixed-cohort exams also show declines between successive retained student checkpoints; these separate exams are corroboration, not substitutes for the exact paired candidate evidence.

## Candidate retention requirements

1. **Stage one: the target.** The target capability's parent-versus-candidate fresh source-oracled probe MUST improve strictly. If it does not, reject immediately. Do not spend additional inference on its unscored peers or fixed-grade replay just to re-prove a failure.
2. **Stage two: fill only missing same-grade scores.** For a candidate that passes stage one, reuse exact scores already measured on that candidate checkpoint and paired source question set. Evaluate only the remaining currently admitted capabilities of that grade on paired identical source questions for parent and candidate, with equal question count per grade capability. Missing grade coverage at the final admission decision is a failed screen. Never borrow scores from a different checkpoint, optimizer step, seed or rubric.
3. The sum of fresh correct-answer changes across the entire target grade MUST be **strictly positive**. A net zero or negative result rejects the candidate, regardless of the positive targeted gain and each protected peer's separate tolerance.
4. **Stage three: independently saved grade evidence.** Only once the target has gained **and the complete fresh same-grade panel has a strictly positive net**, use the last immutable fixed-grade exam if it is from the current active grade and grade-test epoch. A zero/negative grade net rejects the candidate without an unnecessary fixed replay. Evaluate the fixed cohort's grade capabilities on exactly the same questions for parent and candidate. The complete fixed grade score MUST NOT decline. A fixed grade tie is permitted only when the fresh complete same-grade panel improves strictly. Reuse already evaluated rows for this candidate and cohort; do not rescore them.
5. All existing individual protected-capability tolerances, source-gold validation, B.OR/B.XOR fixed per-question composition replay, teacher feedback, student ownership, AdamW custody and graduation rules remain independent additional gates.

If there is no comparable complete fixed cohort (for example before the first exam or in a different grade epoch), report NOT_MEASURED rather than inventing a fixed grade score. A target-only rejection is marked TARGET_ONLY_REJECTED, not falsely described as a complete grade screen. Only a candidate that passed its target undergoes the remaining grade qualification. The independent whole-school assessment remains the authority for school-wide graduation and out-of-sample retention; it is not repeated on every provisional student.

## Bounded execution, provenance and custody

The current curriculum has six Grade B capabilities (12 fixed exam questions each) and seven Grade C capabilities. The mandatory current-grade completion cost scales with **that grade only**, regardless of total school size. The configurable protection budget controls optional rotating cross-grade sentinels, with two available slots reserved when earlier/other grades exist. It does **not** cap same-grade completeness: a grade larger than eight capabilities must still test its unscored grade members after target improvement. Never extend the screen to every school capability merely because another grade has been admitted.

Reuse the saved fixed-cohort file, including the parent/candidate B.OR/B.XOR predictions when part of the same full-grade replay. No new 8 GB model copy, optimizer reset, retrospective rollback, source-gold rewrite, unapproved teacher-policy change or agent-initiated neural update. A rejected candidate discards only its provisional in-RAM model and own trial AdamW, leaving parent untouched. The teacher receives the measured negative retention evidence.

## Executable acceptance examples

- Real generation 11566 pattern: B.XOR +1, B.IFF -1, B.IMPLIES -1 => REJECT, SAME_GRADE_NET_REGRESSION, net -1.
- B target +1, peer B -1 => REJECT, NO_POSITIVE_SAME_GRADE_GAIN, net zero.
- Fresh Grade B net +1 but current whole Grade B fixed cohort declines from 59/72 to 56/72 => REJECT, FIXED_GRADE_COHORT_REGRESSION.
- Target gain with missing same-grade member => fail closed, not PROVISIONAL.
- Target fails first => reject without scoring unrelated peers; retain the true target-only observation and mark the additional grade controls NOT_MEASURED.
- Target passes and two grade capabilities already have valid scores for this exact candidate/cohort => evaluate only the missing capabilities; do not score either previously tested capability again.
- A future grade has more than eight capabilities => completion still includes its entire grade, with bounded optional cross-grade controls; do not fail or silently truncate on the old global panel limit.
- Positive target, strictly positive full fresh-grade net, no fixed grade regression and all other guards pass => PROVISIONAL only, not school graduation.
- Real Grade B fixed cohort is 72 items with 12 for each of six capabilities, tied to a verified immutable digest and the current grade-test epoch.

This is a forward-only retention correction. It does not reverse already retained updates, prove generalization beyond the compared cohorts, or claim new cumulative mastery without a human-run neural experiment.
