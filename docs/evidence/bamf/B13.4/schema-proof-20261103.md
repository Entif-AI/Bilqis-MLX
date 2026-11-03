# B13.4 expanded parameter schema witness

Base: reviewed unified and synchronized Lane B
`7984d7872d49b3987284692f5398da71f2a72605`.
Issue: #481. IPR-0220 remains open.

Existing B01 and B13 owners implement the required schema behavior. This change
adds their joined proof without changing initialization, tensors, optimizer
arithmetic, serialized formats or publication behavior.

The test runs the actual unpatched B01 constructor with two semantic banks and
one initial motif page: 215 parameter tensors, 85,761,254 scalar parameters.
Its initialization manifest matches every expanded ParameterSpec field, including
initializer, group, decay and path-derived storage keys. The only extra parameter
relative to the initial one-bank ledger is `identity.bank.1`; shared feature and
depth parameters remain singular.

The actual B13 bundle writer and cold reader round-trip all 860 weight, first
moment, second moment and local-count arrays, checking every name, shape, dtype
and value. The test checks topology/extents, payload byte accounting, optimizer
step, teacher state and allocation equality. Missing, extra and misowned
`depth.norm` parameter trees are rejected before creating a tensor file.
The complete 100 GiB disk reserve runs normally. Only temporary CPU data and an
isolated temporary data plane are written.

This is an **UNBOUND software schema witness**. Synthetic ABI, teacher and source
sidecars identify test data; they do not admit semantics or establish a real
learning generation. The initial motif page remains empty. A first fixture that
requested a second page without its allocation manifest was correctly rejected;
page-growth admission is not asserted here. Source-qualified continuation, actual
Factory selection, next controlled optimizer update, retained learning, historical
v1 and cross-backend qualification stay with #480/#479/#709/#372 and their owners.

## Reproduce

With the repository's installed MLX and other native test dependencies:

```sh
BILQIS_BAMF_FULL_WITNESS=1 python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_parameter_schema.py
```

Observed: 1 passed, 0 failed, 0 skipped; 9.664 seconds. The witness explicitly
selects CPU and restores the previous default device. It performs no optimizer
step. Without the opt-in variable, the full allocation is an explicit skip.

The adjacent codec, boundary, sidecar and pre-CAS compatibility selection passes
13/13 on CPU, zero skips. Reproduce with the four files `test_codec.py`,
`test_codec_boundaries.py`, `test_sidecar_contracts.py` and
`test_pre_cas_compatibility.py` in the same custody test package.

No actual student, own AdamW, teacher, champion, saved checkpoint or human-run
state is changed. Human review owns integration. Parent acceptance remains open.
Existing PM-2026-11-01-004/-005 custody/proof controls remain applicable.

## Dependency and review receipts

The usable #480 reader/cache-separation checkpoint is
https://github.com/Entif-AI/Bilqis-MLX/issues/480#issuecomment-6586982500
at its separate branch head `39bf54e820c6e9f6aef75345557a50f0d51cd7ef`.
That head is **not integrated into this base**. Its full transition acceptance
remains EGM-Failed with #754 open. It identifies the existing B13 reader interface;
it is not substituted for current-code verification.

The actual codec consumed here is the reviewed-unified version at
`7984d7872d49b3987284692f5398da71f2a72605`, last changed by
`bcffdcdf` (B07 continuation custody). The current constructor, writer, reader and
adjacent 13-case selection are exercised directly by this #481 proof. No old
#480 test result is relabeled as a current-code result.

Fresh isolated GPT-6.1 Terra High Goldfish reviewed executable/test head
`4dcfc7169738e721df0f1df259f2d9659d54cab4`, using pinned Google EGM
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`, both codebase-details and
comprehension personas, and the implementation-readiness standard.
Episode `B13.4-SCHEMA-20261103`, round 1 of 5. The initial prerequisite-receipt
finding was contested against the leaf's exact usable-interface rule; the
reviewer withdrew it after distinguishing scoped receipt from full #480
acceptance. Final disposition: **0 Blockers, 0 Majors, 0 Nits**, with this explicit
mechanical receipt binding. No second Goldfish round was spent.

The reviewer inspected source and existing logs without rerunning tests. It
reported one protocol deviation: writing BIOS reference material to a temporary
file during bootstrap; no workspace edit or compilation occurred. This does not
alter the review's findings or claim filesystem isolation.

Structure, governance, docs, Factory architecture, semantic boundaries, release
version and whitespace checks pass. Changed-code hygiene has zero findings;
base-aware error control has zero new debt. Local historical ABI checks pass in
advisory mode because no independent expected fingerprint is supplied.
