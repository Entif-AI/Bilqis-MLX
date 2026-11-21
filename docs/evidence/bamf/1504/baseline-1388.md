# Retained #1388 live warm-production baseline

Source: <https://github.com/Entif-AI/Bilqis-MLX/issues/1388>  
Issue title: `BAMF B11/MLX throughput | Reduce actual four-row forward/backward step cost`  
Source issue updated: 2026-11-18T20:22:42Z  
Retained for #1504: 2026-11-20

This file preserves the part of the live #1388 issue contract that is the
apples-to-apples warm production comparator for #1504. It supplements, rather than
replaces, `docs/evidence/bamf/B11/1388/throughput.md`, whose later isolated witness
is intentionally cold/disposable and therefore has a different full-step wall.

## Observed baseline recorded by #1388 on 2026-11-17

The live `trainer-observed/v5` B.COMPOSITE 16-step candidate reported:

| Measure | Median / shape |
| --- | ---: |
| Full candidate optimizer step | ~9.78 s |
| `b11_autodiff_wall_seconds` | ~4.09 s |
| `c08_logical_batch_wall_seconds` | ~5.35 s |
| `b11_preflight_wall_seconds` | ~0.027 s |
| Logical rows | 4 |
| C08 gradient launches | 1 |
| Vectorized microbatches | 1 |
| Scalar fallback rows | 0 |
| Compiled positions | ~49 |

#1388 explicitly states that B11 autodiff is nested within C08/logical-batch and
full-step time, not additive. It also states that the path was already vectorized.

The source issue's acceptance contract required before/after comparison on the
same BAMF topology and four-row source-qualified workload, preservation of the
real production candidate path as one vectorized launch with zero unintended
scalar fallback, no new per-row source requalification, and no accepted-state
mutation by benchmark runs.

## Boundary with the retained cold witness

`docs/evidence/bamf/B11/1388/throughput.md` records a later isolated MLX 0.32.4
four-row B.COMPOSITE witness with 14/14/12/12 compiled positions. Its focused B11
measurement is useful, but its full disposable candidate step is ~33.6231 seconds
because it pays ~20.8353 seconds of fresh pre-neural source compilation. That cold
fixture is not evidence that the live warm production step was 33 seconds.

