# C01 combined structural and verifier checkpoint — 3 November 2026

The [round-three repair receipt](round3-repairs-20261103.md) records the newer
201/124 source; the 199/122 evidence below remains pinned to its stated source.

This is scoped source-frame structural integration proof, not full #347 acceptance.
Tested source is `47188f5340450eeab189995456b14979ad078216`.
Lane C `bcae1037a434f886df4e84444cd2dc26daa42dde` consumes reviewed unified
`aa828eb5cb8822a5614aa3353864bf187f83444d`. The isolated issue branch is
`codex/bamf02-c-347-integration-20261103`. It consumes canonical same-lane
structural head `13b67a5994d1a06aac26dda42968c8e4139bff64` and the verified
#770 candidate from PR #781. The original issue branches/worktrees remain intact.
Only flow-control records conflicted; resolution retained current live PR inventory,
accepted integrations, and the #771/#774 remediation records. No semantic source,
registry, body fingerprint, dependency edge or hold was edited.

## Executed verification

- Checkout and fresh Git archive source selections: **199/199 each**, no skips.
- Fresh wheel build and isolated installed target: **122/122**, no skips. Every
  loaded Bilqis module and namespace path resolves below the installed target.
- Observed wheel SHA256: `3823055aecddba10a8ef82c0f590d39837265aae47daab72fce1625fc26cb82b`.
- Disposable native MLX frame callers: **6/6 on CPU**, no skips, in a new native
  environment with `mlx==0.32.4`. No durable student or optimizer is opened.
- Verifier/registry adversaries: **58/58**, no skips. Actual contract-verifier CLI
  passes all 214 owner/child identity and fingerprint checks; all 14 original
  baseline failures are gone.
- Existing repaired-recipe validator regressions: **4/4**. Their historical
  193/122 literals still belong to source `3174c368`, not this larger selection.
- Structure, governance, Factory architecture, docs and whitespace checks pass.
  Changed-file hygiene has zero new findings. Error control with the exact unified
  base reports zero new debt; the unbased whole-repository check reports existing
  debt and is not represented as green.
- Live flow control passes at three open implementation PRs: #690, #781, #782.

The portable runtime reuses the dependency-pinned environment from the previous
recipe. Archive, build environment, wheel, installed target and native environment
are fresh. Both previously verified source bundles are supplied read-only; this
proof neither regenerates nor distributes them. The initial native attempt used
an environment without MLX; no native pass was claimed until the new environment
ran all six cases.

## Reproduction

Use [the archive/environment recipe](installed-wheel-probe.md) and the
[callable-identity additions](public-callable-identity-771.md). Set `proof_commit`
to the tested source above. Add the owning `_public_identity/tests` selection and
its six installed cases exactly as the callable-identity receipt specifies.
For this source, use the following source success predicate instead of historical
187 or 193 totals:

```sh
grep -Fx 'TEST_TOTALS total=199 passed=199 failed=0 skipped=0 errors=0' \
  "$proof_root/source-tests.log"
```

The installed count remains 122. Preserve the one explicit vendor-only exclusion,
no-skip check, all-module/namespace origin guards and both success predicates:

```sh
grep -Fx 'INSTALLED_TEST_TOTALS 122 0 0 0' "$proof_root/installed-tests.log"
grep -Fx 'INSTALLED_WHEEL_MODULE_ORIGINS_OK' "$proof_root/installed-tests.log"
```

Replace the inherited historical-validator step with this invocation for this
specific 199/122 source. Do not run the default 193/122 validator on these logs:

```console
python3 -B docs/evidence/bamf/C01/registry-20261101/verify_repaired_recipe.py "$proof_root" \
  --document docs/evidence/bamf/C01/registry-20261101/integrated-20261103.md \
  --source-total 199 --installed-total 122
```

The six native CPU callers use the exact selection and fresh explicit environment
in [native-cpu-recipe-801.md](native-cpu-recipe-801.md). The actual contract verifier is
`python3 -B scripts/verify_bamf_0_2_contracts.py`. Registry validation is
`python3 -B scripts/check_bamf_workstack.py docs/tasks/bamf-0.2/workstack.json`.
The latter intentionally exits 1: integrity is valid with 171 children, but the
same eight normalization holds remain and executable order is empty.

## Next gate and authority

PR #781 is open with hosted portable/core and Semantic ABI checks successful.
It remains the current Lane C integration PR. No competing C01 PR is opened.
The combined C01 branch already contains #781's repair. Once all known repairs,
available gates and complete final aggregate review pass, the combined parent may
supersede #781 as consumed in the same governed PR replacement operation. Keep
#781 intact until that replacement is ready. The ready parent still requires human
integration before another lane consumes its structural repair through unified.
The existing episode is `C01-STRUCTURE-20261103`; source changes do not reset its
round count or five-round cap. This checkpoint claims no new aggregate EGM PASS.
Full #347, source/evaluator/custody/admission and normalization obligations remain.
No self-merge, real learner, matching AdamW, teacher, source-release, graph or
human-run state mutation is authorized. IPR-0220 remains opaque.
