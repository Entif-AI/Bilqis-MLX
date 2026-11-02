"""Declared contract fixtures; no historical checkpoint or admission authority."""
from contextlib import contextmanager
from pathlib import Path
import tempfile
from unittest.mock import patch

from bilqis_mlx.verification.generated_tests import publication


@contextmanager
def boolean_release_fixture():
    parity = {'source_sha256': {'contract-fixture': 'a' * 64},
              'graph_sha256': 'b' * 64,
              'heads': {'semantic_token': {'values': ['school.number.' + str(i) for i in range(4)]},
                        'numeric_full_101': {'values': [str(i) for i in range(4)]}}}
    with tempfile.TemporaryDirectory() as directory, \
            patch.dict('os.environ', {'BILQIS_INTEGER_MAX': '3'}), \
            patch.object(publication, 'generate_integer_curriculum', return_value={'rows': []}), \
            patch.object(publication, '_source_stack', return_value=(None, None, None, None, {}, None)):
        yield parity, Path(directory)


def publish(parity, root, *, seed=97):
    return publication.regenerate(parity, Path('/declared-contract-fixture'), root,
        selector='family:boolean.constants', seed=seed, count=32)
