# Contributing to Bilqis MLX

This is a private, human-operated MLX student and teacher project. Source changes, disposable tests and read-only inspection are allowed. Only the human operator starts or resumes training the real student. Never put a model bundle or actual training state into Git.

## One canonical checkout

Work in `~/Code/bilqis-mlx`. The root `bilqis_mlx/` owns active software. The pinned `vendor/legacy-v16/` contains immutable historical source code needed by the teacher and source oracles. All new development belongs in `bilqis_mlx/`, never in the vendor directory.

Ignored `runs/`, `vendor/legacy-v16/runs/`, `.local/`, and `data/` store mutable local data. `BILQIS_STORAGE_ROOT` explicitly relocates the active run root. Do not use an unstaged checkout or an external sibling repository as an implicit runtime dependency.

## Changes and commits

Use Conventional Commit subjects: `feat(scope): …`, `fix(scope): …`, `docs: …`, `test: …`, `refactor: …`, `perf: …`, `ci: …`, `build: …`, `style: …`, or `chore: …`. Breaking changes use `!` and a corresponding migration note. Each commit should leave independently verifiable code. `python3 -B scripts/release_version.py --validate-subject 'fix(training): preserve custody'` checks the syntax.

Run `python3 -B -m unittest discover -s tests -q` on Apple Silicon for the full MLX-dependent suite, plus `npm run quality:check` and `npm run release:check`. The portable GitHub CI intentionally does not create neural updates, download the human student, or claim Linux MLX parity.

## Release discipline

Normal feature/fix PRs do **not** hand-edit the release number or add a future release heading to `CHANGELOG.md`. Use Conventional Commit subjects and titles. After changes land on `main`, Release Please maintains a reviewable `chore(release): X.Y.Z` pull request that derives the next SemVer from those commits, updates `CHANGELOG.md`, `package.json`, `package-lock.json`, `pyproject.toml`, `bilqis_mlx.__version__`, and `.release-please-manifest.json`, then creates the immutable `vMAJOR.MINOR.PATCH` tag and GitHub Release after that release PR merges.

Commit semantics carry release intent: `fix:` is PATCH, `feat:` is MINOR, and a Conventional Commit breaking marker (`!` / `BREAKING CHANGE`) is MAJOR. Local Husky hooks reject malformed commit subjects and whitespace errors before they leave the workstation; GitHub independently validates the PR title and every commit. `npm run release:check` remains an independent consistency proof for all version surfaces and the current changelog entry.

The operator dashboard displays the active run's recorded software version; `SCHOOL_SESSION_STARTED` events carry that version so a detached observer does not confuse an older running trainer with a newer checkout. Bot-created Release Please PR workflows may require GitHub's normal maintainer approval before CI runs. Treat that approval as a security gate, not as permission to synthesize checks or bypass protected `main`.

Never re-tag a release after publication. Use another patch version to correct an error. Experimental checkpoint scores and best-of-history markers are not claims of qualified neural performance.
