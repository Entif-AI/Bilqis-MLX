# C01 round-three repairs and composed proof — 3 November 2026

Tested archive source: `d2d2a0bf5526b5c7fd690f0d9f3069f0dd8fcd84`.
Reviewed unified remains `aa828eb5cb8822a5614aa3353864bf187f83444d`.
The parent consumes separate issue branches for #786 and #787. The source-frame
structural scope and the eight explicit normalization holds are unchanged.

## Repaired findings

#786 restores the original public dependency routes for released-schema
verification. Each verifier resolves its public dependency at the original call
boundary, after the same preceding validation. Two literal public sentinel probes
failed before the repair and pass afterward. Canonical A01/A03 loading and body
comparison remain intact; the real released-schema owner suite passes 14/14.

#787 makes the document and declared source/installed totals explicit at the
recipe validator boundary. The historical defaults remain 193/122. Six new literal
cases first fail before the extension; all ten validator tests now pass. Actual
historical 193/122 logs pass the default command, and the preceding 199/122 logs
pass their explicit document/totals command. Skipped tests, stale predicates,
unsupported grep forms and missing installed origins still reject.

The old serial-merge paragraph is corrected: #781 stays open while the combined
parent is repaired/reviewed, then may be genuinely superseded as consumed in one
replacement operation. There is no new child Goldfish or additional PR inventory.

## Actual composed proof

- Fresh Git archive source selection: **201/201**, no failures/errors/skips.
- Fresh build environment, wheel and isolated installed target: **124/124**,
  no failures/errors/skips; every loaded Bilqis module and namespace path is
  below the installed target. Exactly one declared vendor-only fixture is excluded.
- Wheel SHA256: `ae4d1af28baee3ce077d08c7b6d9c39fdaf6f3a15c11f46af60020f0a535f81c`.
- Disposable native frame callers: **6/6 on CPU**, no failures/errors/skips.
- Recipe validator: **10/10**; flow-control regressions: **13/13**.
- Actual contract verifier checks all 214 owner/child identities/fingerprints;
  registry integrity remains valid with 171 children, the same eight holds and
  empty executable order. Its held exit is not a runnable-graph claim.
- Structure, governance, Factory architecture, docs, whitespace and live flow
  checks pass. Changed-file hygiene has zero new findings. Error control reports
  zero new debt against exact unified. Historical ABI remains advisory without
  the independent external expected fingerprint.

The archive, build environment, wheel and installed target are fresh. Portable
runtime and disposable native MLX 0.32.4 environment are reused from the preceding
qualified proof. Source fixtures are supplied read-only, not regenerated or
redistributed. Actual source/wheel identities are in `source-commit.txt` and
`build-receipt.txt`; dependency freezes and full logs are retained with the proof.

## Reproduce this exact source

Start from a checkout containing this receipt and the tested source commit. Follow
[the complete archive/environment recipe](installed-wheel-probe.md), including
both explicit immutable source-fixture access requirements. Set `proof_commit`
to `d2d2a0bf5526b5c7fd690f0d9f3069f0dd8fcd84`.

Make these complete replacements for the historical selection-specific steps:

1. Append `bilqis_mlx/semantics/_public_identity/tests` to the source test command
   from the archive recipe. The released-schema target already includes the two
   new public-hook tests; the resulting source total is 201.
2. In the installed Python probe, add the following before the case-count assertion:

```python
suite.addTests(unittest.defaultTestLoader.loadTestsFromName(
    'bilqis_mlx.semantics._public_identity.tests.test_module_identity'))
```

3. Replace the installed count assertion with
   `assert suite.countTestCases() == 124, suite.countTestCases()`.
   Preserve the single vendor-only exclusion, no-skip assertion and complete
   module/namespace origin checks. Do not use historical 116 or 122 assertions.
4. Replace both historical source/installed success predicates with these exact
   commands; preserve the separate origin predicate:

```sh
grep -Fx 'TEST_TOTALS total=201 passed=201 failed=0 skipped=0 errors=0' \
  "$proof_root/source-tests.log"
```

```sh
grep -Fx 'INSTALLED_TEST_TOTALS 124 0 0 0' "$proof_root/installed-tests.log"
grep -Fx 'INSTALLED_WHEEL_MODULE_ORIGINS_OK' "$proof_root/installed-tests.log"
```

5. Replace every inherited historical-validator invocation with this command,
   run from the checkout containing this receipt:

```console
python3 -B docs/evidence/bamf/C01/registry-20261101/verify_repaired_recipe.py "$proof_root" \
  --document docs/evidence/bamf/C01/registry-20261101/round3-repairs-20261103.md \
  --source-total 201 --installed-total 124
```

Do not run the default historical 193/122 command on these 201/124 logs. The native
six-case CPU selection is unchanged from [the native recipe](current-20261103.md).

## Review and authority

[Review attempt three](egm-round3-20261103.md) remains FAIL with incomplete codebase
coverage; these deterministic repairs do not relabel it PASS. The next otherwise
ready aggregate review is attempt four in `C01-STRUCTURE-20261103`, retaining the
five-attempt cap. Full #347, eight normalization holds and human integration remain
open. No source admission, retained learning, real student/own AdamW/teacher,
source-release/graph/human-run mutation or self-merge is authorized. IPR-0220 opaque.
