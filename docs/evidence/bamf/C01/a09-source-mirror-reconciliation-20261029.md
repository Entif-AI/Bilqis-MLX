# C01 workstack source-mirror reconciliation | A09.1 #389

Observed on the reviewed unified branch 2026-10-29: `scripts/check_bamf_workstack.py docs/tasks/bamf-0.2/workstack.json` failed solely with `MIRROR_HASH_MISMATCH` for A09.1. The repository child mirror had an additive, security-relevant A08 source-authority consumption clarification that the live issue and two machine indexes had not yet received. It requires A09 consumers to independently replay the pinned A01 source selection and reject caller-minted A08 proposal records. The clarification was already committed in the repository and was not invented by this repair.

- Before: live GitHub #389 body and both index hashes `6808b61e74d76148eaf11cdb5e7eb93e1a6206b30cc80f2260f1dd10492da735`.
- Repo child mirror SHA-256: `2bdcdb6e24a46e4c3284525b5c32e2ed5946714a76c9ab93a0ccbc1595032e53`.
- The exact original live body was preserved in the private local Work Stack before any mutation.
- The live GitHub issue body was updated with the **additive 18-line clarification only**, preserving every pre-existing requirement. Immediate GitHub readback matched the repo mirror byte-for-byte and had the new digest.
- The recursive child registry and child index are updated to the same digest. No A09 code, source admission, learner state, or parent closure was changed.

This is a C01 cross-lane metadata repair. It is not A09.1 implementation acceptance and does not authorize merging into `main` or self-merging the reviewed unified PR.
