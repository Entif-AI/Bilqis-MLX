# C10 structural follow-up #641: accepted B05 extraction reconciliation

2026-11-02; Lane C #344; issue #641; structural parent #520. IPR-0220 governs.
Base: synchronized Lane C `46bfa98d564e1262be43463ec96d3ce1a95aa8c4`, containing
reviewed unified `67c964a1548cb0075a28a90aa2565d8bdab0fd71`.

## Existing implementation

The prescribed structural work already landed in PR #652 (merged 2026-10-31),
commit `cec6a8ee1659854c292dc59566d4d14a53b75ae5`. This proof-only change reuses it.
The old 365-line `runtime/block_attnres.py` is now the 205-line numerical/API owner
`runtime/_depth/block_attnres.py` plus 196-line `depth_contracts.py`. The latter owns
parameter views and their shared private seal, feature/summary records, schema
constants and B01 prefix validation. The numerical owner retains feature composition,
normalized depth selection, gates, diagnostics and group-boundary execution order.
There is one public module identity, `bilqis_mlx.runtime.block_attnres`.

The 491-line original test owner is mirrored into contracts (154 lines), numerical
proof (194), public integration (119) and shared helpers (125). Production has
three direct Python files including package initialization; tests have five. Every
file is below 240 lines and each directory has at most 12 direct code files.

## Reproduce preservation and behavior

From repository root with the normal MLX dependencies installed:

```sh
PYTHONPATH=. python3 -B docs/evidence/bamf/C10.2-641/verify_preservation.py
python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/depth
```

The first command reads the accepted pre-split owner directly from Git, hashes
location-independent ASTs and requires all 15 original top-level production
functions/classes and all 24 original test/helper functions to remain exact.
Decorators are included. It rejects duplicate/missing/changed definitions and
checks file/directory targets and the four relocated public class module names.
`preservation.json` records the observed output. The helper is read-only; it neither
initializes a student nor updates an optimizer.

The behavioral suite passed **13/13 on CPU**, zero skips. Tests retain independent
selector equations, normalization/gates and gradients, type-mean/UNKNOWN and
source-coordinate behavior, public parameter/source/schema rejection, exact
B01 views and group/motif/capture/adapter order. There are no source or baseline
changes in this follow-up; prior functions, classes and test decorators are exact.
The existing B05.4 fail-closed admission disposition remains intact.

## Scope and remaining owners

This is structural #641 acceptance, not #355/#520/#586 completion. It grants no
trusted B11 summary-producer authority, source admission, B08 hit, checkpoint or
retained learning. No actual student, own AdamW, teacher, champion or human-run
was changed. No fresh semantic rule or neural experiment was introduced.

Final pinned EGM and exact-head hosted checks are recorded in the PR/issue
receipt before turn-in. A review launch is not a pass. Existing related incidents
PM-2026-11-02-003 (committed-scope proof) and PM-2026-11-02-007 (live public visibility)
remain applicable; public receipts use opaque IPR-0220.
