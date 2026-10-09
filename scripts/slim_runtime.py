"""Trim a Deeper-only runtime; not intended for a shared Python installation."""
import argparse
import json
from pathlib import Path

BUILD_TOOLS = {'pip', 'setuptools', 'wheel', 'pkg_resources', '_distutils_hack'}


def _files(root):
    return [path for path in root.rglob('*')
            if path.is_file() and not path.is_symlink()
            and path.resolve().is_relative_to(root)]


def prune(root: Path) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Runtime root must be a directory')
    files = _files(root)
    before = sum(path.stat().st_size for path in files)
    removed = 0
    for path in files:
        relative = path.relative_to(root)
        parts = relative.parts
        # Preserve notices even when they live inside an auxiliary directory.
        if path.name.lower().startswith(('license', 'licence', 'notice', 'copying', 'copyright')):
            continue
        auxiliary = (
            '__pycache__' in parts or path.suffix in ('.pyc', '.pyo')
            or 'tests' in parts or 'test' in parts
            or parts[:2] == ('pycountry', 'locales')
            or parts[0] in BUILD_TOOLS
        )
        if auxiliary:
            path.unlink()
            removed += 1
    # Empty directories only: never follow links or delete an unexamined tree.
    for path in sorted(root.rglob('*'), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            try:
                path.rmdir()
            except OSError:
                pass
    after = sum(path.stat().st_size for path in _files(root))
    return {'root': str(root), 'before_bytes': before, 'after_bytes': after,
            'saved_bytes': before - after, 'removed_files': removed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('roots', type=Path, nargs='+')
    for root in parser.parse_args().roots:
        print(json.dumps(prune(root)))


if __name__ == '__main__':
    main()
