# Admission proof import repair

[Issue #685](https://github.com/Entif-AI/Bilqis-MLX/issues/685) starts from reviewed unified/Lane C
`0cac1a27abfb909b61646e5303ed40e9f60aa977`.

The Factory staging fixture moved to
`bilqis_mlx.factory.tests.curriculum.frontier.test_candidate_staging`.
Three runtime consumers still import its removed path. Admission discovery
reports 19 tests with two import errors; direct prepared/JIT/staging selection
reports three import errors. PM-2026-11-01-006 records this failure in the internal incident ledger; the linked issue preserves its public reproduction.

## Exact changes

Modify the fixture import in these existing consumers:

- `bilqis_mlx/runtime/tests/admission/test_jit_adoption.py`
- `bilqis_mlx/runtime/tests/capability/test_candidate_staging.py`
- `bilqis_mlx/runtime/tests/test_prepared_successor.py`

The last file has 648 lines and requires a structural interruption. Preserve
every original method body, signature and decorator. Extract its existing
`PreparedSuccessorFixture` and `_BeforeMaterialization` exception into the new
`runtime/tests/admission/prepared_successor_fixtures.py`. All split modules import
that fixture through `bilqis_mlx.runtime.tests.admission.prepared_successor_fixtures`.
Commit and topology modules also import `_BeforeMaterialization` there.

Allocate the existing methods exactly as follows (line numbers refer to base):

| Destination relative to runtime/tests | Class | Original method lines |
| --- | --- | --- |
| test_prepared_successor.py | PreparedSuccessorTests | 276, 303, 622 |
| admission/test_prepared_successor_materialization.py | PreparedMaterializationTests | 157, 214 |
| admission/test_prepared_successor_commit.py | PreparedCommitTests | 381, 462 (helper), 492 |
| admission/test_prepared_successor_topology.py | PreparedTopologyTests | 317, 522, 566, 593, 607 |

Each test class inherits `PreparedSuccessorFixture, unittest.TestCase`.
Retain only original imports whose bound names are referenced in each destination;
preserve local imports inside methods. Each new file and the original must be
under 240 lines. Add no production shim, duplicated fixture, or new behavior.

## Verification

Run these selections in fresh Python processes:

```sh
python3 -B -m unittest discover -s bilqis_mlx/runtime/tests/admission -p 'test_atlas*.py' -q
python3 -B -m unittest bilqis_mlx.runtime.tests.test_prepared_successor bilqis_mlx.runtime.tests.admission.test_prepared_successor_materialization bilqis_mlx.runtime.tests.admission.test_prepared_successor_commit bilqis_mlx.runtime.tests.admission.test_prepared_successor_topology bilqis_mlx.runtime.tests.admission.test_jit_adoption bilqis_mlx.runtime.tests.capability.test_candidate_staging -q
```

For cold import proof, import `CandidateStagingFixture` from its canonical Factory
module and import all six runtime modules named above plus
`bilqis_mlx.runtime.tests.admission.test_atlas_admission_command` and
`bilqis_mlx.runtime.tests.admission.test_atlas_admission_policy`. Assert each runtime
`CandidateStagingFixture` binding, when present, is that exact class object.
Assert its source path ends with
`factory/tests/curriculum/frontier/test_candidate_staging.py`.

For preservation proof, parse the base file obtained with
`git show 0cac1a27:bilqis_mlx/runtime/tests/test_prepared_successor.py` and all five
resulting files using `ast.parse`. Compare `ast.dump(include_attributes=False)`
for every fixture method and every original test/helper method, keyed by name.
Require equal name sets, no duplicate names, exactly twelve test methods, and
unchanged exception class AST. Only module imports, class names, grouping and
module docstrings may change. Persist the comparison script/results locally in
the issue's Work Stack bucket.

Run the affected quality and immutable-source checks:

```sh
BILQIS_QUALITY_BASE_REF=0cac1a27 npm run quality:changed
python3 -B scripts/check_factory_architecture.py
python3 -B scripts/quality/check_docs.py
python3 -B scripts/check_semantic_boundaries.py
python3 -B scripts/check_historical_abi.py
python3 -B scripts/error_control_plane.py --check --base-ref 0cac1a27
git diff --check
```

Long finite checks use `node ~/.codex/hooks/validation-output-runner.mjs --`.
Native tests use temporary directories and preserve the original checks against
optimizer updates. Full [C07 continuous admission](https://github.com/Entif-AI/Bilqis-MLX/issues/380), source authority and retained learning
remain open. No production, semantic, actual student or own-AdamW change is owned
by this issue. IPR-0220 remains governing authority.
