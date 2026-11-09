# A02.1 production staging and admission-boundary correction — 2026-11-07

## Scope

- Issue: #399 — A02.1 | Allocate stable semantic banks and activate admitted identity rows
- Branch: `codex/bamf02-a-399-production-admission-20261106`
- Historical PR #887: closed unmerged after the earlier A02 publication-authority overreach was corrected.
- Reviewed integration trunk consumed for the current candidate: `9385ac7f336dca090cdd746fe8b87904ff2e5415`
- Dependency authority consumed: reviewed B13 accepted-generation feature authority from #708/#809.
- Additional B13 integration repair in this branch: recursive accepted-generation feature lineage is rederived through the same accepted source authority, while the immediate parent generation's effective feature map is kept distinct from the current feature artifact's last distinct construction predecessor. A02 therefore does not mint a parallel factor-map authority or mistake retained reuse for a new feature transition.
- Rejected historical PR #698 lineage was not revived or used as current authority.

## Correct ownership boundary

A02 owns deterministic append-only allocation and preparation. C07 owns admission authorization and atomic adoption.

The public A02 path therefore now returns an exact `A02StagedVocabularyExtension` containing the complete `BamfBundleCandidate` plus immutable `A02VocabularyStagingReceipt`. It does **not** mint a publication capability and does **not** advance the accepted generation pointer.

The staged candidate binds:

- stable `bank * 8192 + row` ABI allocation;
- exact accepted parent generation and B13 predecessor-feature receipt;
- source-allocation digest, complete plan digest and admitted IDs;
- exact prepared extents and active-mask identity;
- zero moments/counts for newly staged identity rows;
- exact preservation of all pre-existing parameter, moment and count bytes;
- source-derived Registry mirror and conservative bank resource estimate;
- accepted active semantic ABI separately from immutable source feature-map authority.

B13 publication now fails closed with `BAMF_ATLAS_ADMISSION_EXECUTOR_REQUIRED` whenever a candidate attempts to change semantic-bank count or active-set digest through ordinary retention publication. No A02-owned parameter-extension publication token remains.

## Material findings and repairs

Preflight review found material defects in the earlier turn-in. They were accepted rather than contested away:

1. **C07 authority bypass — Blocker.** The earlier `admit_vocabulary_extension()` directly minted A02 acceptance and called `publish_bamf_generation()`. C07 #380/#510 explicitly owns persisted lease authorization and atomic adoption for subsequent source-valid additions. The A02-owned publication path and its live token issuer were removed.
2. **Admission evidence replay.** The earlier acceptance design did not initially bind the entire plan payload. The staging receipt now binds the complete canonical plan digest; C07 will need to consume this exact staged evidence when its executor becomes available.
3. **Existing optimizer mutation.** Parameter-extension state issuance now rejects changes to all pre-existing parameter/moment/count rows and requires zero moments/counts for new identity rows.
4. **Generic retention bypass.** Ordinary C05 retention acceptance cannot publish a semantic-bank or active-set change; publication requires the missing C07 adoption executor instead.
5. **Recursive B13 predecessor lineage.** Reviewed B13 source-rederivation authority existed through #708/#809, but the accepted reader could not recursively reconstruct predecessor-bearing feature lineage. This branch repairs that projection while preserving source ownership and separately tracks the immediate parent generation's effective map and the current feature artifact's last distinct construction predecessor.
6. **Successive A02 parent state.** The earlier path rebuilt the active set from immutable source `entry.active` flags. Accepted BAMF `PlasticityPolicy.row_ages` now supplies the admitted identity-row set, while the source snapshot remains the immutable semantic-ID/index authority. Active semantic ABI and feature-map authority remain distinct identities.
7. **Accepted run-seed drift.** Fresh exact-head review found that the production staging adapter passed `ModelTopologySpecV2.default_run_seed` (fixed at zero) into new identity-row initialization instead of the accepted generation's `BamfRunIdentity.run_seed`. The adapter now fails closed without accepted run identity and passes the accepted run seed. The full-topology witness deliberately uses a nonzero accepted seed and independently recomputes the new row bytes from that seed and the source-derived factor.
8. **Authenticated full-parent validation.** The authenticated full-tree staging path now performs the same explicit `VocabularyBankParent` type guard as the ordinary staging path, so malformed authenticated input fails through the typed ErrorBus boundary rather than leaking an attribute error.
9. **Initial and retained same-map staging.** Fresh exact-head EGM found that the production adapter conflated the immediate parent generation's feature map with the current feature artifact's own predecessor. That rejected generation zero outright and also broke ordinary retained descendants that reused an unchanged map. B13 replay now exposes both relationships distinctly. A02 uses source-replayed predecessor-free validation when the accepted feature artifact has no construction predecessor, and authenticated predecessor validation only when the artifact actually records one. The full-topology witness now stages directly from accepted generation zero instead of manufacturing a generation-one feature transition first.

