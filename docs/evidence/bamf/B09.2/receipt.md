# B09.2 per-step legal participation and update masks

Issue: [#465](https://github.com/Entif-AI/Bilqis-MLX/issues/465)
Lane: B, isolated candidate `codex/b09-465-participation-20261101`
Consumed reviewed unified / Lane B: `bd62f3cb6c296151aba7b9ed5fa90ee814492494`

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
FAST identity banks remain whole-tensor SLOW in the B01 census, but only their
age0-7 rows are exposed through the existing `fast_identity_rows` exception;
established age8 rows remain frozen until FULL. Motif global slots are mapped to
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

This candidate deliberately accepts detached typed participation evidence only
as a fixture-level software contract. Final production turn-in must bind those
inputs to the actual accepted B05/B08/B11 execution/read receipts. B08.1/#460 is
currently blocked on the separately decomposed A06/A13/B02 type-authority issue
#691, so this receipt does not claim production provenance or final B09
integration. No synthetic motif read, group plan, or caller record is promoted
into retained authority.

## Verification

Focused B09.2 tests prove:

- two internal optimizer steps produce different literal row masks;
- actual B01 FAST eligibility exposes young identity rows but not established
  rows;
- active/admitted state is independently required;
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
