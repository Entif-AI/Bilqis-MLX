# B06.3 | Exact frame-bound local refinement

## Scope

This receipt covers issue #454 only: bind the existing B06 numerical recurrence
to the exact B03 frame/member outputs while preserving one already-computed
backbone result. It does not authenticate the origin of the backbone tensor,
invent requested-role feature authority, complete B06 parent integration, or run
the durable student.

Consumed reviewed unified and Lane B baseline:

`3088ee02d085f2a88e53b7c78c8d9637916663fe`

The final feature SHA is recorded after commit and remote verification; this
document does not use a working-tree state as a checkpoint identity.

## Assembly contract

`refine_selected` consumes:

- one complete immutable `[B,P,768]` backbone result;
- the original `CompiledEncoderInput`, `CompiledEmbeddingVectors`, and B03
  frame-encoder parameter view used to deterministically rederive the exact
  `FrameEncoding`;
- one B06.2 `RefinementChoice`;
- one upstream-produced finite FP32 requested-role 768-vector; and
- the existing B01-declared `refine.*` numerical parameters.

The selected neural position is resolved by exact compiled frame handle and
occurrence identity, never by treating B06.2 `source_position` as a tensor index.
The prediction boundary in the choice cache identity must equal the compiled B03
row boundary.

B06.3 does not accept a caller-supplied `FrameEncoding` as authority. It invokes
B03's own `encode_frames` path from the B03 inputs, so replacing a valid encoding
with altered seed/member tensors cannot affect refinement. B02/source ownership of
the supplied B03 input vectors remains an upstream boundary rather than being
reinvented here.

For a normal nonempty structural closure, exact member handles come from B03's
source-bound `FrameFactorTerms.requests`. For an atomic closure, they come from
the matching public `CompiledEncoderInput.atomic_handles` record. A legal empty
structural closure has no member handles and may take the exact zero-pass identity
path; a positive-pass empty attention request fails closed rather than inventing
keys or values.

The recurrence borrows the selected backbone value, rederived B03 frame seed and
immutable B03 member vectors. It returns a separate frozen `RefinementResult` and
has no writeback operation. It does not rerun the twelve-layer backbone.

The result's `refinement_key` extends the B06.2 prediction cache identity with
both the execution-local batch row index and the compiled row cache key. Two batch
rows may therefore share the same B06.2 four-tuple without aliasing prediction-
local refinement state.

## Verification

Failing-before witness:

The first focused B06.3 test run failed to import `refine_selected` from
`bilqis_mlx.runtime.atlas_refinement`, proving the production assembly boundary
did not exist before this change.

Current exact-tree tests after refreshing onto the reviewed unified trunk:

```sh
PYTHONPATH=/tmp/bamf-b14-testdeps:. python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/model/refinement \
  bilqis_mlx/runtime/tests/model/test_atlas_refinement.py \
  bilqis_mlx/runtime/tests/model/test_refinement_policy.py

PYTHONPATH=/tmp/bamf-b14-testdeps:. python3 -B scripts/run_tests.py \
  bilqis_mlx/learning/tests/frames \
  bilqis_mlx/learning/tests/test_frame_encoder.py

python3 -B scripts/check_module_size.py
python3 -B scripts/quality/check_governance_integrity.py \
  --base-ref origin/codex/bamf-unified-base-20261028
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check \
  --base-ref origin/codex/bamf-unified-base-20261028
git diff --check
```

Results:

- refinement execution, numerical kernel and B06.2 policy: **32/32 PASS**, zero skips;
- B03 nested/compiled frame proof: **7/7 PASS**, zero skips;
- development structure: **0 violations**;
- governance integrity: **0 violations**;
- factory architecture: **PASS**;
- docs: **PASS**;
- error control: **new debt 0**;
- diff check: **clean**.

The B06.3-focused adversaries prove exact B03 structural and atomic handle
binding, prediction-boundary mismatch rejection, non-aliasing batch-row result
keys, rejection of caller-replaced `FrameEncoding` evidence, zero-pass empty-frame
identity, positive-pass empty-frame rejection, immutable backbone/seed/member
inputs, prediction-local backbone gradients, and independence from unrelated
backbone positions.

## Remaining authority boundaries

B06.3 deliberately does not claim three authorities owned elsewhere:

- B05/B11 own trusted backbone execution provenance;
- the shared feature owner must supply the requested-role 768-vector; B06.3 does
  not map arbitrary role strings into learned vectors;
- final B06/B11/B13 integration and retained-generation custody remain parent or
  downstream obligations.

The issue-prescribed pinned Google EGM remains required for turn-in acceptance.
The current execution surface exposes no pinned Google EGM runner. Any additional
CoS review is defect-discovery evidence only and must remain labeled non-EGM.

No actual student, native AdamW, teacher, checkpoint, retained generation or
human-run state is modified. No self-merge.
