# B13.1 / #478 bounded custody turn-in

## Branch and authority

`codex/bamf02-b13-478-custody-20261101` starts from current Lane B e73e9478,
which already contains unified bb626d75. It merges the exact existing same-Lane-B
candidate dd6a6879 without rewriting its history. The original branch remains
untouched. No sibling-lane candidate was imported into Lane C. No self-merge,
durable student start, protected lineage mutation or actual learning acceptance.

## Reproduced defects and repairs

The original ten native codec/publication tests passed. They missed these actual
crash/ownership cases:

- Red 522d2f7c: three durability tests fail four assertions. Tensor bytes had no
  explicit fsync before pointer publication; publish/recovery could overlap outbox
  observation+append; advancing a successor stranded its predecessor's pending
  event. Repair 8f76ee90 fsyncs the tensor descriptor, keeps publication/recovery/
  rejection reconciliation under the pointer lock and drains the validated parent
  before advancing. The first affected native union passes 13/13.
- Red ea76dc5b: four sidecar tests fail 24 assertions. Arbitrary/missing schema
  versions, absent compiler/bank identity and incomplete correction metadata were
  accepted. Repair 7c441224 adds explicitly NEW B13 storage-envelope versions and
  required identity/epoch/frontier cross-bindings. These preserve supplied B13
  JSON fields/values, not upstream serialized bytes or source admission. The
  resulting native union passes 17/17.
- Red d71827c0: three codec-boundary tests fail seven assertions. Rehashed unowned
  or empty outboxes reached tensor construction; matching external tensor symlinks
  were accepted; malformed candidate identity reached payload persistence. Repair
  baafd544 validates generation identity before destination creation, outbox
  ownership before numerical loading, and regular non-symlink tensor entries
  before hashing/MLX loading. Native bundle union passes 20/20, zero skips/errors.

The operator gate independently found seven unregistered legacy error identities.
They now use typed checkpoint-custody recovery contracts while preserving exact
legacy error args. Historical catalog prefix digest remains unchanged. Error
control reports new debt 0; no threshold, baseline or policy waiver was used.

## Verification

Native tests run on the M3 in an isolated worktree/environment, with only disposable
run directories and data planes. The runner checks current Python trainer/test
processes and acquires a nonblocking shared local MLX lock before its finite test
process. It does not touch an existing student. Shape-patched small B12 numerical
fixtures establish the bounded codec/transaction claims below, not full-model
custody or real learning.

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_codec.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_publication.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_publication_durability.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_sidecar_contracts.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_codec_boundaries.py
python3 -B scripts/check_module_size.py --changed-from bb626d75
python3 -B scripts/quality/check_governance_integrity.py --base-ref bb626d75
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/error_control_plane.py --check --base-ref bb626d75
git diff --check
```

All listed checks pass. The catalog selection passes 3/3 separately. Broader historical checkpoint/outbox/catalog testing passes **18/18**, zero
skips/errors, after installing its declared Torch dependency in the isolated M3
environment. Its first attempt passed16 with one missing-Torch import error; that
environment gap was repaired without changing code or criteria. Combined native
selections: **38/38 PASS**. The 100 GiB reserve was preserved during dependency
installation (observed free space 256.95 GiB before Torch installation).

## Independent EGM

Actual pinned Google EGM checkout:
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`. Native fresh-context Goldfish used
`fork_turns=none`, actual personas and standard, the issue, named source/tests and
bounded docs; no parent implementation transcript or memory was supplied.

- `b13_dependency_review` performed a preliminary read-only dependency review and
  identified the initial four Majors. Its later readiness review accepted the
  bounded storage-envelope design after preservation wording and exact epoch
  typing were clarified. It did not certify full feature EGM or execute tests.
- Fresh `b13_turnin_review` read the actual codebase-details/comprehension personas,
  implementation-readiness standard, issue, plan, custody owners and all bounded
  tests. It confirmed the first four repairs, then found the outbox-ownership and
  tensor-symlink Majors plus early candidate-validation observation. These were
  reproduced and repaired. Targeted re-review at baafd544 including intervening
  catalog changes: **no remaining Major or Blocker**. Native result verification
  remains the implementing agent's responsibility and is recorded above.

## Remaining acceptance

These are bounded custody/runtime repairs, not accepted A02/B07/B12 producer,
source/rights, full-model tensor, genuine frozen six-layer v1, retained-learning,
complete B13 or Lane C production acceptance. The historical test creates its own
small v1 fixture; it does not witness the frozen real v1 student. No existing
lineage was coerced into v2. B13.2-.4 and full parent qualification remain open.
