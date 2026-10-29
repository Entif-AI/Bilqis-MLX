# A05.1-A05.3 independent review reconciliation

Initial independent read-only target: `e1b45f0`.
Reviewed unified source: `6b54600` (consumed into Lane A).
Scope: A05.1 #408, A05.2 #409, A05.3 #410.

The initial reviewer reported one Blocker and three Majors:

1. Atom-only prefixes could emit raw source atoms without a source
   grant. Repaired with per-atom A13 source-owned evidence and
   rights/temporal/revocation checks; first-admission negatives added.
2. Lawful segments could mix correction generations or observation
   frontiers. Repaired with a shared cross-segment authority tuple,
   plus independent drift negatives.
3. The compact four-member sidecar had no literal canonical-byte
   witness. Added the pinned 2,563-byte JSON fixture, SHA-256
   `cd2485f302d7e05bea293493e7f697315763fbf0cc8c0df4dbbe99167a7e43fc`,
   and a byte-for-byte test.
4. The earlier 1025 rejection test did not prove inclusive admission
   at 1024. Already repaired at `63583b6`, with literal 1024-atom
   and 1023-atom-plus-closure positive tests.

Prime execution after these repairs: owner 20 passed, 0 failed;
adjacent A03/A04/A13/A05 suites 83 passed, 0 failed, 1 optional
real-Atlas skip. The reviewer did not execute these tests.

**Disposition: EGM re-review pending.** Do not promote to PASS
without independent immutable-head readback. No source promotion,
live optimizer start, parent integration closure or merge is claimed.
