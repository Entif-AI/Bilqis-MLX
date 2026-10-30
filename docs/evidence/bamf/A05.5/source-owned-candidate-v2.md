# A05.5 source-owned candidate

Issue #594, parent #357, Lane A; delivery PR #611 targets unified.
Disposition: implementation candidate, independent EGM pending.

## Source custody

The A01 dependency is reproducible from tracked source IR. The existing source
conformance command passes all four gates and reproduces source bundle
`f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec`.
`scripts/bamf/rebuild_atlas_artifact.py` replays the original A01.2 formal
bindings, verifies the independent source pins, and reproduces Atlas bundle
`5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7` and release
`58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`.
This does not change the recorded partial source coverage or admit new semantics.

The source adapter now constructs exact raw atom instances and references from
canonical reproduced source rows. The independently pinned prior registry owns
the native signature and existing ABI mapping. ABI 227 keeps its full
`Entity*Entity->Boolean` signature. Native formal signatures are not A06 factor
categories. Revalidation rejects changed source roots, graphs, rows, ABI/type
claims, releases, source instances/references, rights, corrections and prefixes.
Self-pinned digests are not accepted as independent authority.

The existing public-formal policy owns grants. The new raw-atom operation issues
grants only for visible atoms and rejects collisions instead of replacing revoked
or stale grants. Unsupported sources remain held or unmapped. No ConceptRef is
invented from token spelling and no UNKNOWN semantic identity is manufactured.

## Neural custody

`learning.source_atoms.encode_source_compiled` reconstructs source authority and
the A06 feature manifest before reading identity tensors from the complete B01
parameter tree. It derives raw atom vectors internally and invokes the existing
B03 encoder. Caller-provided raw vectors are not an input to this operation.
Real-source differentiation reaches the selected B01 identity rows and factor
parameters. Inactive banks receive no gradient. Known but inactive future Atlas
rows do not force an unadmitted physical bank expansion.

This proof exposed a pre-existing B02 active-set digest mismatch: B02 used compact
JSON while A01/A02 use canonical publication JSON. Bank validation and identity
initialization now use the same existing canonical serializer. Validation is not
weakened to accept either representation.

Native atomic-frame fallback still requires its separate source-to-identity law
and remains held in this new entrypoint. Ordinary source-bound frame members use
existing B02/B03 owners. This change does not issue B11 producer admission, B05
summary authority, a curriculum release, learner mastery or training permission.

## Verification

The combined source, neural and relocated-owner run passed **231 tests and 111
subtests, with zero skips**. Its source boundary subset previously passed 52
tests and 49 subtests; the neural/owner subset passed 179 tests and 62 subtests.
The latter includes literal numerical output checks,
actual MLX gradients, canonical import identity, lazy loading, active-bank
capacity and rejection of incomplete parameter trees or caller atom vectors.

Rebuild the source conformance bundle and Atlas artifact using the commands in
PR #611. Set `BILQIS_A01_ATLAS_BUNDLE` to the reproduced Atlas directory. Run:

```sh
python3 -B -m pytest -q \
  bilqis_mlx/semantics/tests/frame_adapters \
  bilqis_mlx/semantics/tests/context \
  bilqis_mlx/semantics/tests/source_atom_binding \
  bilqis_mlx/source_adapters/tests/atoms \
  bilqis_mlx/learning/source_atoms/tests \
  bilqis_mlx/learning/frame_embeddings/tests \
  bilqis_mlx/learning/_championship/tests \
  bilqis_mlx/learning/_salience/tests \
  bilqis_mlx/learning/_retention/tests \
  bilqis_mlx/learning/_engram/tests \
  bilqis_mlx/learning/_teaching/tests
sh .husky/pre-push
```

The required structural cleanup keeps existing logical learning imports and
source bytes intact while grouping small owners physically. Package imports stay
lazy. No quality threshold or smell baseline was changed. Existing large,
unmodified teacher/runtime owners remain outside this change.

The PR includes earlier Lane A work and structural dependency #609. That
dependency is not silently promoted to accepted unified state. The remotely
verified final head and final test result belong in the issue checkpoint; this
receipt does not claim its own future commit hash.
