# A02.3 accepted Registry mirror/resource export qualification — 2026-11-09

Issue #401. Lane A branch `codex/bamf02-a-semantics`.

Reviewed unified consumed before issue-owned edits:
`0338f334388a01389163fb0cba74614c2bcdb83a`.

Current remotely verified semantic head:
`db0bde381eccca4207623014cb1f728258bf4d3e`.

Status: **IMPLEMENTATION_AND_ACCEPTED_READBACK_PROOF_COMPLETE; INDEPENDENT EXACT-HEAD REVIEW PENDING**.

## Historical A02.3 work retained

The historical A02.3 implementation already owned the source-derived Registry
mirror and conservative bank resource estimate:

- each mirror row binds semantic ID, exact ABI index, bank/row, source status,
  source-record digest and source-attested `SKOS.definition`;
- mirror active indices equal the staged output domain and are deterministic
  under admission input reordering;
- resource estimation accounts for new FP32 bank weights plus both AdamW moment
  arrays, the full-checkpoint lower bound, the existing 100 GiB runtime reserve
  and the additional 30 GiB planning allowance;
- A02 stages both derivatives with the exact successor candidate and seals their
  digests in `A02VocabularyStagingReceipt`.

The prior scoped EGM had already passed after the source-definition and
foreign-source-bundle repairs. Its explicit remaining owner work was accepted
Registry evidence/export persistence and readback.

## Accepted export boundary

Current #399/#400/#510 integration now persists A02's staging event inside the
accepted B13 generation bundle. A02.3 therefore completes its missing boundary
by reading the derivative back from **accepted custody**, rather than writing
semantic truth into the live Curriculum Registry spreadsheet.

`read_accepted_vocabulary_registry_export(run_dir)`:

1. follows the accepted `bamf-state.json` pointer and immutable B13 bundle;
2. requires a generation-specific C07 `AtlasAdmissionBinding`;
3. parses and re-digests the persisted A02 staging receipt;
4. requires the C07 binding's `staging_receipt_sha256` to match that receipt;
5. revalidates accepted candidate identity, extents, active set, feature digest
   and semantic-bank count;
6. re-digests the persisted allocation plan, Registry mirror and stable resource
   requirement against the receipt;
7. cross-checks source release, source bundle, predecessor generation,
   allocation-source digest, active indices, and every mirror row against the
   persisted plan allocation;
8. returns a typed `AcceptedVocabularyRegistryExport` containing mirror rows,
   allocation lineage and the complete stable bank resource requirement.

The export is explicitly
`status=ACCEPTED_DERIVED_NAVIGATION_EVIDENCE`,
`semantic_authority=false`, and `training_authorized=false`. It does not
modify the Curriculum Registry or create a parallel semantic registry. The
spreadsheet remains a navigable evidence/review surface; accepted source and
B13/C07 custody remain execution authority.

## TDD receipt

The composed C07/B13 cold-read witness was extended first. Before production
implementation it failed exactly because
`read_accepted_vocabulary_registry_export` did not exist:

```text
ImportError: cannot import name 'read_accepted_vocabulary_registry_export'
from 'bilqis_mlx.runtime.bamf_bundle'
```

After implementation, the same real composed witness:

`real B13 genesis -> A02 staged plan/mirror/resource -> C07/B13 publication
-> accepted cold read -> Registry export readback -> exact retry`

passes and verifies the accepted manifest, mirror digest, active indices,
resource requirement, export digest, and both authority-denial flags.

## Verification

```text
accepted C07/B13 commit + Registry export readback:                  1 PASS
A02 mirror/resources + allocation planning:                        9 run; 8 PASS, 1 explicit opt-in skip
A02 production staging/acceptance + C07 executor/publication:     12 run; 11 PASS, 1 explicit opt-in skip

development structure/governance: PASS
changed-file smell audit:         0 findings
error-control:                    PASS, new debt 0
BAMF flow-control tests:          15/15 PASS
BAMF exact issue mirrors:         43/43 PASS
docs check:                       PASS
git diff --check:                 PASS
```

No live learner, shared optimizer update, Registry spreadsheet mutation or
neural training workload was started by this qualification.

## Remaining gate

Fresh independent exact-head review must inspect semantic head `db0bde38`
against #401's Registry evidence/export and resource-estimate contract before
normal human-review PR turn-in. No self-merge is authorized.
