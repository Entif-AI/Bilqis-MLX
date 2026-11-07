# C02.5 run/visit provenance transport — 2026-11-07

Issue #905. Branch `codex/905-c02-5-visit-provenance-20261107`.
Reviewed unified consumed for this scoped implementation:
`bd3657e170c8bdc046a7bb28524c0fb829ca7ce9`.

Status: **IMPLEMENTED_AND_QUALIFIED; REVIEWED_PARENT_INTEGRATION_HELD**.

## Authority boundary

C02 transports, but does not mint, the run/visit authority needed downstream by
B11/B06. The transport binds the frozen B13 run identity and `run_seed` to the
C03-issued visit record. It keeps `run_seed`, `visit_id`, `episode_id`, and
`optimizer_step_seed` semantically distinct. Ordinary callers cannot construct the
transport or substitute a different visit record without invalidating the digest.

The process-local visit issuer token remains authority evidence only. It is not
portable row content and is excluded from canonical row hashing. Portable hashing
uses the C03 record projection instead.

## Implementation and repair

The initial semantic head `88baf8718d5de1cc5c2830b16a564cac679de825`
transported the authority but its detached affected ring exposed two errors:

1. generic recursive dataclass `asdict()` flattened nested visit provenance and
   accidentally pulled the private process-local issuer token into canonical resource
   hashing;
2. an inherited B11 source witness requested `A.IDENTITY` with `each=1`, which is
   illegal under the current balanced Grade-A draw contract (`each >= 2` and even).

Both failures were investigated before rerun. Semantic repair head
`c3d5619e50d98576caaeb324d8ec1de3403026f8`:

- canonicalizes dataclasses field-by-field so nested `BamfVisitProvenance` reaches its
  explicit portable C03-record codec while private issuer fields stay non-portable;
- changes only the invalid source witness draw from `each=1` to `each=2`; the test
  still consumes the same first row and does not change product policy.

Targeted M3 proof for the exact canonical-resource failure path:

```text
test_microbatch_plans.py: 5/5 PASS
```

## Exact affected qualification

The repaired head was archived to `/tmp/bamf905-final-c3d5619` on `m3-ultra`.
The run used the previously qualified A01 artifact:

`/Users/emilie/Code/371-c02-complete-20261106/.local/c02-a01-rebuild/5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`

Detached run directory: `/tmp/bamf905-final-run-c3d5619`.
The runner emitted a macOS completion notification and did not touch shared learner
state.

Affected result on exact semantic head:

```text
Ran 90 tests in 308.245s
OK
TEST_TOTALS total=90 passed=90 failed=0 skipped=0 errors=0
```

The ring covers visit transport, training adapter/authority/compilation/contracts/
delivery/visibility, real-source authority, the live Factory/B11 bridge, and native
candidate retention custody. It includes the production-style B11 proposer witness
and explicit checks that visit authority cannot alias optimizer or episode identity.

Changed-scope structure/governance, legacy-trainer authority, BAMF flow control,
Python compilation, and `git diff --check` were green before the detached run. No
neural optimizer update, persistent learner, source promotion, or accepted generation
was started by this proof.

## Remaining integration gate

This scoped C02.5 implementation is complete, but it is not independently eligible
for final review/PR because its authority parents are not yet in reviewed unified:

- B13.6/#904 final preserved head `6f91ccf6352888411f76491b58d9e7e9234ec055`
  remains waiting on accepted B13.1/#478 reviewed integration;
- C03/#376 final preserved head `6efa4ebe619b700de49b0942defada6a4919b225`
  remains waiting on reviewed #904 integration.

Resume only after those owner receipts arrive through reviewed unified. Then refresh
this branch once from reviewed unified, rerun only dependency-sensitive proof, and
select #905 for its actual final review/turn-in. Do not sibling-merge #904 or #376.

With this implementation, all four known B06 composition prerequisites now have
scoped implementation branches. B11/#471 still must not compose them until the owner
branches are accepted through reviewed integration.
