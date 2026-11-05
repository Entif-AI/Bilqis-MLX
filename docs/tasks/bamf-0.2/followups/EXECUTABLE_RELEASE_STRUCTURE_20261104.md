# Executable Factory release structural repair

## Observed trigger and ownership

While tracing #785's existing Factory profile authority on reviewed unified
`06eb34d0435d2f41c6f3561cf8cad6988d5b849f`, the encounter checker reports
`executable_release.py` at 908 LoC and its companion test at 568 LoC. The
repository's mandatory structural interruption requires both owners and every
extracted companion to be below 240 LoC before selection work resumes.

Lane A owns the release-contract refactor and its tests. Keep the existing public
module, immutable record and callable identities, source/provider binding,
verification, predecessor checks, serialization and content digests. Factor
cohesive private owners and matching focused tests. Preserve public patch points
used by existing callers. Do not add profile selection or admission policy.

## Exact file and ownership plan

Modify `bilqis_mlx/factory/executable_release.py` into the compatibility facade.
Preserve every original imported public name and `SCHEMA`. Create the private
package `bilqis_mlx/factory/_executable_release/` with these owners:

| File | Definitions moved from the original module |
| --- | --- |
| `primitives.py` | `_ReleaseError`, `_require`, `_digest`, `_require_sha256`, `_tuples`, `AnswerHeadBinding`, `CapabilityVerificationReceipt`, `VerifiedAssessmentSeal`, `ExecutableVerificationReceipt`, `ExecutableAdmissionReceipt` |
| `release.py` | `ExecutableFactoryRelease`, including manifest read/write and digest methods |
| `verification.py` | All six `_verify_release_*` functions: structure, providers, answers, evidence, assessments and lineage |
| `decode.py` | `_decode_curriculum`, `_decode_source_bindings`, `_decode_profile`, `_decode_plan`, `_decode_verification` |
| `evidence.py` | `_provider_descriptors`, `_answer_head_bindings`, `_verification_receipt` |
| `compile.py` | `compile_executable_factory_release` |
| `operations.py` | `compile_successor_profile_release`, `admit_executable_factory_release`, `answer_heads_from_executable_release`, `_prepare_predecessor_transition` |
| `__init__.py` | Package documentation only |

Keep function signatures, bodies, exception strings, serialization key sets and
ordering unchanged. References to original module-global dependencies in moved
bodies resolve through `from .. import executable_release as _api`; this keeps
public facade monkeypatches effective. Annotation-only imports stay with their
owners. After facade imports finish, bind the receipt's forward
`ExecutableFactoryRelease` annotation in `primitives`; do not import the release
class eagerly into that module and create an initialization cycle.

Reexport the same classes/functions from the facade. Set each moved definition's
`__module__` to the original facade name, including ordinary methods and
classmethod/staticmethod functions. Keep dataclass-generated behavior, names and
qualnames intact, so pickle and introspection still use the original public path.
Do not introduce module replacement, dynamic import search paths or new APIs.

Modify `factory/tests/test_executable_release.py` to retain instructional closure,
source footprint, graph and historical compatibility tests. Create companion
files in that same tests directory: `_executable_release_support.py` for unchanged shared disposable
fixtures; `test_executable_release_catalog.py` for semantic graph/catalog and
native modality checks, plus public identity/pickle/facade-patch regression; `test_executable_release_lineage.py` for successor and
predecessor custody; `test_executable_release_manifest.py` for manifests,
rehashing/tamper and verification. Preserve the existing 22 test methods' bodies
and move them by those responsibilities. Add the public identity regression.

Update `docs/operations/error_catalog.json` and `ERROR_FIELD_MANUAL.md` through
the existing generator only after staging all extracted source modules. Its file
inventory uses Git-tracked paths. Preserve the multiset of existing raw exception
identities/counts while updating physical source locations. Do not change scanner
exclusions, governance baselines, debt thresholds or runtime error behavior.

## Ordered implementation and proof

1. Record the existing focused 22-test pass and structural failures at 908/568
   LoC. Preserve the original Git source as the comparison input.
2. Move production definitions and companion tests to the exact owners above.
   Add a failing public-module identity regression before applying the facade
   metadata compatibility binding. Verify the final 23-test selection passes.
3. Check the same representative release against original and extracted source:
   canonical manifest bytes and release digest must match exactly. Compare moved
   definition ASTs after undoing only facade qualification of global lookups.
4. Explicitly verify class/function/method module names, pickle roundtrip,
   public `_digest` monkeypatch behavior and resolution of postponed
   public type annotations. Rehashed profile/provider/specimen drift must still
   reject, as must incompatible predecessor semantic geometry. A valid
   twelve-capability successor remains accepted by the existing test.
5. Stage every new source file, regenerate the error artifacts, and run the
   existing committed-input error-control check. Compare original/candidate raw
   exception identity/count multisets: no active raise disappears during this
   behavior-preserving move. A pre-staging pass is not candidate-wide evidence.
6. Run changed-scope structure, governance, hygiene, Factory architecture, docs,
   ABI and flow-control checks. Every extracted production/test owner is below
   240 LoC. Request independent pinned review only for the stable candidate;
   retain the same episode across repairs. Publish a ready PR to unified only
   after available gates pass. Human sign-off remains required for integration.

## Acceptance

- The public facade and every extracted implementation and companion test are
  below 240 LoC, with cohesive domain names rather than numbered file chunks.
- Existing focused release tests pass before and after extraction. Direct public
  identity, serialization/digest, tamper and predecessor checks remain covered.
- The import graph has no circular initialization failure. Existing release
  readers, compile/admit APIs and provider/answer verification remain usable.
- Source/ABI, changed-scope structure/governance/error/hygiene and independent
  pinned review pass before a ready PR to unified. Human integration is separate.

## Remaining source-selection boundary

A06 `build_feature_manifest(release, feature_schema)` validates the supplied
schema/role/adapter bindings. A03 pins authenticate the selected families; neither
chooses the set for an admitted Factory profile. The A06.2 receipt qualifies
immutable export/readback, not the later C02 fixture's three-family union.
#785 still requires an independently admitted profile/release/generation selector
naming those bindings and predecessor lineage. Hash pinning alone cannot grant
that authority. Multiple valid profiles must remain possible.

This structural repair does not close #785, #420, #395, #490 or the governing
IPR-0220 remediation. Source admission, accepted-generation custody and empirical
learning remain separate. Historical students, own AdamW, teacher, champions,
archives and the 100 GiB reserve remain untouched. Only the human initiates or
resumes actual student updates.
