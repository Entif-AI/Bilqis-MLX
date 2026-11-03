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
