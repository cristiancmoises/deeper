"""Run visual/native-form QA; Playwright is a test tool, never a page script."""
import argparse
import asyncio
import json
import sys
import threading
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maigret.sites import MaigretSite
from playwright.sync_api import sync_playwright
from test_engine import synthetic_sites
from waitress import create_server

from deeper.app import create_app
from deeper.config import Settings
from deeper.engine import search_username
from deeper.jobs import JobManager


@contextmanager
def progressive_sites():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith('/fast/'):
                self.send_response(200)
                body = b'<html><h1>progressive_user</h1></html>'
            else:
                time.sleep(4)
                self.send_response(503)
                body = b'Synthetic delayed site'
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    sites = {name: MaigretSite(name, {
        'urlMain': base, 'url': f'{base}/{path}/{{username}}',
        'checkType': 'status_code', 'requestHeadOnly': False,
        'disabled': False, 'tags': ['synthetic'],
    }) for name, path in [('Fast', 'fast'), ('Slow', 'slow')]}
    try:
        yield sites
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', default=None, help='Optional Chromium executable path')
    parser.add_argument('--output', default='docs/evidence')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    evidence = {'javascript_enabled': False, 'engine': 'maigret 0.6.6', 'source': 'local synthetic HTTP sites', 'views': []}
    with contextmanager(synthetic_sites.__wrapped__)() as sites, progressive_sites() as live_sites:
        settings = Settings(site_timeout=6, search_timeout=12, secret_key='synthetic-qa-session')
        hostile_started = threading.Event()
        hostile_release = threading.Event()
        retry_started = threading.Event()
        retry_release = threading.Event()
        stalled_started = threading.Event()
        stalled_release = threading.Event()
        reconcile_started = threading.Event()
        reconcile_release = threading.Event()
        unavailable_started = threading.Event()
        unavailable_release = threading.Event()

        def runner(username, config, emit):
            if username == 'hostile':
                hostile_started.set()
                if not hostile_release.wait(8):
                    raise TimeoutError()
                profile = {
                    'name': '<img src=x onerror=alert(1)>',
                    'url': 'javascript:alert(1)',
                    'tags': ['<svg onload=alert(1)>'],
                    'details': [{'label': '<script>', 'value': '<b>unsafe text</b>'}],
                    'links': ['javascript:alert(1)', 'https://example.org/safe'],
                    'similar': False,
                }
                emit({'state': 'running', 'checked': 1, 'total': 1,
                      'unknown': 0, 'profiles_delta': [profile]})
                return {'state': 'done', 'checked': 1, 'total': 1,
                        'unknown': 0, 'profiles': [profile]}
            if username == 'retry':
                retry_started.set()
                if not retry_release.wait(10):
                    raise TimeoutError()
                return {'state': 'done', 'checked': 2, 'total': 2,
                        'unknown': 2, 'profiles': []}
            if username == 'stalled':
                stalled_started.set()
                if not stalled_release.wait(10):
                    raise TimeoutError()
                return {'state': 'done', 'checked': 1, 'total': 1,
                        'unknown': 1, 'profiles': []}
            if username == 'reconcile':
                stale = {'name': 'First', 'url': 'https://example.com/old',
                         'tags': [], 'details': [], 'links': [], 'similar': False}
                removed = {'name': 'Removed', 'url': 'https://example.com/removed',
                           'tags': [], 'details': [], 'links': [], 'similar': False}
                corrected = {'name': 'First', 'url': 'https://example.com/current',
                             'tags': [], 'details': [], 'links': [], 'similar': False}
                emit({'state': 'running', 'checked': 2, 'total': 3, 'unknown': 0,
                      'profiles_delta': [stale, removed]})
                reconcile_started.set()
                if not reconcile_release.wait(8):
                    raise TimeoutError()
                return {'state': 'done', 'checked': 3, 'total': 3, 'unknown': 0,
                        'profiles': [corrected]}
            if username == 'unavailable':
                unavailable_started.set()
                if not unavailable_release.wait(8):
                    raise TimeoutError()
                return {'state': 'done', 'checked': 1, 'total': 1,
                        'unknown': 1, 'profiles': []}
            selected_sites = live_sites if username.startswith('progressive_') else sites
            return asyncio.run(search_username(username, config, emit, sites=selected_sites))

        with JobManager(settings, runner=runner) as manager:
            app = create_app(settings, manager)
            server = create_server(app, host='127.0.0.1', port=0, threads=4)
            thread = threading.Thread(target=server.run, daemon=True)
            thread.start()
            base = f'http://127.0.0.1:{server.effective_port}'
            try:
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=args.browser,
                        headless=True, args=['--disable-dev-shm-usage'])
                    evidence['browser_version'] = browser.version
                    for name, viewport in [('desktop', {'width': 1440, 'height': 900}),
                                           ('mobile', {'width': 390, 'height': 844})]:
                        context = browser.new_context(java_script_enabled=False, viewport=viewport)
                        page = context.new_page()
                        script_requests = []
                        page.on('request', lambda request, script_requests=script_requests:
                                script_requests.append(request.url)
                                if request.resource_type == 'script' else None)
                        assert page.goto(base).status == 200
                        assert page.locator('script').count() == 0
                        assert page.get_by_role('heading', name='Deeper, início').is_visible()
                        assert page.get_by_role('searchbox', name='Nome de usuário').is_visible()
                        assert page.get_by_role('button', name='Pesquisar').is_visible()
                        assert page.locator('nav,footer,.results').count() == 0
                        layout = page.evaluate('''() => ({
                          width: innerWidth, scroll: document.documentElement.scrollWidth,
                          background: getComputedStyle(document.body).backgroundColor,
                          animation: getComputedStyle(document.querySelector('.wordmark')).animationName
                        })''')
                        assert layout['scroll'] <= layout['width']
                        assert layout['background'] == 'rgb(0, 0, 0)'
                        assert layout['animation'] == 'title-breathe'
                        page.screenshot(path=str(output / f'home-{name}.png'))
                        page.get_by_role('searchbox', name='Nome de usuário').fill('synthetic_profile')
                        page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                        refresh_deadline = time.monotonic() + 12
                        while (page.locator('.profile-link').count() == 0
                               and time.monotonic() < refresh_deadline):
                            refresh = page.locator('a.refresh-link')
                            if refresh.count() == 0:
                                break
                            refresh.click()
                            page.wait_for_timeout(250)
                        page.locator('.profile-link').wait_for(state='visible', timeout=1000)
                        assert page.locator('.profile-link').count() == 1
                        assert page.locator('.profile-link').get_attribute('href').endswith('/found/synthetic_profile')
                        assert '1 verificação inconclusiva' in page.locator('body').inner_text()
                        assert page.locator('meta[http-equiv="refresh"]').count() == 0
                        assert page.locator('script').count() == 0
                        assert not script_requests
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(output / f'results-{name}.png'), full_page=True)
                        context.close()
                        evidence['views'].append({'name': name, 'viewport': viewport,
                            'home_only_title_and_search': True, 'native_enter_search': True,
                            'real_engine_profiles': 1, 'unknown_sites': 1, 'script_requests': 0,
                            'horizontal_overflow': False, 'background': layout['background']})

                    evidence['javascript_enabled'] = True
                    evidence['incremental_updates'] = []
                    for name, viewport in [('desktop', {'width': 1440, 'height': 900}),
                                           ('mobile', {'width': 390, 'height': 844})]:
                        context = browser.new_context(java_script_enabled=True, viewport=viewport)
                        page = context.new_page()
                        console_issues = []
                        page.on('console', lambda message, console_issues=console_issues:
                                console_issues.append(message.text)
                                if message.type in ('error', 'warning') else None)
                        page.on('pageerror', lambda error, console_issues=console_issues:
                                console_issues.append(str(error)))
                        network = {'inflight': 0, 'maximum': 0, 'requests': 0}
                        navigations = []

                        def update_started(request, network=network):
                            if '/updates' in request.url:
                                network['inflight'] += 1
                                network['requests'] += 1
                                network['maximum'] = max(network['maximum'], network['inflight'])

                        def update_finished(request, network=network):
                            if '/updates' in request.url:
                                network['inflight'] -= 1

                        page.on('request', update_started)
                        page.on('requestfinished', update_finished)
                        page.on('requestfailed', update_finished)
                        update_responses = []

                        def record_update_response(response, update_responses=update_responses):
                            if '/updates' not in response.url:
                                return
                            payload = response.json()
                            update_responses.append({
                                'status': response.status,
                                'after': parse_qs(urlsplit(response.url).query).get('after'),
                                'state': payload.get('state'),
                                'checked': payload.get('checked'),
                                'total': payload.get('total'),
                                'cursor': payload.get('cursor'),
                                'unknown': payload.get('unknown'),
                                'elapsed': payload.get('elapsed'),
                                'error': payload.get('error'),
                                'profiles': len(payload.get('profiles', [])),
                                'profile_shapes': [{
                                    'keys': sorted(profile),
                                    'name_type': type(profile.get('name')).__name__,
                                    'tags_type': type(profile.get('tags')).__name__,
                                    'details_shape': [sorted(item) if isinstance(item, dict)
                                                      else type(item).__name__
                                                      for item in profile.get('details', [])],
                                    'links_type': type(profile.get('links')).__name__,
                                    'similar_type': type(profile.get('similar')).__name__,
                                } for profile in payload.get('profiles', [])],
                            })

                        page.on('response', record_update_response)
                        page.on('framenavigated', lambda frame, navigations=navigations, page=page:
                                navigations.append(frame.url)
                                if frame == page.main_frame else None)
                        delayed = {'done': False}

                        def delay_first_update(route, _request=None, delayed=delayed):
                            if not delayed['done']:
                                delayed['done'] = True
                                time.sleep(1.25)
                            route.continue_()

                        page.route('**/updates*', delay_first_update)
                        landing_response = page.goto(base)
                        assert landing_response is not None and landing_response.status == 200
                        started_at = time.monotonic()
                        username = f'progressive_{name}'
                        page.get_by_role('searchbox', name='Nome de usuário').fill(username)
                        page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                        page.locator('.results').wait_for(state='attached')
                        results_url = page.url
                        result_navigation_count = len(navigations)
                        page.locator('.profile[data-profile-name="Fast"]').wait_for(
                            state='visible', timeout=9000)
                        initial_cursor = page.locator('.results').get_attribute('data-cursor')
                        assert initial_cursor is not None
                        expected_cursor = int(initial_cursor)
                        for update_response in update_responses:
                            assert update_response['after'] == [str(expected_cursor)], update_responses
                            expected_cursor = update_response['cursor']
                        profile_time = time.monotonic() - started_at
                        assert profile_time < 3.5, profile_time
                        assert page.locator('.results').get_attribute('aria-busy') == 'true'
                        progress = page.locator('progress')
                        checked = progress.evaluate('(element) => element.value')
                        total = progress.evaluate('(element) => element.max')
                        assert 0 < checked < total, (checked, total)
                        assert page.locator('.result-count').inner_text() == '1'
                        assert page.url == results_url
                        assert len(navigations) == result_navigation_count
                        assert network['maximum'] == 1, network
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        page.screenshot(path=str(output / f'progress-{name}.png'), full_page=True)
                        terminal_deadline = time.monotonic() + settings.search_timeout + 2
                        while (page.locator('.results').get_attribute('aria-busy') != 'false'
                               and time.monotonic() < terminal_deadline):
                            page.wait_for_timeout(100)
                        assert page.locator('.results').get_attribute('aria-busy') == 'false', {
                            'network': network,
                            'updates': update_responses[-5:],
                            'status': page.locator('[data-update-status]').inner_text(),
                            'errors': page.locator('[data-update-error]').inner_text(),
                            'console': console_issues,
                        }
                        assert page.locator('.search-status h2').inner_text() == (
                            f'Busca concluída @{username}')
                        terminal_requests = network['requests']
                        page.wait_for_timeout(1300)
                        assert network['requests'] == terminal_requests
                        assert page.url == results_url
                        assert len(navigations) == result_navigation_count
                        assert not console_issues, console_issues
                        evidence['incremental_updates'].append({
                            'name': name, 'viewport': viewport,
                            'profile_before_slow_site_finished': True,
                            'profile_seconds': round(profile_time, 3),
                            'progress_checked_before_terminal': checked,
                            'progress_total': total,
                            'max_inflight_updates': network['maximum'],
                            'polling_stopped_at_terminal': True,
                            'page_reloads_after_results': 0,
                            'horizontal_overflow': False,
                            'console_issues': console_issues,
                        })
                        context.close()

                    reconcile_context = browser.new_context(java_script_enabled=True,
                        viewport={'width': 1024, 'height': 768})
                    reconcile_page = reconcile_context.new_page()
                    update_reconciliations = []
                    reconcile_page.on('response', lambda response:
                        update_reconciliations.append(response.json().get('reconcile'))
                        if '/updates' in response.url else None)
                    reconcile_page.goto(base)
                    reconcile_page.get_by_role('searchbox', name='Nome de usuário').fill('reconcile')
                    reconcile_page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                    assert reconcile_started.wait(3)
                    try:
                        reconcile_page.locator('.profile[data-profile-name="First"]').wait_for(
                            state='visible', timeout=5000)
                        reconcile_page.locator('.profile[data-profile-name="Removed"]').wait_for(
                            state='visible', timeout=5000)
                        assert reconcile_page.locator(
                            '.profile[data-profile-name="First"] .profile-link'
                        ).get_attribute('href').endswith('/old')
                        reconcile_release.set()
                        reconcile_page.locator('.results[aria-busy="false"]').wait_for(timeout=5000)
                        assert reconcile_page.locator('.profile').count() == 1
                        assert reconcile_page.locator('.profile[data-profile-name="First"] .profile-link').get_attribute(
                            'href').endswith('/current')
                        assert reconcile_page.locator('.profile[data-profile-name="Removed"]').count() == 0
                        assert True in update_reconciliations, update_reconciliations
                        assert reconcile_page.locator('.search-status h2').inner_text() == (
                            'Busca concluída @reconcile')
                        evidence['authoritative_reconciliation'] = True
                    finally:
                        reconcile_release.set()
                        reconcile_context.close()

                    hostile_context = browser.new_context(java_script_enabled=True,
                        viewport={'width': 1024, 'height': 768})
                    hostile_page = hostile_context.new_page()
                    hostile_page.goto(base)
                    hostile_page.get_by_role('searchbox', name='Nome de usuário').fill('hostile')
                    hostile_page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                    hostile_page.locator('.results').wait_for(state='attached')
                    assert hostile_started.wait(3)
                    try:
                        hostile_release.set()
                        hostile_card = hostile_page.locator('.profile')
                        hostile_card.wait_for(state='visible', timeout=5000)
                        assert hostile_card.locator('h3').inner_text() == '<img src=x onerror=alert(1)>'
                        assert hostile_card.locator('dd').inner_text() == '<b>unsafe text</b>'
                        assert hostile_card.locator('li').first.inner_text() == '<svg onload=alert(1)>'
                        assert hostile_card.locator('img,svg,script:not([src])').count() == 0
                        assert hostile_card.locator('a[href^="javascript:"]').count() == 0
                        safe_link = hostile_card.locator('a[href="https://example.org/safe"]')
                        assert safe_link.get_attribute('target') == '_blank'
                        assert safe_link.get_attribute('rel') == 'noopener noreferrer'
                        evidence['hostile_content_inert'] = True
                    finally:
                        hostile_release.set()
                        hostile_context.close()

                    retry_context = browser.new_context(java_script_enabled=True,
                        viewport={'width': 1024, 'height': 768})
                    retry_page = retry_context.new_page()
                    failures = {'count': 0}

                    def fail_update(route):
                        failures['count'] += 1
                        route.fulfill(status=503, content_type='application/json', body='{}')

                    retry_page.route('**/updates*', fail_update)
                    retry_page.goto(base)
                    retry_page.get_by_role('searchbox', name='Nome de usuário').fill('retry')
                    retry_page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                    retry_page.locator('.results').wait_for(state='attached')
                    assert retry_started.wait(3)
                    try:
                        retry_page.locator('[data-update-error]').wait_for(
                            state='visible', timeout=7000)
                        assert 'atualize a página' in retry_page.locator(
                            '[data-update-error]').inner_text().lower()
                        assert failures['count'] == 3, failures
                        retry_page.wait_for_timeout(1300)
                        assert failures['count'] == 3, failures
                        assert retry_page.locator('.results').get_attribute('aria-busy') == 'false'
                        evidence['polling_stops_after_failures'] = failures['count']
                    finally:
                        retry_release.set()
                        retry_context.close()

                    stalled_context = browser.new_context(java_script_enabled=True,
                        viewport={'width': 1024, 'height': 768})
                    stalled_page = stalled_context.new_page()
                    stalled_page.add_init_script('''
                        (() => {
                          const nativeSetTimeout = window.setTimeout.bind(window);
                          window.setTimeout = (callback, delay, ...args) =>
                            nativeSetTimeout(callback, Math.min(Number(delay) || 0, 50), ...args);
                          const nativeFetch = window.fetch.bind(window);
                          window.__stalledPollAttempts = 0;
                          window.fetch = (input, options = {}) => {
                            const requestUrl = new URL(input, window.location.href);
                            if (!requestUrl.pathname.endsWith('/updates')) {
                              return nativeFetch(input, options);
                            }
                            window.__stalledPollAttempts += 1;
                            return new Promise((resolve, reject) => {
                              const fail = () => reject(new DOMException('Aborted', 'AbortError'));
                              if (options.signal?.aborted) fail();
                              else options.signal?.addEventListener('abort', fail, {once: true});
                            });
                          };
                        })();
                    ''')
                    stalled_page.goto(base)
                    stalled_page.get_by_role('searchbox', name='Nome de usuário').fill('stalled')
                    stalled_page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                    stalled_page.locator('.results').wait_for(state='attached')
                    assert stalled_started.wait(3)
                    try:
                        stalled_page.locator('[data-update-error]').wait_for(
                            state='visible', timeout=7000)
                        assert 'atualize a página' in stalled_page.locator(
                            '[data-update-error]').inner_text().lower()
                        assert stalled_page.locator('.search-status h2').inner_text() == (
                            'Atualização interrompida @stalled')
                        assert stalled_page.evaluate('window.__stalledPollAttempts') == 3
                        stalled_page.wait_for_timeout(1300)
                        assert stalled_page.evaluate('window.__stalledPollAttempts') == 3
                        assert stalled_page.locator('.results').get_attribute('aria-busy') == 'false'
                        evidence['stalled_poll_stops_after_timeouts'] = 3
                    finally:
                        stalled_release.set()
                        stalled_context.close()

                    unavailable_context = browser.new_context(java_script_enabled=True,
                        viewport={'width': 1024, 'height': 768})
                    unavailable_page = unavailable_context.new_page()
                    unavailable_page.route('**/updates*', lambda route: route.fulfill(
                        status=404, content_type='application/json', body='{"error":"Busca indisponível."}'))
                    unavailable_page.goto(base)
                    unavailable_page.get_by_role('searchbox', name='Nome de usuário').fill('unavailable')
                    unavailable_page.get_by_role('searchbox', name='Nome de usuário').press('Enter')
                    assert unavailable_started.wait(3)
                    try:
                        unavailable_page.locator('[data-update-error]').wait_for(
                            state='visible', timeout=5000)
                        assert 'não está mais disponível' in unavailable_page.locator(
                            '[data-update-error]').inner_text().lower()
                        assert unavailable_page.locator('.search-status h2').inner_text() == (
                            'Busca indisponível @unavailable')
                        assert unavailable_page.locator('.results').get_attribute('aria-busy') == 'false'
                        assert unavailable_page.locator('.scanner').is_hidden()
                        evidence['visible_unavailable_recovery'] = True
                    finally:
                        unavailable_release.set()
                        unavailable_context.close()

                    context = browser.new_context(java_script_enabled=False,
                        viewport={'width': 320, 'height': 720}, reduced_motion='reduce')
                    page = context.new_page()
                    page.goto(base)
                    assert page.evaluate("getComputedStyle(document.querySelector('.wordmark')).animationName") == 'none'
                    evidence['reduced_motion'] = True
                    context.close()
                    browser.close()
                    # CSP stays unchanged: enlargement uses an allowed same-origin CSS asset.
                    browser = playwright.chromium.launch(executable_path=args.browser,
                        headless=True, args=['--disable-dev-shm-usage'])
                    context = browser.new_context(java_script_enabled=False,
                        viewport={'width': 320, 'height': 720}, reduced_motion='reduce')
                    page = context.new_page()
                    css = (Path(__file__).resolve().parents[1] / 'deeper/static/deeper.css').read_text()
                    page.route('**/static/deeper.css', lambda route: route.fulfill(
                        body=css + '\nhtml { font-size: 200%; }', content_type='text/css'))
                    page.goto(base)
                    font_size = page.evaluate('getComputedStyle(document.documentElement).fontSize')
                    assert font_size == '32px', font_size
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    assert page.get_by_role('searchbox').is_visible()
                    page.screenshot(path=str(output / 'home-large-text-reduced-motion.png'))
                    evidence['large_text_320px'] = True
                    evidence['large_text_root_font'] = font_size
                    context.close()
                    browser.close()
            finally:
                server.close()
                thread.join(timeout=3)
    (output / 'ui-verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(evidence, ensure_ascii=False))


if __name__ == '__main__':
    main()
