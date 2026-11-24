"""Ordinary replay is an exact, isolated, append-only projection."""
from types import SimpleNamespace
from unittest.mock import patch

from bilqis_mlx.runtime.bamf_operator.session_parts.evidence_mode import evidence_mode
from bilqis_mlx.runtime.outcomes import replay
from bilqis_mlx.runtime.outcomes.replay_cache import _snapshot
from bilqis_mlx.runtime.outcomes.replay_fold import PORTABLE_TEACHER_AUTHORITY


def test_incremental_replay_reuses_only_unchanged_authenticated_prefix(tmp_path):
    _snapshot.cache_clear()
    cache = SimpleNamespace(generation=7, accepted_manifest_sha256="a" * 64)
    base = {"credit": []}
    rows = []
    calls = []

    def append(receipt, *, portable=True):
        rows.append(("A.EDGE", receipt, "REJECT", receipt,
                     {PORTABLE_TEACHER_AUTHORITY: portable}))

    def fold(_run, _cache, teacher, tail, _override):
        receipts = [row[3] for row in tail]
        calls.append(receipts)
        return {"credit": [*teacher["credit"], *receipts]}

    def project(*, strict=False):
        with evidence_mode(strict=strict):
            return replay.replay_rejected_outcomes(tmp_path, None, cache, base)

    with patch.object(replay, "current_rejection_outcomes", side_effect=lambda *args: tuple(rows)), \
            patch("bilqis_mlx.runtime.outcomes.replay_fold.fold_rejections", side_effect=fold):
        append("one")
        append("two")
        assert project() == {"credit": ["one", "two"]}
        append("three")
        warm = project()
        assert warm == {"credit": ["one", "two", "three"]}
        assert calls[-1] == ["three"]
        warm["credit"].append("caller mutation")
        assert project() == {"credit": ["one", "two", "three"]}
        assert calls[-1] == []
        assert project(strict=True) == {"credit": ["one", "two", "three"]}
        assert calls[-1] == ["one", "two", "three"]
        rows.pop()
        assert project() == {"credit": ["one", "two"]}
        assert calls[-1] == ["one", "two"]
        rows.pop(0)
        append("replacement")
        assert project() == {"credit": ["two", "replacement"]}
        assert calls[-1] == ["two", "replacement"]
        cache.generation += 1
        assert project() == {"credit": ["two", "replacement"]}
        assert calls[-1] == ["two", "replacement"]
        base["credit"].append("new base")
        assert project() == {"credit": ["new base", "two", "replacement"]}
        assert calls[-1] == ["two", "replacement"]
        append("legacy", portable=False)
        assert project() == {"credit": ["new base", "two", "replacement", "legacy"]}
        assert calls[-1] == ["two", "replacement", "legacy"]
    assert base == {"credit": ["new base"]}
    _snapshot.cache_clear()
