# C11.3 / #524 compatibility interruption checkpoint

Consumed unified and synchronized Lane C:
`3088ee02d085f2a88e53b7c78c8d9637916663fe`.

The runbook task encountered a 464-line historical release provider during
review. Its behavior now belongs to provider construction, course reconstruction,
successor planning, read-only preflight and historical receipt modules.
`compatibility/live_releases.py` remains a 35-line public import boundary.
Every extracted owner and focused companion is below 240 lines. All 26 original
production definitions retain identical AST bodies, except for the required
relative-import depth in moved lazy imports. All seven original focused test
methods retain identical ASTs; successor tests now mirror their owner.

The compatibility root also triggered the directory rule with 19 direct code
files. Eight modules moved byte-for-byte into historical-evidence and recovery
groups, reducing that root to 11 files. The existing package-search-path pattern
preserves canonical import names and relative imports without wrapper modules.
The settled-matchup companion follows its recovery owner.

## Validation

The structure check failed before the repair at 464 lines. The staged structure,
governance, strict code-smell, Factory architecture, documentation and diff checks
pass after the repair. The focused selection passes 33 tests with two unchanged
explicit full-Grade-B opt-in skips:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/factory/tests/lifecycle/test_live_release.py \
  bilqis_mlx/compatibility/live_release_parts/tests/test_succession.py \
  bilqis_mlx/runtime/tests/operator/test_admission.py \
  bilqis_mlx/presentation/operator_cli/tests/test_bamf_preflight.py \
  bilqis_mlx/compatibility/tests/_recovery/test_settled_matchup_recovery.py
```

A built wheel installed outside the source tree resolves all eight relocated
canonical imports, the historical Factory shim and the actual v2 held inspector.
The imported origin is checked against the installation directory. Inspection
returns HELD exit 2, zero neural updates and no created run directory.

With `BILQIS_FULL_GRADE_B_TESTS=1`, one historical frozen-hash assertion fails:
expected `b6904a67849a8788f90b0c62cdbd4b3abeb3f24e686cf11e289895991bda470a`,
observed `2825a4a4a4aa6b865a5da91a45fa96cee7b8671cf3361b714f3a2884d71707a3`.
The same assertion fails on untouched synchronized unified, where six of seven
original tests pass. The refactored affected selection passes 28 of 29 with that
same failure. The assertion, expected digest and opt-in policy remain unchanged.

## Independent review and remaining work

A fresh-context GPT-6.1 Terra High reviewer read the pinned Google EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` Codex instructions and the
codebase-details and comprehension personas. Final scoped review found no
concrete Blocker or Major. Review covered the extraction, public boundary and
subsequent byte-identical directory moves; tests and wheel proof above were run
by the implementing worker, not independently reproduced by that reviewer.

This is a behavior-preserving interruption checkpoint, not full #524 acceptance.
Work Stack preserves the runbook task and the other already-encountered
interruptions: `runtime/checkpoints.py`, `runtime/operating_loop.py` and
`factory/tests/test_live_profile_execution.py`. They remain required follow-up
before the original task resumes. No recursive debt census is authorized.
Source authority remains IPR-0220; no learner, optimizer, teacher, source release
or admission state changes.
