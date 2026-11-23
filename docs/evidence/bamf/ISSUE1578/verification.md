# Issue #1578 verification

## Conclusion

- A fixed 32-row logical optimizer objective cannot use more than 32 distinct row-count work items in one C08 gradient launch without crossing logical-step membership. Sequential candidate steps consume AdamW-updated parameters from the prior step, so a 64-row fusion would change the learning trajectory unless a new cross-step executor preserves both updates and their authority/OOM boundaries.
- Physical caps of 8, 16, and 32 rows/launch all preserved the 32-row logical objective under the repository C08 FP32 equivalence tolerance (`atol=1e-6`) and applied one optimizer step. Bitwise optimizer-state hashes differed and are retained as diagnostics, not treated as semantic drift.
- The explicit equal-96-row-presentation logical-batch policy experiment (8/16/24/32) passed the disposable C05 retention screen for all four arms. Durable useful-retentions/hour is **NOT_MEASURED** because this fixture does not publish a retained lineage or establish downstream usefulness.
- No default logical batch change is justified or made. The current 32-row default had the highest retained-candidate throughput of the four disposable arms, and there is no durable useful-learning evidence supporting a change.
- OOM retry and resource-budget semantics are untouched by this issue implementation.

## Physical 32-row objective qualification

| cap | rows/launch | launches | candidate step wall (s) | C08 wall (s) | B11 materialization wall (s) | actual MLX peak (GiB) | estimated peak (GiB) | loss |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 8 | 8 | 4 | 3.7336 | 2.3103 | 1.8486 | 3.473 | 1.764 | 0.695968509 |
| 16 | 16 | 2 | 3.9597 | 2.3440 | 1.9160 | 2.913 | 1.968 | 0.695968568 |
| 32 | 32 | 1 | 3.7815 | 2.2814 | 1.8472 | 3.041 | 2.432 | 0.695968568 |

## Equal-row-budget logical-batch policy experiment

| logical batch | steps | rows presented | rows/launch | launches | candidate wall total (s) | C08 wall total (s) | materialization wall total (s) | actual MLX peak (GiB) | steps/hour | retained candidates/hour | yield | steps/retention | useful retentions/hour |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 8 | 12 | 96 | 8 | 12 | 920.405 | 9.015 | 4.999 | 11.879 | 46.092 | 3.841 | 1.0 | 12 | NOT_MEASURED |
| 16 | 6 | 96 | 16 | 6 | 948.393 | 9.726 | 6.129 | 6.841 | 22.360 | 3.727 | 1.0 | 6 | NOT_MEASURED |
| 24 | 4 | 96 | 24 | 4 | 932.169 | 8.657 | 5.051 | 5.187 | 15.167 | 3.792 | 1.0 | 4 | NOT_MEASURED |
| 32 | 3 | 96 | 32 | 3 | 905.682 | 8.728 | 5.395 | 4.743 | 11.698 | 3.899 | 1.0 | 3 | NOT_MEASURED |

All four arms returned `ELIGIBLE` / `PAIRED_SCREEN_WITHIN_BUDGET`. Because each arm uses a different optimizer-step count under the fixed 96-row presentation budget, raw steps/hour is not a learning-quality comparison by itself; retained-candidate throughput and retention outcome are reported beside it.

## Evidence boundaries

- The physical witness is disposable and non-authorizing. It measures one 32-row candidate step under physical caps 8/16/32.
- The logical-policy witness is disposable and non-publishing. It runs genuine candidate training and the production C05 evaluator but does not publish any candidate into the human learner.
- `actual_mlx_peak_bytes` is read from MLX peak-memory telemetry after the bounded witness; `estimated_peak_bytes` remains the C08 analytical planner estimate. They are intentionally reported separately.
- No `--human-run` invocation occurred and no production neural state was mutated.
