"""Reproduce #641 source/test preservation against the accepted pre-split owner."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess


BASE = 'cec6a8ee1659854c292dc59566d4d14a53b75ae5^'
PRODUCTION = Path('bilqis_mlx/runtime/_depth')
TESTS = Path('bilqis_mlx/runtime/tests/depth')


def original(path):
    return ast.parse(subprocess.check_output(['git', 'show', BASE + ':' + path], text=True))


def definitions(trees, *, recursive):
    result = {}
    for tree in trees:
        nodes = ast.walk(tree) if recursive else tree.body
        for node in nodes:
            kinds = (ast.FunctionDef,) if recursive else (ast.FunctionDef, ast.ClassDef)
            if isinstance(node, kinds):
                if node.name in result:
                    raise ValueError('duplicate preserved definition: ' + node.name)
                result[node.name] = hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()).hexdigest()
    return result


def verify():
    reports = {}
    cases = (
        ('production', 'bilqis_mlx/runtime/block_attnres.py', PRODUCTION, False),
        ('tests', 'bilqis_mlx/runtime/tests/test_block_attnres.py', TESTS, True),
    )
    for label, old_path, directory, recursive in cases:
        before = definitions([original(old_path)], recursive=recursive)
        paths = sorted(directory.glob('*.py'))
        after = definitions([ast.parse(path.read_text()) for path in paths], recursive=recursive)
        if any(after.get(name) != digest for name, digest in before.items()):
            raise ValueError(label + ': definition/decorator drift')
        sizes = {str(path): len(path.read_text().splitlines()) for path in paths}
        if any(size >= 240 for size in sizes.values()) or len(paths) > 12:
            raise ValueError(label + ': structural target violated')
        reports[label] = {'preserved_definitions': before, 'file_lines': sizes}
    from bilqis_mlx.runtime import block_attnres
    for name in ('DepthParameterView', '_DepthFeatureValues', 'DepthFrameFeatures', 'DepthSummary'):
        if getattr(block_attnres, name).__module__ != 'bilqis_mlx.runtime.block_attnres':
            raise ValueError('public class identity drift: ' + name)
    return {'baseline': BASE, 'reports': reports}


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, sort_keys=True))
