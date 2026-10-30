# B10.4 AnswerPlan/v2 and readout tensor-census candidate

- Issue: #470; parent B10 #367; Lane B
- Consumed unified: `9104ce733e04fb9c82420428b18dfdbf5db49535`
- Feature branch: `feature/bamf-b10-4-470-20261030`
- Direct prerequisite: B10.3 #469 exact candidate receipt at
  `7f074d00097ba8147ebf02261e5b49592eda9d1b`; final B10.4 turn-in must
  consume B10.3 after its independent-review gate.
- Learning state: software-only; no learner or optimizer mutation
- Independent EGM: pending

## Owned behavior

B10.4 does not create another parameter registry. The readout owner projects its
entire tensor census from B01's normative `expected_bamf_shapes` ledger and owns
only the `readout.` prefix. The resulting 18-row view contains state/output
norms, Q/K/V/output refinement, dependency feedback, role query, CONTROL,
epistemic and three salience heads with their declared biases. Shared
`features.`, `depth.`, `identity.`, `motif.` and `plastic.` paths remain
outside B10 ownership.

`bind_readout_parameters` accepts only an exact B01-declared readout view with
the recorded names, FP32 dtypes and shapes. Missing tensors, extra shared tensors,
wrong shapes or non-finite values fail closed. Initializers are inherited from
B01 `ParameterSpec` rows rather than copied into B10.

The existing AnswerPlan/v2 implementation is exercised directly: the plan schema
is `bilqis.mlx.answer-plan/v2`, dependencies execute in deterministic
topological/stable-ID order, maximum decisions remain <=64, and
`input_prefix_end + position_budget` remains within B01's 1024-position
context.

## Red/green proof

Before the B10.4 owner existed, the focused suite failed because
`bilqis_mlx.learning.atlas_readout.parameters` did not exist.

After implementation:

- B10.4 focused: **5 passed + 3 subtests**
- complete compartmentalized atlas-readout suite: **46 passed + 42 subtests**
- development structure: **0 violations**
- governance integrity: **0 violations**
- changed-file smell audit: **0 new findings**
- `git diff --check`: PASS

## Boundary

This is a branch candidate against the frozen #469 interface. It does not claim
B10.3 acceptance, parent B10 integration, learner improvement, live training or
merge readiness. Fresh independent EGM remains required, and final turn-in must
consume the accepted B10.3 receipt rather than treating its open state as closed.
