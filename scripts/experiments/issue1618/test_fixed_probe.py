"""Exercise the actual release roster and row-disjoint probe contract."""
from pathlib import Path

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from scripts.bamf.profiling.issue1578_logical_arm import c16, profile
from scripts.experiments.issue1618.fixed_probe import probe_rows


def test_reduced_boolean_release_probe_is_drawable_and_disjoint():
    root = Path(__file__).resolve().parents[3]
    context, _ = profile.live_factory_context(root, root / "vendor/legacy-v16")
    with evidence_mode(strict=False):
        training = context.draw_rows(seed=c16.SOURCE_SEED, capability="B.AND", each=32)
        seed, caps, rows = probe_rows(context, "B.AND", training)
        assert caps == ("B.AND", "B.IFF", "A.IDENTITY")
        assert seed == 98318
        ids = {row["id"] for row in rows}
        assert len(ids) == len(rows) == 18
        assert not ids.intersection(row["id"] for row in training)
        assert probe_rows(context, "B.AND", training) == (seed, caps, rows)
