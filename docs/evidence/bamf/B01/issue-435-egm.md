# Issue #435: typed FP32 tensor registry

## Scope and dependencies

The Lane B registry is implemented on `codex/bamf02-b-neural`, consuming unified `44f78431709ec3b8fc23f47b45d9b18f167c7354`. Its direct #434 dependency is complete at `e5023e138e41a85a304632ed9f5a87d9211e972c`, with the independently reviewed issue receipt `6481062930`. The original registry commit is `f4da35cf5d0ee5dfec118c640a37b9031007a1da`; the final guard and proof repairs follow that commit.

The shared ledger declares 214 FP32 tensors and 79,469,798 scalar parameters for one semantic bank and one motif page. Initialization, validation, unbound zero-moment state, serialization keys and inverse array mapping derive from the same ParameterSpec declaration. Source-bound row admission and motif allocation remain with their source owners. Actual masked optimizer updates, model assembly, and durable generation persistence remain downstream work.

## Independent EGM review

Fresh Goldfish reviewers used Google EGM at `b3a35956759bf7f024af2ff061b2e0b44b438e4c`. The original ordinal storage keys were repaired to encode stable parameter paths, and targeted reviews cleared write-side key stability, inverse mapping and malformed-tree rejection. The final #435 review found no owned ledger/initializer/codec code defect; it required separate bank-only and page-only physical readback plus an explicit extent-digest witness and final receipt.

Those proof additions now execute in the full fixture. The bounded independent re-audit cleared both findings and found no new blocker, major or nit. Commit/push readback and the final issue/PR receipt remain turn-in steps at this review boundary.

## Proof and integration limits

With `BILQIS_BAMF_FULL_WITNESS=1` and the pinned local frozen-v1 bundle supplied through `BILQIS_V1_BUNDLE_WITNESS`, the package-local topology suite passed **14/14, no skips**. The actual MLX safetensors roundtrip covers bank-only, page-only and combined growth; every existing weight and moment is compared exactly, including explicit nonzero moments. Each extension changes the extent digest while retaining the dense topology digest. The retained local output is `.local/bamf-lane-b/issue-435-full-validation.log`.

The operator-contract scanner reports zero debt in the Lane B topology module after the numeric guard repair. The repository-wide error-control gate still reports nine inherited literal-error findings, and the size gate has three inherited regressions. Their baselines were not changed. The source/ABI hosted workflow succeeded at `e5023e138e41a85a304632ed9f5a87d9211e972c`; the portable workflow stopped at the operator-contract gate before later checks.

The hygiene gate also found one long Lane B registry function and twelve inherited findings. The registry now expands cohesive input, block, depth, motif, plasticity and output declarations. An exact before/after comparison of the ordered ParameterSpec records for all four bank/page combinations matched SHA-256 `b308c56ea227a8551944accb5ebf03627a4350fb8d23d7c8824e192c751122c0`. The Lane B hygiene scanner reports zero findings; final full MLX validation remains 14/14 with no skips. The inherited findings remain visible.

`PM-2026-10-28-004` / `RC-138` / `PAT-099` records serialization identity across growth. `PM-2026-10-28-006` / `PAT-090` records inherited size debt. `PM-2026-10-28-008` / `PAT-086` records the new numeric-guard findings and their repair. All were read back from the canonical ledger.

IPR-0220 remains governing where applicable. No durable student, optimizer, teacher, or original checkpoint was modified. The human alone starts real training. These software fixtures establish neither admitted source coverage nor actual learning/retention.
