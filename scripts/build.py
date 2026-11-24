"""Build Hugo and its Pagefind index together; optionally serve the finished site."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serve', action='store_true', help='Preview the indexed build')
    parser.add_argument('--destination', '-d', type=Path, default=ROOT / 'public')
    options, hugo_arguments = parser.parse_known_args()
    destination = options.destination.resolve()
    result = subprocess.call([
        sys.executable, str(ROOT / 'scripts/hugo.py'),
        '--destination', str(destination), *hugo_arguments,
    ], cwd=ROOT)
    if result:
        return result
    return subprocess.call([
        sys.executable, '-m', 'pagefind', '--site', str(destination),
        *(['--serve'] if options.serve else []),
    ], cwd=ROOT)


if __name__ == '__main__':
    sys.exit(main())
