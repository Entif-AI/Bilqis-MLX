# Factory execution ownership extraction — #842

Reviewed unified and synchronized Lane A/C source: `e58dd31574a6ee2ce0b3e35f92293a09befd15c1`.
Issue branch: `codex/bamf02-a-842-execution-structure-20261105`.

The #785 selector trace encountered the 564-line execution owner and 634-line companion test. Its context is preserved in local validated Work Stack `785-execution-20261105`. The user's per-issue branch instruction supplies isolation for this interruption. No source/profile admission or #785/#490 acceptance is claimed.

Execution algorithms now have cohesive lineage, profiling, projection and compilation owners. Public profile/record classes remain in their historical module so class source inspection, patch lookup authority and canonical module/pickle identities remain available. Tests mirror those seams; the historical test entrypoint remains available. All 17 affected source/test files are below 240 physical lines. No size/debt baseline or governance threshold changes.

## Proof

- Before extraction: 26/26 execution and executable-release tests, zero skips.
- After extraction: 30/30 focused execution/package and executable-release tests, zero skips; includes four public contract regressions.
- Historical `python -m unittest bilqis_mlx.factory.tests.test_execution_plan`: 17/17. Imported class aliases are removed after aggregate construction to prevent duplicate discovery in that entrypoint.
- Real C02 consumer interface: 4/4, zero skips, using the pinned A01 artifact directory `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`.
- `verify_extraction.py`: all 25 original source definitions match ASTs after normalizing only declared facade global lookups `_api.NAME` back to `NAME`; all 17 existing test bodies and seven fixtures match without normalization. All 25 original public metadata/signature/annotation records match.
- Locally captured full, reduced, Boolean and delta canonical JSON and protocol-4 pickle bytes match pre-extraction snapshots in the same Python 3.14.4 interpreter. `baseline.json` records hashes; `snapshots.json` preserves all four pre-extraction literal JSON strings and protocol-4 pickle payloads as hexadecimal. The verifier reconstructs every representative, compares exact JSON/pickle bytes, and reads back each old payload. Pickle byte identity is scoped to the recorded interpreter, not a cross-version guarantee.
- Ordinary independent Terra review found no functional blocker. Its stale error-catalog finding was corrected: new files must enter Git's index before tracked-path generation. Regeneration retains all 2029 raw error sites, including all 28 moved raises; new debt zero. No raises were eliminated.

Run with repository test dependencies installed:

```sh
python3 -B docs/evidence/bamf/A06-842/verify_extraction.py
python3 -B scripts/run_tests.py bilqis_mlx/factory/tests/execution_plan bilqis_mlx/factory/tests/test_executable_release.py
python3 -B -m unittest bilqis_mlx.factory.tests.test_execution_plan
BILQIS_ATLAS_REAL_ARTIFACT=/path/to/pinned/artifact python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/batch/test_atlas_training_real_source.py
```

Use the historical test entrypoint or the split package, rather than both, when counting unique execution cases. The real fixture proves rejection/acceptance seams under its explicit test authority; it does not establish initial A06 selection authority. No student/AdamW, teacher, source release, admission, checkpoint, graph or human-run state changed. No self-merge.

## Review state

Round 1 at472989ac found a missing durable literal witness (MECHANICAL_PROOF). A reviewer source-inspection concern also reproduced OSError for public classes (TARGET_LOCAL). The repair keeps all 11 original classes in the 218-line public owner, adds source-inspection regression, and commits the original local literal snapshots. The source verifier now proves all25definitions across that owner and extracted algorithms. Aggregate EGM remains failed until a complete subsequent round; no PASS or merge readiness is claimed. Handoff #829 remains separately parked at its exhausted five-round cap; this Factory extraction does not continue or reset that episode.
