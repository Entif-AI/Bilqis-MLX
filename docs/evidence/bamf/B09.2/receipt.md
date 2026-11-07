# B09.2 per-step legal participation and update masks

Issue: [#465](https://github.com/Entif-AI/Bilqis-MLX/issues/465)
Lane: B, isolated candidate `codex/b09-465-participation-20261101`
Consumed reviewed unified / Lane B: `3088ee02d085f2a88e53b7c78c8d9637916663fe`

## Owned software

`learning/atlas_participation.py` is a pure B09.2 policy surface. It does not own
AdamW state, clipping, retained-generation publication, source admission, or
model execution receipts.

The typed inputs preserve the four distinct participation sources from B09:

- visible/input and feedback identity rows;
- legal tied-output identity and feature denominator rows;
- motif slots reported as actually gathered by B08 read results;
- role/type/schema feature rows reported as gathered by the role-output path;
- dense parameter names reported as actually executed on a loss-bearing path.

`step_participation(...)` unions only those witnesses for the current optimizer
step. No loss-bearing target yields an empty participation record, so the whole
optimizer step is skipped downstream.

`parameter_update_mask(...)` derives the final legal mask as candidate-start
group eligibility AND actual per-step participation AND active/admitted rows.
Identity rows are always intersected with the candidate-start frozen
`admitted_identity_rows` set before any optimizer geometry is emitted. FAST
identity banks remain whole-tensor SLOW in the B01 census, and further narrow
that frozen set to age0-7 `fast_identity_rows`; established age8 rows remain
frozen until FULL. Motif global slots are mapped to
their declared B01 page rows, and type/role/schema tables are row-masked.
Eligible dense modules update only when named as actually executed on the
loss-bearing path.

`mask_gradients(...)` applies that mask before any clipping or AdamW arithmetic.
It intentionally does not inspect numerical gradient magnitude: a legally
participating row with a zero numerical gradient remains participating, while a
huge gradient on an ineligible or unparticipating row becomes exact zero before
the downstream global norm. B12 remains the owner of moment/count/decay
arithmetic and must advance counts for legally participating zero-gradient rows.

Existing retained row-age arithmetic consumes the deduplicated union of actual
masked identity rows across internal steps and increments each such row once per
accepted candidate. Rejection preserves the exact parent ages.

## Dependency boundary

The participation inputs now come from their owners on the production path.
`runtime/_custody/bamf_bundle/admission.py` derives the group eligibility from
the B01 parameter census owner and the retained policy owner, the admitted rows
from the published custody, the executed parameter names from the same census,
and the topology and extents from the accepted parent. The production step API
accepts no caller-authored participation facts, so no caller can claim a
parameter executed, substitute identity rows or admission state, or reclassify a
SLOW parameter. The B08 motif read results remain owner records, and the
binder uses only the participating slots those records report.

The owner also seals the provenance against replay: it binds the run,
generation, parent manifest, parent candidate identity, parent optimizer step
and topology digest, and B12.2 refuses provenance issued for another candidate,
step, generation or topology.

B08.1/#460 remains blocked on the separately decomposed A06/A13/B02 type-authority
issue #691, so this receipt does not claim the final B09 integration. No
synthetic motif read, group plan, or caller record is promoted into retained
authority.

## Verification

Focused B09.2 tests prove:

- two internal optimizer steps produce different literal row masks;
- actual B01 FAST eligibility exposes young identity rows but not established
  rows;
- active/admitted state is independently required;
- FULL/FOUNDATION cannot update an identity row absent from the candidate-start
  frozen admission set, even if later step evidence marks it active/admitted;
- motif and feature rows update only when actually gathered/legal;
- a huge masked gradient is exact zero before clipping;
- a participating numerical-zero row remains legally participating;
- no-loss steps produce no updates;
- eight internal steps still contribute at most one accepted-age increment per
  row once the candidate is retained;
- malformed/unsorted participation evidence fails closed.

The inherited B09 adapter/cadence suite remains green. No live learner, optimizer
moments/counts, checkpoint, accepted generation, teacher choice, or student
parameter was mutated.


## Completion addendum — 2026-11-06

This addendum supersedes the historical integration-status sentence above without
rewriting the evidence that was true when the original receipt was authored.

Issue #465's original candidate was correctly rejected by pinned Goldfish because
caller-mintable eligibility/participation records could authorize a contradictory
FAST-over-SLOW update. Remediation issue #711 closed that authority seam by binding
B09 participation and final masks to production execution ownership and the B01
census, while #710 bound B12 candidate steps to the resulting owner-issued
execution provenance.

The accepted remediation lineage was consolidated in PR #809. Pinned Goldfish EGM
checkout `b3a35956759bf7f024af2ff061b2e0b44b438e4c` passed the semantic candidate
`93233f86849f374ce5026291d4fd5cfa902a2e31` with **0 Blockers / 0 Majors /
0 Nits** after the sole initial mirror-policy Major was repaired and re-audited.
PR #809 then passed fresh hosted `portable-core`, `portable`, and
`semantic-abi-integrity` checks and merged into reviewed unified as
`b16941114dee33247ee9a9e6c013797b9d82af27`.

The reviewed-unified production path now:
- rederives group eligibility from accepted B01 topology/census and retained policy;
- consumes B11-issued loss execution, including actual identity, feature,
  local-slot, dense-parameter, semantic-denominator, role-read, and retained B08
  motif-read facts;
- rejects caller-authored execution participation and forged FAST
  reclassification of SLOW parameters;
- applies the final B09 mask before clipping and B12 AdamW arithmetic;
- advances selected zero-gradient rows through B12's moment/count/decay owner while
  leaving nonparticipants byte-identical;
- increments row establishment age only from accepted candidates and preserves
  parent clocks/state on rejection;
- seals run/generation/parent/topology/step identity so provenance cannot be
  replayed as another candidate step.

The historical #691/B08.1 integration hold recorded above is therefore no longer a
B09.2 completion blocker. The accepted #710/#711 remediation is present in the
reviewed-unified ancestry, and both remediation issues are CLOSED/COMPLETED with
`EGM-Passed`.

### Final B09.2 acceptance ledger

- Original issue: #465 / B09.2.
- Original failed candidate: PR #692, head
  `a1025e442277ee71b2120f87b9254179cee88dfb`.
- Corrective owner: #711; coupled B12 provenance remediation: #710.
- Accepted integration: PR #809.
- Accepted reviewed-unified merge commit:
  `b16941114dee33247ee9a9e6c013797b9d82af27`.
- Pinned semantic EGM: PASS, 0 Blockers / 0 Majors / 0 Nits.
- Fresh hosted merge-head checks: portable-core PASS; portable PASS;
  semantic-abi-integrity PASS.
- No live human-owned student, optimizer lineage, checkpoint, teacher, champion,
  or durable neural run was started or mutated by this closeout.

This closeout branch is documentation-only. It does not create a second B09.2
implementation or fork the accepted authority path.
