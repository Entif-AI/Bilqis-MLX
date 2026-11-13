# Issue #436: exact parameter census

The implementation starts from Lane B `eca35a00df329f680fe7d3c9d43156427ac197ec`, consuming unified `44f78431709ec3b8fc23f47b45d9b18f167c7354`. Direct dependency #435 is implemented and independently reviewed at that head; its final issue receipt is `6486066752`. This review boundary precedes the #436 commit/push and final issue/PR receipts.

The census derives every row from the canonical ParameterSpec ledger. For the selected one-bank/one-page body it reports dense matrices 67,239,936; semantic tables 6,291,456; motif tables 2,097,152; adapter matrices 36,864; and explicitly itemized auxiliary tensors 3,804,390. The final total is 79,469,798 across 214 tensors. Feature type/role/schema tables each remain 512x128; local slots and identity banks retain their separate capacities. `issue-436-census.txt` contains the actual printed per-tensor report and final total for an unbound structural fixture.

The versioned record is `bilqis.mlx.bamf-parameter-census/v1`. The unbound initialization manifest reuses this census for its total and subtotals, rather than keeping a separate count implementation.

With both the full disposable MLX and real frozen-v1 witnesses enabled, the package suite passed **17/17, no skips**, including literal subtotals, all itemized rows, independent table extent changes, invalid census identities, and agreement with the allocated tree's actual scalar count. Retained output is `.local/bamf-lane-b/issue-436-full-validation.log`. Lane B operator and hygiene scans report zero findings; inherited integration failures remain unchanged.

Fresh independent Google EGM review pinned at `b3a35956759bf7f024af2ff061b2e0b44b438e4c` verified every owned count and capacity clause, with disposition `EGM_VERIFIED_NO_MATERIAL_FINDINGS`. A nonblocking test-hardening suggestion does not change that disposition. The final issue/PR receipt remains a turn-in step and will record the pushed commit after that action occurs.

Existing controls remain `PM-2026-10-28-004` / `RC-138` / `PAT-099`, `PM-2026-10-28-006` / `PAT-090`, and `PM-2026-10-28-008` / `PAT-086`. IPR-0220 remains governing where applicable. No actual student, own AdamW, teacher or original checkpoint was modified. Source coverage, actual learning and retention remain unmeasured; only the human starts a durable student.
