# B10.3 causal typed-decoder candidate

- Issue: #469; parent B10 #367; Lane B
- Consumed unified: `9104ce733e04fb9c82420428b18dfdbf5db49535`
- Feature branch: `feature/bamf-b10-3-469-20261030`
- Learning state: software-only; no learner or optimizer mutation
- Independent EGM: pending

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

Existing B10.2 publication remains the final typed-answer gate. It validates
source-active semantic values, frame role/cardinality/source rules and
`END_FRAME` legality before producing a `FrameAnswer`.

## Red/green proof

Before the implementation existed:

`python3 -B -m pytest -q bilqis_mlx/learning/atlas_readout/tests/test_causal_training.py`

failed 5/5 cases with
`ModuleNotFoundError: bilqis_mlx.learning.atlas_readout.causal_training`.

After implementation:

- B10.3 focused: **8 passed**
- Complete compartmentalized atlas-readout suite: **49 passed + 39 subtests**
- Development structure: **0 violations**
- Governance integrity: **0 violations**
- Changed-file smell audit: **0 new findings**
- `git diff --check`: PASS

The tests prove that changing current/future gold cannot change the current
decision feedback state; training step 2 may use only a legal teacher-forced
step 1 target; inference step 2 uses committed predicted step 1; a forged parent
teacher target fails closed; ConceptRef feedback is the exact active tied
identity row and rejects active-set drift; illegal CONTROL logits are excluded
from loss with zero gradient; missing auxiliary labels contribute zero; and an
illegal neural output returns a fallback request without mutating the decode
state.

## Boundary

This candidate does not claim full B10 parent integration, learner improvement,
source promotion, checkpoint publication, or live training. Fresh independent
EGM remains required before #469 can be called acceptance-complete.
