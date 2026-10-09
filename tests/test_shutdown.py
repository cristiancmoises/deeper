"""A normal Unix stop must reap an actual child process, not just the server."""
import http.cookiejar
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup
import pytest


@pytest.mark.skipif(os.name == 'nt', reason='Unix SIGTERM lifecycle')
def test_sigterm_stops_and_reaps_active_worker(tmp_path):
    pid_path = tmp_path / 'worker.pid'
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1', 0))
        port = reservation.getsockname()[1]
    # Replace only the external worker command with a benign sleeping process.
    # Keep the real process controller, Flask app, Waitress and CLI lifecycle.
    script = f'''
import subprocess,sys
from pathlib import Path
import deeper.__main__ as cli
from deeper.app import create_app
from deeper.config import Settings
from deeper.jobs import JobManager
original_popen = subprocess.Popen
def sleeping_worker(*args, **kwargs):
    child = original_popen([sys.executable, '-c',
        "import sys,time,json;sys.stdin.read();print(json.dumps(dict(state='running',checked=0,total=1,unknown=0,profiles=[])),flush=True);time.sleep(60)"], **kwargs)
    temporary_pid = Path({str(pid_path)!r} + '.tmp')
    temporary_pid.write_text(str(child.pid))
    temporary_pid.replace({str(pid_path)!r})
    return child
subprocess.Popen = sleeping_worker
settings = Settings(secret_key='test',search_timeout=60)
manager = JobManager(settings)
app = create_app(settings,manager)
cli.create_app = lambda: app
sys.argv = ['deeper','--host','127.0.0.1','--port',{str(port)!r}]
cli.main()
'''
    server = subprocess.Popen([sys.executable, '-c', script], stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    base = f'http://127.0.0.1:{port}'
    worker_pid = None
    try:
        until = time.monotonic() + 8
        while True:
            try:
                with opener.open(base, timeout=0.5) as response:
                    page = BeautifulSoup(response.read(), 'html.parser')
                break
            except OSError:
                if time.monotonic() > until:
                    raise AssertionError('Server did not start')
                time.sleep(0.02)
        form = urllib.parse.urlencode({'username': 'synthetic_profile',
                    'csrf_token': page.select_one('input[name="csrf_token"]')['value']}).encode()
        with opener.open(base + '/search', data=form, timeout=2):
            pass
        until = time.monotonic() + 3
        while not pid_path.exists():
            assert time.monotonic() < until
            time.sleep(0.01)
        worker_pid = int(pid_path.read_text())
        server.send_signal(signal.SIGTERM)
        assert server.wait(timeout=5) == 0
        with pytest.raises(ProcessLookupError):
            os.kill(worker_pid, 0)
    finally:
        if server.poll() is None:
            server.kill()
        server.wait()
        if worker_pid is None and pid_path.exists():
            text = pid_path.read_text().strip()
            worker_pid = int(text) if text else None
        if worker_pid is not None:
            try:
                os.kill(worker_pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
