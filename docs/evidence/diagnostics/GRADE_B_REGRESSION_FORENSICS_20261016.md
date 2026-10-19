# Grade B regression audit (2026-10-16)

**Historical implementation note (later 2026-10-16):** The 24-item backlog
and automatic quarter-batch prerequisite injection described below were
unratified experimental repairs and have since been retired from the active
trainer under ADR-031 and private issue #336. Current code retains unresolved
exam mistakes until verified correction, tracks replay exposure, preserves
the inherited teacher selection, and uses a fixed examination per grade
enrollment. The observations and original trial below remain historical
evidence of the earlier design and human-run regression.

Private internal record. Governing policy: IPR-0220, ADR-022 through ADR-025.

Read-only inspection of the human saved run at `runs/school-mlx-v1` confirmed
the current FP32 student at optimizer step 155640, 2430 visits, 6718 teacher
events. The original Grade A champion remains at step 153144.

| Matched exam | Current A | Frozen A champion A | Current B | Frozen A champion B |
| --- | ---: | ---: | ---: | ---: |
| First B exam, step 153240 | 56/72 | 72/72 | 35/72 | 42/72 |
| Latest B exam, step 155640 | 55/72 | 71/72 | 33/72 | 39/72 |

Each row is a genuinely paired cohort comparison. The 39 observed B exams
repeatedly showed near-chance B scores and rapid regression of mastered A.
The disposable engineering graduation tests did not measure neural learning.

Grade B has NO permanent sealed-example embargo: `draw_connectives` supplies
both the sampled teaching questions and `_take_exam` with original source
truth functions and three-way oracle agreement. Assessment cohorts are held
fixed only during matched checkpoint comparisons, then their failed examples
are permitted in teaching. The separate historical integer partitions do
not control the live B trainer.

## Proven implementation failures

1. Each `_take_exam` overwrote the entire prior mistake queue. Across 38 B
   examination intervals, 2,103 failed rows were observed. Of these, 1,179
   (56.1%) belonged to capabilities that received no intervening teaching
   visit before the next exam erased those failed rows. This measures lost
   direct feedback opportunities, not proof that equivalent semantic patterns
   never occurred in randomly sampled lessons.
2. `school.assess` excluded all three first-round weakest capabilities from
   the second recovery round, even when they remained weakest after a fresh
   exam. The user authorized freshly *ranked* weakest-three selections, not
   disjoint trios. The exclusion withheld teaching from persistent weaknesses.

Grade B visits often received positive immediate source-training reward,
while full sampled examinations stayed near chance. The evidence supports
a feedback-and-retention mismatch, without identifying a unique mechanism
for every neural failure.

## Corrective engineering

- The second recovery round now reranks the entire currently eligible pool.
  Still-weak capabilities can receive consecutive rounds. The grading gate,
  active-grade full pass, and separately ranked recovery cadence remain.
- Post-exam `retain_missed_semantics` retains source-verified old examples
  still answered incorrectly, together with recent counterexamples. It
  removes old misses the current student now answers correctly. The teaching
  queue stays bounded to 24 specimens per capability, exposes counts for
  retained/resolved/new/budget-evicted items, and is never a sealed exam
  or a substitute for a complete qualification cohort. This explicitly
  repairs the overwrite mechanism, though the bound means not every historic
  failure remains physically present forever.
- Every Grade B optimizer step dynamically generates constituent questions
  from the *same attested micro-worlds* as its B operator questions. The
  direct A.IDENTITY, A.PARENT and A.LINK operand questions are independently
  checked against the original dual interpreters and Grade A record oracle,
  and take up at most one quarter of each B batch. The B operation remains
  the primary objective, while exact missed-item replay has final priority.
  This adds connected semantic reinforcement, not separate sequential
  passes through older grades or unadmitted operators.

The trainer-only corrections do not change either source generator's bytes,
the versioned Grade A/B assessment rubric, the 222-token graph, past cohorts,
the frozen Grade A champion, or the actual student and matching AdamW.

## Verification boundary

The updated synthetic, source-oracle and regression suite establishes the
software mechanisms only. There is no evidence yet that live B acquisition,
generalization or retention has improved. Constituent rehearsal does not
directly preserve A.MEMBER, A.EDGE or A.MAPS, and an unmodified full-student
optimizer can still interfere with acquired representations. Future empirical
validation is human initiated, must use matched sampled cohorts for model
comparisons, and must preserve the original whole Grade A champion. No agent
invokes `--human-run` or changes human-operated checkpoints.
