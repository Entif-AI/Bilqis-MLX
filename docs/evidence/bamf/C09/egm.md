# C09.1–C09.3 independent review ledger

Review authority: pinned google/elephant-goldfish-model
`b3a35956759bf7f024af2ff061b2e0b44b438e4c`,
read-only fresh-context Goldfish workers.

## Initial independent dispositions

Worker-7 reviewed immutable C09.1 `d0fd5ab`, executed
12 focused tests and found **0 Blockers, 2 Majors**:
transitive held-ancestor readiness and unverified source-owner
receipt authority. It did not issue EGM PASS.

Worker-8 reviewed C09.1/.2/.3 at immutable `053f6f4`,
executed 17 focused tests, and found **0 Blockers, 2 Majors**
in C09.3: actor-prefix collision (`a` versus `a:b`) and
receipt-only relabeling of stale post-remediation evidence.
Its C09.1/.2 scoped checks passed, but worker-7's additional
C09.1 findings remain authoritative until repaired.

## Prime repair candidate

Immutable pushed repair `cd3ec533a823eea3bd407d5e9ac13c87cfb42230`:

1. Full transitive DAG readiness before lazy revalidation.
2. Host-provisioned Ed25519 public-key source authority,
   dependency-kind and key-scope binding; v2 signed correction,
   recomputation and transition records. No self-attested hash
   grants access. Actual upstream key provisioning is pending.
3. Length-prefixed actor identity in TIME dependencies.
4. Remediation v2 original actor binding and receipt-only
   stale replay escalation, preserving legitimate later actor/time
   evidence.
5. C09.2 moved into `atlas_requalification.py` to keep
   source files small and independently reviewable.

Prime's combined C09/C08/C02/source-prefetch/error-control
suite after repair: **79 passed, 0 failed, 1 optional skip**.
No new C09-specific static error-control or module-size debt.

**Disposition: RE-REVIEW PENDING.** These repairs are not
silently marked EGM PASS. Actual source-owner A01/B07/B13/C04
keys, C10 delivery, C09 parent integration and neural runtime
remain separate gates. No merge or live training occurred.

## Second targeted C09.1 review

Worker-7 inspected immutable `cd3ec53` and found **0 Blockers,
2 new Majors**: signed old recomputation evidence was not
bound to the active correction, and the key's independent
kind/prefix allowlists created cross-scope authority.

Repair `8ee79c23ec7e88b7915bc185e8c5c61ccc7fce79`
binds v3 signed recomputation/transition records to the
exact active correction event and receipt. It replaces
Cartesian allowlists with v2 explicit kind+prefix scope
pairs. Both failing-before adversaries now reject.
Combined focused prime tests: **90 passed, 1 optional skip**.

**Latest C09.1 EGM: RE-REVIEW PENDING.** Earlier C09.3
actor-prefix and receipt-relabel repairs also await
independent readback. No scoped EGM PASS is inferred.
