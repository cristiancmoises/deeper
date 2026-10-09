"""Runtime pruning must be limited to audited auxiliaries and keep licenses."""
from pathlib import Path


def test_slim_runtime_removes_auxiliaries_and_preserves_engine_data_and_licenses(tmp_path):
    from scripts.slim_runtime import prune
    retained = [
        'maigret/checking.py', 'maigret/resources/data.json',
        'pycountry/databases/iso3166-1.json', 'pycountry/__init__.py',
        'aiohttp/client.py', 'curl_cffi/_wrapper.abi3.so',
        'maigret-0.6.6.dist-info/licenses/LICENSE',
        'pip-1.dist-info/licenses/LICENSE', 'example/tests/LICENSE',
    ]
    removed = [
        'maigret/__pycache__/checking.cpython-312.pyc',
        'example/tests/test_aux.py', 'pycountry/locales/pt/LC_MESSAGES/iso.mo',
        'pip/__init__.py', 'setuptools/__init__.py', 'wheel/cli.py',
        '_distutils_hack/__init__.py', 'pkg_resources/__init__.py',
    ]
    for name in retained + removed:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'Keep or remove exactly this file')
    result = prune(tmp_path)
    assert result['after_bytes'] < result['before_bytes']
    assert result['removed_files'] == len(removed)
    assert all((tmp_path / name).read_bytes() for name in retained)
    assert all(not (tmp_path / name).exists() for name in removed)
    assert prune(tmp_path)['removed_files'] == 0


def test_runtime_pruning_does_not_follow_symlinks_outside_its_root(tmp_path):
    from scripts.slim_runtime import prune
    runtime = tmp_path / 'runtime'
    runtime.mkdir()
    external = tmp_path / 'external'
    external.mkdir()
    protected = external / 'test_private.py'
    protected.write_text('never delete outside runtime')
    (runtime / 'tests').symlink_to(external, target_is_directory=True)
    prune(runtime)
    assert protected.read_text() == 'never delete outside runtime'
