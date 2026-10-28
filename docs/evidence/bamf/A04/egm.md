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

Disposition: implementation repair pushed for independent
immutable-head re-review. No EGM PASS is claimed until that
readback. No live training, source admission or merge occurred.
