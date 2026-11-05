"""Check the repaired recipe's exact predicates against its executed proof logs."""
import argparse
from pathlib import Path
import re
import shlex


ORIGINS = 'INSTALLED_WHEEL_MODULE_ORIGINS_OK'


def validate_recipe(document: str, proof_root: Path, *,
                    source_total: int = 193, installed_total: int = 122) -> None:
    if any(type(total) is not int or total < 1
           for total in (source_total, installed_total)):
        raise ValueError('declared proof totals must be positive integers')
    source = (f'TEST_TOTALS total={source_total} passed={source_total} '
              'failed=0 skipped=0 errors=0')
    installed = f'INSTALLED_TEST_TOTALS {installed_total} 0 0 0'
    blocks = re.findall(r'```sh\n(.*?)\n```', document, re.S)
    expected = ((source, 'source-tests.log'), (installed, 'installed-tests.log'))
    commands = [shlex.split(line) for block in blocks
                for line in block.replace('\\\n', '').splitlines() if line.strip()]
    required = [['grep', '-Fx', line, '$proof_root/' + filename]
                for line, filename in expected]
    origins = ['grep', '-Fx', ORIGINS, '$proof_root/installed-tests.log']
    if commands not in (required, required + [origins]):
        raise ValueError('stale or unsupported recipe success predicate')
    for line, filename in expected:
        if line not in (proof_root / filename).read_text().splitlines():
            raise ValueError('required no-skip success line missing: ' + filename)
    if ORIGINS not in (proof_root / 'installed-tests.log').read_text().splitlines():
        raise ValueError('installed module-origin proof missing')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('proof_root', type=Path)
    parser.add_argument('--document', type=Path,
                        default=Path(__file__).with_name('public-callable-identity-771.md'))
    parser.add_argument('--source-total', type=int, default=193)
    parser.add_argument('--installed-total', type=int, default=122)
    args = parser.parse_args()
    validate_recipe(args.document.read_text(), args.proof_root,
                    source_total=args.source_total, installed_total=args.installed_total)
    print('REPAIRED_RECIPE_PROOF_OK')
