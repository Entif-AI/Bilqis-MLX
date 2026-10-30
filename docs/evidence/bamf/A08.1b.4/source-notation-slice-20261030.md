# A08.1b.4 source-notation slice (not accepted)

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
No A13 task grant, rights/revocation, prefix, temporal scope, A03 frame
role law, A07 executable transformation, Factory registration, learner
admission, training, or new root is inferred from this identity evidence.
The A01 `released_transformations` eligible family count is **zero**;
those source rows cannot be silently reclassified as transformation
lessons from a grammar category or a table name.

## Local proof

With `BILQIS_A01_ATLAS_BUNDLE` pointing to the exact recorded
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
artifact, `python3 -m pytest -q
bilqis_mlx/factory/tests/skos/test_scope_source.py` passed **3 tests,
22 subtests, zero skips**. Adjacent source construct/checker tests
passed **9 tests and 8 subtests**. Changed-file structure and
governance checks each returned **zero violations**. No neural run.

## Explicit remaining acceptance debt

Issue #556 remains OPEN. A source-qualified, task-scoped A13 rights
and correction grant, causal-prefix and temporal enforcement, A03
frame/role semantics, A07 released transformation laws and an independent
typed checker for those actual operations still require owned source
evidence and adversarial proof. Exercise wrong scope, future suffix,
role swap, revocation and checker spoof against that eventual executable
path, followed by independent EGM. Do not use this partial as
`ADAPTER_READY`, `LEARNING_VERIFIED`, or a source-to-neural credential.
