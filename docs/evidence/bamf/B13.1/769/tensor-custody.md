# Tensor content-addressed custody: follow-up #769

The candidate starts from synchronized Lane B/unified
`deaa8b9dbd277993f884abeea7413f9cb799d945`, preserving the externally merged
#753 / PR #768 implementation and its directory-creation regression. The prior
reviewed repair consumed unified `dfc0c7586c23b6477c08d4db486ade3deeb79fae`
through synchronized Lane B; the final sync also consumes unified
`338a3c5263772566502af70d731b95af1d91a81e`. It preserves the existing issue implementation
`349ac665880dbdd545cddd0ec8e50817095d73b1`. IPR-0220 governs. Only disposable
fixtures execute; real student, own AdamW, teacher and original checkpoints remain
human-owned. This repair does not establish full B13 learning acceptance.

## Storage and compatibility

`DataPlaneFileObjectMixin` owns tensor objects beside the shared data-plane SQLite
file, addressed by SHA-256. Adoption streams into a private temporary inode,
flushes/fsyncs its bytes, checks its digest and installs it with a no-overwrite
hard link. Competing installers verify/reuse the winner. The shard, object root
and object-root parent directories are fsynced before adoption returns, including
reuse. Caller source aliases cannot modify the copied object.

The B13 codec serializes its numerical payload through the existing checkpoint
owner, checks the CAS filesystem's configured disk reserve before an additional
copy, adopts the payload and removes its staging copy. New tensor bindings carry
`object_sha256`; cold read resolves and deep-verifies that object before MLX
construction. Existing six-field local-file v2 bindings remain readable. No old
bundle or schema is rewritten. A positive compatibility fixture executes the exact
pre-CAS writer from the pinned unified Git object above (source SHA-256
`01e66fcbe15802615c3557a2a4b99c0fb75a37d64fe3d61ee30bf56d1301fcdc`).
It publishes a genuine old local-file v2 bundle, compares every weight/moment/count
against the pre-save candidate, reads it in a fresh process through the current
pointer owner and proves every old bundle byte unchanged. This fixture needs Git
and that commit object; no stored student binary is added to the repository. Existing sidecar validation, generation pointer
lock, staging, atomic publication and outbox reconciliation retain ownership.

## Reproduction

Run on the supported host with Python and MLX installed:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/custody/data_plane/test_file_objects.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_tensor_cas.py \
  bilqis_mlx/runtime/tests/custody/bamf_bundle/test_pre_cas_compatibility.py
python3 -B -m unittest \
  bilqis_mlx.runtime.tests.custody.bamf_bundle.test_codec \
  bilqis_mlx.runtime.tests.custody.bamf_bundle.test_codec_boundaries \
  bilqis_mlx.runtime.tests.custody.bamf_bundle.test_publication \
  bilqis_mlx.runtime.tests.custody.bamf_bundle.test_publication_durability \
  bilqis_mlx.runtime.tests.custody.data_plane.test_store \
  bilqis_mlx.runtime.tests.custody.data_plane.test_custody \
  bilqis_mlx.runtime.tests.custody.data_plane.test_events
```

Expected: 11 targeted tests and 37 existing tests pass without skips. Controls
cover unchanged-object reuse, changed-object separation, corruption rejection,
pointer-crash/retry reuse, caller-alias mutation, competing installation,
independent-process convergence and directory fsync calls. A three-generation
published sequence covers data-only active-set extension with identical numerical
bytes, then a retained numerical update with distinct bytes. It checks exact
parent-bundle bytes, cold readback and generation-bound outbox delivery. The three ownership,
race and ancestry tests failed before the additional repair. Test fixtures use
small numerical shapes and patch headroom; production reserve remains 100 GiB.
Publication intercepts the pointer and verifies fsync of the actual persisted CAS
inode and its directory ancestry, including object reuse. Negative controls remove
CAS file or directory fsync and prove the pointer check fails before installation.
Power-loss durability is supported by these ordering tests, not a physical power-cut run.

Incident PM-2026-11-03-001 records the newly discovered CAS gaps and native ledger
readback. Historical PM-2026-11-01-004/005 remain separate custody/proof provenance.
Final isolated pinned EGM and hosted PR checks are separate required receipts.
Source-qualified next-step continuation (#709), cache transitions (#754) and
accepted feature authority (#708) remain separate owner work.
