# B03.3 structure prerequisite

Issue #444 consumes reviewed unified and Lane B head
`d468b1af1c70a8dc0c0a7aa5ffa6d19b55cb2e18`. Its former source blockers
#575 and #576 are accepted through unified merges `c3fab66` and `9077f2e`.
The current owner direction uses a separate issue branch and PR to unified.

## Observed behavior and bounded change

The existing compiled encoder already computes nested child seeds before their
parent, preserves source/parent/scope sidecars, returns the compiler's original
rows and excludes padding from compiler statistics. The initial focused baseline
passed 48 tests with zero failures/skips. This checkpoint changes structure only.

The encounter-time rule requires an oversized encoder and its companion suites
to be split before adding the remaining #444 acceptance assertions. The encoder
is now a package with distinct input/output contracts, current-source validation,
embedding-vector contracts, numerical equations, compiled execution and public
dispatch, including source-bound member gathering. Every extracted encoder module is below 240 lines. Existing public
imports and class pickle identities remain stable.

The learning root and test root each have at most 12 direct Python files. Existing short
modules move into atlas, championship, teacher and core compartments. Original
logical import names remain canonical through explicit package search paths;
physical production namespaces reject imports before a second module identity
can be created. The frame companion tests use shared non-TestCase fixtures and
separate kernel/input/compiled and nested-gradient/visibility suites. Original
fixture import names remain available. Relocated fixture paths still resolve
against the same tracked data.

The source-bound `teacher_observations.py` and `source_selection.py` remain byte-identical at their original physical paths. The motif-key/allocation and stagnation owners instead become cohesive packages with mirrored companion suites, keeping those receipt paths intact. The actual `policy_epoch` consumer has a regression test covering its complete source-owner key set. Near miss PM-2026-10-30-002 was filed and read back in the native ledger before repair.

No source algorithm, source release, token identity, tensor equation, teacher
policy, optimizer state or durable student changes. AXI disposition:
`NOT_AGENT_FACING`; this preserves internal Python interfaces.

## Reproducible validation

From the issue branch, run:

```bash
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py bilqis_mlx/learning/tests
python3 -B scripts/check_module_size.py --changed-from origin/codex/bamf-unified-base-20261028
python3 -B scripts/check_module_size.py bilqis_mlx/learning bilqis_mlx/learning/tests
python3 -B scripts/quality/check_governance_integrity.py --base-ref origin/codex/bamf-unified-base-20261028
python3 -B scripts/check_historical_abi.py
git diff --check
```

Final repaired proof: 366 passed, zero failed, one skipped (367 total), including the actual source-receipt consumer test. Staged structure, explicit learning-root checks, governance and changed-file hygiene pass with zero new findings. The skip requires the real pinned A01 artifact via `BILQIS_ATLAS_REAL_ARTIFACT`; its source-neural admission remains outside this structural checkpoint. The import-identity tests check canonical versus forbidden
physical paths and round-trip original class pickle identities. The historical
ABI source check passes in advisory mode: no external expected fingerprint was
provided, so independent fingerprint enforcement is not established.

## Remaining gates

This is a **structural prerequisite**, not #444 completion. Fresh independent
implementation review found a source-receipt path blocker; the byte-identical physical paths are restored and targeted re-review reports no remaining Blocker/Major in this structural prerequisite (see `egm.md`). The directly encountered semantic compiler,
codec and companion suites also require splitting; their prepared extraction is
preserved locally but excluded from this patch. Draft #609 already owns semantic
root-directory remediation. Consume its accepted unified receipt instead of
introducing a competing directory layout.

After #609 reaches reviewed unified, apply and requalify the preserved extraction of `semantics/frame_compiler.py`, `semantics/frame_codec.py`, and their `tests/test_frame_compiler.py` / `test_frame_codec.py` companions. Each source/test module must remain below240 lines. Add assertions in `learning/tests/frames/test_nested_visibility.py`: at p4, the child closure retains the original source span, parent occurrence and schema scope although its parent is absent; at p8, both source occurrences and their parent edge survive. Assert literal atoms/frame/position/disposition counts from the returned compiled rows and exclude padded None handles. Rerun `learning/tests/frames` plus the compiler/codec suites, retain the existing future-parent invariance and child/type/local-slot gradients, then obtain fresh #444 acceptance review. B03 parent A02/B02 source-origin
qualification, A05.5 #594, B11/B05 producer authority and whole-model custody
remain separate. Learning and retention are NOT_MEASURED. IPR-0220 remains OPEN;
existing PM-2026-10-29-001/003/004 and RC-024/PAT-028 controls apply. The human
owns durable training and all integration merges.

The whole-repository error-control-plane check remains failing on inherited scheduler/release debt and pre-existing untyped guards exposed under relocated paths. No error baseline or threshold was expanded. This checkpoint does not claim the aggregate repository gate passed.
