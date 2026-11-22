"""#1537 exact selected-source cross-offer cache regressions."""
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("BILQIS_STRICT_EVIDENCE_TESTS") != "1",
    reason="strict source-materialization cache is opt-in during BAMF stabilization",
)

from bilqis_mlx.runtime.priority_source_materialization import (
    prepare_priority_source_materialization,
)
from bilqis_mlx.runtime.priority_source_materialization_cache import (
    PreparedPrioritySourceArtifacts, PrioritySourceMaterializationCache,
    rebind_priority_source_rows,
)
from bilqis_mlx.runtime.source_execution import (
    SourcePreparationMetrics, source_content_digest,
)


class _Owner:
    def __init__(self):
        self.requires = 0

    def require(self, *_args):
        self.requires += 1

    def require_row(self, *_args):
        self.requires += 1

    def require_current(self):
        self.requires += 1


class _Registrar:
    def __init__(self):
        self.registrations = []

    def register(self, kind, owner):
        self.registrations.append((kind, owner))


def _planning(
        authenticated, registrar, *, correction="c" * 64,
        accepted_manifest="a" * 64):
    return SimpleNamespace(
        accepted_manifest_sha256=accepted_manifest,
        generation_binding="b" * 64,
        acceptance_sha256="d" * 64,
        acceptance_file_identity_sha256="e" * 64,
        run_identity_sha256="f" * 64,
        release_sha256="1" * 64,
        correction_frontier_sha256=correction,
        feature_receipt_sha256="2" * 64,
        parent_candidate_identity_sha256="3" * 64,
        _authenticated_features=authenticated,
        _target_registrar=registrar,
    )


def _cache_offer(
        cache, authenticated, registrar, rows, *, correction="c" * 64,
        accepted_manifest="a" * 64):
    return SimpleNamespace(
        _materialized={},
        _materialization_cache=cache,
        _planning_generation=_planning(
            authenticated, registrar, correction=correction,
            accepted_manifest=accepted_manifest),
        release_sha256="1" * 64,
        capability_id="cap",
        source_seed=17,
        source_each=1,
        source_family_id="family",
        source_binding_digest="4" * 64,
        _rows_sha256="5" * 64,
        source_authority=SimpleNamespace(
            provider_id="provider",
            provider_implementation_sha256="6" * 64,
            content_sha256=source_content_digest(rows),
            episode_ids=(rows[0]["id"],),
        ),
        require_qualified_current=lambda *_args, **_kwargs: rows,
    )


def _prepared_fixture(rows):
    prefix = SimpleNamespace(positions=(1,))
    source_rows = (SimpleNamespace(row=rows[0], source_adapter="adapter"),)
    model_sources = (SimpleNamespace(prefix=prefix),)
    return source_rows, model_sources


def _materialize_two(offers, context, source_rows, model_sources):
    with patch(
            "bilqis_mlx.runtime.factory_training_bridge._prepare_factory_source_rows",
            return_value=("adapter", "manifest", "profile", source_rows)) as prepare, patch(
                "bilqis_mlx.runtime.priority_source_materialization._prepare_model_sources",
                return_value=(model_sources, ("config",))), patch(
                    "bilqis_mlx.runtime.factory_training_bridge._prepare_b11_source_binding",
                    return_value=_Owner()), patch(
                    "bilqis_mlx.runtime.factory_training_bridge._motif_planning_input",
                    return_value="motif"), patch(
                    "bilqis_mlx.runtime.priority_source_materialization.rebind_priority_source_rows",
                    return_value=("adapter", "profile", source_rows)), patch(
                    "bilqis_mlx.runtime.priority_source_materialization._owners",
                    side_effect=((_Owner(), _Owner(), _Owner()),
                                 (_Owner(), _Owner(), _Owner()))):
        results = tuple(
            prepare_priority_source_materialization(offer, context, "parent")
            for offer in offers)
    return prepare, results


def test_exact_cross_offer_reuses_heavy_artifacts_with_fresh_visit_owners():
    rows = ({"id": "row:one", "capability": "cap", "tokens": [1]},)
    source_rows, model_sources = _prepared_fixture(rows)
    cache = PrioritySourceMaterializationCache()
    first_registrar, second_registrar = _Registrar(), _Registrar()
    first_authenticated = SimpleNamespace(features="features")
    second_authenticated = SimpleNamespace(features="features")
    offers = (
        _cache_offer(cache, first_authenticated, first_registrar, rows),
        _cache_offer(cache, second_authenticated, second_registrar, rows),
    )
    context = SimpleNamespace(
        _source_preparation_metrics=SourcePreparationMetrics())

    prepare, (first, second) = _materialize_two(
        offers, context, source_rows, model_sources)

    assert first is not second
    assert first.semantic_context is first_authenticated
    assert second.semantic_context is second_authenticated
    assert second.rows == first.rows
    assert second.manifest == first.manifest
    assert second.profile == first.profile
    assert tuple(item.row for item in second.source_rows) == tuple(
        item.row for item in first.source_rows)
    assert second.source_rows is first.source_rows
    assert second.model_sources is first.model_sources
    assert second.prefixes is first.prefixes
    assert second.b11_sources is not first.b11_sources
    prepare.assert_called_once()
    assert len(first_registrar.registrations) == 3
    assert len(second_registrar.registrations) == 3
    assert cache.metrics() == {
        "hits": 1, "misses": 1, "evictions": 0, "entries": 1}
    assert first._performance_observation["source_materialization_cache_hit"] == 0
    assert second._performance_observation["source_materialization_cache_hit"] == 1


