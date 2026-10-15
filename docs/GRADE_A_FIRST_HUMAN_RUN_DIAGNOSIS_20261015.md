# Grade A first human-run evidence, 2026-10-15

## Observed state

This is a read-only diagnosis of the first human-operated Grade A run, not an
endorsement of an agent-run optimizer update or a new curriculum release.

- Run: `runs/school-mlx-v1`, latest receipt generation 61.
- School: Grade A, `MAIN`, 48 committed capability visits; no champion.
- Native student AdamW optimizer step: 117528, up from source step 116760,
  consistent with 48 visits at 16 steps per visit.
- Adaptive teacher event counter: 4336, up from inherited 4288.
- The source-admitted 72-item fixed rubric remains
  `7f351f93b81a1d08a45dd53d5f253ad34c238019015e84284d50ca40378a1370`.
- Read-only original historical student baseline: 34/72.

All 12 scheduled complete Grade A exams, in generation order:

| Generation | Correct / 72 | Next phase |
| --- | ---: | --- |
| 8 | 38 | RECOVERY_1 |
| 12 | 34 | RECOVERY_2 |
| 16 | 34 | MAIN |
| 23 | 31 | RECOVERY_1 |
| 27 | 37 | RECOVERY_2 |
| 31 | 35 | MAIN |
| 38 | 34 | RECOVERY_1 |
| 42 | 37 | RECOVERY_2 |
| 46 | 34 | MAIN |
| 53 | 33 | RECOVERY_1 |
| 57 | 31 | RECOVERY_2 |
| 61 | 33 | MAIN |

The latest per-capability sealed examination scores were: A.IDENTITY 6/12,
A.PARENT 3/12, A.LINK 7/12, A.MEMBER 7/12, A.EDGE 6/12, and A.MAPS 4/12.
Multiple recent capability-visit receipts report source-training accuracy of
1.0 after their optimization steps, while full exams remain near chance.

## Mechanism and leading hypothesis

`grade_a_trainer._take_visit` samples exclusively from 24 pre-generated
instructional rows for the active capability, with replacement, for 16
minibatches per visit. `_train_score` evaluates on those same 24 rows before
and after; their accuracy difference becomes the adaptive teacher's reward.
This reward estimates improvement on the lesson pool, not generalization to
unseen examples. The fixed 12-item examination per capability is correctly
kept out of the reward path.

The leading hypothesis is **training-set memorization and inadequate transfer
from a narrow sampled world/query distribution**, exacerbated by reward
selection against in-sample accuracy. The measurements establish lack of
improvement on the sealed rubric; they do **not** uniquely establish the
causal mechanism. Other live possibilities include insufficient semantic
coverage, interference from other capabilities, model representation limits,
or train/exam distribution structure differences.

## Next safe discriminating work

1. Add neural-inert diagnostics of training-versus-exam token/world/answer
   distributions, canonical record overlap, and per-capability prediction
   errors; keep all 72 exam answers and the rubric frozen.
2. Prototype an *independent training-derived validation partition* for
   teacher-policy rewards on synthetic/disposable model fixtures. The sealed
   examination must never become a policy reward or optimizer signal.
3. Investigate richer, independently source-oracled instruction generation
   across legal **already-taught** semantic worlds; test for trivial label
   cues, repeated query identities and held-out transfer before admission.
4. Measure retention and per-capability cross-interference on detached
   read-only checkpoints. Any proposed scheduler/learning changes require
   specific fixture tests and a versioned rollout strategy that preserves
   historical run state and its optimizer.
5. Only the human may resume the actual student using `--human-run`. Do not
   recommend another identical 48-visit run as evidence of progress while
   examination outcomes remain near the original baseline.

## Preservation boundary

Do not modify `runs/school-mlx-v1`, any committed model/optimizer bundle, the
historical original checkpoint, the inherited teacher source or its history,
or the accepted Grade A source/examination seal while diagnosing this run.
The one unrelated untracked `bilqis_mlx/ni_named.py` is not part of this work.
