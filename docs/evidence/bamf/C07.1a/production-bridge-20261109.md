# C07.1a production adoption bridge checkpoint — 2026-11-09

Status: **PARTIAL; #509 remains open.** This checkpoint extends the earlier
C07.1a lease/staging slice after reviewed #510 and A02.2 integration. It does
not claim the human command can yet enroll a production Atlas lease, and it
does not claim the parent C07 three-successor/resume acceptance.

## Reviewed baseline and consumed owners

- reviewed unified consumed by Lane C:
  `0338f334388a01389163fb0cba74614c2bcdb83a`
- #509 / PR #550 integration is an ancestor:
  `4fdb3dc069e6c1f5a156cbf0c2551f2d8161e7f5`
- #510 / PR #944 native adoption integration is an ancestor:
  `6a770f10074df6f4f8889d439f783ad42f5efe63`
- current reviewed unified also contains the A02.2 production-staging work
  qualified through PR #952.

## Bounded change in this checkpoint

`AtlasAdmissionContext` may now carry one all-or-none accepted-run handoff:
the prepared-successor runtime, an owner-issued A02 staged vocabulary
extension, and opaque current C09 source authority. These values are not a new
authorization token. The existing C07 policy still validates the exact native
proposal/staged Factory successor, persisted lease run identity, source/rights
scope, post-admission resource ceilings, per-delta budget, and current source
and answer implementations before the handoff can be used.

Before mutation, the production bridge additionally requires the disposable
delta registry digest to equal the registry digest already sealed into accepted
B13/C09 execution custody. Current source and answer implementations are loaded
from their code-owned production registries rather than accepted from the caller,
and post-admission bank/resource totals are recomputed from the owner-issued A02
candidate plus the B01 parameter census rather than trusted from the signed C07
envelope.

After those checks, `advance_atlas_frontier(...)` may delegate the exact
transaction to #510's native executor. A successful native publication returns
the v2 `ADOPTED` result with zero neural updates, the accepted generation and
manifest identity, and an explicit `requires_cold_resume=true` invariant. The
caller must cold-resume from accepted B13 custody rather than continue on stale
in-memory parameters or optimizer state. Without the accepted-run handoff, the
previous `STAGED / ACCEPTED_RUN_AUTHORITY_UNAVAILABLE` behavior is unchanged.

The bridge additionally checks that the semantic IDs in the sealed A02 staging
plan equal the semantic-catalog suffix of the selected Factory successor and
that this exact count equals the C07 delta envelope's declared new-semantic-ID
count. This closes the cross-owner mismatch in which a valid A02 parameter
extension for one semantic delta could otherwise accompany a different Factory
successor.

## Verification

Focused policy ring after the semantic, registry, resource and cold-resume
bindings:

```text
/tmp/bamf-c05-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/admission/atlas/test_atlas_admission_policy.py
TEST_TOTALS total=10 passed=10 failed=0 skipped=0 errors=0
```

Concrete owner-issued A02 helper witness (no patched A02 issuance, semantic
binding or resource-total derivation):

```text
/tmp/bamf-c05-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/admission/atlas/test_atlas_production_admission.py
TEST_TOTALS total=1 passed=1 failed=0 skipped=0 errors=0
```

Complete Atlas-admission package:

```text
/tmp/bamf-c05-venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/runtime/tests/admission/atlas
TEST_TOTALS total=46 passed=45 failed=0 skipped=1 errors=0
```

The one skip is the existing explicitly gated full A02 -> C07/B13 environment
witness. The concrete #510 Factory-persist -> B13-publish -> cold-read -> exact
retry witness runs and passes inside this package.

Repository gates:

```text
/tmp/bamf-c05-venv/bin/python -B scripts/check_bamf_flow_control.py
BAMF_FLOW_CONTROL_OK

/tmp/bamf-c05-venv/bin/python -B scripts/verify_bamf_0_2_contracts.py
PASS: 43/43 exact checked-in issue mirrors
PASS: 43/43 issue API, implementation and acceptance fields
PASS: all 217 BAMF owner/child specs retain indexed identity and source fingerprints
PASS: 174 recursive child mirrors retain correct SHA/parent/source partitions

git diff --check
PASS
```

No live learner, optimizer step, or PRIVATE_REAL payload was started or read.

## Remaining #509 acceptance gaps

This checkpoint deliberately does not close #509.

1. The historical `AtlasDeltaEnvelope` is still a signed disposable C07
   projection. There is no production issuer for its detached per-delta
   signature. C09 verifies source authority but must not be repurposed as a
   signer. Production must either consume an already-authoritative A09/A02
   handoff for these fields or gain an explicit source-owner issuer; fixture
   signatures are not production authority.
2. The current human `--admission-policy atlas-release` command still rejects
   before learner initialization because accepted BAMF create/resume authority
   is not yet available at that CLI boundary. This is now explicitly owned by
   #950 (`C16.1c` generation-zero C09 source authority); do not route around the
   guard or consume an unreviewed sibling branch directly.
3. A production source bundle is content-verified by A02 but still arrives by
   mounted path; no accepted content-addressed `source_bundle_id -> Path`
   resolver exists. This checkpoint consumes an already owner-issued A02
   handoff and therefore does not invent or persist a host path.
4. A09 can lawfully produce a Factory successor which adds an executable
   capability while introducing **zero** semantic catalog rows. The current
   #510/B13 native mutation path, however, accepts an owner-issued A02
   `PARAMETER_EXTENSION`; A02 correctly cannot issue an empty vocabulary
   extension. The current #510 native fixture itself demonstrates this case
   (`Z.C6` is added with an empty semantic-catalog suffix). This capability-only
   transition therefore needs an explicit C07/B13 owner path; it must not be
   counterfeited as an empty A02 parameter extension.
5. Recursive repetition, rebind after each B13 generation, three-successor
   admission, and cold resume after the second successor remain the downstream
   integration/flywheel proof. In particular, current C09 source authority is
   generation-bound and must be reacquired from accepted custody after an
   admitted generation.

These gaps are preserved as blockers rather than weakened into fixture-only
acceptance.
