"""Private, expiring in-memory jobs and bounded isolated worker processes."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import secrets
import threading
import time

from .config import Settings
from .engine import validate_username
from .processes import WorkerPool


class CapacityError(Exception):
    pass


class JobManager:
    def __init__(self, settings: Settings, *, runner=None):
        self.settings = settings
        self._lock = threading.RLock()
        self._jobs = {}
        self._pool = WorkerPool(settings)
        self._closed = False
        self._executor = ThreadPoolExecutor(max_workers=settings.workers, thread_name_prefix='deeper')
        self._runner = runner or self._run_process
        self._stop = threading.Event()
        self._maintenance_thread = threading.Thread(
            target=self._maintain, name='deeper-maintenance', daemon=True)
        self._maintenance_thread.start()

    def _maintain(self):
        interval = max(0.05, min(5, self.settings.retention, self.settings.worker_idle_timeout))
        while not self._stop.wait(interval):
            with self._lock:
                self._expire_locked()
            self._pool.reap_idle()

    def _expire_locked(self):
        cutoff = time.monotonic() - self.settings.retention
        for token, job in list(self._jobs.items()):
            if job.get('finished') is not None and job['finished'] < cutoff:
                del self._jobs[token]

    def submit(self, username: str, owner: str) -> str:
        username = validate_username(username)
        with self._lock:
            if self._closed:
                raise CapacityError('Server is shutting down')
            self._expire_locked()
            for token, job in self._jobs.items():
                if (job['owner'] == owner and job['username'] == username
                        and job['state'] in ('queued', 'running')):
                    return token
                if (job['owner'] == owner and job['username'] == username
                        and job['state'] == 'done' and self.settings.cache_ttl
                        and time.monotonic() - job['finished'] < self.settings.cache_ttl):
                    job['cache_reused'] = True
                    return token
            if len(self._jobs) >= self.settings.max_jobs:
                completed = [(job['finished'], token) for token, job in self._jobs.items()
                             if job.get('finished') is not None]
                if not completed:
                    raise CapacityError('Server queue is full')
                del self._jobs[min(completed)[1]]
            token = secrets.token_urlsafe(24)
            self._jobs[token] = {
                'owner': owner, 'username': username, 'state': 'queued',
                'created': time.monotonic(), 'started': None, 'finished': None,
                'checked': 0, 'total': self.settings.top_sites, 'unknown': 0,
                'profiles': [], 'profile_events': [], 'profile_names': set(),
                'error': '', 'cache_reused': False,
            }
            self._executor.submit(self._execute, token)
            return token

    def snapshot(self, token: str, owner: str) -> dict | None:
        with self._lock:
            self._expire_locked()
            job = self._jobs.get(token)
            if job is None or job['owner'] != owner:
                return None
            internal = {'owner', 'profile_events', 'profile_names'}
            snapshot = deepcopy({key: value for key, value in job.items()
                                 if key not in internal})
            snapshot['cursor'] = len(job['profile_events'])
            reused = snapshot.pop('cache_reused')
            snapshot['cache_age'] = (max(0, int(time.monotonic() - job['finished']))
                                     if reused else None)
            endpoint = job['finished'] or time.monotonic()
            snapshot['elapsed'] = int(endpoint - (job['started'] or job['created']))
            return snapshot

    def updates(self, token: str, owner: str, after: int) -> dict | None:
        with self._lock:
            self._expire_locked()
            job = self._jobs.get(token)
            if job is None or job['owner'] != owner:
                return None
            cursor = len(job['profile_events'])
            if after < 0 or after > cursor:
                raise ValueError('Invalid update cursor')
            endpoint = job['finished'] or time.monotonic()
            return {
                'state': job['state'], 'checked': job['checked'],
                'total': job['total'], 'unknown': job['unknown'],
                'elapsed': int(endpoint - (job['started'] or job['created'])),
                'cursor': cursor,
                'profiles': deepcopy(job['profile_events'][after:]),
                'error': job['error'],
            }

    @staticmethod
    def _index_profiles(job, profiles):
        if not isinstance(profiles, list):
            return []
        limit = job['total']
        if not isinstance(limit, int) or limit <= 0:
            return []
        added = []
        for profile in profiles:
            if not isinstance(profile, dict) or not isinstance(profile.get('name'), str):
                continue
            name = profile['name']
            if name in job['profile_names']:
                continue
            if len(job['profile_events']) >= limit:
                break
            saved = deepcopy(profile)
            job['profile_names'].add(name)
            job['profile_events'].append(saved)
            added.append(saved)
        return added

    def _update(self, token: str, report: dict):
        with self._lock:
            job = self._jobs.get(token)
            if job is None:
                return
            for name in ('checked', 'total', 'unknown'):
                if name in report:
                    job[name] = deepcopy(report[name])
            if 'profiles_delta' in report:
                added = self._index_profiles(job, report['profiles_delta'])
                job['profiles'].extend(deepcopy(added))
            if 'profiles' in report:
                job['profiles'] = deepcopy(report['profiles'])
                self._index_profiles(job, report['profiles'])
            # The worker's message is never allowed to reveal private exceptions.
            if report.get('state') == 'error':
                job['error'] = 'Não foi possível concluir a busca. Tente novamente.'

    def _execute(self, token: str):
        with self._lock:
            job = self._jobs[token]
            job.update(state='running', started=time.monotonic())
            username = job['username']
        state = 'error'
        try:
            report = self._runner(username, self.settings, lambda event: self._update(token, event))
            self._update(token, report)
            state = report.get('state', 'error')
            if state not in ('done', 'partial', 'error'):
                state = 'error'
        except TimeoutError:
            state = 'partial'
        except Exception:
            state = 'error'
        finally:
            with self._lock:
                if token in self._jobs:
                    self._jobs[token].update(state=state, finished=time.monotonic())
                    if state == 'error':
                        self._jobs[token]['error'] = 'Não foi possível concluir a busca. Tente novamente.'

    def _run_process(self, username, settings, emit):
        return self._pool.run(username, settings, emit)

    def close(self):
        self._stop.set()
        self._maintenance_thread.join()
        with self._lock:
            self._closed = True
        self._pool.close()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
