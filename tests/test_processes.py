"""Exercise actual child processes: reuse, bounded lifetime, timeout and cleanup."""
import importlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
import threading

import pytest

from deeper.config import Settings
from test_engine import synthetic_sites


def pool_type():
    try:
        return importlib.import_module('deeper.processes').WorkerPool
    except ModuleNotFoundError:
        pytest.fail('Reusable WorkerPool is not implemented')


@pytest.fixture
def launch_worker(monkeypatch, tmp_path):
    original = subprocess.Popen
    started = []

    def launch(script):
        path = tmp_path / 'worker.py'
        path.write_text(script, encoding='utf-8')

        def popen(command, **kwargs):
            process = original([sys.executable, '-c', path.read_text()], **kwargs)
            started.append(process)
            return process

        monkeypatch.setattr(subprocess, 'Popen', popen)
        return started

    return launch


def local_worker_script(sites, log_path, *, explicit_headers=True):
    base = sites['Found'].url_main
    header_field = "'headers': {'Original': 'yes'}," if explicit_headers else ''
    expected_headers = "{'Original': 'yes'}" if explicit_headers else '{}'
    return f'''
from pathlib import Path
from maigret.sites import MaigretSite
import deeper.worker as worker
def load(settings):
    with Path({str(log_path)!r}).open('a') as out: out.write('load\\n')
    return {{'Found': MaigretSite('Found', {{'urlMain': {base!r},
        'url': {base!r} + '/found/{{username}}', 'checkType': 'status_code',
        'requestHeadOnly': False, {header_field} 'disabled': False}})}}
worker.load_sites = load
original_search = worker.search_username
async def search(username, settings, emit, *, sites):
    assert sites['Found'].headers == {expected_headers}
    result = await original_search(username, settings, emit, sites=sites)
    sites['Found'].headers['Leaked'] = username
    return result
worker.search_username = search
raise SystemExit(worker.main())
'''


def test_worker_reuses_pid_and_database_but_clones_sites_per_search(launch_worker, synthetic_sites, tmp_path):
    loads = tmp_path / 'loads'
    started = launch_worker(local_worker_script(synthetic_sites, loads))
    with pool_type()(Settings(workers=1)) as pool:
        first = pool.run('first', pool.settings, lambda event: None)
        second = pool.run('second', pool.settings, lambda event: None)
        assert first['state'] == second['state'] == 'done'
        assert first['profiles'][0]['url'].endswith('/first')
        assert second['profiles'][0]['url'].endswith('/second')
        assert len(started) == 1
        assert started[0].poll() is None
        assert loads.read_text().splitlines() == ['load']
    assert started[0].poll() is not None


def test_worker_recycles_after_configured_number_of_queries(launch_worker, synthetic_sites, tmp_path):
    started = launch_worker(local_worker_script(synthetic_sites, tmp_path / 'loads'))
    with pool_type()(Settings(workers=1, worker_max_jobs=2)) as pool:
        for username in ['first', 'second', 'third']:
            assert pool.run(username, pool.settings, lambda event: None)['state'] == 'done'
        assert len(started) == 2
        assert started[0].poll() is not None
        assert started[1].poll() is None
    assert all(p.poll() is not None for p in started)


def test_worker_isolates_mutable_maigret_defaults_without_explicit_headers(launch_worker, synthetic_sites, tmp_path):
    # Maigret's default headers dict is a class attribute. deepcopy(instance)
    # alone leaves it shared, so activation can leak cookies/tokens across jobs.
    launch_worker(local_worker_script(synthetic_sites, tmp_path / 'loads', explicit_headers=False))
    with pool_type()(Settings(workers=1)) as pool:
        assert pool.run('first', pool.settings, lambda event: None)['state'] == 'done'
        assert pool.run('second', pool.settings, lambda event: None)['state'] == 'done'


def test_idle_worker_is_reaped_then_recreated(launch_worker, synthetic_sites, tmp_path):
    started = launch_worker(local_worker_script(synthetic_sites, tmp_path / 'loads'))
    with pool_type()(Settings(workers=1, worker_idle_timeout=0.05)) as pool:
        pool.run('first', pool.settings, lambda event: None)
        time.sleep(0.06)
        pool.reap_idle()
        assert started[0].poll() is not None
        pool.run('second', pool.settings, lambda event: None)
        assert len(started) == 2


def test_worker_eof_preserves_progress_and_next_call_uses_fresh_process(launch_worker):
    started = launch_worker("""
import sys,json
json.loads(sys.stdin.readline())
print(json.dumps(dict(state='running',checked=1,total=2,unknown=0,profiles=[dict(name='Found')])),flush=True)
sys.exit(3)
""")
    with pool_type()(Settings(workers=1)) as pool:
        updates = []
        with pytest.raises(RuntimeError):
            pool.run('first', pool.settings, updates.append)
        assert updates[-1]['profiles'] == [{'name': 'Found'}]
        with pytest.raises(RuntimeError):
            pool.run('second', pool.settings, lambda event: None)
        assert len(started) == 2
        assert all(p.poll() is not None for p in started)


