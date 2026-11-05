"""Public compiler identity and packing seam compatibility."""
import pickle
from unittest import TestCase
from unittest.mock import patch

from bilqis_mlx.semantics import frame_compiler
from bilqis_mlx.semantics.frame_codec import pack_frame
from bilqis_mlx.semantics.tests.test_frame_compiler import (
    RELEASE, _case, _mixed_case, _with_atom_grants,
)


class PublicCompilerTests(TestCase):
    def test_source_records_and_enum_keep_canonical_pickle_identity(self):
        atom = frame_compiler.SourceAtom(0, "token", "source:token")
        for value in (atom, frame_compiler.PositionKind.ATOM):
            with self.subTest(value=value):
                self.assertEqual(type(value).__module__, frame_compiler.__name__)
                restored = pickle.loads(pickle.dumps(value))
                self.assertIs(type(restored), type(value))
                self.assertEqual(restored, value)

    def test_public_packer_patch_observes_successful_closure(self):
        ast, config = _case()
        with patch.object(frame_compiler, "pack_frame", wraps=pack_frame) as pack:
            compiled = frame_compiler.compile_prefix(ast, 8, RELEASE, config)
        self.assertEqual(pack.call_count, 1)
        self.assertEqual(compiled.stats.actual_frames, 1)
        self.assertEqual(frame_compiler.reconstruct(compiled).atoms, ast.atoms)

    def test_legacy_fixture_imports_keep_source_authority(self):
        ast, config = _mixed_case()
        self.assertEqual(_with_atom_grants(ast, config), config)
        compiled = frame_compiler.compile_prefix(ast, 8, RELEASE, config)
        self.assertIs(type(compiled), frame_compiler.CompiledFrameBatch)
        self.assertEqual(compiled.stats.actual_frames, 3)

    def test_batch_property_type_hints_keep_public_record_identity(self):
        from typing import get_type_hints

        batch = frame_compiler.CompiledFrameBatch
        self.assertIs(
            get_type_hints(batch.maps.fget)["return"], frame_compiler.PrefixMaps)
        self.assertIs(
            get_type_hints(batch.stats.fget)["return"], frame_compiler.CompileStats)

    def test_legacy_fixture_file_loads_without_package_context(self):
        from pathlib import Path
        import runpy

        fixture_file = Path(__file__).resolve().parents[1] / "test_frame_compiler.py"
        exported = runpy.run_path(str(fixture_file))
        self.assertIs(exported["_mixed_case"], _mixed_case)
