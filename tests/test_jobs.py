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


def test_updates_return_only_new_profiles_and_are_private():
    first = {'name': 'First', 'url': 'https://example.com/first', 'tags': [],
             'details': [], 'links': [], 'similar': False}
    second = {'name': 'Second', 'url': 'https://example.com/second', 'tags': [],
              'details': [], 'links': [], 'similar': False}
    first_sent = threading.Event()
    release_second = threading.Event()
    second_sent = threading.Event()

    def runner(username, settings, emit):
        emit({'state': 'running', 'checked': 1, 'total': 2, 'unknown': 0,
              'profiles_delta': [first]})
        first_sent.set()
        assert release_second.wait(2)
        emit({'state': 'running', 'checked': 2, 'total': 2, 'unknown': 0,
              'profiles_delta': [second]})
        second_sent.set()
        return {'state': 'done', 'checked': 2, 'total': 2, 'unknown': 0,
                'profiles': [first, second]}

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner-a')
        try:
            assert first_sent.wait(2)
            first_page = manager.updates(token, 'owner-a', 0)
            assert first_page is not None
            assert first_page['cursor'] == 1
            assert first_page['profiles'] == [first]
            assert manager.updates(token, 'owner-b', 0) is None
            release_second.set()
            assert second_sent.wait(2)
            second_page = manager.updates(token, 'owner-a', 1)
            assert second_page is not None
            assert second_page['cursor'] == 2
            assert second_page['profiles'] == [second]
        finally:
            release_second.set()


def test_final_report_reconciles_without_duplicate_events():
    first = {'name': 'First', 'url': 'https://example.com/first', 'tags': [],
             'details': [], 'links': [], 'similar': False}
    second = {'name': 'Second', 'url': 'https://example.com/second', 'tags': [],
              'details': [], 'links': [], 'similar': False}

    def runner(username, settings, emit):
        emit({'state': 'running', 'checked': 1, 'total': 2, 'unknown': 0,
              'profiles_delta': [first]})
        return {'state': 'done', 'checked': 2, 'total': 2, 'unknown': 0,
                'profiles': [first, second]}

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner')
        job = wait_for_job(manager, token, 'owner')
        updates = manager.updates(token, 'owner', 0)
        assert updates is not None
        assert job['profiles'] == [first, second]
        assert updates['cursor'] == 2
        assert updates['profiles'] == [first, second]


def test_authoritative_final_profiles_replace_stale_progress_events():
    stale = {'name': 'First', 'url': 'https://example.com/old', 'tags': [],
             'details': [], 'links': [], 'similar': False}
    removed = {'name': 'Removed', 'url': 'https://example.com/removed', 'tags': [],
               'details': [], 'links': [], 'similar': False}
    corrected = {'name': 'First', 'url': 'https://example.com/current', 'tags': [],
                 'details': [], 'links': [], 'similar': False}

    def runner(username, settings, emit):
        emit({'state': 'running', 'checked': 2, 'total': 3, 'unknown': 0,
              'profiles_delta': [stale, removed]})
        return {'state': 'done', 'checked': 3, 'total': 3, 'unknown': 0,
                'profiles': [corrected]}

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner')
        job = wait_for_job(manager, token, 'owner')
        updates = manager.updates(token, 'owner', 2)

        assert job['profiles'] == [corrected]
        assert updates is not None
        assert updates['reconcile'] is True
        assert updates['profiles'] == [corrected]


def test_snapshot_exposes_cursor_not_internal_event_storage():
    with manager_type()(Settings(), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        job = wait_for_job(manager, token, 'owner')
        assert job['cursor'] == 1
        assert len(job['profiles']) == 1
        assert 'profile_events' not in job
        assert 'profile_names' not in job


@pytest.mark.parametrize('after', [-1, 2])
def test_updates_reject_negative_or_future_cursors(after):
    with manager_type()(Settings(), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        with pytest.raises(ValueError):
            manager.updates(token, 'owner', after)


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

    from deeper import jobs
    clock = [100.0]
    monkeypatch.setattr(jobs, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    with manager_type()(Settings(retention=15), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        clock[0] += 16
        assert manager.snapshot(token, 'owner') is None
