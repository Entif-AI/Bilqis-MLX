# A08.1a formal-domain authority repair candidate

Issue: #417 (A08.1a). Parent A08.1 #416 / A08 #358.
Isolated candidate: `codex/bamf02-a08-formal-authority-20261029`.
Source Lane A baseline: `915e22a884e09b2d981b55378d749db177c1ee8b`.
Reviewed unified ancestor: `6b5460032fc0b19115843cce95fe8be9582af141`.
Independent EGM: **PENDING**. This is not a leaf acceptance or parent closure.

## Source boundary

The A01 v1 artifact already commits the exact formal-domain binding set:
`bundle_id = SHA256(canonical manifest)`; the manifest commits
`atlas.json` bytes; `atlas.json` contains the full canonical formal
bindings. A bare `FrozenAtlasSnapshot` is constructible and can be
replaced while retaining the old identity strings, so A08 must not
accept it as source authority.

`AtlasArtifactSelection/v1` carries an A01 artifact path and claimed
bundle/release/source IDs, but those caller fields are **not** an
authority. The A01 reader first checks them against the repository-owned
`atlas_source_pins_v1.json` whose exact canonical bytes are pinned by
`ATLAS_SOURCE_PIN_REGISTRY_SHA256` in source code. The registry contains
the A01.2 real-corpus receipt identity and explicitly labels it
`A01_SOURCE_ATTESTED_NOT_NEURAL_ADMITTED`. Only then does the existing
database-free reader verify every artifact member and manifest digest.

All four public A08 census, compiler, lesson and checker entrypoints
take a selection and **reload the verified artifact at the consuming
boundary**. There is no caller-constructible in-memory authority
wrapper. Internal pure snapshot functions remain separate for literal
algorithm tests, not for public source admission.

Adding a future source release requires an explicit, reviewed registry
and code-pinned digest update; a caller cannot self-attest a repacked
artifact by changing the expected bundle ID.
This repair does not itself grant a new semantic release or source
admission. It changes no A01 v1 artifact files, schema, bundle ID,
release digest, neural state, or optimizer.

## Discriminating verification

- Real pinned A01 corpus plus synthetic owner suites:
  `test_atlas_projection.py` and `test_skos_curriculum.py`,
  **28 passed, 0 failed, 0 skipped**.
- Adjacent `test_frame_adapters.py` and `test_atlas_features.py`:
  **23 passed, 0 failed, 0 skipped**.
- Repacking a same-family Boolean binding to OR or OR/XOR produces a
  different A01 bundle ID. It fails both the **original** trusted pin
  and a forged **self-attested replacement** pin before any public
  census is returned.
- All public A08 paths reject raw caller-replaced snapshots. The
  removed wrapper cannot be forged with a leaked issuer or mutated
  with `object.__setattr__` because no such wrapper exists.
- The original real A01 bundle identity
  `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`
  remains unchanged. The real census remains 9,307 eligible identities
  and 12,351 required obligations, with no learning credit.
- `git diff --check`: clean. Static error-control and module-size
  checks introduce no new findings beyond inherited unrelated debt.

## Independent review and repair history

Goldfish reviewed immutable `ae2faa1` and returned **EGM NOT PASS**:
zero Blockers, one Major. The initial implementation treated a
caller-mintable selection and an in-process wrapper as source authority.
The reviewer reproduced single-ID and equal-cardinality same-family
substitution using a repacked manifest/new caller pin, plus issuer-token
and `object.__setattr__` wrapper forgery.

The repair removes the wrapper entirely, introduces the repo-owned
SHA-pinned A01 source registry, and reloads the artifact at each public
entrypoint. The original v1 artifact identity is preserved. The
expanded real-corpus tests now reject both self-attested repack forms.
**Fresh independent immutable-head re-review remains required.**

## Second EGM Major: unverified helper outputs

Goldfish reviewed `f8b90c1` and returned **EGM NOT PASS**, zero
Blockers and one Major. Raw-snapshot helper APIs still emitted
authority-looking census/candidate/lesson records when given a
forged eight-concept snapshot carrying all three trusted A01 IDs.
The reviewer also obtained a true checker result from that snapshot.

The next candidate (`0d638ee`) separated unverified schemas and
status from loader-issued attested schemas. Its real pinned owner
suites passed 29/29, but the next EGM exposed a transferable-status
forgery, so this approach was superseded.

## Third EGM Major: no transferable source authority

