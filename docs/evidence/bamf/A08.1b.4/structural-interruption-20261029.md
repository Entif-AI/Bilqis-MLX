# A08.1b.4 structural interruption | 2026-10-29

Issue: #556. This is a repository-structure checkpoint, not the scope/modality/time lesson implementation or an acceptance claim.

## Authority and entry state

- Original Lane A source head: `ff2857c`.
- Reviewed unified consumed: `3fe5b85`; the isolated candidate's merge commit is `59b99c2`.
- The shared Lane A worktree already had a separate in-progress merge, so this work used `codex/bamf02-a08-1b4-scope-20261029` without modifying that index or the unified trunk.
- `AGENTS.md` requires encounter-time interruption for a code file above 360 lines or a directory with at least 18 direct project-authored code files. The semantic source directory had 26 direct Python modules and its test directory had more than 18.

## Structural changes

- `cognitive_operators.py` (689 lines) was split into the stable `cognitive_operators` package: shared contract constants, typed operands, operator registry/source contracts, source authorization, pure computation, and execution. The old import path and source-authorized behavior are preserved. The implementation digest covers every package source file in deterministic order.
- The 588-line companion test file was split into four owner-mirrored test files; every resulting operator production/test file is below 240 lines. The independent unified-rooted review cut is draft PR #600.
- Thirteen existing oversized semantic subsystem modules were moved to same-name packages, retaining their Python import identities while establishing separate module ownership boundaries. Relative imports and source-pinned resource paths were adjusted. This directory-level move does not claim that the moved `__init__.py` files are below the separate file-size remediation threshold.
- The semantic test suite was grouped by `atlas`, `frames`, `cognition`, and `source`; existing test helper imports and physical fixture paths were updated. The two CI workflows' `test_domain_contracts.py` path was deliberately retained at its original location.
- After the directory repair, both `bilqis_mlx/semantics` and `bilqis_mlx/semantics/tests` have exactly 12 direct Python files. No recursive cleanup of the new directories was undertaken.

## Verification and holds

- Available semantics tests excluding nine suites requiring unavailable MLX/Torch/SymPy dependencies: **242 passed, 0 failed, 8 optional skips**. The complete initial discovery attempted 256 tests and had nine import/setup errors from missing external dependencies, not a confirmed semantic assertion regression.
- Adjacent cognitive solver, formal lesson/constructive and capability authority tests: **30 passed, 0 failed, 2 optional skips**.
- `scripts/check_module_size.py`: changed-path check reports zero violations; it does not prove the historical large-file debt is cleared.
- `scripts/check_semantic_boundaries.py` retains the three pre-existing `frame_adapters` source-adapter import-boundary findings. No new boundary finding was observed.
- Source admission, rights, neural training and learner-retention claims remain unchanged. A08.1b.4 still needs source-attested constructive lessons, typed checkers, variation witnesses and independent EGM.
- Next mandatory structural interruption: split a directly encountered oversized subsystem package and its companion tests below 240 lines before resuming the feature, then revalidate. No parent or lane PR is self-merged.
