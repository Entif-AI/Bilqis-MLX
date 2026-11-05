# Restore three script-test imports after canonical owner relocation

## Observed baseline failure

On reviewed unified `e58dd31574a6ee2ce0b3e35f92293a09befd15c1`, the canonical
script-suite selection has three load errors. Each also reproduces with the
original Git version of `scripts/run_tests.py`, before the #784 package-context
repair. This is an independent import-migration defect, not a #784 regression.

## Exact patch

Modify only these imports; preserve every other test-body AST node:

| Test file | Old import owner | Canonical existing owner |
| --- | --- | --- |
| `scripts/tests/test_audit_championship_quarantine.py` | `scripts.audit_championship_quarantine` | `scripts.operations.audit_championship_quarantine` |
| `scripts/tests/test_check_factory_workstack.py` | `scripts.check_factory_workstack` | `scripts.bamf.check_factory_workstack` |
| `scripts/tests/test_issue349_query_probe.py` | `scripts.issue349_query_probe` | `scripts.experiments.issue349_query_probe` |

Keep imported names unchanged: `audit`; `WorkstackError`, `ready_specs`,
`validate_manifest`; and `query_pair_scores`, respectively. Those definitions
exist at the canonical owners. Do not add duplicate compatibility modules,
change the runner, alter production script behavior, weaken assertions, rewrite
fixtures or modify governance baselines to clear these failures.

## Ordered acceptance

1. Preserve the three literal baseline `ModuleNotFoundError` failures using the
   original runner. Existing logs are in the #784 worktree under
   `.local/784-runner-context/baseline-affected-scripts.log`.
2. Change the three imports on a separate issue branch from the applicable lane
   integration branch synchronized to current reviewed unified. Verify import-
   normalized AST equality against the base for each changed test.
3. Run the three affected files with the original canonical runner and require
   their actual assertions to pass, not merely module import success.
4. Run the complete `scripts/tests` selection. Distinguish any unrelated baseline
   failure from these three repaired mechanisms rather than concealing it.
5. Run changed-scope structure/governance/hygiene/docs checks, preserve native
   source/ABI and operator boundaries, then independent pinned review and ready
   PR to unified. Accepted merge and explicit issue closeout remain separate.

PM-2026-11-01-007 records the repeated entrypoint/import failure family and has
been enriched with these exact baseline failures. This repair does not modify
actual students, native AdamW, teacher, source/graph/checkpoint state or authorize
training. IPR-0220 remains open. No self-merge authority is delegated.
