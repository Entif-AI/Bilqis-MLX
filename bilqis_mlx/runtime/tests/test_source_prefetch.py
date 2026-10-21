"""Three-lane source preparation must stay deterministic and neural-inert."""
from pathlib import Path
import signal
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from bilqis_mlx.cli import parse_args
from bilqis_mlx.runtime import source_prefetch
from bilqis_mlx.runtime.source_prefetch import prepare_step_sources


ROOT = Path(__file__).resolve().parents[3]
SOURCE_ROOT = ROOT / "vendor" / "legacy-v16"
CHECKPOINT = (SOURCE_ROOT / "runs/primitive-consolidation-v16-triplets/"
              "student-116760-7e9af4651f28.pt")
MANIFEST = ROOT / "docs/provenance/GRADE_A_CANDIDATE_MANIFEST_V2.json"


class SourcePrefetchTests(unittest.TestCase):
    def test_human_cli_defaults_to_two_prep_workers_with_serial_escape_hatch(self):
        self.assertEqual(parse_args(["train"]).source_prefetch_workers, 2)
        self.assertEqual(
            parse_args(["train", "--source-prefetch-workers", "0"]).source_prefetch_workers,
            0,
        )

    def test_spawned_prefetch_workers_ignore_terminal_sigint(self):
        with source_prefetch.source_prefetch_pool(1) as pool:
            # Child importability must not depend on the dynamic module name
            # that scripts/run_tests.py assigns to collected test files.
            self.assertEqual(
                pool.submit(signal.getsignal, signal.SIGINT).result(timeout=10),
                signal.SIG_IGN)

    def test_step_packet_is_deterministic_and_rejects_neural_or_write_authority(self):
        course = SimpleNamespace(grades=(SimpleNamespace(id="B"),))
        request = {
            "identity": "a" * 64,
            "source_root": "/source",
            "graph": {"tokens": []},
            "course": course,
            "capability": "B.XOR",
            "batch_size": 4,
            "fresh_seed": 11,
            "prior_capability": None,
            "prior_seed": None,
            "fragile_fixed_rows": (),
            "fragile_requested": (),
            "fragile_seeds": {},
            "fragile_rotation": 0,
            "teaching_seed": 13,
            "teaching_enrichment_enabled": False,
        }
        rows = [
            {"id": f"r{i}", "source_id": f"r{i}", "capability": "B.XOR",
             "gold": "TRUE" if i % 2 else "FALSE", "tokens": [1, i + 2]}
            for i in range(8)
        ]
        with patch("bilqis_mlx.runtime.source_prefetch.draw_course_rows", return_value=rows):
            first = prepare_step_sources(request)
            second = prepare_step_sources(request)
        self.assertEqual(first, second)
        self.assertEqual(first["identity"], request["identity"])
        self.assertEqual(len(first["fresh"]), 8)
        self.assertEqual(first["prior"], [])
        self.assertNotIn("parameters", first)
        self.assertNotIn("optimizer", first)
        self.assertNotIn("run_dir", first)

        for forbidden in ("parameters", "optimizer", "run_dir", "checkpoint"):
            with self.subTest(forbidden=forbidden):
                with self.assertRaisesRegex(ValueError, "SOURCE_PREFETCH_FORBIDDEN_AUTHORITY"):
                    prepare_step_sources({**request, forbidden: object()})

    def test_active_v2_packet_uses_executable_release_instead_of_legacy_course(self):
        request = {
            "identity": "b" * 64, "source_root": "/source",
            "graph": {"tokens": []}, "course": SimpleNamespace(),
            "executable_release": SimpleNamespace(release_sha256="c" * 64),
            "capability": "B.AND", "batch_size": 4,
            "fresh_seed": 15, "prior_capability": None,
            "prior_seed": None, "fragile_fixed_rows": (),
            "fragile_requested": (), "fragile_seeds": {},
            "fragile_rotation": 0, "teaching_seed": 16,
            "teaching_enrichment_enabled": False,
        }
        expected = [{"id": "v2", "capability": "B.AND", "gold": "TRUE"}]
        with (patch("bilqis_mlx.runtime.source_prefetch.draw_course_rows",
                    side_effect=AssertionError("Legacy v1 generation forbidden")),
              patch("bilqis_mlx.factory.generation.draw_executable_release_rows",
                    return_value=expected) as executable):
            result = prepare_step_sources(request)
        self.assertEqual(result["fresh"], expected)
        self.assertEqual(executable.call_args.kwargs["legacy_course"],
                         request["course"])

    @unittest.skipUnless(CHECKPOINT.is_file(), "Original source not mounted")
    def test_real_source_packet_survives_spawned_process_boundary(self):
        import torch
        from bilqis_mlx.trainer import prepare_source
        from bilqis_mlx.live_grade_a import live_course as a_live_course
        from bilqis_mlx.live_grade_b import live_course as b_live_course

        _manifest, historical, _engine, _teacher_sha, _teacher, _provenance = (
            prepare_source(SOURCE_ROOT, CHECKPOINT, MANIFEST))
        course = b_live_course(a_live_course(historical), SOURCE_ROOT)
        graph = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)["graph"]
        request = {
            "identity": "b" * 64,
            "source_root": str(SOURCE_ROOT),
            "graph": graph,
            "course": course,
            "capability": "B.XOR",
            "batch_size": 4,
            "fresh_seed": 119,
            "prior_capability": None,
            "prior_seed": None,
            "fragile_fixed_rows": (),
            "fragile_requested": (),
            "fragile_seeds": {},
            "fragile_rotation": 0,
            "teaching_seed": 120,
            "teaching_enrichment_enabled": False,
        }
        with source_prefetch.source_prefetch_pool(1) as pool:
            prepared = pool.submit(prepare_step_sources, request).result(timeout=30)
        direct = prepare_step_sources(request)
        self.assertEqual(prepared, direct)
        self.assertEqual(prepared["identity"], request["identity"])
        self.assertEqual(len(prepared["fresh"]), 32)
        self.assertEqual({row["capability"] for row in prepared["fresh"]}, {"B.XOR"})
