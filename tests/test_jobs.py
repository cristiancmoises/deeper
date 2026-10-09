"""Catch result leakage, refresh re-execution, capacity errors and lost partials."""
import threading
import time

import pytest

from deeper.config import Settings


def wait_for_job(manager, token, owner, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        job = manager.snapshot(token, owner)
        if job and job['state'] not in ('queued', 'running'):
            return job
        time.sleep(0.01)
    raise AssertionError('Job did not finish')


def complete_runner(username, settings, emit):
    return {'state': 'done', 'checked': 2, 'total': 2, 'unknown': 1,
        'profiles': [{'name': 'Example', 'url': 'https://example.com/' + username,
                     'tags': [], 'details': [], 'links': [], 'similar': False}]}


def manager_type():
    from deeper.jobs import JobManager
    return JobManager


def test_job_is_private_to_its_owner_and_snapshot_cannot_mutate_store():
    with manager_type()(Settings(), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner-a')
        job = wait_for_job(manager, token, 'owner-a')
        assert job['profiles'][0]['url'] == 'https://example.com/synthetic'
        assert manager.snapshot(token, 'owner-b') is None
        assert 'owner' not in job
        job['profiles'].clear()
        assert len(manager.snapshot(token, 'owner-a')['profiles']) == 1


def test_running_duplicate_and_refresh_do_not_start_more_jobs():
    release = threading.Event()

    def runner(username, settings, emit):
        release.wait(2)
        return complete_runner(username, settings, emit)

    with manager_type()(Settings(workers=1), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner-a')
        assert manager.submit('synthetic', 'owner-a') == token
        assert manager.snapshot(token, 'owner-a')['username'] == 'synthetic'
        release.set()
        assert wait_for_job(manager, token, 'owner-a')['checked'] == 2


def test_full_queue_is_recoverable_and_finished_jobs_free_capacity():
    from deeper.jobs import CapacityError
    release = threading.Event()

    def runner(username, settings, emit):
        release.wait(2)
        return complete_runner(username, settings, emit)

    with manager_type()(Settings(workers=1, max_jobs=1), runner=runner) as manager:
        token = manager.submit('first', 'owner')
        with pytest.raises(CapacityError):
            manager.submit('second', 'owner')
        release.set()
        wait_for_job(manager, token, 'owner')
        second = manager.submit('second', 'owner')
        assert second != token
        assert wait_for_job(manager, second, 'owner')['state'] == 'done'


def test_failure_after_progress_preserves_profiles_and_reports_error():
    def runner(username, settings, emit):
        update = complete_runner(username, settings, emit)
        update['state'] = 'running'
        emit(update)
        raise RuntimeError('Private internal exception')

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner')
        job = wait_for_job(manager, token, 'owner')
        assert job['state'] == 'error'
        assert len(job['profiles']) == 1
        assert 'Private' not in job['error']


def test_hard_timeout_retains_partial_profiles():
    def runner(username, settings, emit):
        update = complete_runner(username, settings, emit)
        update['state'] = 'running'
        emit(update)
        raise TimeoutError()

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner')
        job = wait_for_job(manager, token, 'owner')
        assert job['state'] == 'partial'
        assert len(job['profiles']) == 1


def test_finished_jobs_expire_in_memory(monkeypatch):
    from types import SimpleNamespace
    import deeper.jobs as jobs
    clock = [100.0]
    monkeypatch.setattr(jobs, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    with manager_type()(Settings(retention=15), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        clock[0] += 16
        assert manager.snapshot(token, 'owner') is None
