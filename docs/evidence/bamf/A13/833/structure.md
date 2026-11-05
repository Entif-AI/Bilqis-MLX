# #833 context eligibility structural proof

Base is synchronized Lane A / reviewed unified
`06eb34d0435d2f41c6f3561cf8cad6988d5b849f`.
Specification: `docs/tasks/bamf-0.2/followups/CONTEXT_ELIGIBILITY_STRUCTURE_20261104.md`.

The original 767-line owner is split into a public compatibility facade and
cohesive evidence, member, source, result, gate/check, projection and transition
owners. Every changed source and test file remains below 240 LoC. No eligibility
policy, source/rights/revocation rule, causal visibility or C09 transition is
intentionally changed.

## Red/green and equivalence evidence

- Original focused selection: 22/22, zero skips.
- Extraction initially reproduces seven public identity/type-hint test failures;
  facade metadata and annotation bindings repair those failures.
- Initial relocated gate produces two hygiene findings: 178 lines and 43 branches.
  Pure task/envelope/member/grant/join checks preserve the existing shared hold
  callback, used-handle accounting and validation order. No baseline changes.
- Final focused selection: 25/25, zero skips, including a combined denial from
  stale envelope, revoked source grant and forbidden join.
- The other 23 moved definitions retain exact ASTs after undoing facade-qualified
  globals. The gate is intentionally decomposed and separately behavior-checked.
- Public classes/functions/methods retain module and pickle identity; postponed
  type hints resolve. Public gate, projection and digest patch interception passes.
- An identical deterministic fixture under original and candidate source produces
  exactly 13,350 matching serialized bytes for eligibility, evidence, holds,
  projection cache and changed/revoked C09 decisions and receipts.

Representative exact identities from that comparison:

| Surface | SHA-256 |
| --- | --- |
| Approved context | `41442056c497151332800030873505074191024a6b64da9b63261614d8548e03` |
| Projection cache | `ce9214949aaedaea3821535777b78669e0926e1e3b7248a8fefb07cb9a530d69` |
| Changed-context event | `1336d5f8ced14c72ac6f1a7c050e27d6d8fdce7eb30c197b9432785091d29477` |
| Revoked-context event | `a6d94c10eb177b1c2a1eee62eeab8bab6cfe30d03491d537763502edbcee2430` |

Reproduce focused proof:

```sh
python3 -B scripts/run_tests.py \
  bilqis_mlx/semantics/tests/context/test_revocation_and_missing_member.py \
  bilqis_mlx/semantics/tests/context/test_c09_boundary_rejects_malformed.py \
  bilqis_mlx/semantics/tests/context/test_real_public_formal_a.py \
  bilqis_mlx/semantics/tests/context/test_public_identity.py
python3 -B scripts/check_module_size.py --changed-from 06eb34d0
```

Detailed baseline/red/green/comparison logs and original-source comparison script
are local execution artifacts under `.local/833-context-structure/`. The fixture
and source-bound positive cases establish engineering behavior, not an A01 source
release qualification or neural learning result. Final static gates, pinned
independent review and hosted receipts are recorded on #833 at the committed head.

All new source files are staged before error documentation generation. The raw
exception identity/count multiset must remain equal to base; PM-2026-11-04-001 /
RC-144 protects this ordering. No scanner exclusions or debt baselines change.
Historical ABI external expectation remains advisory/unconfigured.

#354 aggregate acceptance, #424 source/checker mappings and #785 profile-selection
authority remain separately open. Actual student/native AdamW/teacher, source
release, graph, archives, checkpoints and reserve remain untouched. Only the human
starts/resumes real neural updates. IPR-0220 remains open.
