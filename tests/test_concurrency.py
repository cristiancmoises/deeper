"""Fair admission and scheduling under concurrent anonymous visitors."""

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from test_app import csrf
from test_jobs import complete_runner, wait_for_job

from deeper.app import create_app
from deeper.config import Settings
from deeper.jobs import CapacityError, JobManager


class HeldSearches:
    """Hold only the external search, keeping the actual scheduler and routes."""

    def __init__(self):
        self.condition = threading.Condition()
        self.started = []
        self.released = set()
        self.finished = False
        self.active = 0
        self.peak = 0

    def __call__(self, username, settings, emit):
        with self.condition:
            self.started.append(username)
            self.active += 1
            self.peak = max(self.peak, self.active)
            self.condition.notify_all()
            assert self.condition.wait_for(
                lambda: self.finished or username in self.released, timeout=5
            )
            self.active -= 1
        if username == "fails":
            raise RuntimeError("Private upstream failure")
        return complete_runner(username, settings, emit)

    def wait_started(self, count):
        with self.condition:
            assert self.condition.wait_for(
                lambda: len(self.started) >= count, timeout=3
            )
            return list(self.started)

    def release(self, username):
        with self.condition:
            self.released.add(username)
            self.condition.notify_all()

    def finish(self):
        with self.condition:
            self.finished = True
            self.condition.notify_all()


@contextmanager
def held_manager(settings):
    runner = HeldSearches()
    with JobManager(settings, runner=runner) as manager:
        try:
            yield manager, runner
        finally:
            runner.finish()


def test_session_quota_keeps_other_visitors_admissible_and_recovers():
    with held_manager(Settings(workers=1)) as (manager, runner):
        first = manager.submit("first", "owner-a")
        runner.wait_started(1)
        second = manager.submit("second", "owner-a")
        with pytest.raises(CapacityError) as rejected:
            manager.submit("third", "owner-a")
        assert type(rejected.value).__name__ == "SessionCapacityError"
        assert manager.submit("second", "owner-a") == second
        other = manager.submit("other", "owner-b")
        assert manager.snapshot(other, "owner-b")["state"] == "queued"
        runner.release("first")
        wait_for_job(manager, first, "owner-a")
        assert manager.submit("third", "owner-a") not in (first, second)


def test_least_recently_served_sessions_get_a_turn_and_keep_their_own_fifo():
    with held_manager(Settings(workers=1)) as (manager, runner):
        manager.submit("a_first", "a")
        runner.wait_started(1)
        manager.submit("a_second", "a")
        manager.submit("b_first", "b")
        manager.submit("b_second", "b")
        manager.submit("c_first", "c")
        expected = ["a_first", "b_first", "c_first", "a_second", "b_second"]
        for count, name in enumerate(expected[:-1], start=2):
            runner.release(name)
            assert runner.wait_started(count) == expected[:count]


def test_queue_position_tracks_fair_order_and_is_private():
    with held_manager(Settings(workers=1)) as (manager, runner):
        active = manager.submit("a_first", "a")
        runner.wait_started(1)
        repeat = manager.submit("a_second", "a")
        next_up = manager.submit("b_first", "b")
        third_session = manager.submit("c_first", "c")
        assert manager.snapshot(active, "a")["queue_position"] == 0
        for token, owner, position in (
            (next_up, "b", 1),
            (third_session, "c", 2),
            (repeat, "a", 3),
        ):
            assert manager.snapshot(token, owner)["queue_position"] == position
            assert manager.updates(token, owner, 0)["queue_position"] == position
            assert manager.updates(token, "foreign", 0) is None
        runner.release("a_first")
        runner.wait_started(2)
        assert manager.updates(next_up, "b", 0)["queue_position"] == 0
        assert manager.updates(third_session, "c", 0)["queue_position"] == 1
        runner.release("b_first")
        wait_for_job(manager, next_up, "b")
        assert manager.snapshot(next_up, "b")["queue_position"] == 0


def test_twenty_concurrent_sessions_are_accepted_with_only_two_searches_running():
    with held_manager(Settings(workers=2, max_jobs=64)) as (manager, runner):
        with ThreadPoolExecutor(max_workers=20) as visitors:
            tokens = list(
                visitors.map(
                    lambda index: manager.submit(f"user_{index}", f"owner_{index}"),
                    range(20),
                )
            )
        runner.wait_started(2)
        jobs = [
            manager.snapshot(token, f"owner_{index}")
            for index, token in enumerate(tokens)
        ]
        assert sum(job["state"] == "running" for job in jobs) == 2
        assert sum(job["state"] == "queued" for job in jobs) == 18
        assert sorted(
            job["queue_position"] for job in jobs if job["state"] == "queued"
        ) == list(range(1, 19))
        runner.finish()
        for index, token in enumerate(tokens):
            assert wait_for_job(manager, token, f"owner_{index}")["state"] == "done"
        assert runner.peak == 2


