"""Cache must save work without leaking profiles or hiding stale/error results."""
import json
import time

import pytest
from test_jobs import complete_runner, manager_type, wait_for_job

from deeper.config import Settings


def test_completed_search_reuses_same_session_job_without_running_again():
    calls = []

    def runner(username, settings, emit):
        calls.append(username)
        return complete_runner(username, settings, emit)

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner-a')
        wait_for_job(manager, token, 'owner-a')
        assert manager.submit('synthetic', 'owner-a') == token
        assert manager.snapshot(token, 'owner-a')['cache_age'] >= 0
        assert calls == ['synthetic']
        other = manager.submit('synthetic', 'owner-b')
        assert other != token
        wait_for_job(manager, other, 'owner-b')
        assert len(calls) == 2
        assert manager.snapshot(token, 'owner-b') is None


def test_cache_can_be_disabled():
    with manager_type()(Settings(cache_ttl=0), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        next_token = manager.submit('synthetic', 'owner')
        assert next_token != token
        assert wait_for_job(manager, next_token, 'owner')['cache_age'] is None


def test_expired_cache_runs_fresh_search(monkeypatch):
    from types import SimpleNamespace

    from deeper import jobs
    clock = [100.0]
    monkeypatch.setattr(jobs, 'time', SimpleNamespace(monotonic=lambda: clock[0]))
    with manager_type()(Settings(cache_ttl=60), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        clock[0] += 61
        next_token = manager.submit('synthetic', 'owner')
        assert next_token != token
        assert wait_for_job(manager, next_token, 'owner')['state'] == 'done'


@pytest.mark.parametrize('state', ['partial', 'error'])
def test_incomplete_search_is_not_cached(state):
    def runner(username, settings, emit):
        return dict(complete_runner(username, settings, emit), state=state)

    with manager_type()(Settings(), runner=runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        next_token = manager.submit('synthetic', 'owner')
        assert next_token != token
        wait_for_job(manager, next_token, 'owner')


def test_completed_jobs_are_removed_from_ram_even_without_page_visits():
    with manager_type()(Settings(retention=0.08), runner=complete_runner) as manager:
        token = manager.submit('synthetic', 'owner')
        wait_for_job(manager, token, 'owner')
        # snapshot() would clean lazily; inspect RAM without triggering cleanup.
        deadline = time.monotonic() + 1
        while token in manager._jobs and time.monotonic() < deadline:
            time.sleep(0.02)
        assert token not in manager._jobs


@pytest.mark.parametrize('values', [
    {'cache_ttl': -1}, {'cache_ttl': float('nan')},
    {'worker_max_jobs': 0}, {'worker_max_jobs': 1.5},
    {'worker_idle_timeout': 0}, {'worker_idle_timeout': float('inf')},
])
def test_invalid_performance_limits_are_rejected(values):
    with pytest.raises(ValueError):
        Settings(**values)


def test_performance_settings_read_from_environment(monkeypatch):
    monkeypatch.setenv('DEEPER_CACHE_TTL', '0')
    monkeypatch.setenv('DEEPER_WORKER_MAX_JOBS', '3')
    monkeypatch.setenv('DEEPER_WORKER_IDLE_TIMEOUT', '45')
    settings = Settings.from_env()
    assert settings.cache_ttl == 0
    assert settings.worker_max_jobs == 3
    assert settings.worker_idle_timeout == 45


def test_progress_delta_payloads_are_smaller_than_cumulative_snapshots(monkeypatch):
    from types import SimpleNamespace

    from maigret.result import MaigretCheckResult, MaigretCheckStatus

    import deeper.engine as implementation

    clock = iter(float(index) for index in range(1, 21))
    # Make every synthetic update observable while leaving unrelated clocks real.
    monkeypatch.setattr(implementation, 'time', SimpleNamespace(monotonic=lambda: next(clock)))
    events = []
    progress = implementation._Progress(20, events.append)
    cumulative = []
    for index in range(20):
        result = MaigretCheckResult('synthetic', f'Site {index}',
            f'https://example.com/{index}', MaigretCheckStatus.CLAIMED,
            ids_data={'bio': 'A representative profile description.' * 4})
        progress.update(result)
        snapshot = progress.snapshot()
        cumulative.append({'state': 'running', 'checked': index + 1,
            'total': 20, 'unknown': 0, 'profiles': snapshot['profiles']})

    assert len(events) == len(cumulative)
    assert all('profiles_delta' in event and 'profiles' not in event for event in events)
    delta_bytes = sum(len((json.dumps(event, ensure_ascii=False) + '\n').encode())
                      for event in events)
    cumulative_bytes = sum(len((json.dumps(event, ensure_ascii=False) + '\n').encode())
                           for event in cumulative)
    assert delta_bytes < cumulative_bytes
