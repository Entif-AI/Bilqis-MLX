# #784 native package context for uniquely loaded test files

## Observed defect and owned outcome

The canonical file runner uses a top-level synthetic module name, so valid
relative helper imports fail despite working through dotted unittest loading.
Fix the responsible spec/name construction without rewriting affected source
fixtures, importing another test framework or changing production semantics.
The stable file basename remains `_bilqis_test_<SHA256(relative-path)>`.

Modify `scripts/run_tests.py` only at these responsibilities:

1. `_module_name` retains the original relative-path digest. If every parent path
   segment is a Python identifier, prepend the full native dotted parent package;
   otherwise keep the original top-level synthetic name. Root files also keep it.
2. Add `_verify_package_context(name, path, root)`. For each native parent prefix,
   use standard `importlib.util.find_spec` and `importlib.import_module`. Require
   the expected source directory first in both spec search locations and loaded
   `__path__`, with every allowed search path inside the repository root. This
   permits regular and PEP420 namespace packages, including legitimate additional
   namespace paths within the same repository, while rejecting foreign installed
   or cached parents without replacing them.
3. Check already cached descendants of the immediate parent against that parent's
   actual validated native search locations. A helper from an approved secondary
   namespace path remains legal; a helper outside all those paths fails closed.
   Do not replace unrelated cached helpers or globally clear package identities.
4. In `load_test_files`, verify native context before constructing/executing the
   test-module spec. Reject an existing synthetic name whose file differs from the
   selected file. Use the existing unique synthetic module object for discovery;
   keep `_local_test_suite` filtering by the complete new module name.
5. Account package/spec/execution failures through the existing `_LoadFailure`
   unittest path. If re-execution of the same file fails, restore its previous
   synthetic module entry; remove only the newly installed entry when none
   existed. Do not remove an unrelated module installed by another action.

Root precedence, ignored-directory selection, directory and dotted targets,
source-only geometry shim, duplicate-basename discovery, imported-TestCase
filtering, totals/error accounting and CLI exit behavior remain unchanged.
This is a compatible runner bug fix, with no model/release/schema change.

## Exact tests and ordered proof

Modify `scripts/tests/test_run_tests.py` to retain its existing tests and add the
preserved regular/namespace relative-helper regression with duplicate file
basenames, distinct helper values, deterministic unique loaded names and exact
`__package__`/`__spec__.parent` assertions. Use unique temporary package names;
do not intentionally shadow live repository packages in positive fixtures.
Create `scripts/tests/test_run_tests_package_collision.py` for installed/cached
parent/helper and synthetic-name collision rejection plus a two-file namespace
fixture using an allowed secondary in-repository helper path. Keep each source
and test owner below the encountered structure thresholds; no baseline waiver.

1. Run the preserved relative-import regression against original Git source
   `e58dd315`: regular and namespace variants must fail before the fix.
2. Verify the initial package-prefix-only candidate fails the three provenance
   adversaries. Verify the first strict cached-helper guard rejects the legal
   secondary-namespace two-file case before repairing it.
3. Run both runner test files: expect 14 passing tests, no skips. Check native
   helper values, package metadata, imported-TestCase filtering, root precedence,
   duplicate basenames, fallback root/nonpackage files and accounted load errors.
4. Run actual `learning/tests/motif_reads/test_gradients.py` and `test_guarded.py`
   with the canonically verified A01 artifact: expect five passes, zero skips.
   Their current imports are absolute, so this is compatibility/source proof;
   the literal synthetic fixtures establish relative-import behavior.
5. Stage new files before changed-file hygiene/structure/governance checks.
   Source tests remain unchanged. Run available branch gates and final fresh
   pinned EGM before opening a ready PR to unified. Human integration is separate.

## Preservation and boundaries

The initial two-file candidate is reused from the preserved 808a worktree. Its
unrelated dirty B/C flow records are not imported; all four original dirty files
remain byte-identical. Exact original hashes and full/scoped patches are saved
under the controlling worktree's `.local/784-recovery/`. The issue feature is
cloned from Lane B and consumes reviewed unified before adoption. Current flow
bookkeeping reconciles accepted PR830/836/808 to remove stale active inventory.

PM-2026-11-01-007 is enriched and natively read back for the recurring runner
mechanism. No new source qualification, actual student/native AdamW/teacher,
checkpoint, source/graph/archive, human-run or self-merge change. IPR-0220 remains
open; source fixture and admission authority remain separately enforced.
