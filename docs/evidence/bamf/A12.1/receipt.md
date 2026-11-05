# BAMF-0.2 A12.1 completion receipt

Issue: #427
Lane: A
Implementation base reviewed unified: 88ac132db2fd1c3606fa5f06637d10a7ab40cba4
Latest reviewed unified consumed before final turn-in: 672f97d7049dd951f86630844e3a80b60c4563dd
Implementation checkpoint: c2a3c9e27f98f38c4e904bd9bd7d4a05002b3739
Branch: codex/bamf02-a12-1-427-20261105
Disposition: TURNED_IN / EGM_PENDING

## Source authority consumed

The audit re-enters the repository-owned A01 source pin. It does not mint source
or neural admission.

- Atlas bundle: 5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7
- Semantic release: 58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306
- Source bundle: f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec
- A03 released-frame schemas are loaded through the repository-owned current
  source-pin ledger after consuming merged PR #859 / reviewed unified 978ac927.
- Prior ABI ledger: copular_registry_v1.json, verified against the frozen
  snapshot prior_abi_sha256
  30d18c7140d49c168488416e04644b934ea79492561c2b73f65e55be18ed4e8c.

## Source-to-consumer table

| Consumer | Current typed owner | Binding checked |
| --- | --- | --- |
| ABI | VocabularyExtension | A01 semantic release, source bundle, exact ABI index |
| AST / frames | VerifiedReleasedFrameSchemas | A03 pinned manifest, A01 release/bundle/source |
| Lessons | SourceConstructiveLessonSet | A01 release and source/formal semantic identity |
| Graph projection | frozen A01 FrozenAtlasSnapshot | independently derived digest over current read-only semantic/concept lookup and relations |
| Registry mirror | RegistryMirrorDelta | A02 allocation digest, predecessor, active indices and exact rows |

Declared formal-domain bindings are derived from the frozen snapshot and remain
separate source authorities, digest-bound individually. copular_registry_v1.json
is the current predecessor/prior-ABI ledger, not a formal domain.
atlas_projection.py is classified as a historical compatibility facade, not an
independent current semantic authority. The A01 and A03 repository pin ledgers
are current source and derived-source pin ledgers.

## Observable behavior

audit_atlas_authority(release, abi, ast, lesson_manifest, registry_mirror,
*, abi_prior, source_bundle_path) accepts only the current immutable typed
records plus two replay locators owned by existing upstream authorities. The
VocabularyPrior is revalidated by the A02 planner; source_bundle_path is only a
locator whose content-addressed identity is verified against A01. The audit
replays VocabularyExtension, RegistryMirrorDelta and the complete Factory
lesson set from those pinned owners before returning a deterministic
AuthorityReceipt. It also re-enters the repository-owned A03 frame-schema pin
ledger and separately binds the read-only graph/formal-domain projections.

A deliberate ABI release mismatch is rejected at the first audit boundary with
A12_AUTHORITY_SOURCE_BINDING_MISMATCH. Self-consistent caller tampering of the
ABI source-allocation/prospective-feature digests is rejected with
A12_AUTHORITY_ABI_SOURCE_MISMATCH; caller-minted Registry source-record lineage
is rejected with A12_AUTHORITY_REGISTRY_MIRROR_MISMATCH; and lesson census or
source-evidence drift is rejected with A12_AUTHORITY_LESSON_SOURCE_MISMATCH. An
unpinned A03 manifest is rejected with A12_AUTHORITY_AST_SOURCE_PIN_MISMATCH.
A held source identity remains held even when a nearby admitted concept receives
a plausible English gloss or its labels are renamed/reordered: the held identity
cannot be activated through the vocabulary planner, projected into prospective
factor features, emitted as a Factory source lesson, or promoted by the
curriculum/teacher candidate surface. The Factory `SourceConstructiveLessonSet`
now carries the exact source-owned `SOURCE_HELD` rows alongside emitted lessons,
so omission is observable with the original reason/owner rather than becoming a
silent exclusion; the teacher surface preserves the same evidence.

The status remains SOURCE_ATTESTED_NOT_NEURAL_ADMITTED; this leaf does not
upgrade staged A02 vocabulary state or source-projection lessons into neural
admission.

## Verification

Owner suite, source-free, including the final independent-review repair:

