# Contributing to Bilqis MLX

This is the public source repository for a human-operated MLX student and teacher project. Source changes, disposable tests and read-only inspection are allowed. Only the human operator starts or resumes training the real student. Protected source-authority material, model bundles and actual training state do not belong in Git.

## One canonical checkout

Work in `~/Code/bilqis-mlx`. The root `bilqis_mlx/` owns active software. The pinned `vendor/legacy-v16/` contains immutable historical source code needed by the teacher and source oracles. All new development belongs in `bilqis_mlx/`, never in the vendor directory.

Ignored `runs/`, `vendor/legacy-v16/runs/`, `.local/`, and `data/` store mutable local data. `BILQIS_STORAGE_ROOT` explicitly relocates the active run root. Do not use an unstaged checkout or an external sibling repository as an implicit runtime dependency.

## Changes and commits

Use Conventional Commit subjects: `feat(scope): …`, `fix(scope): …`, `docs: …`, `test: …`, `refactor: …`, `perf: …`, `ci: …`, `build: …`, or `chore: …`. Breaking changes use `!` and a corresponding migration note. Each commit should leave independently verifiable code. `python3 -B scripts/maintenance/release_version.py --validate-subject 'fix(training): preserve custody'` checks the syntax.

Run `python3 -B -m unittest discover -s tests -q` on Apple Silicon for the full MLX-dependent suite, plus `npm run quality:check` and `npm run release:check`. The portable GitHub CI intentionally does not create neural updates, download the human student, or claim Linux MLX parity.

## Checked detached witnesses

Use `scripts/bamf/detached_long_run.py launch --witness PATH` for custom Python
qualification and profiling witnesses (ADR-132 and ADR-139). The selected file
must define `prepare(argv, probes)`, returning the callable that performs the
expensive work. Keep module initialization and preparation neural-inert. Validate
arguments, fixture identity, imports, and probe bindings in preparation. Put
model allocation, fixture copying, and training in the returned callable.

Bind a timing probe to the function that consumes the global callable:

~~~python
from pathlib import Path

# Inside prepare(), after importing the public model entrypoint:
from bilqis_mlx.runtime import atlas_model

samples = probes.bind(
    Path("bilqis_mlx/runtime/_model/backbone/microbatch/execution.py"),
    "_learning_first_microbatch_value_and_grad_impl",
    "_materialize_gradient",
)
~~~

The resolver also accepts the canonical module name
`bilqis_mlx.runtime.microbatch.execution`. It rejects ambiguous module identities,
wrong-checkout origins, missing bindings, and a consumer that does not load the
named global. The current probe API covers direct module-global callable lookups.

Launch the selected witness with its arguments after `--`:

~~~bash
python3 -B scripts/bamf/detached_long_run.py launch \
  --label "checked qualification" --workdir "$PWD" \
  --snapshot "$CAMPAIGN/source-snapshot" \
  --log "$CAMPAIGN/witness.log" --receipt "$CAMPAIGN/receipt.json" \
  --pid-file "$CAMPAIGN/witness.pid" --witness "$CAMPAIGN/witness.py" \
  -- "$DISPOSABLE_RUN"
~~~

The launcher runs preparation in the immutable source snapshot before starting
the detached worker. The worker checks the same probe contract, resets preparation
samples, and requires observed consumer calls during execution. The terminal receipt
records the probe results. A changed source, missing completion record, or failed
preflight cannot yield PASS. Unchanged failed-preflight snapshots are removed; a
mutated snapshot is retained for diagnosis. External witness files are digest-pinned.
Use only explicitly selected trusted witness code and disposable learner inputs.

Ordinary detached commands retain their existing syntax. Direct Python profiling
modules and external scripts require checked mode or an explicit
`--raw-command-reason` for legacy or non-witness execution.

## Release discipline

Tag releases with immutable annotated SemVer tags `vMAJOR.MINOR.PATCH`. Python and npm project versions must agree, and `CHANGELOG.md` must include a dated version section. Run `npm run release:check` before tagging. Verify the release tag points at the same reviewed commit on `main`. Release Please treats `feat`, `fix`, `perf`, `revert`, and `refactor` merge commits as user-facing release-note entries; `refactor` therefore produces a patch release candidate instead of disappearing from the changelog. `.github/workflows/release.yml` checks the tag and publishes GitHub Release notes derived from the checked-in changelog.

Never re-tag a release after publication. Use another patch version to correct an error. Experimental checkpoint scores and best-of-history markers are not claims of qualified neural performance.
