# A02.1 source-bound allocation and detached bank candidate

## Scope and custody

This is an implementation candidate for A02.1/#399, not an admission
receipt or a completed A02 parent. The isolated branch starts from
the scoped source-factor repair at be3b3ac; that repair consumed the
reviewed unified head 7ad8f8a through Lane A at 9fa752b.

New public APIs:

- plan_vocabulary_extension(VocabularyPrior, admissions, ModelTopologySpecV2)
  returns VocabularyExtension
- apply_vocabulary_extension(VocabularyBankParent, VocabularyExtension)
  returns CandidateState
- staged_tied_logits(CandidateState, hidden) returns indices and logits

Versioned records: bilqis.atlas-vocabulary-prior/v1,
bilqis.atlas-vocabulary-extension/v1 and
bilqis.atlas-vocabulary-candidate/v1.

The public planner reloads A01's repository-pinned immutable Atlas
artifact and independently replays the A06 feature manifest. It uses
the existing ABI index, not a new ID allocator. Admission ordering
does not change allocation; 8191 is bank 0 row 8191, 8192 is bank 1
row 0, 16384 is bank 2 row 0, and 65536 is bank 8 row 0. Source
qualification and predecessor digests bind the proposed allocation.

The detached candidate replays the plan against the source, stages
FP32 identity rows from the B01 initializer and A06/B01 source factor,
creates zero AdamW moments and participation counts for new rows,
preserves existing row bytes, and produces an exact active bitmask,
ordered global output domain and Registry mirror delta. Inactive
rows cannot win the tied readout, including an inactive row with
artificially high logits. New bank bytes are estimated and budget
checked before materialization. A feature-category table expansion
not yet staged by its owner fails closed.

The candidate is explicitly STAGED_NOT_ADMITTED. It does not mutate
a persistent student, call an optimizer, publish a checkpoint
pointer, or confer source/rights authority. A02.2 still owns the
complete parameter-tree/optimizer transaction, source admission
receipt, rejection and crash/cold-resume proof. A02.3 still owns the
full Registry evidence/export and resource estimator contract.

## Independent factor-authority review repair

A fresh-context Goldfish review of upstream be3b3ac found one Major:
A06's prospective graph channel 7 treated every row in
release.withheld_rows as unresolved mapping. A01 also puts
source-eligible but implementation-uncovered rows in that file.
Thus an eligible inactive identity was incorrectly assigned an
unresolved graph feature, contaminating its initialized factor.

Both A06 admitted and prospective paths now derive channel 7 only
from source_disposition == SOURCE_HELD, not downstream implementation
debt. The regression supplies an explicit SOURCE_ELIGIBLE /
IMPLEMENTATION_UNCOVERED row and a graph projector reading only
channel 7; the resulting 768-wide factor is exactly zero.
The original Goldfish review also verified the numerical projector,
pin checks and absence of a B02 dependency. A fresh immutable-head
re-review of this repair remains required.

## Focused verification

Use the established Python 3.12 MLX environment with the focused
atlas_vocabulary, atlas_features and model_topology_v2 suites.
The real A01 corpus witness recompiles and persists A01 into a
disposable directory, reloads through the registered source pin,
and exercises the public allocation planner. It never starts a
learner or promotes a source.

Scoped EGM disposition: PENDING targeted readback of the final
immutable candidate. No leaf or parent closure is claimed.
