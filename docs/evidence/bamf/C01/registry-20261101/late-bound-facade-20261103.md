# C01 late-bound public-facade dependency repair — 3 November 2026

Issue #800 repairs the dependency-semantics regression introduced by the C01
structural extraction.  The extracted compiler, partial-visible-forest, frame-schema
and released-schema owners had retained Python function objects in private module
globals.  Patching a dependency on the historical public facade could therefore stop
affecting the relocated implementation even though callable identity remained public.

## Authority and lineage

- Reviewed unified consumed before feature edits:
  `7984d7872d49b3987284692f5398da71f2a72605`.
- The #347 attempt4 structural parent `2765b5df6ce0a23c9388800c13375ac2f67a98b3`
  is not an ancestor of reviewed unified, so #347 remains a separate integration
  candidate rather than accepted unified authority.
- This isolated continuation merged reviewed unified without rebasing.  The merge
  commit is `37060b3d6730d174253c59bcfd77de0bfdd46cc1`.
- Semantic repair checkpoint:
  `d2d88078a042687ebfad49586735b66a8c5d4926`.
- Branch: `codex/800-c01-latebound-20261103`.

The merge-forward reconciled live flow bookkeeping after human merge of PR #690.
During verification, concurrent PR #802 appeared in Lane B; the branch imported only
its public flow-control inventory row.  Live flow then reported one open integration
PR of three permitted and one active Lane C writer.

## Repair

`bilqis_mlx.semantics._public_identity.facade_dependency.public_facade()` resolves
the canonical public module at call time.  Extracted owners now use `_public().name`
for dependencies that historically lived on their public facade.  The relocated
function and class objects themselves remain the same objects; no wrapper functions,
`__globals__` mutation or runtime code rewriting is introduced.

The dependency census is recursive over nested code objects.  This is important:
the first direct-bytecode-only implementation missed seven live routes inside nested
functions/generator expressions.  The recursive regression exposed those routes and
they were repaired before this checkpoint.  The issue's historical census was 168
captured facade-callable routes across the four owner families (50 compiler, 25
partial forest, 55 frame schema, 38 released schemas).  The repaired recursive census
reports zero unresolved routes.  Synthetic regressions prove that a deliberately
captured global is detected, including a nested capture, while explicit live public
lookup is not falsely classified.

Literal runtime sentinels prove call-time lookup through the real consumers:

- compiler `project_context` injection reaches public `compile_prefix`;
- partial-forest `reconstruct` and `compile_prefix` injections reach
  `validate_partial_visible_forest`;
- released-schema Atlas and manifest loader injections reach the pinned source path;
- frame-schema `_fail` injection reaches the canonical schema constructor.

## Exact semantic verification

Focused late-binding selection: 16 tests, 15 pass and one optional real-artifact skip.
The skipped released-schema pin test was then rerun with the exact A01 artifact and
passed 5/5 with no skips.

The complete C01 source-owned selection was run with the existing exact A01 Atlas
artifact and exact conformance corpus.  Result:

`TEST_TOTALS total=200 passed=200 failed=0 skipped=0 errors=0`

The current total exceeds the historical 187-case C01 receipt because reviewed
unified and this repair add regressions; the same source-owned families and exact
source authorities remain in the selection.

Native frame callers were rerun using the existing Python 3.14 MLX environment:

`TEST_TOTALS total=6 passed=6 failed=0 skipped=0 errors=0`

No learner update, optimizer update, teacher mutation, checkpoint mutation or
`--human-run` occurred.

## Fresh archive and installed-wheel proof

Exact semantic commit `d2d88078a042687ebfad49586735b66a8c5d4926` was exported with
`git archive`, built in an isolated Python 3.14 build-only environment and installed
into a fresh target consumed from outside the checkout.

- Wheel: `bilqis_mlx_private-0.5.0-py3-none-any.whl`.
- Wheel SHA-256:
  `cade4199837fd124db1a650ba49f18c9d51e48659237a022388d7da1358d0475`.
- Installed selection: `126` tests, zero failures, zero errors, zero skips.
- Every loaded `bilqis_mlx` module and namespace path resolved inside the fresh
  installed target.
- The one repository-only IO fixture remains deliberately excluded from the installed
  probe, as in the established C01 installed-wheel contract; its source-tree owner is
  covered by the no-skip source selection above.

## Quality and structural gates

- Development structure: `violations=0`.
- Every touched production Python file is below 240 lines.
- Every touched directory remains below the 18-direct-authored-file interruption
  threshold; no directory reorganization is required.
- Governance integrity: zero violations.
- Factory architecture: pass.
- Documentation check: pass.
- Changed-scope smell audit: zero findings.
- Base-aware error control against reviewed unified: zero new debt.
- `git diff --check`: clean.
- Public/private-material screen of the feature diff: clean.
- Live flow-control: pass; integration inventory 1/3, mode NORMAL.
- Flow-control regressions: 6/6 pass.

The repository-wide unscoped error-control command still reports inherited opaque
error debt that is also present on pristine reviewed unified.  The required
base-aware command reports `new debt 0`.  A broad all-semantics convenience run also
encountered missing optional local packages and two transitive-import guard failures;
both import-guard failures reproduce unchanged on pristine reviewed unified and are
not introduced by #800.  They are not represented as passing #800 evidence.

## Remaining parent obligation

This receipt closes only the #800 facade-dependency repair body.  #347 remains the
aggregate structural candidate and still owns exact-current-unified integration,
hosted checks and the fresh pinned exact-head EGM before any parent turn-in.  Nothing
in this receipt merges or closes a PR or issue.
