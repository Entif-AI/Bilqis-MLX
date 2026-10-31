# B10.4 AnswerPlan/v2 and readout tensor-census candidate

- Issue: #470; parent B10 #367; Lane B
- Consumed unified: `9ab0eb9fd31f1cabb825a478adbd17864d74f5a4`
- Feature branch: `feature/bamf-b10-4-470-20261030`
- Candidate implementation head: `b0fa18ec08f202b4e343b8e1b849b16df9847c21`
- Direct prerequisite: B10.3 #469 exact reviewed head
  `b63a65e91412f5cfc945eccc3d060b8ed60707fe`, integrated into unified as
  `a02458cea06063a0e0a751306dd9d54f2c8ca389`. Pinned EGM
  `b3a35956759bf7f024af2ff061b2e0b44b438e4c` reports 0 Blockers,
  0 Majors and 0 Nits for B10.3 owned scope.
- Learning state: software-only; no learner or optimizer mutation
- Independent EGM: pending

## Contract identity

- Answer plan input: `bilqis.mlx.answer-plan/v2`
- Decision spec input: `bilqis.mlx.decision-spec/v1`
- Readout parameter authority: B01 `expected_bamf_shapes(ModelTopologySpecV2, GenerationExtents)` `ParameterSpec` rows
- Bound parameter output: immutable `MappingProxyType[str, mlx.core.array]` containing exactly the 18 B01-declared `readout.` rows

Changed paths at this candidate head:

- `bilqis_mlx/learning/atlas_readout/__init__.py`
- `bilqis_mlx/learning/atlas_readout/parameters.py`
- `bilqis_mlx/learning/atlas_readout/tests/test_parameter_contract.py`
- `docs/evidence/bamf/B10.4/receipt.md`

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
- complete current atlas-readout suite after consuming integrated B10.3:
  **58 passed, 0 failed, 0 skipped**
- BAMF child-contract verifier: **157 indexed children PASS**
- operator-contract ratchet: **0 new debt**
- factory architecture: **PASS**
- docs: **PASS**
- development structure: **0 violations**
- governance integrity: **0 violations**
- changed-file smell audit: **0 new findings**
- `git diff --check`: PASS

## Boundary

This branch now consumes integrated B10.3 from unified. It does not claim parent
B10 integration, learner improvement or live training. Fresh independent B10.4
EGM remains the final review gate before merge readiness.

Next integration boundary after accepted B10.4: parent B10 / issue #367 reconciles
all four B10 child clauses against the original full acceptance contract.
