"""Check the repaired recipe's exact predicates against its executed proof logs."""
import argparse
from pathlib import Path
import re
import shlex


SOURCE = 'TEST_TOTALS total=193 passed=193 failed=0 skipped=0 errors=0'
INSTALLED = 'INSTALLED_TEST_TOTALS 122 0 0 0'
ORIGINS = 'INSTALLED_WHEEL_MODULE_ORIGINS_OK'


def validate_recipe(document: str, proof_root: Path) -> None:
    blocks = re.findall(r'```sh\n(.*?)\n```', document, re.S)
    expected = ((SOURCE, 'source-tests.log'), (INSTALLED, 'installed-tests.log'))
    if len(blocks) != len(expected):
        raise ValueError('expected exactly the source and installed success predicates')
    for command, (line, filename) in zip(blocks, expected):
        words = shlex.split(command.replace('\\\n', ''))
        if words != ['grep', '-Fx', line, '$proof_root/' + filename]:
            raise ValueError('stale or unsupported recipe success predicate')
        if line not in (proof_root / filename).read_text().splitlines():
            raise ValueError('required no-skip success line missing: ' + filename)
    if ORIGINS not in (proof_root / 'installed-tests.log').read_text().splitlines():
        raise ValueError('installed module-origin proof missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proof_root', type=Path)
    args = parser.parse_args()
    document = Path(__file__).with_name('public-callable-identity-771.md').read_text()
    validate_recipe(document, args.proof_root)
    print('REPAIRED_RECIPE_PROOF_OK')
