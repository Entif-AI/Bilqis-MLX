# BAMF-0.2 unified base | 2026-10-28

This branch is a selective composition for BAMF issues #341 through #545.

## Executable authority

The branch starts directly from Factory commit
`d84d2ab9e2d79817c131ef7e0d4ec0d574e57b32` on
`codex/337-replay-349-20261026`.

No `bilqis_mlx/` file differs from that Factory commit in this integration.
Newer `main` controller, trainer, scheduler, teacher, retention, admission, and
runtime code was not merged or copied into the branch.

## Imported source and planning surfaces

The New Ithkuil/SKOS corpus, ingestion Skill, fingerprint receipt, and SKOS test
policy come from `codex/338-skos-test-fingerprint-20261026` at
`36b5c2b954290264e24ff0e47b64a555ef9291bb`. The dedicated SKOS branch wins for
`lib/ithkuil/`, including its newer `RELEASE_REBUILD.md` test-tier contract.

The BAMF-0.2 architecture, planning evidence, recursive issue workstack, lane
instructions, and BAMF planning verification scripts come from
`codex/bamf02-specification-20261027` at
`6aa5ff386e9a3087822f8335ccf42754d94d1ff2`.

Root integration is additive. Factory `README.md`, `AGENTS.md`, `package.json`, and
portable CI remain the base. The unified branch adds scoped BAMF routing, SKOS npm
commands, SKOS CI verification, and the Ithkuil private-data ignore without
removing Factory commands or tests.

## Verification

- `scripts/verify_bamf_0_2_contracts.py`: pass, including all 43 owner issues and
  157 recursive child mirrors.
- `scripts/skos_test_policy.py status`: verified bundle unchanged,
  SHA-256 `572926819c70e390faf419c6fe522344fec7b9fe3a2c219d96a7b515c07e88ae`.
- SKOS runner/policy tests: 14 passed.
- `scripts/check_factory_architecture.py`: pass.
- `scripts/check_docs.py`: pass.
- `git diff --check`: pass.
- Diff against Factory under `bilqis_mlx/`: zero files.

A broader focused run passed 61 of 62 tests. The sole failure is the pre-existing
`EarlierGradeExpansionTests.test_additive_prior_grade_revision_preserves_frontier_and_adds_debt`
expectation already reproduced on the Factory lineage before this integration.
It is not caused by the unified branch.
