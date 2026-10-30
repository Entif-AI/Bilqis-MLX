# C11.1 command-boundary structure checkpoint

Date: 2026-10-30. Issue: #522; parent: #384; lane: #344.

## Baseline and scope

Lane C consumed unified `9104ce733e04fb9c82420428b18dfdbf5db49535` in merge
`89398df8686a288d2ce77e65e68b847228ba9af2`, pushed and independently read back.
The per-issue branch `codex/bamf02-c11-522-cli-20261030` starts from that lane merge.
No main or other implementation lane was imported.

Inspection encountered the 844-line CLI and 785-line companion. Pre-commit then
identified the crowded package, runtime-test, and integration-test roots. The CLI
now delegates to cohesive parser, inspection, preflight, lifecycle, terminal and
command owners, with matching focused tests. Original CLI functions, flags,
comments, status payloads and operator safeguards remain available. Historical
labels live under the compatibility boundary.

The package root has 12 direct Python files; runtime and runtime-test roots each
have 12. Integration tests are grouped by operator, experiment and migration
ownership. Canonical module names survive through explicit package search paths;
alternate physical module names cannot create duplicate owners. Source fingerprints
retain their logical keys while resolving actual module bytes. Architecture checks
follow the relocated owners without weakening their rules.

## Reused same-lane structure

Reviewed pure structural patches from #620/#614 were reused with their provenance:
`db24cfa0`, `e80e983b`, `f248d020`, `557663d0`, `de5467f7`, `113d43a2`,
`9710f1ea`, `b591cf2c`, `278b67d9`, `8dfef6f3`, `a131aea8`, `9b629388`,
`5b7e6793`, `cabd7a7b`, `776ba256`, `da693249`, `93e67ed2`, `e7d188d5`,
`bd466a98`, `6d4c400d`, `a1f6c852`, and `99f30680`.
The #521 behavior patches `a0891dec` and `ff96a5e0` were not imported. The original
C10 outbox behavior is preserved by `8dfef6f3`; #520 atomic-batch work remains separate.

Packaging discovers the real Bilqis subpackages and required Ithkuil compiler
namespace. The installed-wheel regression first failed because the donor namespace
was absent; after including that namespace it passes outside the checkout. This
proves import/source identity, not a complete external corpus or live run distribution.

## Verification

Use Python with cryptography, numpy, rdflib and pyshacl; source-law tests additionally
need sympy. The local verification environment was `/private/tmp/bamf521-venv`;
extra test dependencies were isolated outside the checkout.

- CLI/stop/dashboard/admission boundary selection: 62 passed, 1 optional historical-source skip.
- Admission, batch, correction, grouped identity and root-source tests: 100 passed, no skips.
- Actual portable workflow selection: 96 passed, 18 existing skips, no failures/errors.
- Source verification and historical Boolean migration selection: 36 passed, 2 opt-in historical skips.
- Installed wheel, outside the checkout: 9 passed, no skips.
- Staged structure and governance: zero violations. Changed-file hygiene: zero new findings. Docs: PASS.

Reproduce the boundary proof with:

```sh
python3 -B scripts/run_tests.py bilqis_mlx/presentation/operator_cli/tests bilqis_mlx/tests/test_paths.py tests/integration/operator/test_operator.py tests/integration/operator/test_training_stop_reason.py bilqis_mlx/presentation/tests/test_operator_dashboard_events.py bilqis_mlx/presentation/tests/test_operator_dashboard_titles.py bilqis_mlx/runtime/tests/operator/test_explain_cli.py bilqis_mlx/runtime/tests/operator/test_admission.py
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/admission bilqis_mlx/runtime/tests/batch bilqis_mlx/runtime/tests/correction bilqis_mlx/runtime/tests/projection/test_grouped_runtime_identity.py
python3 -B scripts/check_module_size.py --changed-from 89398df
python3 -B scripts/quality/check_governance_integrity.py --base-ref 89398df
python3 -B scripts/code_smell_audit.py --changed-from 89398df --check-baseline docs/evidence/development/code_smell_baseline.json
```

