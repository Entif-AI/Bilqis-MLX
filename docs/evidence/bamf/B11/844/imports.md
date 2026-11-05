# #844 canonical script helper import migration

Base: Lane B synchronized to reviewed unified
`e58dd31574a6ee2ce0b3e35f92293a09befd15c1`.
Specification: `docs/tasks/bamf-0.2/followups/SCRIPT_HELPER_IMPORTS_20261105.md`.

Only the three documented test import owners change. Imported symbols and every
non-import AST node remain equal to the base. No production script, runner,
fixture behavior, assertion, source policy or governance baseline changes.

Executed red/green proof in this independent worktree, using the unchanged
canonical runner:

- Before the import repair: exactly three `ModuleNotFoundError` load failures.
- After repair: affected assertions pass 12/12, zero skips.
- Complete `scripts/tests` selection: 171/171, zero skips.
- Import-normalized AST comparison to the exact base: all three files equal.

Reproduce:

```sh
python3 -B scripts/run_tests.py scripts/tests/test_audit_championship_quarantine.py scripts/tests/test_check_factory_workstack.py scripts/tests/test_issue349_query_probe.py
python3 -B scripts/run_tests.py scripts/tests
```

Local full logs are `.local/844-script-imports/{red,green,scripts-suite}.log`.
The #784 relative-import repair is independent; this branch does not consume its
runner changes. Its different focused cases/counts must not be substituted for
this branch's actual assertions. Flow-only metadata reconciles previously
accepted PR830/836/808 and represents independently active #784.

Final structure/governance/hygiene/docs/static flow and pinned independent review
are reported on #844 at the durable head. PM-2026-11-01-007 has native ledger
readback for the observed baseline. No new source qualification or actual
student/native AdamW/teacher/checkpoint/graph/source mutation. IPR-0220 remains
open; human integration is separate from review readiness.
