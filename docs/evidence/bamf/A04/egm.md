# A04 codec independent review and repair

Reviewer: fresh-context Goldfish worker-3, read-only.
Reviewed target: Lane A `5e84ffb`.
Prime tests after repair: `test_frame_codec.py`, 17 passed.

The independent reviewer found zero Blockers and one Major in
A04.2/A04.3: the codec treated a same-schema singular-role
cardinality violation as an EXTENDED representation fallback.
The source schema must constrain every representation.

The prime reproduced the duplicate-role acceptance with a
failing-before test. The codec now checks authoritative role
ordering, cardinality, occurrence sequence and allowed types
before pack classification and on decoded frames. A same-ID
schema with a different role order also fails. The new negative
tests and existing codec suite pass 17/17.

The same independent reviewer read back immutable pushed
`9e3ec5b019c0468e4be762540894ee45f4c31923` and returned
**A04.2/A04.3 EGM PASS, zero remaining Blockers/Majors**. The
reviewer verified pack and unpack both enforce the shared schema
validator before returning any representation. It inspected the
17-test suite but did not successfully execute it in its older
worker checkout; the 17/17 result is prime execution evidence.

A04.1's separate compact-bit-layout review remains pending.
No live training, source admission or merge occurred.