def test_hard_deadline_reaps_hung_child_and_keeps_progress(launch_worker):
    started = launch_worker("""
import sys,json,time
json.loads(sys.stdin.readline())
print(json.dumps(dict(state='running',checked=1,total=2,unknown=0,profiles=[])),flush=True)
time.sleep(60)
""")
    # The extra startup allowance is tested without waiting 15s: replace only
    # its constant. Actual Timer, subprocess, blocking read and kill are real.
    implementation = importlib.import_module('deeper.processes') if importlib.util.find_spec('deeper.processes') else None
    if implementation is None:
        pytest.fail('Reusable WorkerPool is not implemented')
    old = implementation.STARTUP_ALLOWANCE
    implementation.STARTUP_ALLOWANCE = 0.1
    try:
        with pool_type()(Settings(workers=1, search_timeout=0.05)) as pool:
            updates = []
            with pytest.raises(TimeoutError):
                pool.run('synthetic', pool.settings, updates.append)
            assert updates[-1]['checked'] == 1
            assert started[0].poll() is not None
    finally:
        implementation.STARTUP_ALLOWANCE = old


def test_closed_pool_cannot_spawn_a_worker(launch_worker):
    started = launch_worker('raise RuntimeError("Should never run")')
    pool = pool_type()(Settings())
    pool.close()
    with pytest.raises(RuntimeError):
        pool.run('synthetic', pool.settings, lambda event: None)
    assert not started


def test_timer_start_failure_does_not_leave_an_unwatched_worker(launch_worker, monkeypatch):
    started = launch_worker('import time; time.sleep(60)')
    implementation = importlib.import_module('deeper.processes')

    class BrokenTimer:
        def __init__(self, *args, **kwargs):
            pass

        def start(self):
            raise RuntimeError('cannot start new thread')

        def cancel(self):
            pass

        def join(self):
            raise RuntimeError('cannot join thread before it is started')

    monkeypatch.setattr(implementation.threading, 'Timer', BrokenTimer)
    with pool_type()(Settings()) as pool:
        with pytest.raises(RuntimeError, match='cannot start new thread'):
            pool.run('synthetic', pool.settings, lambda event: None)
        assert started[0].poll() is not None


def test_terminal_waits_for_real_maigret_dns_executor_cleanup(launch_worker, synthetic_sites, tmp_path, monkeypatch):
    gate = tmp_path / 'release-dns'
    port = synthetic_sites['Found'].url_main.rsplit(':', 1)[1]
    started = launch_worker(f'''
import socket,time,os
os.environ['NO_PROXY'] = '*'
os.environ['no_proxy'] = '*'
from pathlib import Path
from maigret.sites import MaigretSite
import deeper.worker as worker
original = socket.getaddrinfo
def getaddrinfo(host, *args, **kwargs):
    if host == 'first.invalid':
        while not Path({str(gate)!r}).exists(): time.sleep(0.01)
        host = '127.0.0.1'
    return original(host, *args, **kwargs)
socket.getaddrinfo = getaddrinfo
worker.load_sites = lambda settings: {{'Found': MaigretSite('Found', {{
    'urlMain': 'http://first.invalid:{port}',
    'url': 'http://first.invalid:{port}/found/{{username}}',
    'checkType': 'status_code', 'requestHeadOnly': False, 'disabled': False}})}}
raise SystemExit(worker.main())
''')
    progress = threading.Event()

    def observe(report):
        if report.get('checked') == 1:
            progress.set()

    with pool_type()(Settings(workers=1, site_timeout=0.05, search_timeout=1)) as pool:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(pool.run, 'first', pool.settings, observe)
            try:
                assert progress.wait(3), 'The actual HTTP timeout did not produce progress'
                # A terminal HTTP result is insufficient while DNS still runs.
                with pytest.raises(TimeoutError):
                    future.result(timeout=0.1)
            finally:
                gate.touch()
            assert future.result(timeout=3)['state'] == 'done'
        assert len(started) == 1
        assert pool.run('second', pool.settings, lambda event: None)['state'] == 'done'
        gate.unlink()
        implementation = importlib.import_module('deeper.processes')
        monkeypatch.setattr(implementation, 'STARTUP_ALLOWANCE', 0.1)
        updates = []
        with pytest.raises(TimeoutError):
            pool.run('third', pool.settings, updates.append)
        assert updates[-1]['checked'] == 1 and updates[-1]['unknown'] == 1
        assert updates[-1]['state'] == 'running'
        assert started[0].poll() is not None
        gate.touch()
        assert pool.run('fourth', pool.settings, lambda event: None)['state'] == 'done'
        assert len(started) == 2
