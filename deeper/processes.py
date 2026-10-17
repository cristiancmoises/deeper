"""Bounded, reusable Maigret subprocesses; no persistent search data."""
from dataclasses import asdict, dataclass
import json
import os
import subprocess
import sys
import threading
import time

from .config import Settings

STARTUP_ALLOWANCE = 15


@dataclass(eq=False)
class _Worker:
    process: subprocess.Popen
    jobs: int = 0
    idle_since: float = 0


def _kill(process):
    if process.poll() is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass


class WorkerPool:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self._slots = threading.BoundedSemaphore(settings.workers)
        self._all = set()
        self._idle = []
        self._closed = False

    def _take(self):
        with self._lock:
            if self._closed:
                raise RuntimeError('Worker pool is closed')
            if self._idle:
                return self._idle.pop()
            worker_env = os.environ.copy()
            worker_env.pop('SERPER_API_KEY', None)
            process = subprocess.Popen(
                [sys.executable, '-m', 'deeper.worker'], stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, encoding='utf-8', bufsize=1, env=worker_env,
            )
            worker = _Worker(process)
            self._all.add(worker)
            return worker

    def _dispose(self, worker):
        _kill(worker.process)
        worker.process.wait()
        worker.process.stdin.close()
        worker.process.stdout.close()
        with self._lock:
            self._all.discard(worker)

    def run(self, username, settings, emit):
        self.reap_idle()
        with self._slots:
            worker = self._take()
            process = worker.process
            deadline_hit = threading.Event()
            guard = threading.Lock()
            active = True

            def stop_at_deadline():
                # Serialize against release: a late timer cannot kill the next job.
                with guard:
                    if active and process.poll() is None:
                        deadline_hit.set()
                        _kill(process)

            deadline = threading.Timer(settings.search_timeout + STARTUP_ALLOWANCE, stop_at_deadline)
            deadline.daemon = True
            timer_started = False
            reusable = False
            try:
                values = {key: value for key, value in asdict(settings).items()
                          if key not in ('secret_key', 'secure_cookie')}
                deadline.start()
                timer_started = True
                process.stdin.write(json.dumps({'username': username, 'settings': values}) + '\n')
                process.stdin.flush()
                for line in process.stdout:
                    report = json.loads(line)
                    if not isinstance(report, dict):
                        raise ValueError('Invalid worker event')
                    emit(report)
                    if report.get('state') in ('done', 'partial', 'error'):
                        reusable = report['state'] != 'error'
                        return report
                if deadline_hit.is_set():
                    raise TimeoutError()
                raise RuntimeError('Worker exited before completing the search')
            finally:
                with guard:
                    active = False
                deadline.cancel()
                if timer_started:
                    deadline.join()
                worker.jobs += 1
                with self._lock:
                    keep = (reusable and not deadline_hit.is_set() and not self._closed
                            and process.poll() is None
                            and worker.jobs < self.settings.worker_max_jobs)
                    if keep:
                        worker.idle_since = time.monotonic()
                        self._idle.append(worker)
                if not keep:
                    self._dispose(worker)

    def reap_idle(self):
        with self._lock:
            cutoff = time.monotonic() - self.settings.worker_idle_timeout
            expired = [worker for worker in self._idle
                       if worker.idle_since <= cutoff or worker.process.poll() is not None]
            self._idle = [worker for worker in self._idle if worker not in expired]
        for worker in expired:
            self._dispose(worker)

    def close(self):
        with self._lock:
            self._closed = True
            workers = list(self._all)
            idle, self._idle = self._idle, []
        for worker in workers:
            _kill(worker.process)
        for worker in workers:
            worker.process.wait()
        for worker in idle:
            self._dispose(worker)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
