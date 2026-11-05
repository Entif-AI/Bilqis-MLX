# BAMF-0.2 A12.1 completion receipt

Issue: #427
Lane: A
Implementation base reviewed unified: 88ac132db2fd1c3606fa5f06637d10a7ab40cba4
Latest reviewed unified consumed before final turn-in: 22314c413ba137df69b3d6b35768fe65e1556bfe
Implementation checkpoint: 68f288cd9e20b54bbc8c0b8a775196b9f3335ba8
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

audit_atlas_authority(release, abi, ast, lesson_manifest, registry_mirror)
accepts only the current immutable typed records, reloads the repository-pinned
A01 snapshot, re-enters the repository-owned A03 frame-schema pin ledger, and
returns a deterministic AuthorityReceipt containing separate consumer bindings
and graph/formal-domain digests. Lesson semantic IDs, constituents, and
prerequisite closure must all resolve inside the admitted A01/formal-domain
authority set.

A deliberate ABI release mismatch is rejected at the first audit boundary with
A12_AUTHORITY_SOURCE_BINDING_MISMATCH. An unpinned A03 manifest is rejected with
A12_AUTHORITY_AST_SOURCE_PIN_MISMATCH, and a lesson that smuggles a foreign
constituent/prerequisite is rejected with A12_AUTHORITY_LESSON_SOURCE_MISMATCH.
A held source identity remains held even when a nearby admitted concept receives
a plausible English gloss or its labels are renamed/reordered: the held identity
cannot be activated through the vocabulary planner, projected into prospective
factor features, emitted as a Factory source lesson, or promoted by the
curriculum/teacher candidate surface; its source-owned hold reason is preserved.

The status remains SOURCE_ATTESTED_NOT_NEURAL_ADMITTED; this leaf does not
upgrade staged A02 vocabulary state or source-projection lessons into neural
admission.

## Verification

Owner suite, default:

python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_release_audit.py

Result: 10 passed, 0 failed, 1 expected optional-real-source skip.

Real producer replay, using the repository-pinned A01 artifact and its exact
source bundle:

BILQIS_A01_ATLAS_BUNDLE=<pinned-atlas-artifact> BILQIS_A01_SOURCE_BUNDLE=<pinned-source-bundle> python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/test_atlas_release_audit.py

Result: 9 passed, 0 failed, 0 skipped. The replay exercised the current A02
vocabulary planner and Registry mirror builder, the current A03 pinned released
frame-schema loader, the current Factory source-lesson compiler, and the A12.1
audit.

Adjacent owner proof:

python3 -B scripts/run_tests.py bilqis_mlx/semantics/tests/released_schemas bilqis_mlx/semantics/tests/atlas/test_vocabulary_planning.py bilqis_mlx/factory/tests/skos/test_skos_curriculum_constructive.py

Result: 24 passed, 0 failed, 2 expected optional-source skips.

Additional gates:

- python3 -B scripts/check_semantic_boundaries.py -> SEMANTIC_BOUNDARIES_OK
- governance/error-contract tests -> 11 passed, 0 failed
- exact error-control-plane relative to reviewed unified -> new debt 0
- module-size/development-structure check -> 0 violations
- governance-integrity check -> 0 violations
- py_compile -> clean
- git diff --check -> clean

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

The first fresh exact-head EGM on 859dd3fc identified one Blocker and two Majors:
the audit did not re-enter the A03 source-pin ledger, lesson constituents and
prerequisite closure were not checked against admitted semantic authority, and
the required cross-surface held-gloss adversary had not been demonstrated. This
receipt records the resulting repair. A fresh independent EGM of the final
repair head remains required before integration.
