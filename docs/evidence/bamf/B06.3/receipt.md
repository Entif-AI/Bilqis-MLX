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

`refine_selected` now consumes:

- one complete immutable `[B,P,768]` backbone result;
- the original `CompiledEncoderInput`, B01/B03 parameter tree, exact source rows,
  and feature schema needed by the accepted source-revalidated B02/B03 producer;
- one B06.2 `RefinementChoice`;
- one upstream-produced finite FP32 requested-role 768-vector; and
- the existing B01-declared `refine.*` numerical parameters.

The selected neural position is resolved by exact compiled frame handle and
occurrence identity, never by treating B06.2 `source_position` as a tensor index.
The prediction boundary in the choice cache identity must equal the compiled B03
row boundary.

B06.3 no longer accepts `CompiledEmbeddingVectors` or a caller-supplied
`FrameEncoding` at all. The public `refine_selected` path calls the existing
source-owned `encode_source_compiled` producer itself. That producer revalidates
A05/A13 source identity and rights, derives B01/B02 vectors internally from the
actual parameter tree, then runs B03. The resulting live `FrameEncoding` remains
inside the production call rather than becoming a caller-mintable authority
credential.

This removes the two self-ratification forms reproduced during remediation rather
than attempting to sign them: a caller cannot alter B02 vectors and launder them
through generic B03 execution because no vector/encoding argument exists at the
public B06 boundary, and cannot mutate handle/factor metadata on a supposedly
trusted encoding because B06 does not accept one. The same live MLX tensors flow
directly from source-owned B02/B03 into B06, preserving gradients without a
detached receipt or copied numerical payload.

The source-owned producer intentionally holds native atomic-frame closures because
B03.2 explicitly left their numerical embedding origin to an upstream owner.
Production refinement therefore fails closed for that unresolved authority rather
than treating a caller-supplied atomic vector as source truth. The private
`_refine_selected` numerical fixture keeps the already-specified atomic/empty/
nested arithmetic regression coverage without granting those fixtures production
authority.

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

- refinement execution, numerical kernel and B06.2 policy: **34/34 PASS**, zero skips;
- B02/B03/source and frame proof: **30 PASS**, **5 explicit skips** because the
  real pinned A01 artifact is not mounted locally;
- development structure: **0 violations**;
- governance integrity: **0 violations**;
- factory architecture: **PASS**;
- docs: **PASS**;
- error control: **new debt 0**;
- diff check: **clean**.

The B06.3-focused adversaries prove exact B03 structural and atomic numerical
fixture behavior, prediction-boundary mismatch rejection, non-aliasing batch-row
result keys, absence of caller vector/encoding authority at the public API and
fail-closed invalid source inputs, zero-pass empty-frame identity, positive-pass empty-frame
rejection, immutable backbone/seed/member inputs, prediction-local backbone
gradients, B03 encoder-gradient continuity, and independence from unrelated
backbone positions. Real source-positive B02/B03 tests remain pinned-artifact
gated and are not replaced with mocked authority when that artifact is absent.

## Remaining authority boundaries

B06.3 deliberately does not claim three authorities owned elsewhere:

- B05/B11 own trusted backbone execution provenance;
- the shared feature owner must supply the requested-role 768-vector; B06.3 does
  not map arbitrary role strings into learned vectors;
- final B06/B11/B13 integration and retained-generation custody remain parent or
  downstream obligations.

The issue-prescribed pinned Google EGM remains required for turn-in acceptance,
but under the merged BAMF EGM policy it is a final merge-readiness gate, not a
per-fix regression loop. Ordinary engineering review, targeted regressions and CI
must clear the complete known defect set first; only the otherwise-ready exact PR
head receives the fresh final EGM pass.

No actual student, native AdamW, teacher, checkpoint, retained generation or
human-run state is modified. No self-merge.
