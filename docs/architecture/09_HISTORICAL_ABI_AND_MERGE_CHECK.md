# Original model semantic ABI and proposed merge guard

**Authority:** ADR-030 under protected issue #336. No real trainer/optimizer mutation. The historical count is no longer copied through production code: the code-owned manifest at `bilqis_mlx/semantics/legacy_abi_v1.json` owns `historical_prefix_tokens`; modules import `HISTORICAL_PREFIX_SIZE` from `bilqis_mlx.semantics.abi`.

The historical count is **not the ceiling for later admitted models**. `HISTORICAL_PREFIX_SIZE` refers only to the immutable prefix of the original complete FP32 student. A current or future student's actual vocabulary size is read from its admitted graph/catalog, with separate version, identity, embedding, native AdamW and checkpoint proofs. The older foundational source graph has a different size and digest from the complete saved student's graph. Never substitute one for the other.

The manifest also records the audited historical checkpoint SHA, the complete historical graph digest, the index→symbol/identity/meaning-contract fingerprint **and a separate full source-field fingerprint** covering meaning, signature, family, subtype, arity and source stage. Both fingerprints were independently reproduced from (a) the frozen complete source checkpoint and (b) the checked-in historical Token Atlas snapshot. A snapshot that changes its meaning or type text but leaves a claimed SHA column untouched must fail. The original checkpoint was not modified. The canonical 2026-10-15 snapshot, its row data, source SHA fields, and original research artifacts remain immutable evidence.

## Run the check

```sh
python3 -B scripts/check_historical_abi.py
python3 -B -m unittest tests.test_historical_abi_contract -q
```

`check_historical_abi.py` validates source snapshot index identity and contract fingerprints against the code-owned manifest, and checks production Python for repeated numeric literals equal to the historical count. The semantic-module import-boundary checker runs alongside it in CI. Synthetic tests mutate token identity, index, contract SHA and a missing row; reordering editable Sheet rows remains legal; a new token after the historical prefix does not change the original fingerprint.

## GitHub Actions and independent authority

`.github/workflows/semantic-abi-integrity.yml` runs on feature-branch pushes, pull requests to `main`, and manual dispatch. It uses a pinned checkout commit, no `pull_request_target`, read-only token permission, no secrets, and Python standard-library checks.

The workflow has two materially different states:

- **Advisory:** Without a separately configured GitHub repository variable, the code-owned manifest and snapshot are compared and code literals are audited, but the guard explicitly reports that no independent expected fingerprint was provided.
- **Externally checked:** An authorized human sets `BILQIS_EXPECTED_ABI_SHA256` to the approved **full source-field fingerprint** and `BILQIS_ABI_REQUIRE_EXTERNAL=true`. The workflow then fails closed if that external value is missing, malformed or different from the manifest or actual snapshot semantics.

Merely adding the workflow does **not** turn it into a required merge protection. When a public GitHub Free repository is available, a human repository administrator must explicitly require the unique `semantic-abi-integrity` job and approve branch protection, protect the source/manifest/workflow from unreviewed changes, and apply protections to admins where supported. The admin-controlled variable cannot become a second agent-writable source of truth. Do not publish protected issue URLs, training policies, user-run artifacts or private history as part of making this check public.

## Non-goals and retained fixtures

The guard does not certify new vocabulary admissions, real student learning, formal New Ithkuil language competence, teacher-policy noninterference, or Grade C readiness. Historical dated documents and JSON receipts retain factual numerical counts, immutable identifiers, RNG seeds and source hashes; those are **records**, not live configuration settings. Where docs describe current mutable model state, link to the manifest and use names such as `HISTORICAL_PREFIX_SIZE` and *current admitted graph size* rather than copying a number. The old graph and 100%-same-checkpoint graduation criteria remain governed by their own separate requirements.
