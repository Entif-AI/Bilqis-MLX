"""Isolated test C09 owner; never production source authority."""
from unittest.mock import patch

import bilqis_mlx.runtime.atlas_source_authority as _runtime


_test_lookup, _test_issue = _runtime._new_authority_owner()


def authority_for_registry(registry):
    return _test_issue(registry)


def install_test_owner(test_case):
    owner = patch.object(_runtime, "_authority_state", _test_lookup)
    owner.start()
    test_case.addCleanup(owner.stop)
