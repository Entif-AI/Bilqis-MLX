# Contributing to Bilqis MLX

This is a private, human-operated MLX student and teacher project. Source changes, disposable tests and read-only inspection are allowed. Only the human operator starts or resumes training the real student. Never put a model bundle or actual training state into Git.

## One canonical checkout

Work in `~/Code/bilqis-mlx`. The root `bilqis_mlx/` owns active software. The pinned `vendor/legacy-v16/` contains immutable historical source code needed by the teacher and source oracles. All new development belongs in `bilqis_mlx/`, never in the vendor directory.

Ignored `runs/`, `vendor/legacy-v16/runs/`, `.local/`, and `data/` store mutable local data. `BILQIS_STORAGE_ROOT` explicitly relocates the active run root. Do not use an unstaged checkout or an external sibling repository as an implicit runtime dependency.

## Changes and commits

Use Conventional Commit subjects: `feat(scope): …`, `fix(scope): …`, `docs: …`, `test: …`, `refactor: …`, `perf: …`, `ci: …`, `build: …`, or `chore: …`. Breaking changes use `!` and a corresponding migration note. Each commit should leave independently verifiable code. `python3 -B scripts/release_version.py --validate-subject 'fix(training): preserve custody'` checks the syntax.

Run `python3 -B -m unittest discover -s tests -q` on Apple Silicon for the full MLX-dependent suite, plus `npm run quality:check` and `npm run release:check`. The portable GitHub CI intentionally does not create neural updates, download the human student, or claim Linux MLX parity.

## Release discipline

Tag releases with immutable annotated SemVer tags `vMAJOR.MINOR.PATCH`. The Python package, `pyproject.toml`, and npm project versions must agree, and `CHANGELOG.md` must include a dated version section. Run `npm run release:check` before tagging. Verify the release tag points at the same reviewed commit on `main`. `.github/workflows/release.yml` checks the tag and publishes release notes derived from the checked-in changelog.

Every integrated trainer/runtime/dashboard tranche must choose its SemVer effect explicitly: patch for compatible corrections, minor for backward-compatible capability additions, and major for breaking contracts. Update the checked-in version and changelog in the same integration tranche. The operator dashboard displays the active run's recorded software version; `SCHOOL_SESSION_STARTED` events carry that version so a detached observer does not confuse an older running trainer with a newer checkout.

Never re-tag a release after publication. Use another patch version to correct an error. Experimental checkpoint scores and best-of-history markers are not claims of qualified neural performance.