def test_cached_results_and_duplicates_are_reused_at_session_capacity():
    with held_manager(Settings(workers=1)) as (manager, runner):
        cached = manager.submit("cached", "owner")
        runner.release("cached")
        wait_for_job(manager, cached, "owner")
        first = manager.submit("first", "owner")
        second = manager.submit("second", "owner")
        assert manager.submit("cached", "owner") == cached
        assert manager.submit("first", "owner") == first
        assert manager.submit("second", "owner") == second
        assert runner.started.count("cached") == 1


def test_failed_search_releases_its_slot_to_the_next_visitor():
    with held_manager(Settings(workers=1)) as (manager, runner):
        failed = manager.submit("fails", "a")
        runner.wait_started(1)
        following = manager.submit("following", "b")
        runner.release("fails")
        assert runner.wait_started(2) == ["fails", "following"]
        result = wait_for_job(manager, failed, "a")
        assert result["state"] == "error"
        assert "Private" not in result["error"]
        assert manager.snapshot(following, "b")["state"] == "running"


def test_shutdown_cancels_waiting_jobs_without_starting_them():
    with held_manager(Settings(workers=1)) as (manager, runner):
        manager.submit("active", "a")
        runner.wait_started(1)
        pending = manager.submit("pending", "b")
        closing = threading.Thread(target=manager.close)
        closing.start()
        try:
            deadline = time.monotonic() + 2
            while (
                manager.snapshot(pending, "b")["state"] == "queued"
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            assert manager.snapshot(pending, "b")["state"] == "error"
            with pytest.raises(CapacityError):
                manager.submit("later", "c")
        finally:
            runner.finish()
            closing.join(3)
        assert not closing.is_alive()
        assert runner.started == ["active"]


@pytest.mark.parametrize("limit", [0, -1, 1.5, float("inf")])
def test_session_quota_configuration_rejects_invalid_limits(limit):
    with pytest.raises(ValueError):
        Settings(max_jobs_per_session=limit)


def test_session_quota_is_configurable_from_environment(monkeypatch):
    monkeypatch.setenv("DEEPER_MAX_JOBS_PER_SESSION", "1")
    with held_manager(Settings.from_env()) as (manager, _):
        token = manager.submit("first", "a")
        assert manager.submit("first", "a") == token
        with pytest.raises(CapacityError):
            manager.submit("second", "a")


def test_http_session_capacity_is_429_and_other_visitors_can_still_submit():
    settings = Settings(workers=1, secret_key="concurrency-test")
    with held_manager(settings) as (manager, _):
        app = create_app(settings, manager)
        client = app.test_client()
        csrf_token = csrf(client)
        first = client.post(
            "/search", data={"username": "first", "csrf_token": csrf_token}
        )
        second = client.post(
            "/search", data={"username": "second", "csrf_token": csrf_token}
        )
        denied = client.post(
            "/search", data={"username": "third", "csrf_token": csrf_token}
        )
        assert first.status_code == second.status_code == 303
        assert denied.status_code == 429
        assert denied.headers["Retry-After"] == "5"
        other = app.test_client()
        accepted = other.post(
            "/search", data={"username": "other", "csrf_token": csrf(other)}
        )
        assert accepted.status_code == 303
        assert other.get(first.headers["Location"] + "/updates").status_code == 404


def test_http_true_global_capacity_is_503_but_duplicate_is_still_available():
    settings = Settings(workers=1, max_jobs=2, secret_key="concurrency-test")
    with held_manager(settings) as (manager, _):
        app = create_app(settings, manager)
        client = app.test_client()
        csrf_token = csrf(client)
        first = client.post(
            "/search", data={"username": "first", "csrf_token": csrf_token}
        )
        client.post("/search", data={"username": "second", "csrf_token": csrf_token})
        other = app.test_client()
        denied = other.post(
            "/search", data={"username": "other", "csrf_token": csrf(other)}
        )
        assert denied.status_code == 503
        assert denied.headers["Retry-After"] == "5"
        duplicate = client.post(
            "/search", data={"username": "first", "csrf_token": csrf_token}
        )
        assert duplicate.headers["Location"] == first.headers["Location"]