Goldfish reviewed `0d638ee` and returned **EGM NOT PASS**, zero
Blockers and one Major. A caller could relabel an unverified
`dataclasses.replace`d census, candidate or lesson with the
`A01_PINNED_SOURCE_ATTESTED` status and matching schema. Downstream
A09.1 and A08.1b.5 did not yet require source replay at consumption.

The replacement design **issues no transferable attestation at all**.
Every A08 census, candidate and lesson is a
`SOURCE_PROJECTION_NOT_AUTHORITY` proposal with a proposal-only
schema and fixed, non-promotable status. Raw-snapshot helpers can
produce algorithm projections, but never source authority.

The public consuming assertions
`assert_family_inventory_current`,
`assert_curriculum_candidate_current` and
`assert_source_lesson_set_current` reload the independently
registry-pinned A01 artifact and compare the **entire** proposed
record. They return no reusable authorization token. A09.1 and
A08.1b.5 repo contracts now require these assertions at their own
consuming boundaries, followed by independent live A13 rights.
Direct `dataclasses.replace` status/schema relabeling fails the
record constructor. A forged eight-concept proposal with all three
trusted A01 identity strings fails the consuming assertions.

Real pinned A01 owner suites: **29/29 passed**, zero failures/skips;
no new static debt. The historical v1 A01 artifact remains unchanged.
The subsequent independent review found the equality-override
Major documented below.

## Fourth EGM Major: adversarial equality override

Goldfish reviewed `c78bde8` and returned **EGM NOT PASS**, zero
Blockers and one Major. The source replay assertions still used
Python dataclass `==` on caller-owned objects. Subclasses
overriding `__eq__`/`__ne__` could make an eight-concept fake
inventory, candidate, lesson set or source lesson compare equal
to the real A01-derived record.

The repair uses **exact root and nested type validation** and
canonical source-record bytes, never caller-defined equality,
iteration or deepcopy. The allowed dataclass graph is recursively
walked with exact built-in tuple/dict/scalar types; subclassed
records or nested values fail `BAMF_SOURCE_PROPOSAL_NONCANONICAL_TYPE`.
The independent lesson checker rejects subclasses before
source replay and compares exact canonical bytes to the
source-derived lesson. Optional census inputs receive the same
validation. The consuming curriculum assertion also uses the
code-owned `SOURCE_FAMILY_ADAPTERS`, not caller-supplied
adapter declarations.

The real pinned regression now includes adversarial
`EqAnyInventory`, `EqAnyCandidate`, `EqAnyLessonSet`,
`EqAnyLesson` and nested equality overrides, alongside
same-family self-attested A01 repacks and eight-concept
source-projection drift. **29/29 real owner tests pass**,
zero failures/skips, with no new static debt. No transferable
source attestation, A13 rights, learner credit or neural write
is granted. Fresh independent EGM review of this repair
remains pending.

## Rejected alternative

Adding a new `release.json` to the existing content-addressed
artifact would bind a full release preimage, but would change the
historically pinned A01 bundle ID and require an artifact-format
migration unrelated to this A08 leaf. A local experiment proved that
regression; the candidate preserves the existing v1 artifact instead.

Next: commit this isolated candidate, obtain fresh pinned Goldfish
review against its immutable head, then integrate through the
serialized Lane A writer after its current unrelated dirty work is
reconciled. Do not self-merge the lane PR.

## 2026-10-29 isolated follow-on: exact source-boundary types

The subsequent independent review of immutable `96ae15b` found
three further Majors: subclass-controlled equality at the source-pin
comparison, at the raw A01 reader's expected-ID comparison, and at
lesson/checker answer comparison. A read-only Goldfish inspection of
the separate dirty repair candidate found all three mechanisms
addressed, but that inspection was not an immutable-head EGM PASS.

An independently isolated follow-on branch
`codex/bamf02-a08-authority-final-20261029` incorporates the
reviewed fixes without editing the other candidate worktree.
It revalidates the exact selection dataclass and field types on
each public use, compares repository pins without caller-defined
equality, rejects non-exact expected IDs before artifact access,
and requires exact nested source-lesson/answer types and canonical
relation bytes. The original A01 v1 bundle and source-pin registry
are unchanged. The real-corpus same-family substitution regression
was moved inside the temporary artifact lifetime: its forged
internal projection is allowed to exist as a non-authoritative
proposal, but public A01 replay rejects both one-ID and
equal-cardinality replacements.

Prime verification: `test_skos_curriculum.py` and
`test_atlas_projection.py` with the real pinned corpus,
**31 passed, 0 failed, 0 skipped**. This is an isolated candidate,
not a new source release, A13 rights grant, neural result, or
completed A08 parent. A fresh immutable-head independent EGM
review is still required before integration.
