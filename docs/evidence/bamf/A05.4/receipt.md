# A05.4 partial visible forest revalidation | candidate receipt

- Issue: #575; parent A05 #357; originating blocker B03.3 #444.
- Isolated branch: `codex/bamf02-a05-4-partial-forest-20261029`.
- Base: freshly fetched `origin/codex/bamf02-a-semantics` at
  `9fa752b6410c8248aa784a361247a8a7230fb748`.
- Implementation commit:
  `ad14c7fc1bf1af3258cc7c9795e7ab4694c1dc31`.
- Independent EGM: **PENDING**.

## Source-owned contract

`bilqis_mlx/semantics/partial_visible_forest.py` adds
`PartialVisibleForestReceipt`, `HiddenParentProvenance`, and
`validate_partial_visible_forest(compiled, source_ast, compiler_config,
expected_receipt=None)`.

`frame_compiler.validate_partial_visible_forest` is a narrow compatibility
entrypoint. It does not weaken `compile_prefix`: reconstructing the prefix-4
child as an ordinary temporary source root still fails with
`BAMF_PREFIX_ROOT_PARENT_INVALID`.

The validator instead consumes the already accepted A05 `CompiledFrameBatch`
plus its full source-owned `StreamingAST` and `FrameCompilerConfig`. It:

- reuses the accepted A05 prefix compilation and reconstruction;
- validates the original full source tree and exact nested parent relation;
- keeps the visible child's original `parent_occurrence_id` unchanged;
- returns only source-visible frame trees and visible frame handles;
- records a hidden parent as opaque provenance, never as a synthetic frame;
- binds hidden parent source locus, structural path, schema/scope, release,
  source handle and policy/rights/correction authority in a digest;
- deliberately excludes hidden parent bindings, content digest and member
  handles from the receipt so future member content cannot enter the child-only
  prefix contract;
- optionally revalidates an earlier receipt and fails closed on provenance
  drift.

Schemas:

- `bilqis.partial-visible-parent/v1`
- `bilqis.partial-visible-forest-receipt/v1`

This contract grants no neural admission, learning credit, source-rights
expansion or optimizer authority.

## Acceptance evidence

Failing-before owner run after adding the #575 tests and before production code:

- existing A05 tests: **20 passed**;
- new #575 tests: **4 errors**, all solely because
  `frame_compiler.validate_partial_visible_forest` did not yet exist.

Final owner `test_frame_compiler.py`: **25 passed, 0 failed, 0 skipped**.
The discriminating witnesses prove:

- the B03.3 nested witness: child closes at prefix 4 and parent at prefix 8;
- prefix 4 accepts the child as a partial-forest root while preserving the real
  parent occurrence ID;
- the legacy temporary-root compile path remains fail-closed rather than being
  relaxed;
- a forged/nonexistent parent occurrence fails with
  `BAMF_PREFIX_PARTIAL_PARENT_ORPHAN`;
- source-instance and hidden parent source-locus drift fail closed;
- hidden parent schema-scope drift invalidates the prior receipt;
- task scope and semantic-release drift fail closed;
- prefix 3 contains no future frame, prefix 4 contains only the child, and
  prefix 8 returns the normal full parent/child tree with unchanged occurrence
  and content identities;
- changing valid hidden parent member content changes the hidden parent's full
  content digest but leaves the prefix-4 compiler object and partial-forest
  receipt identical.

Adjacent source-owner suites on the same isolated worktree:

- A03 `test_frame_schema.py`: **14 passed, 1 intentional real-Atlas skip**;
- A04 `test_frame_codec.py`: **17 passed**;
- released frame adapters: **11 passed**;
- A13 `test_context_eligibility.py`: **21 passed**.

`git diff --check` passes. `partial_visible_forest.py` is 345 lines and
`frame_compiler.py` is 1,029 lines, both below the 1,200-line module hard limit.
The repository-wide module-size check still reports the three pre-existing
unrelated regressions in `curriculum/scheduler.py`,
`learning/learning_experiment.py`, and `runtime/visits.py::_take_visit`.
The repository-wide error-control check likewise reports only pre-existing
unrelated debt and no A05.4 path.

## Remaining gates

Fresh independent EGM is required before Lane A integration. B03.3 #444 must
rerun its child-only future-isolation and nested-gradient proof against this
exact source contract after review. No live learner/training, parent A05 close,
shared Lane A mutation, PR merge or unified integration is authorized or claimed
by this candidate.
