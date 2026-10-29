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

## Final independent immutable-head readback

Fresh Goldfish worker-8 independently reviewed immutable pushed
`de5bb9c562992e3620a539dc5519f26a7374e772` against the
pinned Google EGM protocol `b3a35956759bf7f024af2ff061b2e0b44b438e4c`.
It inspected the exact #408/#409/#410 packets, all four original
findings, source, tests and literal sidecar fixture. It also
executed focused and adjacent tests in an isolated immutable archive:
20/20 owner and 83 adjacent passes with one optional real-Atlas skip.
The worker independently verified the 2,563-byte fixture SHA-256,
inclusive 1024 success, missing/revoked/tampered raw-atom rejection,
and cross-segment correction/observation/effective-time coherence.

**Final scoped disposition: A05.1/A05.2/A05.3 EGM PASS, zero
remaining Blockers or Majors.** A05 parent integration and downstream
B11/C13 neural-logit/retained-learning proof remain open. No source
promotion, live optimizer start, self-merge or parent closure occurred.
