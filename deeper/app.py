"""Server-rendered Flask application with same-origin progressive search updates."""

import atexit
import secrets
from importlib.metadata import PackageNotFoundError, version

from flask import Flask, redirect, render_template, request, session, url_for

from .config import Settings
from .documents import FILE_TYPES, validate_file_type, validate_full_name
from .engine import safe_url, validate_username
from .jobs import CapacityError, JobManager, SessionCapacityError


def create_app(
    settings: Settings | None = None, manager: JobManager | None = None
) -> Flask:
    settings = settings or Settings.from_env()
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=settings.secret_key or secrets.token_hex(32),
        SESSION_COOKIE_NAME="deeper_session",
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        SESSION_COOKIE_SECURE=settings.secure_cookie,
        MAX_CONTENT_LENGTH=8192,
    )
    if manager is None:
        manager = JobManager(settings)
        atexit.register(manager.close)
    app.extensions["deeper_jobs"] = manager
    app.jinja_env.filters["safe_url"] = safe_url

    def render(
        *,
        username="",
        job=None,
        error=None,
        code=200,
        mode="username",
        file_type="any",
        consent=False,
    ):
        session.setdefault("owner", secrets.token_urlsafe(32))
        session.setdefault("csrf_token", secrets.token_urlsafe(32))
        return render_template(
            "index.html",
            username=username,
            job=job,
            error=error,
            csrf_token=session["csrf_token"],
            mode=mode,
            file_type=file_type,
            name_search_available=getattr(manager, "name_search_available", False),
            file_types=FILE_TYPES,
            consent=consent,
        ), code

    @app.get("/")
    def home():
        mode = request.args.get("mode", "username")
        if mode not in ("username", "name"):
            return render(error="Escolha um modo de busca válido.", code=422)
        return render(mode=mode)

    @app.post("/search")
    def search():
        mode = request.form.get("mode", "username")
        file_type = request.form.get("file_type", "any")
        consent = request.form.get("consent", "") == "1"
        form = {
            "mode": mode if mode in ("username", "name") else "username",
            "file_type": file_type if file_type in FILE_TYPES else "any",
            "consent": consent,
        }
        expected = session.get("csrf_token", "")
        supplied = request.form.get("csrf_token", "")
        if not expected or not secrets.compare_digest(expected, supplied):
            return render(
                error="A sessão expirou. Envie a busca novamente.", code=400, **form
            )
        value = request.form.get("username", "")
        try:
            if mode not in ("username", "name"):
                raise ValueError("Escolha um modo de busca válido.")
            file_type = validate_file_type(file_type)
            username = (
                validate_full_name(value)
                if mode == "name"
                else validate_username(value)
            )
            if mode == "name" and not consent:
                raise ValueError(
                    "Confirme o envio do nome ao Serper/Google para iniciar a busca."
                )
        except ValueError as error:
            return render(username=value[:120], error=str(error), code=422, **form)
        if mode == "name" and not getattr(manager, "name_search_available", False):
            return render(
                username=username,
                error="A busca por nome está indisponível: o serviço não está configurado.",
                code=503,
                **form,
            )
        try:
            if mode == "username" and file_type == "any":
                token = manager.submit(username, session["owner"])
            else:
                token = manager.submit(
                    username, session["owner"], mode=mode, file_type=file_type
                )
        except SessionCapacityError:
            response, code = render(
                username=username,
                error="Você já tem buscas em andamento. Aguarde uma delas terminar para enviar outra.",
                code=429,
                **form,
            )
            return response, code, {"Retry-After": "5"}
        except CapacityError:
            response, code = render(
                username=username,
                error="As buscas estão ocupadas. Tente novamente em alguns instantes.",
                code=503,
                **form,
            )
            return response, code, {"Retry-After": "5"}
        return redirect(url_for("results", token=token), code=303)

    @app.get("/search/<token>")
    def results(token):
        owner = session.get("owner")
        job = manager.snapshot(token, owner) if owner else None
        if job is None:
            return render(
                error="Esta busca expirou ou não está disponível nesta sessão.",
                code=404,
            )
        return render(
            username=job["username"],
            job=job,
            mode=job.get("mode", "username"),
            file_type=job.get("file_type", "any"),
            consent=job.get("mode") == "name",
        )

    @app.get("/search/<token>/updates")
    def search_updates(token):
        owner = session.get("owner")
        if not owner:
            return {"error": "Busca indisponível."}, 404

        cursors = request.args.getlist("after")
        if len(cursors) > 1:
            return {"error": "Cursor inválido."}, 400
        raw_cursor = cursors[0] if cursors else None
        if raw_cursor is None:
            cursor = 0
        elif (
            not raw_cursor
            or len(raw_cursor) > 10
            or not raw_cursor.isascii()
            or not raw_cursor.isdecimal()
        ):
            return {"error": "Cursor inválido."}, 400
        else:
            cursor = int(raw_cursor)

        try:
            updates = manager.updates(token, owner, cursor)
        except ValueError:
            return {"error": "Cursor inválido."}, 400
        if updates is None:
            return {"error": "Busca indisponível."}, 404
        return updates

    @app.get("/health")
    def health():
        try:
            deeper_version = version("deeper-maigret")
            engine_version = version("maigret")
        except PackageNotFoundError:
            return {"status": "unavailable"}, 503
        return {
            "status": "ok",
            "deeper_version": deeper_version,
            "engine": "maigret",
            "engine_version": engine_version,
        }

    @app.errorhandler(413)
    def request_too_large(error):
        return render(error="A pesquisa enviada é muito longa.", code=413)

    @app.after_request
    def secure_response(response):
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; font-src 'self'; connect-src 'self'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        if request.endpoint != "static":
            response.headers["Cache-Control"] = "no-store"
        return response

    return app
