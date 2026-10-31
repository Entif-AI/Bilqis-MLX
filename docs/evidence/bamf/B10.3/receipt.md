# B10.3 causal typed-decoder candidate

- Issue: #469; parent B10 #367; Lane B
- Consumed unified: `9104ce733e04fb9c82420428b18dfdbf5db49535`
- Feature branch: `feature/bamf-b10-3-469-20261030`
- Implementation head: `c8b2734bb405ed8177bbaa497c857035bbdc5dfa`
- Turn-in head: recorded by remote SHA readback in the PR/issue receipt comment after
  this file is committed; a checked-in file cannot embed the SHA of the commit
  that contains itself without changing that commit.
- Learning state: software-only; no learner or optimizer mutation
- Independent EGM: pending

## Contract identity

- Answer plan: `bilqis.mlx.answer-plan/v2`
- Decision spec: `bilqis.mlx.decision-spec/v1`
- Decision output: `bilqis.mlx.decision-output/v1`
- Decode state: `bilqis.mlx.decode-state/v1`
- Typed-head logits: `bilqis.mlx.typed-head-logits/v1`
- Frame answer: `bilqis.mlx.frame-answer/v1`
- Structured-frame modality: `answer.structured-frame/v1`

Changed paths at this candidate head:

- `bilqis_mlx/learning/atlas_readout/__init__.py`
- `bilqis_mlx/learning/atlas_readout/causal_training.py`
- `bilqis_mlx/learning/atlas_readout/records.py`
- `bilqis_mlx/learning/atlas_readout/tests/test_causal_training.py`
- `docs/tasks/bamf-0.2/children/B10.3.md`
- `docs/tasks/bamf-0.2/children/registry.json`
- `docs/evidence/bamf/B10.3/receipt.md`

## Owned behavior

The B10.3 slice extends the existing B10.1/B10.2 typed decoder without another
backbone or answer registry. Dependency feedback is derived only from declared
parents. Inference uses committed parent outputs. Training may substitute
teacher targets only for those declared parents; the current target and all
descendant targets are ignored by the feedback path and remain loss-only.

Structural parent values use a deterministic 768-wide signed SHA-256 expansion
of canonical typed JSON. A `ConceptRef` instead reads its exact active tied
identity row from the current semantic bank. Parent vectors are averaged and
projected through the declared 768x768 feedback matrix before RMS normalization.

Typed supervised loss masks every candidate outside the decision's released
legal-value set. A missing auxiliary label contributes exactly zero loss. An
illegal target fails closed rather than entering the objective. Invalid neural
decision output is rejected before state mutation and returned as the explicit
`BAMF_B10_NEURAL_OUTPUT_ILLEGAL` fallback request.

`TypedHeadLogits` accepts the decoder's typed VALUE-domain candidates
(`ConceptRef` and `RoleOccurrence`) in addition to native string labels and
`RoleCandidate`. Loss masking therefore operates on the actual typed legal
domain rather than coercing semantic VALUE identities into a string surrogate.

Existing B10.2 publication remains the final typed-answer gate. It validates
source-active semantic values, frame role/cardinality/source rules and
`END_FRAME` legality before producing a `FrameAnswer`.

## Red/green proof

Before the implementation existed:

`python3 -B -m pytest -q bilqis_mlx/learning/atlas_readout/tests/test_causal_training.py`

failed 5/5 cases with
`ModuleNotFoundError: bilqis_mlx.learning.atlas_readout.causal_training`.

After implementation:

- B10.3 focused: **10 passed**
- Complete compartmentalized atlas-readout suite: **51 passed + 39 subtests**
- Development structure: **0 violations**
- Governance integrity: **0 violations**
- Changed-file smell audit: **0 new findings**
- `git diff --check`: PASS

The tests prove that changing current/future gold cannot change the current
decision feedback state; training step 2 may use only a legal teacher-forced
step 1 target; inference step 2 uses committed predicted step 1; a forged parent
teacher target fails closed; ConceptRef feedback is the exact active tied
identity row and rejects active-set drift; illegal CONTROL logits are excluded
from loss with zero gradient; typed `ConceptRef` and `RoleOccurrence` VALUE
domains are accepted directly and illegal VALUE candidates are masked; missing
auxiliary labels contribute zero; and an
illegal neural output returns a fallback request without mutating the decode
state.

## Boundary

This candidate does not claim full B10 parent integration, learner improvement,
source promotion, checkpoint publication, or live training. Fresh independent
EGM remains required before #469 can be called acceptance-complete.

The parent `predict_typed` / `answer_loss` owner boundary is intentionally not
claimed by this leaf. B10.3 owns and directly tests `decision_hidden`,
`typed_decision_loss`, and `commit_neural_decision`; B10.4 plus the parent B10
integrator must compose them into the final owner API.

Next child after accepted #469: B10.4 / issue #470. Its turn-in must consume the
accepted B10.3 receipt before claiming its own dependency complete.
