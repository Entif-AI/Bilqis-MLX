"""B01 records conformance and compatibility."""
import pickle
from bilqis_mlx.runtime.tests.model.topology.helpers import (
    BilqisError,
    GenerationExtents,
    GenerationProvenance,
    Initializer,
    ModelTopologySpecV2,
    ParameterCensus,
    ParameterGroup,
    ParameterSpec,
    TopologyFixture,
    bamf_parameter_census,
    expected_bamf_shapes,
    json,
)


class TopologyRecordsTests(TopologyFixture):
    def test_generation_extents_versioned_roundtrip(self):
        original = self.extents()
        record = original.to_record()
        self.assertEqual(record, {
            "schema": "bilqis.mlx.generation-extents/v1",
            "semantic_bank_count": 1, "motif_page_count": 1,
            "active_semantic_digest": "a" * 64,
            "motif_key_map_digest": "b" * 64, "factor_map_digest": "c" * 64,
            "digest": original.digest,
        })
        self.assertEqual(GenerationExtents.from_record(json.loads(json.dumps(record))), original)
        topology = ModelTopologySpecV2().to_record()
        for banks, pages in ((2, 1), (1, 2), (2, 2)):
            grown = self.extents(banks, pages)
            self.assertEqual(GenerationExtents.from_record(grown.to_record()), grown)
            self.assertNotEqual(grown.digest, original.digest)
            self.assertEqual(ModelTopologySpecV2().to_record(), topology)
        for changed in ({**record, "schema": "future"}, {**record, "digest": "0" * 64},
                        {**record, "semantic_bank_count": 2}, {**record, "extra": 1},
                        {key: value for key, value in record.items() if key != "motif_page_count"},
                        None, []):
            with self.subTest(record=changed), self.assertRaises(BilqisError):
                GenerationExtents.from_record(changed)

    def test_provenance_is_separate_from_dense_and_extent_identity(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        original_topology, original_extents = spec.to_record(), extents.to_record()
        provenance = GenerationProvenance("fixture-source", "d" * 64, "fixture-teacher", 0)
        record = provenance.to_record()
        self.assertEqual(record["schema"], "bilqis.mlx.generation-provenance/v1")
        self.assertEqual(GenerationProvenance.from_record(json.loads(json.dumps(record))), provenance)
        for field, value in (("source_identity", "other-source"), ("release_digest", "e" * 64),
                             ("teacher_identity", "other-teacher"), ("teacher_epoch", 1)):
            other = GenerationProvenance(**{**{key: record[key] for key in (
                "source_identity", "release_digest", "teacher_identity", "teacher_epoch")}, field: value})
            self.assertNotEqual(other.digest, provenance.digest)
            self.assertEqual(spec.to_record(), original_topology)
            self.assertEqual(extents.to_record(), original_extents)
        for field, value in (("source_identity", ""), ("teacher_identity", " "),
                             ("release_digest", "invalid"), ("teacher_epoch", -1),
                             ("teacher_epoch", True)):
            with self.subTest(field=field), self.assertRaises(BilqisError):
                GenerationProvenance.from_record({**record, field: value})
        for bad in (None, [], {**record, "extra": 1}, {**record, "digest": "0" * 64},
                    {**record, "schema": "future"}):
            with self.assertRaises(BilqisError):
                GenerationProvenance.from_record(bad)

    def test_invalid_extents_and_parameter_records_fail_closed(self):
        for args in ((0, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 5, "a" * 64, "b" * 64, "c" * 64),
                     (True, 1, "a" * 64, "b" * 64, "c" * 64),
                     (1, 1, "bad", "b" * 64, "c" * 64)):
            with self.subTest(args=args), self.assertRaises(BilqisError):
                GenerationExtents(*args)
        for shape, initializer in (((0, 3), Initializer.MATRIX), ((3, 2), Initializer.CONV_IDENTITY),
                                   ((3, 4), "unknown"), ((1, 768), Initializer.IDENTITY_BANK),
                                   ((16384, 127), Initializer.MOTIF_PAGE)):
            with self.subTest(shape=shape, initializer=initializer), self.assertRaises(BilqisError):
                ParameterSpec("fixture", shape, initializer, ParameterGroup.SLOW, True)

    def test_parameter_census_rejects_invalid_identity_and_duplicate_rows(self):
        spec, extents = ModelTopologySpecV2(), self.extents()
        row = expected_bamf_shapes(spec, extents)[0]
        for bad_spec, bad_extents in ((None, extents), (spec, None)):
            with self.assertRaises(BilqisError):
                bamf_parameter_census(bad_spec, bad_extents)
        for topology_digest, parameters in (("bad", (row,)), (spec.digest, (row, row))):
            with self.assertRaises(BilqisError):
                ParameterCensus(topology_digest, extents.digest, parameters)

    def test_historical_enum_and_record_pickle_identity(self):
        historical=b'cbilqis_mlx.runtime.model_topology_v2\nParameterGroup\n(VFAST\ntR.'
        self.assertIs(pickle.loads(historical),ParameterGroup.FAST)
        extents=self.extents()
        self.assertEqual(pickle.loads(pickle.dumps(extents)),extents)
        self.assertIn(b'bilqis_mlx.runtime.model_topology_v2',pickle.dumps(extents))
