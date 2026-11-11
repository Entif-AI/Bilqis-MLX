# C08 parent acceptance receipt | 2026-11-11

## Scope and release boundary

- Issue: `#374`, `BAMF-0.2 C08 | Make batch preparation and resource budgets topology-aware`.
- Lane: C runtime/integration.
- Reviewed integration base consumed: `f9aa79b6cececdedd28a0e80db1256f8a70a9d7f` from `origin/codex/bamf-unified-base-20261028`.
- Direct dependency implementation already present in that base:
  - C02: `0a5d0343` (`fix(bamf): align C02 with optimizer manifest authority`).
  - B11: `8899f7d2` (`feat(bamf): assemble atlas-native forward and refinement`).
- C08.1 `#513`, C08.2 `#514`, and C08.3 `#515` are closed.
- C08.4 `#558` remains open as a BAMF-0.3 successor and is nonblocking for BAMF-0.2 C08 closeout under the 2026-11-10 release-boundary amendment.

## Implemented behavior

The parent integration binds the topology-aware `BatchPlan` to one logical teacher batch and carries that exact plan through Factory preparation, B11 row execution, candidate admission, grouped proof, C05/C09 provenance, B09 participation, and motif staging.

The implementation provides deterministic split plans, row-count-weighted logical gradient accumulation, one later clip/AdamW application, exact plan/custody drift rejection before admission, grouped training authority/proof support, multi-row motif staging, and canonical runtime ownership for the moved batch-training modules. Review-driven repairs also close fail-closed proof, structural, and regression gaps discovered during parent turn-in.

Primary implementation sequence:

- `add82428` `C08: bind logical batch accumulation to resource plan (#374)`
- `7f953ee7` `fix(bamf): close C08 review gaps`
- `96159c09` `test(bamf): strengthen C08 drift proofs`
- `f25edba4` `test(bamf): split C08 candidate-step proofs`
- `9b170cbf` `fix(bamf): validate Factory delivery observations`
- `64b85e7a` `test(bamf): preflight C08 Factory witness`
- `42297298` `docs(bamf): require staged expensive-test preflight`
- `8cd10943` `test(bamf): harden staged C08 verification`

## Verification before the real witness

The repaired candidate passed the bounded exact-head verification ring:

- Core C08/resource/authority ring: `56 passed`, `18 subtests passed`.
- Engram and B08 source-owner ring: `32 passed`, `33 skipped`, `14 subtests passed`.
- Runtime batch-training ring: `75 passed`, `8 skipped`, `10 subtests passed`.
- Teacher-observation package after the observation-boundary repair: `10 passed`.
- Focused observation/delivery package: `23 passed`, `5 subtests passed`.
- BAMF flow-control check: `BAMF_FLOW_CONTROL_OK`.
- Development structure check: `0 violations`.
- Changed-file smell audit: `0 new findings`.
- Error-control-plane check: `new debt 0`.
- `git diff --check`: clean.

Independent review found and repaired:

- three long-function code-smell blockers;
- incomplete non-identity B09 logical-batch union coverage;
- plan-drift tests that originally rejected too early on digest mismatch;
- C09 duplicate-proof fixtures that originally failed before reaching duplicate registration;
- nested `_batch/training` canonical-path audit coverage;
- a malformed observation fixture that could survive until post-training bookkeeping;
- an impossible prepared-versus-execution authority-digest equality assertion.

The final implementation/custody re-audits before the real witness reported no remaining blocker, major, or minor finding. A final tooling-only review of the post-PASS preflight hardening is recorded separately at turn-in and does not change production semantics.

## Expensive-witness failure history

The full history is retained because each failure narrowed the problem without mutating accepted source state.

1. Initial real-Factory witness: killed by the artificial 240-second wall guard. Peak RSS was about 8 GiB. No source mutation or semantic assertion surfaced.
2. Detached timing diagnostic: its 180-second alarm fired during accepted-artifact validation after publication consumed about 129 seconds. It never reached row gradients.
3. 720-second real-Factory witness: wall guard only, about 8 GiB peak RSS, no source mutation or semantic assertion.
4. R2 with a 1800-second wall guard: ran 1538.12 seconds and then failed after the expensive candidate path because the test supplied an unprepared `ObservationCapture` without `selected_option`. The fixture and fail-fast boundary were repaired with a cheap regression.
5. R3: ran 1613.33 seconds and then failed on a stale postcondition that required the execution-time training-authority digest to equal the pre-forward digest. B11 lawfully extends execution-observed dependencies, so the correct invariant is stable authority identity plus monotonic dependency extension. A cheap contract regression now proves that rule.

