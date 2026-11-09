# B06.3 #454: production ownership reconciliation

Status: **DESIGN_EGM_PASS; RECONCILIATION_ACTIVE; HUMAN_MERGE_PENDING**.

Issue: [#454](https://github.com/Entif-AI/Bilqis-MLX/issues/454)  
Parent: [#365](https://github.com/Entif-AI/Bilqis-MLX/issues/365)  
Residual registry owner: [#455](https://github.com/Entif-AI/Bilqis-MLX/issues/455)  
Fresh reconciliation branch: `codex/454-b06-3-reconcile-20261109`  
Consumed reviewed unified: `e206ec0e957e24823f3136c0f3bffe1fc950013e`

## Current authority

Parent amendment comment `6751069838` and #454 amendment comment
`6751070420` supersede the historical public `refine_selected(...)`
assembly surface without erasing its provenance. Production composition belongs
to B11. B11 combines canonical B06.2 selection with the private B06.3 numerical
recurrence before typed readout.

Historical PR #684 remains closed and unmerged. This reconciliation does not
reuse or merge-forward that branch.

The accepted production path is:

1. B11 obtains one source-owned compiled batch and one source backbone result.
2. B11 calls canonical B06.2 `select_prediction_refinements(...)`.
3. B11 binds the selected frame by exact frame handle and occurrence identity.
4. B11 passes source-owned B03 seed/member tensors to private
   `_refine_frame(...)`.
5. B11 writes the returned value only into a prediction-local copy before typed
   readout.

No executable production `refine_selected(...)` exists on the consumed
reviewed-unified head.

## Design review

Pinned EGM dependency:
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`.

Fresh-context review of the paired parent/leaf amendments returned:

- Implementation Readiness / Comprehension: **PASS**, 0 Blockers, 0 Majors,
  0 Nits.
- Codebase Details: **PASS**, 0 Blockers, 0 Majors, 0 Nits.
- Design / Structural: **PASS**, 0 Blockers, 0 Majors, 1 Nit.

The one Nit is a discoverability issue: #455 still displays its historical local
`refine_selected(...)` traceability line. Parent #365 already supersedes that
line for current authority. #455 remains open for B06.4 registry reconciliation.

GitHub design-state comments:

- #365 design PASS receipt: comment `6751503412`.
- #454 design PASS receipt: comment `6751504135`.

#365 and #454 carry `EGM-Passed`. #454 also retains historical
`EGM-Failed` provenance.

## Engineering proof reuse and drift

The accepted #454 semantic proof head remains reviewed unified
`6b085f875ab781a3771c89916a1e42653f73e882`, which consumed:

- #471 / PR #939 for B11 production composition.
- #736 / PR #940 for the source-positive B03-to-B06 production witness.

PR #940 exact head is
`7bb7567d2a510ba532f572045f1ed120d13f86c4`. Hosted
`portable-core`, `portable`, and `semantic-abi-integrity` passed there.
The affected pinned-A01 source/refinement proof reported **31 passed plus 34
subtests**.

Reviewed unified advanced from `6b085f87` to `e206ec0e` through 19 C12,
retention, and cognitive-package authority commits. Exact path comparison shows
no changes under the B06/B11/B03 refinement proof surfaces:

- `bilqis_mlx/runtime/_depth/`
- `bilqis_mlx/runtime/_model/backbone/`
- `bilqis_mlx/runtime/topology_v2/ledger.py`
- `bilqis_mlx/learning/source_atoms/encoding.py`

The current drift classification for #454 is therefore **NO_DRIFT**. The prior
runtime proof remains reusable under the repository's exact-SHA/dependency rule.
This classification does not turn EGM into implementation verification and does
not waive current premerge or hosted checks for this reconciliation branch.

## Reconciliation validation

Current branch-local checks after activation and receipt creation:

- `scripts/check_bamf_flow_control.py`: **PASS**.
- `scripts/verify_bamf_0_2_contracts.py`: **PASS** with 43/43 owner mirrors
  and 216 indexed owner/child identities.
- `scripts/check_bamf_workstack.py`: registry integrity **valid**. The command
  retains 11 pre-existing dependency-normalization holds and therefore returns
  the repository's expected `held` status rather than an executable order.
- `npm run quality:structure` with base `e206ec0e`: **PASS**, zero structure
  or governance-integrity violations.
- `npm run quality:changed` with base `e206ec0e`: **PASS**. This includes
  structure/governance, zero new changed-file smell findings, legacy-trainer
  authority plus 7 tests, flow-control validation, and 15 flow-control tests.
- `git diff --check`: **PASS**.

## Closure boundary

#454 may close only after this repository reconciliation is human-merged into
reviewed unified. Closing #454 does not close parent #365 or sibling #455.
Parent #365 retains aggregate B06 integration acceptance. #455 retains complete
tensor/initializer-registry reconciliation.
