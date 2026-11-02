# C11.1 queued coverage and predecessor structure repairs

Issue #522, draft PR #632. Unified consumed remains
`9104ce733e04fb9c82420428b18dfdbf5db49535`; Lane C sync remains
`89398df8686a288d2ce77e65e68b847228ba9af2`.

Two previously queued mandatory structure interruptions are committed and pushed:

- `b0f22b196b62354f1196240687f77e145090c6ec` splits semantic coverage discovery,
  witness accounting, audit, dependency closure and CLI into mirrored owners.
- `2cc49bd90d0b6767c4621b48ca57bcb73082c735` splits historical predecessor
  source custody, lesson construction, plan validation, teacher and reporting.

Both original production files are now 13-line facades. The extracted coverage
owners are at most 157 lines; predecessor owners are at most 92. All companion
test files remain below 240 lines. Public functions, source hashes, schemas,
oracle checks, failure identities, stage semantics and original comments remain.
Predecessor source pins and stage prerequisites now use read-only mappings with
identical contents; the red test reproduces the original mutable-authority gap.
No source, grade, assessment, admission, training or custody policy changed.

## Focused preservation proof

Coverage and sampling-policy tests pass 15/15 before and after, zero skips.
The actual historical coverage plan and empty-witness result serialize to the
same 76,835 bytes, SHA256
`3bdcd3d9b796a84055961785d7b17f9fdf30fba77a9c9cd2b1128062a33c9cfa`.
CLI help is byte-identical.

Predecessor pure contract fixtures pass 7/7 against the original implementation;
the final suite passes 8/8 including read-only authority mappings. Its safe report
serializes to the same 838 bytes, SHA256
`f17f4d5342d50394b5399036313816b2d439b61e58a9e0b6268863f02add92ff`.
CLI help is byte-identical. The eleven original historical tests are preserved
and mirrored, but their exact original checkpoint remains unavailable. These
fixtures are not a replacement source witness or a new BAMF prerequisite.

Fresh independent scoped EGM reviews found no Blockers or Majors. Reviewers
checked all nine coverage functions, sixteen predecessor functions, six original
coverage tests and eleven original predecessor tests. Original test bodies are
AST-identical. Fresh import checks found no new external dependency or cycle.
The coverage reviewer independently ran six tests; the predecessor reviewer ran
the pure contracts. Neither review certifies missing historical source evidence.

The updated portable selection passes 65/65, zero skips. Reproduce with:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/factory/tests/curriculum/test_factory_construction.py \
  bilqis_mlx/factory/tests/test_curriculum_compiler.py \
  bilqis_mlx/factory/tests/test_grade_admission.py \
  bilqis_mlx/semantics/tests/foundation/test_domain_contracts.py \
  bilqis_mlx/verification/tests/test_construction_contracts.py \
  bilqis_mlx/verification/coverage/tests \
  bilqis_mlx/source_adapters/predecessor_parity/tests/test_contracts.py \
  bilqis_mlx/factory/tests/lifecycle/test_release_outcome_contracts.py
```

Staged structure, governance and new-smell checks pass for both interruptions.
No thresholds, exclusions or baselines changed. Portable CI now runs both owner
selections explicitly.

## Integration remains blocked

The full operator-contract audit now reports **1,229 new opaque-contract debt
keys**, up from the prior 1,171 after these relocations. This is an unresolved
integration blocker, not a passing baseline-only result. The separate
`error_control_plane.py --check` output retains 30 diagnostics; do not confuse
that bounded output with the complete operator audit count.

Four previously encountered root owners remain queued: `state_dag.py`,
`data_plane.py`, `curriculum_compiler.py`, `registry_ast.py`. Production #522
still requires accepted run/source authority. No full #522 acceptance or green
aggregate quality claim is made. PR #632 remains draft and no merge or durable
student/optimizer/graph mutation occurred.