For distribution, build a wheel, install it into an isolated environment with the
stated dependencies, leave the checkout and run:

```sh
python3 -B -m unittest bilqis_mlx.tests.test_paths bilqis_mlx.runtime.tests.projection.test_grouped_runtime_identity -v
```

Do not sum overlapping selections as distinct test cases. No real student, AdamW,
graph service, or durable training run was mutated.

## Open acceptance and continuation

This checkpoint does not complete #522. Production BAMF create/resume still fails
closed at the existing B13 model-generation and A12/source-admission boundaries.
A release manifest is not a disposable lease; no alias or invented live authority
has been added. The parser still uses its existing admitted contracts.

Factory architecture retains the inherited `GENERIC_GRADE_IDENTITY_DISPATCH A,B`
finding in `runtime/model_topology_v2.py`. Factory closure retains four inherited
findings. The architecture package test consequently remains red. These gates
were not weakened or rebased.

Further directly encountered oversized files are preserved in Work Stack
`214f40fc-1f89-49d9-b0fe-cae141d17ed9`: the existing package-root state/data/compiler/
registry/coverage/generation/parity owners and the numeric-staircase integration
companion. Handle them as subsequent single interruptions, not a recursive sweep.
Full #522/#384 and integrated BAMF acceptance remain open. Human review/merge and
the durable-student start remain separate authority.

## Numeric companion continuation

The next 736-line numeric-staircase integration companion is split by enrollment,
checkpoint/answer custody, and numeric profile/preview behavior. The original is
109 lines; every extracted fixture/test is below 240. A fresh-context Goldfish
verified all 21 original methods once, all 13 test methods AST-identical, and the
sole fixture adjustment from physical `__file__` ancestry to canonical `REPO_ROOT`.

Both clean Lane C `89398df` and this candidate were exercised on isolated M3
snapshots using the same MLX environment and deterministic public fixtures. Before:
13 total, 5 passed, 5 assertion failures and 3 errors. After: 13 total, 6 passed,
5 assertion failures and 2 errors. No new nonpassing test identity appeared. This
is structural non-regression evidence, not a green numeric lifecycle suite. The
remaining boundary/progression fixture failures stay open. Local CPU discovery
also preserves all 13 tests; it cannot execute their MLX fixtures.

Exact nonpassing identities and machine-readable totals are in
`numeric-structure-result.json`. Hosted run `41105548030` failed on the inherited
`GENERIC_GRADE_IDENTITY_DISPATCH A,B` architecture finding; that failure is not
waived by the independently passing portable test selection.

## Generated-test owner continuation

The next encountered `semantic_test_generation.py` owner was 399 lines. Its
71-line public CLI now imports cohesive contracts, case construction, storage,
publication and validation modules. Every owner and mirrored companion is below
240 lines. All seven historical test methods are retained unchanged.

Five independent contract-fixture tests pass. The immutable manifest, pointer and
Boolean-suite bytes match a fixture captured before extraction exactly; restart,
tampered gold and interrupted pointer replacement are exercised against real
filesystem artifacts. These are explicitly declared software contract fixtures,
not source admission or retained-learning evidence. Normal commands still require
explicit regeneration before writing artifacts.

The original source-backed tests were attempted before mutation. Their setup is
blocked by the absent pinned historical `student-116760-7e9af4651f28.pt`; installing
the test-only Torch dependency did not waive that check. This witness is a limit
of these historical generated-test proofs, not a new BAMF/C16 prerequisite. No
historical checkpoint was substituted or manufactured.

Fresh-context EGM comparison preserved all 15 original functions/classes and all
seven test methods. The only function-body difference names the identical
repeated unsafe-release error string once. Original comments, selectors, CLI,
serialization and atomic publication are preserved. No Blockers/Majors found;
reviewers did not execute the writer's tests. Staged structure/governance and
changed-file hygiene remain clean.
