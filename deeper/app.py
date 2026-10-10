"""Server-rendered Flask application: no JavaScript is served or required."""
import atexit
from importlib.metadata import PackageNotFoundError, version
import secrets

from flask import Flask, redirect, render_template, request, session, url_for

from .config import Settings
from .engine import safe_url, validate_username
from .jobs import CapacityError, JobManager


def create_app(settings: Settings | None = None, manager: JobManager | None = None) -> Flask:
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key or secrets.token_hex(32),
        SESSION_COOKIE_NAME='deeper_session', SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE='Strict', SESSION_COOKIE_SECURE=settings.secure_cookie,
        MAX_CONTENT_LENGTH=8192,
    )
    if manager is None:
        manager = JobManager(settings)
        atexit.register(manager.close)
    app.extensions['deeper_jobs'] = manager
    app.jinja_env.filters['safe_url'] = safe_url

    def render(*, username='', job=None, error=None, code=200):
        session.setdefault('owner', secrets.token_urlsafe(32))
        session.setdefault('csrf_token', secrets.token_urlsafe(32))
        return render_template('index.html', username=username, job=job,
                               error=error, csrf_token=session['csrf_token']), code

    @app.get('/')
    def home():
        return render()

    @app.post('/search')
    def search():
        expected = session.get('csrf_token', '')
        supplied = request.form.get('csrf_token', '')
        if not expected or not secrets.compare_digest(expected, supplied):
            return render(error='A sessão expirou. Envie a busca novamente.', code=400)
        value = request.form.get('username', '')
        try:
            username = validate_username(value)
        except ValueError as error:
            return render(username=value[:65], error=str(error), code=422)
        try:
            token = manager.submit(username, session['owner'])
        except CapacityError:
            response, code = render(username=username,
                error='As buscas estão ocupadas. Tente novamente em alguns instantes.', code=503)
            return response, code, {'Retry-After': '5'}
        return redirect(url_for('results', token=token), code=303)

    @app.get('/search/<token>')
    def results(token):
        owner = session.get('owner')
        job = manager.snapshot(token, owner) if owner else None
        if job is None:
            return render(error='Esta busca expirou ou não está disponível nesta sessão.', code=404)
        return render(username=job['username'], job=job)

    @app.get('/search/<token>/updates')
    def search_updates(token):
        owner = session.get('owner')
        if not owner:
            return {'error': 'Busca indisponível.'}, 404

        cursors = request.args.getlist('after')
        if len(cursors) > 1:
            return {'error': 'Cursor inválido.'}, 400
        raw_cursor = cursors[0] if cursors else None
        if raw_cursor is None:
            cursor = 0
        elif (not raw_cursor or len(raw_cursor) > 10
              or not raw_cursor.isascii() or not raw_cursor.isdecimal()):
            return {'error': 'Cursor inválido.'}, 400
        else:
            cursor = int(raw_cursor)

        try:
            updates = manager.updates(token, owner, cursor)
        except ValueError:
            return {'error': 'Cursor inválido.'}, 400
        if updates is None:
            return {'error': 'Busca indisponível.'}, 404
        return updates

    @app.get('/health')
    def health():
        try:
            engine_version = version('maigret')
        except PackageNotFoundError:
            return {'status': 'unavailable'}, 503
        return {'status': 'ok', 'engine': 'maigret', 'engine_version': engine_version}

    @app.errorhandler(413)
    def request_too_large(error):
        return render(error='A pesquisa enviada é muito longa.', code=413)

    @app.after_request
    def secure_response(response):
        response.headers['Content-Security-Policy'] = (
            "default-src 'none'; script-src 'none'; style-src 'self'; "
            "img-src 'self'; font-src 'self'; connect-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        if request.endpoint != 'static':
            response.headers['Cache-Control'] = 'no-store'
        return response

    return app
