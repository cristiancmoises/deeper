"""Run visual/native-form QA; Playwright is a test tool, never a page script."""
import argparse
import asyncio
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright
from waitress import create_server

from deeper.app import create_app
from deeper.config import Settings
from deeper.engine import search_username
from deeper.jobs import JobManager
from test_engine import synthetic_sites


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', default=None, help='Optional Chromium executable path')
    parser.add_argument('--output', default='docs/evidence')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    evidence = {'javascript_enabled': False, 'engine': 'maigret 0.6.6', 'source': 'local synthetic HTTP sites', 'views': []}
    with contextmanager(synthetic_sites.__wrapped__)() as sites:
        settings = Settings(site_timeout=2, search_timeout=10, secret_key='synthetic-qa-session')

        def runner(username, config, emit):
            return asyncio.run(search_username(username, config, emit, sites=sites))

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
                        page.on('request', lambda request: script_requests.append(request.url)
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
                        page.locator('.profile-link').wait_for(state='visible', timeout=12000)
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
