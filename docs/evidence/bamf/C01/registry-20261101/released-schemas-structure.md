# C01 released-schema structural interruption — 1 November 2026

Work Stack `59d77f15-1d25-4af5-9527-de2939b126de`, task
`struct-released-schemas`, follows committed compiler and partial-forest repairs.
Receipt-normalization feature work remains paused. Frame schema and frame codec
are the two remaining encountered offenders after this checkpoint.

The original417-line production module is a55-line compatibility facade. Owners
separate JSON/error/constants contracts, frozen schema records, artifact IO and
repository pin lookup. Largest source owner154lines; largest mirrored companion149.
The original331-line test module becomes a five-line fixture facade. All9original
methods/decorators/assertions/comments remain once. Three additional cases cover
duplicate/non-object JSON typed rejection and canonical record/pickle identity.

All original production ASTs remain identical except the two planned data-resource
anchors. They still read the same semantic-package pin ledger and release directory;
only source-code-relative path calculation changes. Independent A01 validation
still precedes A03 authority. Hashes, canonical bytes, source rights, symlink checks,
errors, class/callable identities and original private exports remain unchanged.

Verification:

- Original real-artifact baseline9/9, no skips; new contract/identity baseline3/3.
- Models/contracts extraction11/11; untouched expensive pin lookup was excluded
  only from this intermediate selection.
- Final released-schema selection12/12 from cwd`/tmp`, with the real independently
  pinned digest-named A01 artifact and actual micro/Boolean/numeric families.
- Compiler/partial-forest/source-binding/BAMF selection109/109; total121 across
  these two selections, zero failures/skips.
- Staged structure/hygiene PASS:13Pythonfiles, zero findings/new debt. Architecture,
  governance, docs, error-control and diff whitespace PASS.
- Fresh independent readiness review cleared its initial ownership/count gaps.
  Fresh implementation review found zero Blockers/Majors and one duplicate-import
  Nit; that redundant import was removed without changing any test body. Reviews
  were read-only and did not execute tests.
- Exact-candidate native proof is required before complete scoped verification.

Foreign-CWD command, run from `/tmp`:

```sh
: "${REPO_ROOT:?Set REPO_ROOT to the verified checkout}"
: "${BILQIS_ATLAS_REAL_ARTIFACT:?Set the verified A01 artifact directory}"
: "${PORTABLE_PYTHON:?Set the tested portable Python interpreter}"
"$PORTABLE_PYTHON" -B "$REPO_ROOT/scripts/run_tests.py" \
  "$REPO_ROOT/bilqis_mlx/semantics/tests/released_schemas"
```

Both runner and target are absolute because the existing runner resolves path
targets relative to cwd. A relative-target attempt failed before test imports;
no runner change was needed. A non-digest-named artifact alias correctly rejected
with `ATLAS_SNAPSHOT_BUNDLE_PATH_INVALID`; the accepted digest-named path passes.
Neither invocation failure is described as a source-code regression.

Consumes reviewed unified/LaneC`bd62f3cb`, on the existing C01 branch/draftPR694.
No threshold/baseline, learner, AdamW, training, graph or source-admission change.
Full347 stays open with eight holds/order=[]; this structural proof does not settle
those remaining interface gates.

Exact source commit`ff2fc3d6` passed the native M3 six-case encoder/member/execution
selection with no skips in a detached checkout populated from its commit bundle.
The sovereign MLX test lease was used. Cumulative changed-from-unified structure
and hygiene pass across58Pythonfiles with zero findings/new debt. Independent
review rechecked the duplicate-import repair and reports no remaining findings.
Unified was fetched again and remains`bd62f3cb`; PR694 remains an open draft.
