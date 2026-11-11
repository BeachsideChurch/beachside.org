"""Run Hugo with computed message slugs in a temporary content tree."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

try:
    import yaml
except ModuleNotFoundError:
    sys.exit('Missing PyYAML. Install build dependencies with:\n'
             '  python -m pip install -r scripts/requirements-build.txt')

ROOT = Path(__file__).resolve().parents[1]


def prepare_message(raw):
    """Supply part-N when a positive integer part is present and slug is empty."""
    text = raw.decode('utf-8-sig')
    match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
    if not match:
        return raw
    header = match.group(1)
    data = yaml.safe_load(header)
    if not isinstance(data, dict):
        return raw
    slug = data.get('slug')
    if slug is not None and str(slug).strip():
        return raw
    part = data.get('part_number')
    if isinstance(part, bool) or not re.fullmatch(r'[1-9][0-9]*', str(part)):
        return raw
    newline = '\r\n' if '\r\n' in text else '\n'
    # Change only the slug value; preserve the rest of the front matter/body.
    for key, value in yaml.compose(header).value:
        if key.value == 'slug':
            start = match.start(1) + value.start_mark.index
            end = match.start(1) + value.end_mark.index
            return (text[:start] + f' part-{part}' + text[end:]).encode('utf-8')
    start = match.start(1)
    return (text[:start] + f'slug: part-{part}' + newline + text[start:]).encode('utf-8')


def sync_content(source, destination, previous=None):
    """Mirror edits, additions, resources, and deletions for Hugo's watcher."""
    previous = previous or {}
    current = {}
    for path in source.rglob('*'):
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        stat = path.stat()
        signature = (stat.st_mtime_ns, stat.st_size)
        current[relative] = signature
        if previous.get(relative) == signature:
            continue
        raw = path.read_bytes()
        if (relative.parts[0] == 'messages' and path.suffix.lower() == '.md'
                and path.name != '_index.md'):
            try:
                raw = prepare_message(raw)
            except (yaml.YAMLError, UnicodeError) as error:
                raise ValueError(f'{path}: {error}') from error
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for relative in previous.keys() - current.keys():
        (destination / relative).unlink(missing_ok=True)
    # Empty bundle/series directories must disappear after their files do.
    for path in sorted(destination.rglob('*'), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    return current


def main():
    parser = argparse.ArgumentParser(description=__doc__, add_help=False)
    parser.add_argument('--source', '-s', type=Path, default=ROOT)
    options, arguments = parser.parse_known_args()
    if any(arg in ('--contentDir', '-c', '--watch', '-w')
           or arg.startswith('--contentDir=') or arg.startswith('--watch=')
           for arg in arguments):
        parser.error('Use server for live previews; the wrapper manages contentDir and watching.')
    source = options.source.resolve()
    if not (source / 'content').is_dir():
        parser.error(f'Missing content directory: {source / "content"}')
    hugo = shutil.which('hugo')
    if not hugo:
        parser.error('Install Hugo and add it to PATH first.')
    with tempfile.TemporaryDirectory(prefix='beachside-content-') as directory:
        content = Path(directory) / 'content'
        content.mkdir()
        snapshot = sync_content(source / 'content', content)
        command = [hugo, '--source', str(source), '--contentDir', str(content), *arguments]
        if 'server' not in arguments:
            return subprocess.call(command)
        process = subprocess.Popen(command)
        last_error = None
        try:
            while process.poll() is None:
                time.sleep(0.5)
                try:
                    snapshot = sync_content(source / 'content', content, snapshot)
                    last_error = None
                except (ValueError, OSError) as error:
                    # Keep the last valid preview while the editor finishes a save.
                    if str(error) != last_error:
                        print(error, file=sys.stderr, flush=True)
                        last_error = str(error)
            return process.returncode
        except KeyboardInterrupt:
            return 130
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait()


if __name__ == '__main__':
    sys.exit(main())
