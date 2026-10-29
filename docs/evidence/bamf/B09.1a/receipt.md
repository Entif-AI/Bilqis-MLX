# B09.1a rank-eight adapters and static FAST eligibility: scoped candidate

Issue: [#463](https://github.com/Entif-AI/Bilqis-MLX/issues/463)
Lane: B, isolated candidate `codex/bamf02-b09-adapters-20261029`
Consumed Lane B: `7b70b0d4f70c2df7d79ddd69db91a2eaf1da78ae`
Consumed reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`
Direct dependencies: B01 Tensor ledger available; B05 and B08
numerical candidates available, but full source/retention integration
is not yet accepted.

## Owned software

`learning/atlas_plasticity.py` implements all three B01-declared
rank-eight adapters at the group boundaries:

`h' = h + (1/8) * B * SiLU(A * RMSNorm(h))`.

The constructor validates the *entire* B01 parameter ledger before
borrowing only the exact `plastic.group.k.norm/A/B` tensors, with
copy-on-read protection. Zero-initialized B matrices yield an exact
numerical identity while retaining gradients to B; trained nonzero B
also propagates gradients into A.

`group_eligibility` consumes B01's `ParameterCensus` group labels
without inventing a second tensor registry. FAST includes motif
pages, motif sites and all three adapter prefixes; SLOW retains
established/dense paths. Identity banks remain per-row, not a
whole-tensor FAST shortcut. Immutable row ages distinguish newly
activated rows (ages0-7) from established rows (age8).
`advance_accepted_row_ages` increments a participating row at most
once per accepted candidate, never per internal optimizer step.
Rejection returns the exact unchanged parent tuple.

This is a static eligibility proposal, not the final optimizer mask.
B09.1b owns mode/cadence transitions, B09.1c owns step participation,
B12 owns AdamW arithmetic and B13/C owns retained-generation
acceptance. The `accepted` input must come from that owner and
is not self-authorized here.

## Verification

```
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/test_atlas_plasticity.py \
  bilqis_mlx/runtime/tests/test_model_topology_v2.py \
  bilqis_mlx/learning/tests/test_atlas_engram_parameters.py
```

**30 total, 28 passed, 0 failed, 2 existing optional skips.**
New tests verify exact identity at all three boundaries, nonzero
gradients to B at initialization, the literal nonzero-B SiLU
equation and A gradients, full-ledger prefix borrowing, FAST/SLOW
classification, row age7-to8 establishment on the next candidate,
single accepted-candidate increment, rejection identity and invalid
mode/shape/row rejection. No new error-control-plane findings were
observed in the new module; `git diff --check` passed.

## Disposition

**SCOPED_EGM_PASS_B09_AND_OPTIMIZER_INTEGRATION_PENDING.**
Independent Goldfish readback at immutable pushed
`8ba5b8ae3c24221ab3e317a805ffcce62baa7b37`
returned **EGM PASS, zero Blockers/Majors** for the exact
B09.1a scoped numerical and static eligibility obligations.
The reviewer inspected source, B01 ledger and tests but did not
independently execute them; the 28-pass/2-optional-skip counts are
prime execution evidence.

No native AdamW state, row update mask, teacher strategy, retained
checkpoint, accepted generation or live learner was mutated.
Source-qualified row admission, B09.1b/.1c policy and B12/C
integration remain open; no B09.1a or parent closure is claimed.
