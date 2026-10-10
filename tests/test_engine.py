"""These tests catch lost matches, unsafe links and false 'absent' results."""
import asyncio
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from maigret.result import MaigretCheckResult, MaigretCheckStatus
from maigret.sites import MaigretSite


def engine():
    # Import inside a test so RED fails on the missing product, not collection.
    from deeper import engine as implementation
    return implementation


@pytest.mark.parametrize('source,want', [
    (' @synthetic_user ', 'synthetic_user'), ('jörg', 'jörg'),
    ('test-user.24', 'test-user.24'),
])
def test_username_normalizes_only_outer_whitespace_and_at(source, want):
    assert engine().validate_username(source) == want


@pytest.mark.parametrize('source', ['', 'two names', '../../passwd',
    'https://example.com/a', 'x\nother', 'a' * 65, '.', '--', '<script>'])
def test_invalid_username_is_rejected(source):
    with pytest.raises(ValueError):
        engine().validate_username(source)


@pytest.mark.parametrize('url', ['javascript:alert(1)', 'data:text/html,x',
    'https://user:password@example.com/', 'https:///missing',
    '//example.com', 'https://example.com/\nheader', 'file:///etc/passwd'])
def test_unsafe_links_are_never_clickable(url):
    assert engine().safe_url(url) is None


def test_only_claimed_results_become_profiles_with_real_extracted_fields():
    found = MaigretCheckResult('synthetic', 'Example', 'https://example.com/u/synthetic',
        MaigretCheckStatus.CLAIMED, ids_data={'fullname': 'Example User',
        'bio': '<b>Biography</b>', 'website': 'https://example.org/',
        'links': ['https://example.net/', 'javascript:alert(1)']}, tags=['social'])
    profile = engine().normalize_result(found)
    assert profile['url'] == 'https://example.com/u/synthetic'
    assert {'label': 'Nome', 'value': 'Example User'} in profile['details']
    assert {'label': 'Bio', 'value': '<b>Biography</b>'} in profile['details']
    assert profile['links'] == ['https://example.net/', 'https://example.org/']
    assert profile['tags'] == ['social']
    for status in [MaigretCheckStatus.AVAILABLE, MaigretCheckStatus.UNKNOWN]:
        found.status = status
        assert engine().normalize_result(found) is None


@pytest.fixture
def synthetic_sites():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/found/'):
                self.send_response(200)
                body = b'<html><h1>synthetic_profile</h1></html>'
            elif self.path.startswith('/absent/'):
                self.send_response(404)
                body = b'No profile'
            else:
                self.send_response(503)
                body = b'Temporarily unavailable'
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    sites = {name: MaigretSite(name, {'urlMain': base, 'url': base + route + '/{username}',
        'checkType': 'status_code', 'requestHeadOnly': False, 'tags': ['test'],
        'disabled': False}) for name, route in [('Found', '/found'), ('Absent', '/absent'), ('Unavailable', '/error')]}
    yield sites
    server.shutdown()
    server.server_close()
    thread.join()


def test_real_maigret_distinguishes_local_found_absent_and_inconclusive(synthetic_sites):
    from deeper.config import Settings
    updates = []
    result = asyncio.run(engine().search_username('synthetic_profile', Settings(
        site_timeout=2, search_timeout=10), updates.append, sites=synthetic_sites))
    assert result['state'] == 'done'
    assert result['checked'] == 3
    assert result['total'] == 3
    assert result['unknown'] == 1
    assert [p['name'] for p in result['profiles']] == ['Found']
    assert result['profiles'][0]['url'].endswith('/found/synthetic_profile')
    assert any(update['checked'] > 0 for update in updates)


def test_bundled_database_loads_without_home_configuration():
    from deeper.config import Settings
    sites = engine().load_sites(Settings(top_sites=10))
    assert len(sites) == 10
    assert all(not s.disabled for s in sites.values())


def test_source_site_is_counted_once_in_progress_and_final_report(synthetic_sites):
    from deeper.config import Settings
    found = synthetic_sites['Found']
    found.source = 'Synthetic parent'
    assert found.pretty_name != 'Found'
    result = asyncio.run(engine().search_username('synthetic_profile',
        Settings(site_timeout=2, search_timeout=10), lambda event: None,
        sites={'Found': found}))
    assert result['total'] == 1
    assert result['checked'] == 1
    assert len(result['profiles']) == 1


def test_progress_snapshots_do_not_repeat_profile_normalization(monkeypatch):
    implementation = engine()
    original = implementation.normalize_result
    normalized = []

    def normalize(result, similar=False):
        normalized.append(result.site_name)
        return original(result, similar)

    monkeypatch.setattr(implementation, 'normalize_result', normalize)
    progress = implementation._Progress(1, lambda event: None)
    result = MaigretCheckResult('synthetic', 'Example', 'https://example.com/synthetic',
                               MaigretCheckStatus.CLAIMED, ids_data={'bio': 'Test'})
    progress.update(result)
    before = len(normalized)
    for _ in range(10):
        assert progress.snapshot()['profiles'][0]['details'][0]['value'] == 'Test'
    assert len(normalized) == before
    result.status = MaigretCheckStatus.UNKNOWN
    progress.update(result)
    assert progress.snapshot()['profiles'] == []
    assert progress.snapshot()['unknown'] == 1


def test_progress_reports_new_profiles_as_deltas_and_final_profiles_as_full_list(monkeypatch):
    from types import SimpleNamespace

    from deeper.config import Settings

    implementation = engine()
    clock = iter([1.0, 2.0])
    monkeypatch.setattr(implementation, 'time', SimpleNamespace(monotonic=lambda: next(clock)))
    first = MaigretCheckResult('synthetic', 'Zulu', 'https://example.com/zulu',
        MaigretCheckStatus.CLAIMED, ids_data={'fullname': 'Zulu User'})
    second = MaigretCheckResult('synthetic', 'Alpha', 'https://example.com/alpha',
        MaigretCheckStatus.CLAIMED, ids_data={'fullname': 'Alpha User'})

    async def search(**kwargs):
        kwargs['query_notify'].update(first)
        kwargs['query_notify'].update(second)

    monkeypatch.setattr('maigret.search', search)
    events = []
    report = asyncio.run(implementation.search_username(
        'synthetic', Settings(), events.append, sites={'Zulu': object(), 'Alpha': object()}))

    running = [event for event in events if event['state'] == 'running']
    assert len(running) == 3
    assert running[0]['profiles_delta'] == []
    assert [event['profiles_delta'][0]['name'] for event in running[1:]] == ['Zulu', 'Alpha']
    assert all('profiles' not in event for event in running)
    assert [profile['name'] for profile in report['profiles']] == ['Alpha', 'Zulu']
    assert events[-1]['profiles'] == report['profiles']
