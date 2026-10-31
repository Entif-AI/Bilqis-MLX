# A04 parent #351: reversible frame-codec integration crosswalk

Status: **PARENT EGM PENDING**, no parent closure claimed.

## Source and review identity

- Reviewed unified: `7ad8f8abc9efcc4b9fb5311a1572979c49b22cf4`.
- Lane A audit base: `9fa752b6410c8248aa784a361247a8a7230fb748`.
  The unified head is already an ancestor; no no-op merge.
- Original owner: A04 #351, with direct A03 dependency #349.
  Children A04.1 #405, A04.2 #406 and A04.3 #407
  are closed with independent scoped EGM PASS in
  `docs/evidence/bamf/A04/egm.md`.
- The codec remains a representation, not semantic
  identity or source admission. Source-active readout
  is checked through the actual A01 ABI snapshot.

## Original acceptance crosswalk

| Original parent contract | Literal executable witness |
| --- | --- |
| Four 13-bit indices, presence bits 52-55, release-local schema tag 56-59 and codec version 60-63 | `test_literal_bit_layout_and_roundtrip` |
| Literal [0,1,8190,8191], all-zero/all-max and zero-present contrast | `test_all_zero_indices_and_all_max_fields_match_literal_words`, `test_zero_index_is_present_not_empty` |
| Eight-byte little-endian u64 and exact decimal JSON representation | `test_little_endian_eight_bytes_and_decimal_json_are_literal` |
| Version/presence/range/schema-tag errors fail closed | `test_range_version_presence_and_unknown_tag_fail_closed`, `test_schema_map_is_release_local_content_addressed_and_schema_exact` |
| Seventeenth schema, index8192, five occupants, nested/partial/atomic frames use typed extended fallback | `test_index8192_five_slots_and_nested_child_choose_extended`, `test_partial_and_atomic_fallback_are_typed_not_exception_driven` |
| Extended uint32 addresses round-trip; overflow fails | `test_extended_uint32_upper_boundary_roundtrips_and_overflow_rejects` |
| Original role/occurrence/source metadata survives, including identical-content distinct occurrences | `test_constituent_sidecar_preserves_order_source_and_occurrence`, `test_pack_frame_compact_and_extended_reconstruct_exactly` |
| Four same-type constituents in distinct roles must not collapse | `test_constituent_sidecar_preserves_order_source_and_occurrence` and canonical role-order checks |
| Repeated occupants of a singular role, wrong type and schema-order substitution must fail rather than fall back | `test_singular_schema_role_cannot_fall_back_to_extended_when_duplicated`, `test_role_type_mismatch_is_not_a_codec_fallback`, `test_packed_frame_must_match_authoritative_schema_role_order` |
| In-range inactive or source-held semantic IDs cannot be read out | `test_role_index_is_codec_neutral_and_rejects_inactive_or_held_readout` |
| Wrong release, tag reuse or forged coordinated payload/sidecar cannot reinterpret content | `test_wrong_release_or_schema_map_refuses_sidecar_reinterpretation`, `test_payload_and_sidecar_cannot_rebind_another_schema_or_release` |

The source schema's role order, cardinality, occurrence
sequence and allowed types are validated before COMPACT/
EXTENDED selection and again at unpack. The same exact
role-index accessor serves both representations.

## Prime verification and remaining gate

On reviewed unified `7ad8f8a`:
`scripts/run_tests.py bilqis_mlx/semantics/tests/test_frame_codec.py`
returned **17 passed, 0 failed, 0 skipped**.
The three leaf EGM PASS dispositions were separately
verified at their immutable heads and recorded in
`docs/evidence/bamf/A04/egm.md`.

This crosswalk is a **parent audit candidate**, not a
fresh independent parent-level EGM. It must receive
independent review, reconcile any Blocker/Major and
land through the reviewed Lane A process before
closing #351. It does not grant neural, source
admission, training or self-merge authority.