These failures motivated ADR-139 and the staged fail-fast verification contract in `AGENTS.md`.

## Terminal real-Factory witness

Detached label: `C08-374-64b85e7a-staged-real-factory-r4`.

- Tested immutable Git head: `64b85e7a2ebc2a64efb177e58de959e4b8950e41`.
- Source/snapshot SHA-256: `659a1fa5f50ab60a22adacc2668d0fa3081a21d976358266333b1acde812fcd7`.
- Receipt: `/private/tmp/bamf-c08-374-64b85e7a-staged-r4-receipt.json`.
- Log: `/private/tmp/bamf-c08-374-64b85e7a-staged-r4.log`.
- Detached runner result: `PASS`, return code `0`, `source_mutated=false`.
- Fast contracts: `6 passed`, `6 subtests passed`, `0.88s`.
- Real-fixture preflight: `1 passed`, `337.82s`.
- Exact two-row real-Factory MLX witness: `1 passed`, `1597.21s`.
- Resource guard: `GUARD=NONE`.
- Peak RSS: `8,467,872 KiB`, about `8.076 GiB`.

The real witness proves the C08 parent integration on the actual Factory/A01 artifact path: two delivered real rows are planned as one logical teacher batch split into deterministic microbatches, both row-scoped B11 executions contribute to one logical gradient result, the candidate advances exactly one optimizer step, grouped training authority/proof is retained, motif staging remains present, and realized cost reports one optimizer step.

## Evidence reuse after the terminal PASS

The branch subsequently received documentation and verification-tooling changes only: ADR-139/`AGENTS.md` staged-verification doctrine plus hardening of the C08 preflight/runner and structural relocation of BAMF workstack/grooming scripts. These changes do not alter C08 production runtime, model, optimizer, Factory execution, resource planning, custody, or the full witness assertion path. Under ADR-129, the r4 real-Factory PASS therefore remains valid production acceptance evidence; only the newly changed tooling receives fresh lightweight verification and review.

## Current unified reconciliation | 2026-11-11

The feature branch later consumed current reviewed unified head
`c42362ced0309a24f2f95391257df8f4ef3588cc` in merge commit
`d54b0703f66beda6e60f12c1de58c07885e28026`.

- The upstream `ADR-138` resource-containment decision is preserved. This branch's
  staged fail-fast verification decision was mechanically renumbered to `ADR-139`;
  its accepted doctrine is unchanged.
- The runtime package path exports now include both C08 `_batch/training` ownership
  and unified `_admission/v2` ownership.
- Current-base cheap verification is green: the BAMF contract verifier passed,
  `git diff --check` is clean, the focused C08 seam ring passed `14` tests with
  `9` skips and `9` subtests, and `npm run quality:check` passed with
  `BILQIS_QUALITY_BASE_REF=origin/codex/bamf-unified-base-20261028` and
  serialized test workers.
- The first premerge r2 attempt before this merge failed only because the older
  branch lacked four legacy-trainer evidence updates already present on current
  unified. Current-base `quality:check` confirms that integration mismatch is closed.

Current unified also refactored Factory source-frame preparation through
`source_frame_inventory(...)`, which lies on the real C08 pre-gradient path.
Therefore the historical r4 PASS remains valid evidence for its tested immutable
head, but it is not silently promoted into current-base integration proof under
ADR-129. A current-base real-fixture/full witness and aggregate premerge gate remain
the final turn-in evidence.

Those gates are presently resource-blocked rather than semantically failed. Current
host inspection reports swap at approximately `58.15 GiB / 59.39 GiB`, which is
near saturation. Current `ADR-138` explicitly forbids launching another expensive
MLX/full-model witness in that state. No heavy rerun is authorized until that
resource precondition clears; do not weaken the guard or treat detachment as a
substitute for memory safety.

## Disposition

C08 BAMF-0.2 owned acceptance remains satisfied by the owner-declared and durable
r4 production PASS. Current-base integration is reconciled and pushed, but PR
readiness remains pending the resource-lawful current-base witness/premerge gates
described above. This receipt does not authorize self-merge or issue closure before
the human-reviewed PR is merged and read back.
