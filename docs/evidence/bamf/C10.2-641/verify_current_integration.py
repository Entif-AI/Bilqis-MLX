"""Verify the #641 overlay without reverting accepted B05 successor behavior."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from verify_preservation import require_receipt


BASE = 'dfc0c7586c23b6477c08d4db486ade3deeb79fae'
ROOTS = ('bilqis_mlx/runtime/_depth', 'bilqis_mlx/runtime/tests/depth')
OWNER = ROOTS[0] + '/depth_contracts.py'
TEST = ROOTS[1] + '/test_depth_contracts.py'
ANCHOR = 'DepthParameterView.__module__ = "bilqis_mlx.runtime.block_attnres"\n'
IDENTITY = 'depth_parameter_view.__module__ = "bilqis_mlx.runtime.block_attnres"\n'
REGRESSION = '''    def test_parameter_view_factory_keeps_public_pickle_identity(self):
        import pickle
        from bilqis_mlx.runtime import block_attnres
        expected = b'cbilqis_mlx.runtime.block_attnres\\ndepth_parameter_view\\np0\\n.'
        self.assertIs(pickle.loads(expected), block_attnres.depth_parameter_view)
        self.assertEqual(pickle.dumps(block_attnres.depth_parameter_view, protocol=0), expected)

'''


def expected_overlay(path, source):
    if path == OWNER:
        if source.count(ANCHOR) != 1 or IDENTITY in source:
            raise ValueError('unexpected factory metadata baseline')
        return source.replace(ANCHOR, ANCHOR + IDENTITY)
    if path == TEST:
        anchor = 'class DepthSelectionTests(unittest.TestCase):\n'
        if source.count(anchor) != 1 or REGRESSION in source:
            raise ValueError('unexpected regression baseline')
        return source.replace(anchor, anchor + REGRESSION)
    return source


def require_overlay(path, before, after):
    if after != expected_overlay(path, before):
        raise ValueError('unexpected integration delta: ' + path)


def verify():
    paths = subprocess.check_output(
        ['git', 'ls-tree', '-r', '--name-only', BASE, '--', *ROOTS], text=True).splitlines()
    paths = [path for path in paths if path.endswith('.py')]
    actual = sorted(str(path) for root in ROOTS for path in Path(root).glob('*.py'))
    if sorted(paths) != actual:
        raise ValueError('depth owner/test inventory drift')
    hashes, sizes = {}, {}
    for path in paths:
        before = subprocess.check_output(['git', 'show', BASE + ':' + path], text=True)
        after = Path(path).read_text()
        require_overlay(path, before, after)
        hashes[path] = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        sizes[path] = len(after.splitlines())
    if any(size >= 240 for size in sizes.values()):
        raise ValueError('depth file structural target violated')
    if any(sum(Path(path).parent == Path(root) for path in paths) > 12 for root in ROOTS):
        raise ValueError('depth directory structural target violated')
    for name in ('verify_current_integration.py', 'test_verify_current_integration.py'):
        path = Path(__file__).with_name(name)
        hashes[str(path.relative_to(Path.cwd()) if path.is_absolute() else path)] = (
            hashlib.sha256(path.read_bytes()).hexdigest())
    return {'accepted_unified': BASE, 'allowed_delta': [OWNER, TEST],
            'file_lines': sizes, 'inspected_file_sha256': hashes}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    result = verify()
    if args.check:
        require_receipt(result, Path(__file__).with_name('current-integration.json'))
        print('CURRENT_INTEGRATION_RECEIPT_OK')
    else:
        print(json.dumps(result, indent=2, sort_keys=True))
