"""Native form and rendered page contracts, not framework internals."""
from bs4 import BeautifulSoup
import pytest

from deeper.config import Settings
from test_jobs import complete_runner, wait_for_job


@pytest.fixture
def app_bundle():
    from deeper.app import create_app
    from deeper.jobs import JobManager
    settings = Settings(secret_key='test-key-is-only-for-tests')
    with JobManager(settings, runner=complete_runner) as manager:
        app = create_app(settings, manager)
        app.config['TESTING'] = True
        yield app, manager


def csrf(client):
    page = BeautifulSoup(client.get('/').data, 'html.parser')
    return page.select_one('input[name="csrf_token"]')['value']


def test_initial_surface_is_just_title_and_native_search(app_bundle):
    app, _ = app_bundle
    response = app.test_client().get('/')
    page = BeautifulSoup(response.data, 'html.parser')
    assert page.h1.get_text(strip=True) == 'Deeper'
    assert page.select_one('form')['method'].lower() == 'post'
    assert page.select_one('input[type="search"]')['name'] == 'username'
    assert len(page.select('button[type="submit"]')) == 1
    assert not page.select('nav, footer, script, .results')
    assert "script-src 'none'" in response.headers['Content-Security-Policy']
    for element in page.find_all():
        assert not any(key.lower().startswith('on') for key in element.attrs)


def test_enter_form_redirects_to_results_and_does_not_reload_when_finished(app_bundle):
    app, manager = app_bundle
    client = app.test_client()
    response = client.post('/search', data={'username': '@synthetic', 'csrf_token': csrf(client)})
    assert response.status_code == 303
    location = response.headers['Location']
    token = location.rsplit('/', 1)[1]
    with client.session_transaction() as session:
        owner = session['owner']
    wait_for_job(manager, token, owner)
    results = BeautifulSoup(client.get(location).data, 'html.parser')
    assert results.select_one('.profile-link')['href'] == 'https://example.com/synthetic'
    assert results.select_one('input[name="username"]')['value'] == 'synthetic'
    assert not results.select('meta[http-equiv="refresh"]')
    assert 'inconclusiva' in results.get_text()
    assert app.test_client().get(location).status_code == 404


@pytest.mark.parametrize('data', [{'username': 'test'}, {'username': 'test', 'csrf_token': 'invalid'}])
def test_csrf_is_required(app_bundle, data):
    app, _ = app_bundle
    client = app.test_client()
    client.get('/')
    assert client.post('/search', data=data).status_code == 400


def test_invalid_input_returns_feedback_without_starting_a_search(app_bundle):
    app, _ = app_bundle
    client = app.test_client()
    response = client.post('/search', data={'username': '<script>alert(1)</script>', 'csrf_token': csrf(client)})
    assert response.status_code == 422
    assert b'<script>' not in response.data
    page = BeautifulSoup(response.data, 'html.parser')
    assert page.select_one('[role="alert"]') is not None


def test_pending_job_refreshes_native_html_without_javascript():
    import threading
    from deeper.app import create_app
    from deeper.jobs import JobManager
    release = threading.Event()

    def runner(username, settings, emit):
        release.wait(2)
        return complete_runner(username, settings, emit)

    settings = Settings(secret_key='test')
    with JobManager(settings, runner=runner) as manager:
        app = create_app(settings, manager)
        client = app.test_client()
        response = client.post('/search', data={'username': 'synthetic', 'csrf_token': csrf(client)})
        page = BeautifulSoup(client.get(response.headers['Location']).data, 'html.parser')
        assert page.select_one('meta[http-equiv="refresh"]')['content'] == '3'
        assert page.select_one('a.refresh-link') is not None
        assert page.select_one('.results')['aria-busy'] == 'true'
        release.set()


def test_external_html_is_escaped_and_unsafe_links_are_removed():
    from deeper.app import create_app
    from deeper.jobs import JobManager
    def runner(username, settings, emit):
        result = complete_runner(username, settings, emit)
        profile = result['profiles'][0]
        profile['name'] = '<img src=x onerror=alert(1)>'
        profile['url'] = 'javascript:alert(1)'
        profile['details'] = [{'label': 'Bio', 'value': '<script>evil()</script>'}]
        profile['links'] = ['data:text/html,evil', 'https://example.org/']
        return result
    settings = Settings(secret_key='test')
    with JobManager(settings, runner=runner) as manager:
        app = create_app(settings, manager)
        client = app.test_client()
        response = client.post('/search', data={'username': 'synthetic', 'csrf_token': csrf(client)})
        with client.session_transaction() as session:
            owner = session['owner']
        wait_for_job(manager, response.headers['Location'].rsplit('/', 1)[1], owner)
        page = BeautifulSoup(client.get(response.headers['Location']).data, 'html.parser')
        assert not page.select('script, img')
        assert all(not anchor.get('href', '').startswith(('javascript:', 'data:')) for anchor in page.select('a'))
        assert '<script>evil()</script>' in page.get_text()


def test_reused_results_show_age_without_adding_ui_to_home():
    from deeper.app import create_app
    from deeper.config import Settings
    from deeper.jobs import JobManager
    from test_jobs import complete_runner, wait_for_job
    from bs4 import BeautifulSoup
    with JobManager(Settings(), runner=complete_runner) as manager:
        app = create_app(Settings(secret_key='test'), manager)
        client = app.test_client()
        home = BeautifulSoup(client.get('/').data, 'html.parser')
        csrf = home.select_one('input[name="csrf_token"]')['value']
        first = client.post('/search', data={'username': 'synthetic', 'csrf_token': csrf})
        token = first.headers['Location'].rsplit('/', 1)[-1]
        with client.session_transaction() as session:
            owner = session['owner']
        wait_for_job(manager, token, owner)
        second = client.post('/search', data={'username': 'synthetic', 'csrf_token': csrf})
        assert first.headers['Location'] == second.headers['Location']
        assert 'Resultados reutilizados desta sessão' in client.get(second.headers['Location']).text
        assert 'Resultados reutilizados' not in client.get('/').text

