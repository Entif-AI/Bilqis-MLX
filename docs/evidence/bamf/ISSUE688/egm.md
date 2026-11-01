# Cognitive-package file-runner compatibility

[Issue #688](https://github.com/Entif-AI/Bilqis-MLX/issues/688) follows the
reviewed C12.1 manifest integration, PR #668, at
`f3ad98745cef78df87b60d39af4fc2adbb0a5787`.
Before issue-owned edits, Lane C consumed the newer reviewed unified
`97c9c54964059e72103eff7e7907d6d83f6ab11c`, which includes the accepted
#685 proof repair. The cognitive-package files are unchanged between these bases.

## Exact plan

Modify only the fixture import at line 4 of these existing files:

- `bilqis_mlx/runtime/cognitive_package/tests/test_contracts.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_staging.py`
- `bilqis_mlx/runtime/cognitive_package/tests/test_wire.py`

Replace `from .fixtures import ...` with
`from bilqis_mlx.runtime.cognitive_package.tests.fixtures import ...`.
Preserve the imported names, every test body and production files. Add no
fixture, loader modification, dependency or test case.

## Reproduction and verification

```sh
python3 -B scripts/run_tests.py bilqis_mlx/runtime/cognitive_package/tests/test_contracts.py bilqis_mlx/runtime/cognitive_package/tests/test_staging.py bilqis_mlx/runtime/cognitive_package/tests/test_wire.py bilqis_mlx/errors/tests/test_catalog.py
python3 -B -m unittest bilqis_mlx.runtime.cognitive_package.tests.test_contracts bilqis_mlx.runtime.cognitive_package.tests.test_staging bilqis_mlx.runtime.cognitive_package.tests.test_wire bilqis_mlx.errors.tests.test_catalog -q
```

Before repair, the first command records three catalog passes and three package
module load errors; the second passes 21 tests. The file runner assigns unique
module names, so package-relative imports have no parent package.
PM-2026-11-01-007 was filed/read back before repair; the linked issue supplies
the public reproduction and the retained failure-log filename.

After repair, require 21 passing tests from each command. Compare each original
test class AST against the base using `ast.dump(include_attributes=False)`;
only module-level fixture import paths may differ. Run changed-file
structure/governance/smell, Factory/docs/source/ABI checks and
`scripts/error_control_plane.py --check --base-ref 97c9c549`, plus diff hygiene.
Use the validation-output runner for long finite commands.

## Executed proof

Both commands pass all 21 tests, with zero skips/errors. AST comparison of each
entire module is identical after normalizing only the fixture import path.
Changed-file structure/governance/smell, Factory architecture, docs, semantic
boundaries, historical ABI and diff hygiene pass. Base-relative error control
reports zero new debt; inherited opaque-debt inventory remains unchanged.

## Review and scope

Pinned Google EGM: `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
Fresh-context readiness review returned PASS before implementation.
Separate fresh-context codebase/comprehension review returned PASS with no
Blocker, Major or Nit. The reviewer independently inspected the loader, sole
fixture, 21-test static inventory and normalized entire-module AST comparison.
It did not execute tests; executed runner results above are implementer proof.
This is test-entrypoint compatibility. C12 adoption/source/custody acceptance
remains with its existing owners; no production or actual student/own-AdamW
change is included. IPR-0220 applies.
