# B06.3 | Exact frame-bound local refinement

## Scope

This receipt covers issue #454 only: bind the existing B06 numerical recurrence
to the exact B03 frame/member outputs while preserving one already-computed
backbone result. It does not authenticate the origin of the backbone tensor,
invent requested-role feature authority, complete B06 parent integration, or run
the durable student.

Consumed reviewed unified and Lane B baseline:

`48315ee7bae3caa7d5ac279128c79217b9178d16`

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

The 2026-11-03 current-unified reconciliation exposed one more authority drop in
that source path: the pinned `AtlasArtifactSelection` carried by `SourceAtomRow`
was consumed while revalidating raw atoms, but was not forwarded when B02/B03
rederived member and frame factors. Source-qualified formal types therefore
failed closed inside `_pinned_source_types` even for a genuine pinned A01 source.
The source encoder now transports that already-validated selection through
`embed_atoms` and the compiled `encode_frames` path into `frame_factor_terms`.
Ordinary B06 callers still cannot provide an Atlas selection, vector set, or
`FrameEncoding`; the authority originates only from the source row that the
producer independently revalidates. A batched source encoding must also use one
identical pinned selection across every row.

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

Current exact-tree tests on current unified:

```sh
BILQIS_A01_ATLAS_BUNDLE=/private/tmp/bamf-b06-a01-artifact/\
5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7 \
PYTHONPATH=. /private/tmp/bamf769-verify-venv/bin/python -B \
  scripts/run_tests.py \
  bilqis_mlx/runtime/tests/model/refinement \
  bilqis_mlx/runtime/tests/model/test_atlas_refinement.py \
  bilqis_mlx/runtime/tests/model/test_refinement_policy.py \
  bilqis_mlx/learning/source_atoms/tests/test_encoding.py \
  bilqis_mlx/learning/frame_embeddings/tests/test_source_bound_literal_factor.py

python3 -B scripts/check_module_size.py
python3 -B scripts/quality/check_governance_integrity.py \
  --base-ref origin/codex/bamf-unified-base-20261028
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check \
  --base-ref origin/codex/bamf-unified-base-20261028
git diff --check
```

Before that run, `scripts/bamf/rebuild_atlas_artifact.py` reproduced the registered
A01 artifact from the retained source bundle and required the exact recorded
identities: artifact bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`,
and source bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
This is a disposable source witness, not neural admission.

Results:

- B06 refinement, policy, source-owned B02/B03 encoding, and factor composition:
  **52/52 PASS**, **0 skips**;
- the new source-positive cases execute public `refine_selected` through the
  genuine pinned A01 source path and prove gradients reach source-owned identity/
  feature coordinates and B06 refinement parameters;
- a wider source/frame run executed **41 behavioral tests successfully** before
  four pre-existing package-relative-import loader errors in source-atom test
  modules; issue #778 / PR #779 independently owns that canonical-runner defect,
  so this branch does not duplicate its repair;
- development structure: **0 violations**;
- governance integrity: **0 violations**;
- factory architecture: **PASS**;
- docs: **PASS**;
- error control: **new debt 0**;
- code-smell changed scope: **0 findings**;
- flow-control policy tests: **13/13 PASS**;
- live flow-control is reconciled separately against the current open PR inventory;
- `git diff --check`: **PASS**.

The B06.3-focused adversaries prove exact B03 structural and atomic numerical
fixture behavior, prediction-boundary mismatch rejection, non-aliasing batch-row
result keys, absence of caller vector/encoding authority at the public API and
fail-closed invalid source inputs, zero-pass empty-frame identity, positive-pass empty-frame
rejection, immutable backbone/seed/member inputs, prediction-local backbone
gradients, B03 encoder-gradient continuity, and independence from unrelated
backbone positions. The source-positive test is explicitly pinned-artifact gated;
when the witness is present it runs with zero skips, and it is never replaced with
mocked source authority.

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
