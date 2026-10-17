"""Private, expiring in-memory jobs and bounded isolated worker processes."""

import secrets
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy

from .config import Settings
from .documents import (
    DocumentSearchError,
    SecuritySearch,
    build_query,
    google_search_url,
    validate_engine,
    validate_file_type,
    validate_full_name,
)
from .engine import validate_username
from .processes import WorkerPool


class CapacityError(Exception):
    pass


class SessionCapacityError(CapacityError):
    pass


class JobManager:
    def __init__(self, settings: Settings, *, runner=None, document_search=None):
        self.settings = settings
        self._lock = threading.RLock()
        self._jobs = {}
        self._pending = {}
        self._owner_turns = {}
        self._dispatch_sequence = 0
        self._active = 0
        self._pool = WorkerPool(settings)
        self._closed = False
        self._executor = ThreadPoolExecutor(
            max_workers=settings.workers, thread_name_prefix="deeper"
        )
        self._runner = runner or self._run_process
        self._document_search = (
            document_search
            if document_search is not None
            else SecuritySearch.from_env()
        )
        self._stop = threading.Event()
        self._maintenance_thread = threading.Thread(
            target=self._maintain, name="deeper-maintenance", daemon=True
        )
        self._maintenance_thread.start()

    def _maintain(self):
        interval = max(
            0.05, min(5, self.settings.retention, self.settings.worker_idle_timeout)
        )
        while not self._stop.wait(interval):
            with self._lock:
                self._expire_locked()
            self._pool.reap_idle()

    def _expire_locked(self):
        cutoff = time.monotonic() - self.settings.retention
        for token, job in list(self._jobs.items()):
            if job.get("finished") is not None and job["finished"] < cutoff:
                del self._jobs[token]

    @property
    def name_search_available(self):
        return self._document_search.available

    def submit(
        self,
        username: str,
        owner: str,
        *,
        mode="username",
        file_type="any",
        engine="brave",
    ) -> str:
        if mode not in ("username", "name"):
            raise ValueError("Escolha um modo de busca válido.")
        file_type = validate_file_type(file_type)
        if mode == "name":
            engine = validate_engine(engine)
        username = (
            validate_full_name(username)
            if mode == "name"
            else validate_username(username)
        )
        with self._lock:
            if self._closed:
                raise CapacityError("Server is shutting down")
            self._expire_locked()
            for token, job in self._jobs.items():
                if (
                    job["owner"] == owner
                    and job["username"] == username
                    and job["mode"] == mode
                    and job["file_type"] == file_type
                    and (mode != "name" or job["engine"] == engine)
                    and job["state"] in ("queued", "running")
                ):
                    return token
                if (
                    job["owner"] == owner
                    and job["username"] == username
                    and job["mode"] == mode
                    and job["file_type"] == file_type
                    and (mode != "name" or job["engine"] == engine)
                    and job["state"] == "done"
                    and self.settings.cache_ttl
                    and time.monotonic() - job["finished"] < self.settings.cache_ttl
                ):
                    job["cache_reused"] = True
                    return token
            outstanding = sum(
                job["owner"] == owner and job["state"] in ("queued", "running")
                for job in self._jobs.values()
            )
            if outstanding >= self.settings.max_jobs_per_session:
                raise SessionCapacityError("Session already has pending searches")
            if len(self._jobs) >= self.settings.max_jobs:
                completed = [
                    (job["finished"], token)
                    for token, job in self._jobs.items()
                    if job.get("finished") is not None
                ]
                if not completed:
                    raise CapacityError("Server queue is full")
                del self._jobs[min(completed)[1]]
            token = secrets.token_urlsafe(24)
            self._jobs[token] = {
                "owner": owner,
                "username": username,
                "mode": mode,
                "file_type": file_type,
                "state": "queued",
                "created": time.monotonic(),
                "started": None,
                "finished": None,
                "checked": 0,
                "total": 1 if mode == "name" else self.settings.top_sites,
                "unknown": 0,
                "profiles": [],
                "profile_events": [],
                "profile_names": set(),
                "reconcile_profiles": False,
                "error": "",
                "cache_reused": False,
            }
            if mode == "name":
                self._jobs[token].update(
                    engine=engine,
                    query=build_query(username, file_type),
                    google_url=google_search_url(username, file_type),
                    references=[],
                )
            self._pending.setdefault(owner, deque()).append(token)
            self._owner_turns.setdefault(owner, 0)
            self._dispatch_locked()
            return token

    def _dispatch_locked(self):
        while (
            not self._closed and self._active < self.settings.workers and self._pending
        ):
            owner = min(self._pending, key=self._owner_turns.__getitem__)
            token = self._pending[owner].popleft()
            if not self._pending[owner]:
                del self._pending[owner]
            self._dispatch_sequence += 1
            self._owner_turns[owner] = self._dispatch_sequence
            self._jobs[token].update(state="running", started=time.monotonic())
            self._active += 1
            self._executor.submit(self._execute, token)

    def _queue_position_locked(self, token):
        if self._jobs[token]["state"] != "queued":
            return 0
        pending = {owner: deque(tokens) for owner, tokens in self._pending.items()}
        owners = deque(sorted(pending, key=self._owner_turns.__getitem__))
        position = 0
        while owners:
            owner = owners.popleft()
            position += 1
            if pending[owner].popleft() == token:
                return position
            if pending[owner]:
                owners.append(owner)
        return 0

    def snapshot(self, token: str, owner: str) -> dict | None:
        with self._lock:
            self._expire_locked()
            job = self._jobs.get(token)
            if job is None or job["owner"] != owner:
                return None
            internal = {
                "owner",
                "profile_events",
                "profile_names",
                "reconcile_profiles",
            }
            if job["mode"] == "username":
                internal.update(("mode", "file_type"))
            snapshot = deepcopy(
                {key: value for key, value in job.items() if key not in internal}
            )
            snapshot["cursor"] = len(job["profile_events"])
            snapshot["queue_position"] = self._queue_position_locked(token)
            reused = snapshot.pop("cache_reused")
            snapshot["cache_age"] = (
                max(0, int(time.monotonic() - job["finished"])) if reused else None
            )
            endpoint = job["finished"] or time.monotonic()
            snapshot["elapsed"] = int(endpoint - (job["started"] or job["created"]))
            return snapshot

    def updates(self, token: str, owner: str, after: int) -> dict | None:
        with self._lock:
            self._expire_locked()
            job = self._jobs.get(token)
            if job is None or job["owner"] != owner:
                return None
            cursor = len(job["profile_events"])
            if after < 0 or after > cursor:
                raise ValueError("Invalid update cursor")
            endpoint = job["finished"] or time.monotonic()
            reconcile = job["reconcile_profiles"]
            updates = {
                "state": job["state"],
                "checked": job["checked"],
                "total": job["total"],
                "unknown": job["unknown"],
                "elapsed": int(endpoint - (job["started"] or job["created"])),
                "cursor": cursor,
                "reconcile": reconcile,
                "queue_position": self._queue_position_locked(token),
                "profiles": deepcopy(
                    job["profiles"] if reconcile else job["profile_events"][after:]
                ),
                "error": job["error"],
            }
            if job["mode"] == "name":
                updates.update(
                    mode="name",
                    engine=job["engine"],
                    file_type=job["file_type"],
                    references=deepcopy(job["references"]),
                )
            return updates

    @staticmethod
    def _index_profiles(job, profiles):
        if not isinstance(profiles, list):
            return []
        limit = job["total"]
        if not isinstance(limit, int) or limit <= 0:
            return []
        added = []
        for profile in profiles:
            if not isinstance(profile, dict) or not isinstance(
                profile.get("name"), str
            ):
                continue
            name = profile["name"]
            if name in job["profile_names"]:
                continue
            if len(job["profile_events"]) >= limit:
                break
            saved = deepcopy(profile)
            job["profile_names"].add(name)
            job["profile_events"].append(saved)
            added.append(saved)
        return added

    def _update(self, token: str, report: dict):
        with self._lock:
            job = self._jobs.get(token)
            if job is None:
                return
            if job["mode"] == "name":
                if report.get("checked") == 1:
                    job["checked"] = 1
                references = report.get("references")
                if isinstance(references, list):
                    job["references"] = deepcopy(references[:10])
                # Only provider-defined public errors may cross this boundary.
                if report.get("state") == "error":
                    job["error"] = DocumentSearchError(
                        report.get("error_code", "failed")
                    ).public_message
                return
            for name in ("checked", "total", "unknown"):
                if name in report:
                    job[name] = deepcopy(report[name])
            if "profiles_delta" in report:
                added = self._index_profiles(job, report["profiles_delta"])
                job["profiles"].extend(deepcopy(added))
            if "profiles" in report:
                job["profiles"] = deepcopy(report["profiles"])
                self._index_profiles(job, report["profiles"])
                job["reconcile_profiles"] = job["profiles"] != job["profile_events"]
            # The worker's message is never allowed to reveal private exceptions.
            if report.get("state") == "error":
                job["error"] = "Não foi possível concluir a busca. Tente novamente."

    def _execute(self, token: str):
        with self._lock:
            job = self._jobs[token]
            username = job["username"]
            owner = job["owner"]
            mode = job["mode"]
            file_type = job["file_type"]
            engine = job.get("engine", "brave")
        state = "error"
        try:

            def emit(event):
                self._update(token, event)

            if mode == "name":
                report = self._document_search.search(
                    username, file_type, emit, engine=engine
                )
            else:
                report = self._runner(username, self.settings, emit)
            self._update(token, report)
            state = report.get("state", "error")
            if state not in ("done", "partial", "error"):
                state = "error"
        except DocumentSearchError as error:
            with self._lock:
                self._jobs[token]["error"] = error.public_message
        except TimeoutError:
            state = "error" if mode == "name" else "partial"
        except Exception:  # noqa: BLE001 - keep private worker details out of responses
            state = "error"
        finally:
            with self._lock:
                if token in self._jobs:
                    self._jobs[token].update(state=state, finished=time.monotonic())
                    if state == "error" and not self._jobs[token]["error"]:
                        self._jobs[token]["error"] = (
                            "Não foi possível concluir a busca. Tente novamente."
                        )
                self._active -= 1
                if not any(
                    job["owner"] == owner and job["state"] in ("queued", "running")
                    for job in self._jobs.values()
                ):
                    self._owner_turns.pop(owner, None)
                self._dispatch_locked()

    def _run_process(self, username, settings, emit):
        return self._pool.run(username, settings, emit)

    def close(self):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            for tokens in self._pending.values():
                for token in tokens:
                    self._jobs[token].update(
                        state="error",
                        finished=time.monotonic(),
                        error="Não foi possível concluir a busca. Tente novamente.",
                    )
            self._pending.clear()
            self._owner_turns.clear()
        self._stop.set()
        self._maintenance_thread.join()
        self._pool.close()
        self._executor.shutdown(wait=True, cancel_futures=True)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
