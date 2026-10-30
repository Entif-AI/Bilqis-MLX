# A08.1b.4 source-qualified scope/modality slice

Issue: #556. Parent: A08.1b #418. Lane A. Consumed unified:
`d468b1af1c70a8dc0c0a7aa5ffa6d19b55cb2e18` through shared Lane A
`e024b9b405b7097bcefe962283c71a91a392dcd5`.

## Verified bounded behavior

`skos_curriculum/scope_source.py` replays the pinned A01 source bundle
and constructs source-identical notation contrasts for all 13 presently
eligible `scope_modality_time` obligations. The exact observed source
categories are `CASE_SCOPE` (5) and `ILLOCUTION` (8). Every contrast
selects another **attested** source value in the same category; it does
not invent an invalid inflection or an unverified transformation.

Each candidate binds exact semantic release, bundle, identity, source row,
grammar-code notation, New Ithkuil source notation, contrasting source
identity, and source evidence digest. The consumer checker reloads A01
and recomputes the candidate, rejecting changed source/reference/meaning,
foreign release/bundle, forged status, self-asserted digests, and type
spoofs. Its answer is the source semantic identity, not an unverified
surface morphology derivation.

Source status is deliberately `SOURCE_NOTATION_NOT_CONTEXTUAL_LAW`.
The independent `source_scope_debt` projection retains **500** exact A01
source-held atomic rows (without mislabelling all as scope/mood) and
**19** nonconcept allomorph-source rows with their original owner,
disposition and reason. Those 19 are `IMPLEMENTATION_UNCOVERED`:
they are not silently given invented semantic identities, methods or rights.
No A13 task grant, rights/revocation, prefix, temporal scope, A03 frame
role law, A07 executable transformation, Factory registration, learner
admission, training, or new root is inferred from this identity evidence.
The pinned A01 inventory has **zero source-eligible
`released_transformations` obligations**; the family remains pending only
through nonconcept source rows. The 13 CASE_SCOPE/ILLOCUTION identities are
all `active=False`, `IMPLEMENTATION_UNCOVERED`, and
`teaching_candidate=False`. Therefore A08.1b.4 cannot lawfully mint an A03
`ConceptRef`, A13 grant, or executable transformation for them merely to make
the leaf look complete. That would promote source notation into semantic
authority. Those source rows cannot be silently reclassified as transformation
lessons from a grammar category or a table name.

The already-integrated A03, A07 and A13 contracts were rechecked on current
unified. Their availability does not cure the missing source-owner bridge:
`A08.1b.5` #557 explicitly owns source-row byte resolution, the released
SKOS/Ithkuil row-to-A03 frame adapter, per-edge provenance, source-owned A13
grant issuance, and the positive/contrast `ApprovedContextProjection`
crosswalk. Its specification explicitly forbids A08 from inventing
`SourceSpan`, `FrameInstance`, `ContextEligibility` or `SourceGrant`
records. Accordingly this leaf preserves the held boundary instead of
fabricating those records.

## Local proof

With `BILQIS_A01_ATLAS_BUNDLE` pointing to the exact recorded
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
artifact, `python3 -m pytest -q
bilqis_mlx/factory/tests/skos/test_scope_source.py` passed the complete
focused suite with zero skips. The suite now additionally asserts that all 13
scope/modality identities remain inactive implementation debt and that no
source-eligible released transformation law exists. Adjacent source construct/checker tests
passed **9 tests and 8 subtests**. Changed-file structure and
governance checks each returned **zero violations**. No neural run.

## Boundary to A08.1b.5

Wrong-scope, future-suffix, role-swap and revocation behavior cannot be
truthfully exercised for these source identities until #557 supplies the
source-owned frame/grant/projection bridge. #557's finish gate explicitly
owns that revocation regression. This leaf's checker-spoof, foreign-release
and source-replay negatives remain local and complete for the source-qualified
projection it actually owns.

Fresh independent EGM remains required before #556 can be called accepted or
merged. Until that review clears the ownership interpretation above, this
receipt makes no `ADAPTER_READY`, `LEARNING_VERIFIED`, Factory-admission or
source-to-neural claim.
