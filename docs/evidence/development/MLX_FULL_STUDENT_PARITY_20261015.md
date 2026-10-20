# Complete historic FP32 student: first independent MLX CPU mapping receipt

**Date:** 2026-10-15
**Evidence class:** actual saved-model/optimizer read-only verification
**Status:** forward and moment mapping proved; training continuation NOT proved
**Authority:** protected `IPR-0220`, MLX backend evidence from public Bilqis #160 consumed privately

## Source identity

- Saved **complete** (not assembled, not per-grade soup) native checkpoint: `student-116760-7e9af4651f28.pt`
- Source: preserved `runs/primitive-consolidation-v16-triplets/` in the old Bilqis worktree
- SHA-256: `646d8590cf8fddb7b3c412ecead4ac185a0578f93baadf24e05f92dd15068a78` (independently reread at inspection)
- Historical score (legacy exam): **1,052 / 1,150**; NOT a new letter-grade graduation result
- Native optimizer step: **116,760**
- 6 layers, width 384, 24 heads, context 96, 222 tokens, FP32 precision, original tied answer embeddings
- AdamW group: betas `(0.9, 0.95)`, eps `1e-8`, weight decay `0.01`, LR `0.00013`, 39 saved per-parameter moment records

## Actual read-only comparison

The real historical full checkpoint was loaded with its original `bilqis_development.continuation.load` verifier, which checks semantic catalog, whole-model tensor identity and native optimizer receipt. A separately implemented **MLX CPU FP32** transformer forward mapped all original model tensors; PyTorch CPU was the independent comparator on the same two non-exam symbolic input sequences. The source graph itself supplied the correct answer IDs, rather than a guessed vocabulary position.

| Probe | Observed result |
|---|---:|
| Native evidence readout token IDs | `[6, 7, 59, 60, 61]` |
| Actual integer 0–3 readout token IDs | `[121, 122, 123, 124]` |
| Maximum evidence-logit absolute error, MLX vs PyTorch | `5.7220458984375e-06` |
| Maximum numeric 0–3 logit absolute error, MLX vs PyTorch | `5.662441253662109e-07` |
| Admitted FP32 forward tolerance | `2e-3` |
| Complete native AdamW parameter moment mapping | `39 / 39` |
| Maximum copied `exp_avg` / `exp_avg_sq` discrepancy | `0.0` |
| Native optimizer step retained in in-memory mapped state | `116760` |
| Training optimizer updates on this historic checkpoint | **0** |
| Historic checkpoint modified / cloned onto disk | **No / no** |

The optimizer map derives parameter order from the actual original model/optimizer parameter object identities, not from a potentially misleading equal-shaped tensor match. MLX AdamW explicitly uses `bias_correction=True` to match the original PyTorch semantics. The test validates a complete in-memory native moment conversion, **not** a production optimizer step or full checkpoint rehydration under a running MLX training workflow.

### Repeatable nontraining probe

From the private repo's Mac working directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m bilqis_mlx.mlx_parity \
  --checkpoint ../bilqis-triplets-v16/runs/primitive-consolidation-v16-triplets/student-116760-7e9af4651f28.pt \
  --legacy-code-root ../bilqis-triplets-v16
```

The source tree is read-only for this invocation. The probe never calls an optimizer update, creates a model run, or overwrites any file. Its positive results establish a credible **retention and inference-portability foothold**, not MLX student-graduation readiness.

## Open promotion gates (still blocking any neural training)

1. Verify complete MLX optimizer state save/reload and continuation parity against the original on independently copied disposable fixtures. State-step preservation alone cannot certify actual training-step numerical equivalence.
2. Qualify the runtime on Apple GPU against measured CPU/MPS, with realistic memory/disk budgets and the actual candidate batch shapes.
3. Ground about 6–9 Grade A capabilities in independent semantic roots and prereq oracles with exhaustive appropriate binary and bounded typed answers. The synthetic fixtures in unit tests are **not** a source-approved curriculum.
4. Implement the model adapter, actual adaptive teacher vote wiring, learning policy and candidate checkpoint archiving; then prove complete single-checkpoint grade examinations on newly versioned tests.
5. Verify six-panel dashboard source adapter and protected legacy/backup custody before any human-operated neural session.

**Disposition:** `PARTIAL_MLX_READ_ONLY_PARITY_PASS / TRAINING_HELD`.

## Subsequent disposable continuation proof

See [MLX AdamW fixture restart](../experiments/MLX_DISPOSABLE_ADAMW_RESTART_20261015.md). It verifies four PyTorch/MLX continuation steps from restored fixture moments, state-file corruption rejection, and a tiny causal-transformer gradient/clipping comparison. The historical 116760-step student remains read-only; full-student training continuation is still pending.

**2026-10-15 successor evidence:** A complete detached **copy** of this exact student plus all 39 AdamW moment records has now passed one real-shape PyTorch/MLX optimizer comparison on Apple GPU, using twelve source-attested Grade A candidate training records. Gradient, clipping, loss, weights and moments agreed within 0.002; the step advanced in both disposable copies from 116760 to 116761. The complete 222-token semantic catalog and all tensor/moment values reloaded bit-exact from a separately created, automatically deleted temporary MLX bundle. **The real original model received zero updates.** This strengthens the previous read-only forward proof, but is not an end-to-end human-session trainer qualification. See [Grade A repair and backend evidence](../grades/GRADE_A_REPAIR_AND_BACKEND_20261015.md) for exact numbers and reproduction.