python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_release_audit.py bilqis_mlx/semantics/tests/test_atlas_release_held_gloss.py bilqis_mlx/semantics/tests/test_atlas_export_clearance.py

Result: 10 passed, 0 failed, 0 skipped in an isolated verification venv with
`rdflib`, `pyshacl`, and `cryptography` installed. The final repair moves
detached signature verification into the exported clearance validator itself,
so caller-minted 128-hex signatures cannot obtain a clearance digest merely by
matching release/frontier/artifact fields. The stale-shadow regression now
poisons the actual historical catalog loader and proves the current A12 path
does not consult it.

Real producer replay, using the repository-pinned A01 artifact and its exact
source bundle:

BILQIS_A01_ATLAS_BUNDLE=<pinned-atlas-artifact> BILQIS_A01_SOURCE_BUNDLE=<pinned-source-bundle> python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_release_replay.py

Result: 1 passed, 0 failed, 0 skipped. The canonical A01 conformance source
bundle was located by its content address, and the production A01 compiler
regenerated semantic release `58e0c281...` and exact Atlas bundle
`5f8fba20...` before the witness ran. The unmocked chain then exercised the
current A02 vocabulary planner, source-backed Registry mirror builder, A03
pinned released-frame loader, A08 source-lesson compiler, and A12 audit.

Adjacent owner proof:

python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/released_schemas bilqis_mlx/semantics/tests/atlas/test_vocabulary_planning.py bilqis_mlx/semantics/tests/atlas/test_vocabulary_resources.py bilqis_mlx/factory/tests/skos/test_skos_curriculum_constructive.py bilqis_mlx/semantics/tests/test_atlas_features.py

Result: 26 passed, 0 failed, 2 expected optional-source skips.

Additional gates:

- python3 -B scripts/check_semantic_boundaries.py -> SEMANTIC_BOUNDARIES_OK
- exact error-control-plane relative to reviewed unified -> new debt 0
- changed-file smell audit -> 0 findings
- module-size/development-structure check -> 0 violations after splitting the
  387-line audit owner into a 19-line facade plus 131/120/95-line cohesive
  submodules; companion tests are all <240 lines
- governance-integrity check -> 0 violations
- py_compile -> clean
- git diff --check -> clean
- post-unified-merge replay on 672f97d7 repeated focused 10/10, real producer 1/1, adjacent 26 passed / 0 failed / 2 expected skips, and all gates above green

## Existing-owner disposition and non-claims

- #295 remains OPEN. This child supplies the cross-consumer audit mechanism; it
  does not claim the complete no-shadow cutover is integrated.
- #309 remains OPEN for exact combined-candidate qualification.
- Parent A12/#364 remains OPEN for A12.2/A12.3 and complete parent acceptance.
- This leaf does not claim live student/neural admission, does not mutate
  optimizer state, and does not replace any declared formal domain with SKOS.
- Historical receipts/readers remain preserved; no compatibility evidence was
  deleted.

## Independent review

The first fresh exact-head EGM on 859dd3fc identified one Blocker and two Majors
around A03 pinning, lesson authority and the held-gloss adversary. The next
exact-head reviews on e929ed23 found a further source-authentication gap: A12
could still accept self-consistent caller-minted VocabularyExtension,
RegistryMirror and lesson evidence, and the companion test file violated the
repository structure contract. The repair now replays those consumers through
their existing A02/A01/A08 producers, propagates source-owned held reasons, and
remediates the structural offender without weakening the gate. Independent
review of a0c0a6b1 then found one remaining Major: the exported clearance
validator checked signature shape but left detached-signature authentication to
test-local composition, permitting caller-minted clearance evidence. It also
found the stale-shadow regression vacuous. Checkpoint f82cda87 makes the
trusted `SourceAuthorityRegistry` mandatory in the public validator, performs
`verify_detached` before clearance, and replaces the vacuous shadow test with a
poisoned historical-loader witness. Independent review of the subsequent
`a0c0a6b1` repair also required the Factory lesson-emission surface itself to
carry the exact source-owned held reason and required an unmocked real-producer
replay of the newly wired authority composition. Checkpoint `c2a3c9e2` closes
both: `SourceConstructiveLessonSet.source_holds` preserves the A01 hold records,
and the regenerated exact A01 artifact passed the full A02/A03/A08/A12 replay
witness 1/1. A fresh independent EGM of the final pushed head remains required
before integration.