@pytest.mark.parametrize("changed", ("correction", "accepted_manifest"))
def test_materialization_cache_misses_when_authority_identity_changes(changed):
    rows = ({"id": "row:one", "capability": "cap", "tokens": [1]},)
    source_rows, model_sources = _prepared_fixture(rows)
    cache = PrioritySourceMaterializationCache()
    context = SimpleNamespace(
        _source_preparation_metrics=SourcePreparationMetrics())
    kwargs = {changed: "9" * 64}
    offers = (
        _cache_offer(cache, SimpleNamespace(features="f"), _Registrar(), rows),
        _cache_offer(
            cache, SimpleNamespace(features="f"), _Registrar(), rows, **kwargs),
    )

    prepare, _results = _materialize_two(
        offers, context, source_rows, model_sources)

    assert prepare.call_count == 2
    assert cache.metrics() == {
        "hits": 0, "misses": 2, "evictions": 0, "entries": 2}


def test_failed_materialization_does_not_poison_exact_cache():
    rows = ({"id": "row:one", "capability": "cap", "tokens": [1]},)
    cache = PrioritySourceMaterializationCache()
    offer = _cache_offer(
        cache, SimpleNamespace(features="f"), _Registrar(), rows)
    context = SimpleNamespace(
        _source_preparation_metrics=SourcePreparationMetrics())

    with patch(
            "bilqis_mlx.runtime.factory_training_bridge._prepare_factory_source_rows",
            side_effect=RuntimeError("cold build interrupted")):
        with pytest.raises(RuntimeError, match="cold build interrupted"):
            prepare_priority_source_materialization(offer, context, "parent")

    assert cache.metrics() == {
        "hits": 0, "misses": 1, "evictions": 0, "entries": 0}


def test_materialization_cache_is_bounded_and_evicts_oldest_identity():
    cache = PrioritySourceMaterializationCache(capacity=2)

    def item(identity):
        return PreparedPrioritySourceArtifacts(
            (identity,), object(), (object(),), (object(),), (object(),), (object(),))

    cache.put(item("a"))
    cache.put(item("b"))
    cache.put(item("c"))

    assert cache.metrics() == {
        "hits": 0, "misses": 0, "evictions": 1, "entries": 2}
    assert cache.get(("a",)) is None
    assert cache.metrics()["entries"] == 2


def test_cached_source_rows_reject_process_live_source_owner_drift():
    rows = ({
        "id": "row:one", "capability": "cap", "tokens": [1],
        "generator": "generator", "oracle": "oracle",
    },)
    cached = SimpleNamespace(
        row=dict(rows[0]), source_adapter=object(), source_graph={"graph": 1},
        source_seed=17, source_each=1, source_witness=object(),
        formal_projection=object(), formal_frontier=object())
    artifacts = SimpleNamespace(source_rows=(cached,))
    execution = SimpleNamespace(capability_id="cap", provider_parameters={})
    context = SimpleNamespace(
        source_root=Path("/source"), graph={}, source_registry=object(),
        release=SimpleNamespace(
            execution_plan=SimpleNamespace(capability_map={"cap": execution}),
            curriculum=object()))
    authenticated = SimpleNamespace(selection=object())
    offer = SimpleNamespace(capability_id="cap", source_authority=object())

    with patch(
            "bilqis_mlx.factory.generation.runtime_adapter_for_release",
            return_value=object()), patch(
                "bilqis_mlx.source_adapters.atoms.authority.canonical_graph_for",
                return_value={"graph": 1}), patch(
                    "bilqis_mlx.runtime.b11_source_owner_authority.require_row_owner",
                    side_effect=ValueError("B11_SOURCE_EXECUTION_OWNER_DRIFT")):
        with pytest.raises(ValueError, match="B11_SOURCE_EXECUTION_OWNER_DRIFT"):
            rebind_priority_source_rows(
                offer, context, authenticated, rows, artifacts)
