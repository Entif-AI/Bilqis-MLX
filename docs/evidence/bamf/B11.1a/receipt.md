# B11.1a numerical group producer foundation

Issue: canonical #586 (#587 duplicate closed). Parent: B11.1 #471.
Consumer: B05.4 #577.
Lane B base: `ae08c4aa6c9eee86cbc28142de626f382662876d`.
Disposition: **UNADMITTED_NUMERICAL; numerical-only EGM PASS**.

The fixed `run_backbone_group_numerical` executes the four B01/B04
layers selected by group index. It uses the B01 parameter ledger,
pre-RMSNorm, native CCGQA with source/causal/padding masks, squared-ReLU
two-matrix FFN and residuals. Each layer returns its B04 attention
cache. The numerical result records group index and layer interval.

This result is deliberately named `UnadmittedGroupNumerical`. It does
not authenticate its input, parameter generation, prediction prefix,
source rights or motif read ordering. It is **not** a completed-group
producer receipt, and B05.4 must continue to reject it. The caller
still supplies a group index and raw input, so it cannot satisfy
the g2-as-g1 adversary or release #577 by itself.

## Verification

The new B11.1a test first failed to import the missing fixed group API.
After implementation:

- 3/3 focused numerical tests pass on Apple MLX;
- combined B11.1a/B04/B01 suite: **35 passed, 0 failed, 2 existing
  optional skips**;
- exact four-layer output differs from input, group 2 uses layers 4–7,
  and invalid group index or parameter geometry rejects;
- causal prefix isolation passes when a future token is appended;
- gradients to input hidden state, B04 attention query matrix and B01
  FFN input matrix are finite and nonzero;
- `git diff --check` passes, with no new error-control/module-size
  findings in this module.

## 2026-10-29 B04 internal sequence-boundary repair

Independent worker-20's review of follow-on PR #590 found a Major
inherited from this numerical precursor: the wrapper did not forward
`AttentionScope.sequence_starts` to the actual B04 layer calls.
For a single scope ID with an internal sequence reset, convolution
history could cross the reset even though direct B04 execution
would isolate it.

The failing-before regression changes the first two tokens while
keeping the post-reset tokens fixed. It now proves the post-reset
group output is unchanged with an internal sequence start. The
wrapper validates the source mask's exact boolean shape and forwards
it to every layer's B04 scope using the named field, not the
parent-prefix slot. The focused suite now passes **4/4**.
This repair remains numerical-only; it does not issue producer authority.

Independent B04 expert worker-20 reviewed immutable `19ebb05` and
returned **B11.1a numerical-only EGM PASS, zero Blockers/Majors**.
It verified B01 tensor names and geometry, pre-RMSNorm/CCGQA/FFN
equations, causal masking, real gradients and the explicit
`UNADMITTED_NUMERICAL` boundary. A later static-only guard cleanup
`22410ec` preserves those equations and removes two opaque numeric
guards. This PASS does **not** attest the source producer or B08 motif
read. B13 final-generation publication is a separate downstream gate.

## Next authority gate

The next B11.1a unit must take B03/A05.4-approved source h0, derive
the actual B01 parameter-tree content identity and execution
generation/prefix, execute this fixed group path internally, record
the B08 second motif-read boundary (explicit no-hit while quarantined),
and bind the actual output tensor, B04 cache chain and ordered
predecessor chain to an immutable producer receipt. B13 final
retained-generation publication remains separate and is not a
prerequisite. No public raw-array or metadata-only constructor may
issue the receipt. Until this exists and passes independent EGM,
#577 stays fail-closed.

No live training, optimizer mutation, source promotion, issue closure
or lane merge occurred.
