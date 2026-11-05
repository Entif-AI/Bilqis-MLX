# #784 file runner package-context proof

Base: Lane B remote, synchronized to reviewed unified
`e58dd31574a6ee2ce0b3e35f92293a09befd15c1` before issue-owned edits.
Specification: `docs/tasks/bamf-0.2/followups/TEST_RUNNER_PACKAGE_CONTEXT_20261105.md`.

The preserved candidate is reused without changing the original 808a worktree's
four dirty files. Its source/test patch is isolated from stale B/C metadata.
New runner module names retain the original digest basename under the native
package. Package resolution and cached-helper provenance are validated through
standard specs/search paths; legitimate in-repository extended namespace paths
are retained. Unsafe foreign or synthetic collisions become ordinary unittest
load errors, leaving unrelated modules intact.

## Executed proof

- Original Git runner against the adopted regression: 9 tests, with both regular
  and namespace subcases failing relative import before the repair.
- Initial package-prefix candidate fails three installed/cached provenance
  adversaries before fail-closed checks.
- The first cached-helper guard rejects a legal two-file secondary namespace
  helper. Its red fixture precedes the validated-search-path repair.
- Final focused runner selection: 14/14, zero skips.
- Actual motif gradient/guarded selection: 5/5, zero skips, using the canonical
  A01 artifact verified by `load_pinned_atlas_snapshot` before testing.
- Original 808a four-file SHA readback: zero mismatches. No fixture body rewrite.

Reproduce:

```sh
python3 -B scripts/run_tests.py scripts/tests/test_run_tests.py scripts/tests/test_run_tests_package_collision.py
BILQIS_ATLAS_REAL_ARTIFACT=/private/tmp/bamf-a01-456-final/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7 python3 -B scripts/run_tests.py bilqis_mlx/learning/tests/motif_reads/test_gradients.py bilqis_mlx/learning/tests/motif_reads/test_guarded.py
```

The external path is an execution locator. Require bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`, release
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306` and source
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
A missing locator is not a passing source witness. Both current motif files use
absolute imports; the synthetic fixtures provide direct relative-import proof.

Detailed logs are local `.local/784-runner-context/{baseline-red,collision-red,extended-namespace-red,green,motif}.log`.
Final static gates, independent pinned review and hosted receipts are attached to
#784 at the exact durable head. PM-2026-11-01-007 has native ledger readback;
PM-2026-11-04-001/RC-144 tracked-input controls also apply. No actual learner,
native AdamW, teacher, source release, graph or checkpoint changed. IPR-0220
remains open; no source/learning/admission acceptance follows from runner proof.

## Broader existing-script check

The complete `scripts/tests` selection reports 165 passes and three load errors
(168 total, no skips). The same three import errors reproduce with the original
Git runner at unchanged base `e58dd315`: stale imports of
`scripts.audit_championship_quarantine`, `scripts.check_factory_workstack` and
`scripts.issue349_query_probe`. Their source files now live under `operations`,
`bamf` and `experiments`, respectively. No new regression is attributed to #784,
and no broad-suite PASS is claimed. The runner's required focused14/14 and actual
motif5/5 evidence remains distinct. Logs: `scripts-suite.log` and
`baseline-affected-scripts.log`. This independent import-migration repair needs a
bounded follow-up; source-owned test bodies are not rewritten to hide runner
context defects.
