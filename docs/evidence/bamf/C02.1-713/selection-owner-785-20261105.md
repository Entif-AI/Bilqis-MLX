# A06 selection authority after canonical Factory integration

As of 5 November 2026, reviewed unified is `77cd6bf9a49d947d602797c9f5554971ef555728`. Lane A/C remote intake matches that source. The preserved #785 branch consumes it at `934ae6bafde08818d46d178c1e18bbdbfe534d61`; activation preceded merge. Only its Lane A ledger conflicted, resolved by retaining incoming records and the active #785 bookmark. Source assets remain read-only.

PR846 is externally merged as `879c39dd68308c7a8e5f8c09bc1624317f47b457`; #842 is explicitly CLOSED. Its final metadata-only head 0bf80871 preserves the reviewed Factory implementation. This resolves the encountered execution-owner interruption. No additional EGM episode or source admission follows from that integration.

## What the resumed owner trace establishes

- `factory/execution.py` owns `CurriculumProfile`, `GradeProfile`, `CapabilityProfile` and the execution data records. Profile compilation narrows capability/provider/answer parameters and verifies the supplied `SourceBindingSet`; `CurriculumProfile.full()` means full supplied curriculum, not an A03 feature inventory.
- `factory/curriculum_definition.py` source bindings map a capability to source anchor, generator and oracle; the set can carry an opaque source-attestation digest. The current inspected compiler does not interpret that digest as an A06 schema/adapter selection grant.
- `factory/_executable_release/compile.py` binds curriculum, supplied profile, source/provider descriptors, answer heads, semantic catalog, verification, predecessor and transition. Its inspected compile/verification route contains no A06 feature-manifest or A03 schema/role/adapter selection operation. Generic provider parameter slots are not themselves a normative interpretation of a new A06 binding.
- `factory/_executable_release/operations.py:admit_executable_factory_release` binds an already verified release to a causal student baseline. Its receipt binds Factory release, plan, curriculum/source/catalog/graph digests, student and optimizer step. It does not add an independent A01/A03/A06 selection record. No admission function was invoked for this trace.
- `semantics/atlas_features/records.py:FeatureSchema` receives role IDs, schema IDs, predecessor and the caller-supplied schema/adapter tuple. `manifest.py:build_feature_manifest` and `sources.py:_source_rule_categories` prove that tuple source-valid and derive roles from it; they do not choose the tuple. `AtlasFeatures` still omits the original tuple.
- Live #411/#412 receipts still qualify deterministic projection and immutable local export. Their feature contract supplies hashing, append-only rows and source-validity rules; neither receipt independently admits the C02 union selection. The inspected A06 owners are unchanged from the previously pinned 06eb34d0 source. The two distinct source-valid artifacts recorded in `source-selection-785-20261104.md` therefore remain relevant; no duplicate build was run.

These observations exclude this inspected generic Factory route as the missing selection issuer. They are not a claim that an uninspected upstream artifact cannot exist.

## Proof and exact held predicate

Current-source C02 real-artifact consumer interface: **4/4 PASS, zero skips**, loader-verified A01 artifact `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`:

```sh
BILQIS_ATLAS_REAL_ARTIFACT=/path/to/pinned/artifact python3 -B scripts/run_tests.py bilqis_mlx/runtime/tests/batch/test_atlas_training_real_source.py
```

Tested environment is the existing isolated Python 3.14.4 portable environment. Log: `/tmp/c785-77cd-interface.log`. This is consumer interface engineering proof under the fixture's explicit test authority, not proof of initial selection authority. The earlier 26/26 A06 and two exact artifact readbacks are reused because those owners/inputs are unchanged; no full model, A01/C05 witness, native optimizer or expensive suite was rerun.

Classification remains AUTHORITY_GAP: a canonical admitted source/profile selection or an already-approved derivation must bind A01 release/Atlas/source identity, the complete chosen A03/schema/role/adapter tuple, feature bundle/digest and predecessor lineage. A generic profile label, content hash, self-consistent receipt or caller-provided tuple cannot substitute for that missing grant. No normative global schema, parallel registry, selection label, source admission or generation acceptance was invented. #785/#490 remain held; #708 retained-generation authority is separate.

## Preserved fallback checkpoint

While Lane C awaited #846, the stopped #810 solver interruption was resumed and pushed on its existing issue branch. Structural code 344c4a58 and bookkeeping 61ec1e4e preserve all 11 pre-existing dirty/untracked feature files byte-for-byte and unstaged. Solver public execution 73 lines, session 95, routes 79; mirrored route/session/boundary tests 18/18 pass, zero skips. Normalization proves 5 closure bodies, 9 initializers, 4 route bodies and 14 original tests. Scoped hygiene has 0 new findings. Existing import guard remains FAILED with the same 80-name set before/after synchronized 702cc1b2; it was not waived. The already-encountered DAG interruption remains unfinished, and no #810 feature authority, EGM or PR is claimed.

No student/ownAdamW, teacher, checkpoint, graph, source artifact, durable run or human-run mutation; no self-merge. No expensive probe is running. #829 remains separately parked at 5/5 without override; no sixth review.
