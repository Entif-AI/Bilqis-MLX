# Portable package and proof

Package version is declared in `SKILL.md` metadata. This Skill requires a selected
Bilqis-MLX checkout containing the canonical ingestion actions and #91 proof
runner. It is not a standalone compiler. Resolve that checkout and its compatible
interpreter explicitly; install its declared extraction and semantic dependencies.

The repository's `scripts/package_ithkuil_skill.py` stages the exact Skill resource
closure and copies the canonical #91 bounded fixture into `assets/fixture`.
These generated package assets are selected test inputs, not a production corpus.
The repository fixture remains their authoring authority. The packager rejects
unintended Skill files and symlinks; it runs the project validator, upstream Skill
validator, then the upstream Skill Creator packaging command. Supply those tool
paths explicitly. Validators and their dependencies are not runtime package assets.

After packaging, inspect the ZIP-compatible `.skill` archive and extract it into
a fresh directory. From any working directory, run the extracted Skill surface:

```sh
<python> -B <extracted-skill>/scripts/cleanroom.py \
  --repo <repository> --python <python> --output-root <new-proof-root> \
  --verify-failures
```

The wrapper supplies its own packaged fixture to the selected repository's
canonical clean-room runner. It contains no parser, compiler or semantic fallback.
Two independent runtime copies must produce identical semantic artifacts.
The failure proof checks source-pin rejection, actual conformance-gate failure,
required unavailable graph failure, downstream suppression, retry and preservation.
Read `proof.json` and `failure-proof.json`; inspect command evidence in that output.

For explicitly authorized live graph proof, use the canonical graph-proof helper
with the two packaged proof workspaces and an explicitly configured tunnel endpoint.
See `fixture.md` and `graph.md`. Graph runtime is optional and is not bundled.

Record package SHA-256, version, full file/hash listing, validator identities,
commands and resulting proof receipts. Package bytes and fixture artifacts have
separate identities. Neither fixture proof nor package acceptance proves the
production/full-corpus release owned by #93–#97.
