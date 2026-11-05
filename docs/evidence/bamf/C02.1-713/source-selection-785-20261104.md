# A06 source selection / #785 — 4 November 2026

The preserved issue branch `codex/bamf02-a-785-source-features-20261103`
resumed from remote `13b35ae66de6ce1c09d03657c4ed1a084635f0b9`.
The recorded structural trigger occurred: C01 PR803 is integrated through
reviewed unified `06eb34d0435d2f41c6f3561cf8cad6988d5b849f`.
Activation preceded synchronization. Merge `aebc8b94` preserves the current
unified lane ledgers and adds the resumed #785 item; no sibling implementation
was copied. The canonical released-schema owner is now bounded, so the previous
structure-only hold no longer applies.

## Current-source proof

On `aebc8b94`, the same verified A01 selection and A03 pinned manifests compile,
persist and load two different legitimate A06 artifacts:

| Selection | Roles | Schemas | Concepts | Feature digest | Artifact bundle |
| --- | ---: | ---: | ---: | --- | --- |
| Micro | 5 | 6 | 228 | `9750d197793fa3245197bd1d8a0568ce662c79d78278ee84bc2441cc6ef54210` | `2e4816948c12a54341baf31e1319fc8aa2106123efc9c176f6bf301aacadd6a5` |
| Boolean + micro + numeric | 8 | 18 | 228 | `6ccdc67f2f5248493568c37941b55ec0cc6ab138f8a398ec5b800632733ae597` | `0985051ad18344436185fa5b1bd38edc119ee08c082b441a32732dddd8a6693c` |

Each uses `load_pinned_atlas_snapshot`, each family's
`_load_pinned_released_frame_schemas`, the existing registered adapter constants,
`build_feature_manifest`, `persist_feature_manifest`, and `load_feature_manifest`
with all expected bundle/release/source/feature identities supplied. Exact typed
readback equals the compiled manifest in both cases. Temporary output directories
are disposable. No existing source artifact is changed.

The current A06 feature/IO owner selection passes **26/26**, zero skips:

```sh
/path/to/venv/bin/python -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/atlas/features \
  bilqis_mlx/semantics/tests/atlas/test_feature_io.py
```

Environment matches the portable dependency set recorded in
`checkpoint-20261104.md`. The local receipt is
`/tmp/a785-features-20261104.log`. An obsolete historical file locator was
corrected before this successful selection; no test or loader was weakened.

`TEST_EVIDENCE_REUSED`: the 61/61 C02 batch pass at tested head `06eb34d0`
applies to `aebc8b94`: comparison `06eb34d0..aebc8b94` changes only Lane A
flow-control bookkeeping, and production/tests/harness/environment are unchanged.
No repeated batch or native/semantic broad suite is justified by that merge.

## Exact unresolved authority

A06.1 explicitly consumes a supplied `FeatureSchema` with source-owned role,
schema and per-schema adapter bindings. Its source verifier establishes validity
of that configuration; it does not select the configuration for a retained
generation. A06.2 establishes immutable export, caller-supplied expected identity
checks and predecessor stability; it does not select a global feature profile.
A03 pins establish schema bodies, family/release identity and schema-map identity.
The family manifests do not carry the feature selection's adapter-binding tuple.
The registered frame owner has several Boolean adapters, so a family name alone
does not supply a general unique binding decision.

The exported `AtlasFeatures` carries factor maps and feature content but omits
the original `FeatureSchema.source_bindings`. Reconstructing an accepted
selection from the feature artifact alone would therefore discard part of its
source-selection provenance. Re-deriving a different row-local map could also
change factor coordinates; source validity must not silently grant compatibility
with an already retained model's map.

The exact held predicate is an accepted source/profile/generation selection
binding for the chosen A03 schema inventory and adapter bindings, A01 identities,
feature bundle/digest and predecessor lineage. An accepted owner record or
canonical owner derivation must supply it. Neither a matching content hash nor
the generic A06.2 receipt supplies that missing selection authority.

No new global profile, source label, admission API or parallel registry is
introduced. #785 remains blocked on that authority seam; #713/#490 consume its
eventual accepted repair. No fresh EGM, implementation PR, source admission,
student/own AdamW/teacher/checkpoint/graph mutation or self-merge is claimed.
IPR-0220 remains opaque.
