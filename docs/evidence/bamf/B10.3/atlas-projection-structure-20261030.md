# Atlas projection structural interruption

During #469 source-identity validation, the source lookup encountered
`semantics/atlas_projection.py` at 1,067 lines and its companion test at 650.
The mandatory structural contract interrupted decoder feature work. Work Stack
`6b73e287-db16-4088-88bf-ade4b3a5a4c1` preserves the decoder task and next steps.
This is structural evidence, not a replacement algorithm or admission specification.

The historical projection facade now imports cohesive constants, concept/release/
snapshot records, ABI allocation, source coverage/bundle/RDF validation, compiler,
release validation, artifact encoding and durable persistence owners from
`atlas_projection_parts/`. Initial extraction preserved all 41 original function/class ASTs. Committed-head
hygiene then required cohesive extraction of source-input validation and concept
construction from the long compiler and graph construction from the long fixture.
Validation order and artifact goldens remain unchanged. SHAPE_POLICY is now a
read-only mapping; canonical serialization explicitly copies its unchanged values.
Historical public record module names and pickle resolution remain unchanged.
Mirrored tests moved to `semantics/tests/atlas/projection/`; the historical test
module retains fixture imports used by other packages. The fsync fault injection
now patches the responsible persistence owner. All owners and companion tests
remain below 240 lines. Source, release, ABI and serialized artifact bytes are
unchanged; no guard, baseline, source admission or runtime policy was relaxed.

Proof: baseline 12 passed/1 missing-corpus skip; extracted fixture suite 13 passed/
1 missing-corpus skip including a literal historical pickle regression. With the
actual pinned source conformance bundle supplied, 14/14 pass, zero skips. The real
witness pins release `58e0c281b5da18b9b7e6c803709b29eeeb0a88f16b06f48de692808e2fb88306`,
artifact `5f8fba20ecc0adebf39c3b663fdffa4f766e780915197f09d116713042a479e7`,
and all four published payload hashes. Run:

```sh
BILQIS_ATLAS_REAL_CORPUS=/path/to/f1c89c1d1bcd72695c81f8e777d0fbbdf446e92cb27132bebf1cd6873ec689ec \
node ~/.codex/hooks/validation-output-runner.mjs -- python3 -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/atlas/projection
```

Fresh-context Goldfish EGM against pin
`b3a35956759bf7f024af2ff061b2e0b44b438e4c` independently confirmed 41/41 original
production class/function ASTs, acyclic imports, historical record/pickle identity,
coherent mirrored ownership and focused tests. No scoped blocker/major/minor.

The initial combined test selection exposed decoder tests' relative imports under
the repository's path loader (six load errors); their package-based 60-test proof
remains distinct. Correct those imports when resuming #469. Source tests passed;
no failure was hidden or normalized. Broad source/learning acceptance under
IPR-0220 remains open. No real student, own AdamW, teacher or checkpoint changed.