The previous claim that C07 governed only new Atlas releases was incorrect and is withdrawn. C07 explicitly governs subsequent source-valid additions under a persisted lease.

## Verification

Current exact-tree verification after the ownership and run-seed corrections:

```text
A02 staging/authority regressions: 3 passed, 0 failed, 0 skipped
A02 semantic owner suites:         11 passed, 0 failed, 2 explicit opt-in skips
B13 feature authority + lineage:    18 passed, 0 failed, 0 skipped
ordinary B13 publication:           11 passed, 0 failed, 0 skipped
changed-file smell audit:          0 findings
development structure/governance:  pass
legacy-trainer checks:              pass; authority source `/Users/emilie/Code/.worktrees/bilqis-mlx/337-replay-349-20261026/runs/microspenics-349-replay`
contract verifier:                  pass (43/43 issue mirrors)
flow-control checker:              pass
git diff --check:                  pass
```

Historical note: an earlier full-topology witness completed 1/1 PASS in 336.214s after repairing a duplicate Python module identity. That witness exercised direct A02 pointer publication and therefore is **not current admission acceptance evidence** after the C07 boundary correction. It remains diagnostic history only.

The prior detached witness at snapshot `83ea978691054b0eb25912f31cda9d9af8d3af805e41e3ab330ac8c113a9243f` and the later 387.353s run are historical only because subsequent production changes invalidated them. The current full-topology staging witness is `test_production_staging.py`; after the accepted run-seed and feature-construction-lineage repairs it stages directly from accepted generation zero and passed:

```text
command: env BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/vocabulary/test_production_staging.py
Ran 1 test in 316.421s
OK
TEST_TOTALS total=1 passed=1 failed=0 skipped=0 errors=0
```

This current witness proves that the ordinary initial accepted generation can stage A02 growth without a fabricated predecessor feature artifact. It additionally proves that a nonzero accepted `BamfRunIdentity.run_seed` determines the staged new-row bytes by independently recomputing the expected row from the accepted seed and source-derived factor. It proves the corrected A02 staging path and fail-closed publication boundary. It does **not** prove or authorize C07 admission.

## Dependency and disposition

- #399 is **ACTIVE for final A02 qualification**. Live contract reconciliation established that its staging-only leaf acceptance does not require final C07 adoption; the prior WAITING-on-C07 trigger inverted the cross-lane dependency.
- The lawful cross-lane sequence is A02 owner-issued staged handoff -> reviewed unified -> C07/#510 consumption. No sibling branch merge or copied receipt is authorized.
- C07.1b/#510 remains the downstream owner for persisted-lease validation and atomic adoption of the exact A02 staged candidate, but its Blockers 1/2/4 are not prerequisites for this A02 leaf turn-in.
- Historical PR #887 remains closed. A fresh Lane-A -> reviewed-unified PR is required after exact-head EGM and premerge qualification.
- Official merge-readiness EGM must review the repaired exact semantic head; earlier reviews remain historical/preflight evidence.
- No self-merge or issue closure is authorized.

## 2026-11-09 current-unified qualification

The repaired A02 owner branch consumed reviewed unified
`636ac8ffdeece7d6f8b24e9d1f46596396848db7` exactly once at the turn-in boundary.
The resulting semantic integration head is
`6c59b20230ba222cfbd24933c1de046b558aceb2`.

The reviewed-unified delta was limited to C09 packed-frame/context-view custody and
the accepted execution cache. No A02 semantic/staging owner was changed by the sync.
Accordingly the already-completed 316.421s full-topology witness remains reusable:
its A02 staging inputs and implementation are unchanged. The newly invalidated C09
seam was instead requalified directly after the sync.

Post-sync differential proof:

```text
A02/B13 focused staging + feature/publication ring: 30/30 PASS
new C09 packed/context accepted-custody ring:       5/5 PASS
A02 semantic owner ring:                           11 PASS / 0 fail / 2 explicit opt-in skips
git diff --check:                                  PASS
```

No neural workload, `AdamW.update`, accepted generation publication, C07 lease, or
live learner mutation was exercised by this qualification. A fresh merge-readiness
independent review/EGM is still required before the new human-review PR is opened.
