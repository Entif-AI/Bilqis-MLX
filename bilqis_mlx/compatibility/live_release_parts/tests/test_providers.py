"""Historical graph policy keeps its existing ABI-prefix and source-digest checks."""
import unittest

from bilqis_mlx.compatibility import live_releases
from bilqis_mlx.compatibility.live_release_parts import providers
from bilqis_mlx.semantics.abi import HISTORICAL_PREFIX_SIZE


class HistoricalGraphProviderTests(unittest.TestCase):
    versions = (None, providers.INITIAL_RELEASE, providers.BOOLEAN_RELEASE,
                providers.BOOLEAN_COMPOSITE_RELEASE,
                providers.BOOLEAN_IDENTIFICATION_RELEASE,
                providers.MINIMAL_BOOLEAN_RELEASE)

    def test_historical_releases_accept_matching_prefix_and_digest(self):
        graph = {"tokens": tuple(range(HISTORICAL_PREFIX_SIZE))}
        manifest = {"parent_student": {"full_student_graph_sha256": "accepted-graph"}}
        for check in (providers.graph_matches_release, live_releases.graph_matches_release):
            for version in self.versions:
                with self.subTest(api=check.__module__, version=version):
                    self.assertIs(check(version, graph, manifest,
                                        lambda value: "accepted-graph"), True)

    def test_historical_releases_reject_wrong_prefix(self):
        graph = {"tokens": tuple(range(HISTORICAL_PREFIX_SIZE - 1))}
        manifest = {"parent_student": {"full_student_graph_sha256": "accepted-graph"}}
        for check in (providers.graph_matches_release, live_releases.graph_matches_release):
            for version in self.versions:
                with self.subTest(api=check.__module__, version=version):
                    self.assertIs(check(version, graph, manifest,
                                        lambda value: "accepted-graph"), False)

    def test_historical_releases_reject_wrong_digest(self):
        graph = {"tokens": tuple(range(HISTORICAL_PREFIX_SIZE))}
        manifest = {"parent_student": {"full_student_graph_sha256": "accepted-graph"}}
        for check in (providers.graph_matches_release, live_releases.graph_matches_release):
            for version in self.versions:
                with self.subTest(api=check.__module__, version=version):
                    self.assertIs(check(version, graph, manifest,
                                        lambda value: "different-graph"), False)
