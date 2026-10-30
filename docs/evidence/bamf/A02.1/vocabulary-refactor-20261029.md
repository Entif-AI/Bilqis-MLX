# A02 vocabulary maintenance refactor | 2026-10-29

- Issue: #399 (`A02.1 | Allocate stable semantic banks and activate admitted identity rows`).
- Maintenance branch: `codex/bamf02-a-399-vocabulary-refactor-20261029`.
- Immutable takeover base: `da0431bee37c0e4f766f05cc94ceb6b23ac7d054`.
- Scope: structural maintenance only. No live learner, optimizer, vocabulary admission,
  semantic release, merge, or shared Lane A mutation.

## Refactor shape

The paused maintenance target began with:

- `bilqis_mlx/semantics/atlas_vocabulary.py`: **452** lines;
- `bilqis_mlx/semantics/tests/test_atlas_vocabulary.py`: **425** lines.

The A02 implementation is now split under `bilqis_mlx/semantics/atlas/` into
mirrored responsibility modules. The largest vocabulary implementation module is
`vocabulary_staging.py` at **203** lines; planning is **135**, contracts **102**,
factors **35**, and the public vocabulary facade **21**. Existing resources and
transaction owners remain **193** and **128** lines.

The former 425-line vocabulary test is split under
`bilqis_mlx/semantics/tests/atlas/` into:

- `test_vocabulary_planning.py`: **189** lines;
- `test_vocabulary_staging.py`: **104** lines;
- `test_vocabulary_factors.py`: **89** lines;
- shared synthetic fixtures: **64** lines.

Related A02 mirrors remain below the same ceiling: resource tests **128**,
transaction tests **116**, and feature-I/O tests **238** lines. Every moved or
new source/test module in the affected Atlas/foundation organization is below
the requested **240-line** ceiling.

During the refactor the affected `bilqis_mlx/semantics/` directory was found to
contain **26** immediate first-party Python files. Per the maintenance gate it
was organized into the meaningful `semantics/atlas/` and
`semantics/foundation/` packages. The root now has exactly **12** immediate
Python files. Repository imports were migrated to the canonical physical
namespaces; stable semantic/provider identity strings retain their historical
logical names where those names are part of an evidence contract.

## Verification

The MLX/RDF-capable local runtime used for semantic tests was
`/private/tmp/bilqis-c-runtime-py312/bin/python`.

Focused A02/Atlas split suite:

- **22 passed, 0 failed, 2 skipped**;
- skips are the pre-existing optional real-A01 source-bundle witness and the
  explicit full 80M-parameter disposable B01 witness.

Adjacent behavior suites:

- cognitive DAG/operators, numeric/domain/memo/ABI: **76 passed, 2 skipped**;
- released frame schema + copular provider: **17 passed, 1 skipped**;
- factory/curriculum adjacency: **50 passed, 1 skipped**;
- runtime Atlas adapter + capability championship: **49 passed, 0 skipped**.

Full `bilqis_mlx/semantics/tests` sweep:

- **264 passed, 0 assertion failures, 12 skipped, 3 setup errors**;
- all three setup errors are environment-only: two legacy parity suites require
  unavailable `torch`, and one symbolic algebra suite requires unavailable
  `sympy`.

`git diff --check` passes. `compileall` over the affected production packages
passes.

Repository-wide static checks retain only pre-existing debt. This was verified
by running the same gates in a temporary detached worktree at the exact
`da0431b` base:

- module-size check: the same three inherited regressions
  (`curriculum/scheduler.py`, `learning/learning_experiment.py`, and
  `runtime/visits.py::_take_visit`);
- semantic-boundary check: the same three inherited `frame_adapters.py`
  source-adapter boundary findings;
- error-control check: the same inherited opaque/literal contract debt set.

No new A02/foundation path is named by those repository-wide failures.

## Turn-in limits

This receipt proves the structural split and behavior-preserving import/path
migration on the isolated maintenance branch only. It does not claim a new A02
semantic admission, parent closure, source-lane integration, merge authority, or
live training authority. The pull request remains draft for independent review.
