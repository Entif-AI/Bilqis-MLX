"""Original public-facade function dependencies remain late-bound after extraction."""
import unittest
from types import SimpleNamespace

from bilqis_mlx.semantics._public_identity.facade_dependencies import (
    audit_contract, captured_code_routes, captured_source_routes,
)


class FacadeDependencyTests(unittest.TestCase):
    def test_disassembly_rejects_captured_global_and_nested_calls_but_accepts_lookup(self):
        helper = lambda: "value"
        namespace = {"helper": helper, "facade": SimpleNamespace(helper=helper)}
        exec("def captured(): return helper()\n"
             "def nested(): return lambda: helper()\n"
             "def dynamic(): return facade.helper()\n", namespace)
        self.assertEqual(list(captured_code_routes(
            namespace["captured"].__code__, ("helper",))),
            [("captured", "helper")])
        self.assertEqual(list(captured_code_routes(
            namespace["nested"].__code__, ("helper",))),
            [("nested.<locals>.<lambda>", "helper")])
        self.assertEqual(list(captured_code_routes(
            namespace["dynamic"].__code__, ("helper",))), [])

    def test_source_census_rejects_captured_import_alias_default_and_closure(self):
        bad = (
            "def read():\n from facade import helper\n return helper()\n",
            "from facade import helper as alias\ndef read(): return alias()\n",
            "cached = facade.helper\ndef read(): return cached()\n",
            "def read(callback=facade.helper): return callback()\n",
            "cached = getattr(facade, 'helper')\ndef read(): return cached()\n",
            "def read(callback=getattr(facade, 'helper')): return callback()\n",
            "read = lambda callback=facade.helper: callback()\n",
            "def outer():\n cached = helper\n return lambda: cached()\n",
        )
        for source in bad:
            with self.subTest(source=source):
                self.assertTrue(list(captured_source_routes(source, ("helper",))))
        self.assertEqual(list(captured_source_routes(
            "def read(): return facade.helper()\n", ("helper",))), [])

    def test_all_four_owners_have_no_captured_original_callable_routes(self):
        reports = audit_contract()
        self.assertEqual(len(reports), 4)
        for report in reports:
            with self.subTest(owner=report["facade"]):
                self.assertEqual(report["captured_routes"], [])
