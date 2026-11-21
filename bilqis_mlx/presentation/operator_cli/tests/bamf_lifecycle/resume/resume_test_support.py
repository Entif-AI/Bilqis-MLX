"""Shared BAMF resume CLI test support."""
from contextlib import contextmanager, redirect_stderr, redirect_stdout
import io
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.cli import main
from bilqis_mlx.runtime.tests.bamf_first_student._bamf_first_student_support import BamfFirstStudentCase
from bilqis_mlx.runtime.tests.custody.bamf_bundle.genesis_authority_fixtures import accepted_feature_source_patch
from bilqis_mlx.runtime.tests.custody.bamf_bundle.helpers import shape_patch

ROOT = Path(__file__).resolve().parents[6]
TOPOLOGY = ROOT / "configs/models/bamf-0.2.json"


def tree_snapshot(root: Path):
    return tuple(
        (str(path.relative_to(root)), path.is_dir(), path.stat().st_mtime_ns,
         None if path.is_dir() else path.read_bytes())
        for path in (root, *sorted(root.rglob("*")))
    )


class ResumeCase(BamfFirstStudentCase):
    def invoke(self, argv):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(["train", *argv])
        return code, output.getvalue(), errors.getvalue()

    @contextmanager
    def accepted_read_context(self, atlas=None):
        if atlas is None:
            atlas = SimpleNamespace(
                bundle_id="a" * 64, release_sha256="b" * 64,
                source_bundle_id="c" * 64)
        with shape_patch(), accepted_feature_source_patch(), patch(
                "bilqis_mlx.presentation.operator_cli.bamf_lifecycle._accepted_atlas",
                return_value=atlas):
            yield
